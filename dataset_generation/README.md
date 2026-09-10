# dataset_generation

This folder contains the complete dataset-generation pipeline. It generates randomized STEP geometries, converts them into Abaqus input files, submits the simulations to the UXCS cluster through NURD, postprocesses the resulting ODB files on the cluster, and retrieves the completed data.

The pipeline is divided into two main stages:

1. Generate the geometries and input files and submit the NURD job.
2. Retrieve the completed results and clean the local dataset directory.

This separation is necessary because the first stage finishes once the NURD job has been submitted. The simulations may then remain in the cluster queue for some time.

## Initial setup

Before using the pipeline for the first time, update `dataset_config.json` and `nurd/NURD.bat`.

### NURD setup

NURD is an NLR script written by Jos. It transfers Abaqus input files to the cluster and submits them in a way that supports queueing and sequential execution.

The NURD files in this repository are modified copies of the original files. The main changes are:

* The paths have been updated for this repository.
* `NURD_uxcs.py` runs the postprocessing on UXCS immediately after each Abaqus simulation.
* Successfully postprocessed ODB and auxiliary Abaqus files are deleted on the cluster.

Open `nurd/NURD.bat` and update the following values:

* `user_name`: your NLR username.
* `user_pool`: the pool in the shared directory assigned to you. Ask Jos if you do not know which pool to use.
* `script_location`: the full path to `dataset_generation\nurd\NURD.py`.
* `custom_python_path`: the full path to the Python executable in the local virtual environment.

For example:

```bat
SET user_name="username"
SET user_pool="pool000"
SET script_location="C:\PBF-MeshGraphNet\dataset_generation\nurd\NURD.py"
SET custom_python_path="C:\PBF-MeshGraphNet\.venv\Scripts\python.exe"
```

Both path variables must be changed if the repository is not located at `C:\PBF-MeshGraphNet`.

## How to use

### Generate and submit a dataset

First, update the values in `dataset_config.json` to suit your needs. Then run the following command from the repository root:

```bat
".venv\Scripts\python.exe" dataset_generation\generate_dataset.py
```

The wrapper performs the following operations:

1. Checks that `dataset_generation\nurd_jobs\<dataset_name>` is empty. This prevents files from separate NURD jobs from being mixed.
2. Generates STEP geometries and divides them into training, validation and test sets.
3. Uses Abaqus CAE to turn each STEP file into an INP file.
4. Copies the INP files, global-feature files and postprocessing code into a flat NURD job directory.
5. Starts `NURD.bat` and submits the directory to UXCS.

NURD will ask for information such as the job priority, target machine, number of CPUs and Abaqus version. If you are unsure, all the defaults are fine. It will also ask for your password when connecting to the cluster.

The wrapper finishes once the NURD job has been submitted. It does not wait for the simulations to finish. An email is sent by NURD when the job is complete or has failed.

### Cluster solving and postprocessing

Each sample is solved and postprocessed sequentially on UXCS. Once Abaqus has successfully created an ODB, `postprocess_sample.py`:

* reads the mesh, temperatures and required simulation results directly from the ODB;
* calculates the engineered node and edge features;
* reads the total Abaqus CPU time from the DAT file;
* creates the main CSV, edge CSV and sample metadata JSON;
* deletes the ODB and other auxiliary Abaqus files after successful postprocessing.

Processing each sample immediately means that normally only one ODB needs to exist at a time. This avoids transferring large ODB files back to the local computer and reduces the amount of cluster storage required.

If postprocessing fails, the relevant Abaqus files should be retained so that the failure can be investigated.

### Retrieve and finalize the dataset

After receiving the completion email, locate the completed NURD directory in the shared drive. The naming convention is 'NURD-[year]-[month]-[day]-[time]'. Run:

```bat
".venv\Scripts\python.exe" dataset_generation\finalize_dataset.py "<completed NURD directory>"
```

The supplied path must be a Windows-accessible path to the result directory, rather than its Linux `/shared/...` equivalent.

This wrapper:

1. Retrieves the generated files.
2. Restores them to the correct `train`, `val` and `test` sample directories.
3. Constructs `dataset_metadata.csv` from the individual sample metadata files.
4. Verifies that all expected final files exist.
5. Deletes the local STEP, INP, CAE and other intermediate files.
6. Deletes the local `nurd_jobs\<dataset_name>` staging directory.

The final directory for each sample contains:

```text
sample_name.csv
sample_name_edges.csv
sample_name_global.json
sample_name_metadata.json
```

The dataset root also contains `dataset_metadata.csv`.

The remote NURD result directory is not deleted automatically. Check that the retrieved dataset is complete before deleting the remote directory manually.

## Running individual stages

The two wrappers are recommended for normal use. The individual scripts can also be run separately when debugging or when the generated geometries should be inspected before creating the Abaqus files:

```bat
".venv\Scripts\python.exe" dataset_generation\geometry_generation.py
".venv\Scripts\python.exe" dataset_generation\prepare_inp_files.py
".venv\Scripts\python.exe" dataset_generation\prepare_nurd_job.py
```

The separation between geometry generation and INP preparation makes it possible to inspect the STEP files before committing cluster resources, even though the complete wrapper normally runs both stages automatically.

## dataset_config

The following parameters are defined in `dataset_config.json`:

* `dataset_dir`: directory in which the generated datasets are stored.
* `dataset_name`: name of the dataset being generated. The dataset is saved under `dataset_dir/dataset_name`.
* `disabled_families`: list of geometry families that should not be generated. An empty list enables all available families.
* `num_per_family`: number of samples generated for each enabled geometry family.
* `train_fraction`: fraction of samples assigned to the training split.
* `val_fraction`: fraction of samples assigned to the validation split.
* `test_fraction`: fraction of samples assigned to the test split. The three fractions should add up to 1.
* `seed`: random seed used for geometry generation and dataset splitting. Using the same seed and configuration should reproduce the same dataset when using the same software environment.
* `maxsize`: maximum size used during randomized geometry generation.
* `shuffle`: whether the generated samples are shuffled before being assigned to the dataset splits.
* `abaqus_command`: command used to start Abaqus, such as `abq2021`. Change this if a different Abaqus version is installed.
* `am_modeler_path`: path to the Abaqus AM Modeler plug-in. This path must correspond to the installed Abaqus version.
* `part_seed_size`: approximate mesh seed size for the printed part. A smaller value produces a finer mesh but increases the computational cost.
* `baseplate_seed_size`: approximate mesh seed size for the baseplate.
* `baseplate_thickness`: thickness of the generated baseplate.
* `print_margin`: additional margin added to the part dimensions when determining the scanning area.
* `slice_height`: height of an individual deposited layer.
* `time_buffer`: fractional buffer added to the estimated simulation duration. For example, `0.1` adds 10% to the estimated duration.
* `laser_power`: heat-source power supplied to the Abaqus AM model.
* `hatch_spacing`: spacing between adjacent scan lines.
* `scan_speed`: velocity of the heat source.
* `on_time_fraction`: fraction of time for which the heat source is active.
* `rotation_angle`: rotation applied to the scan pattern between layers.
* `baseplate_initial_temperature`: initial temperature of the baseplate.
* `part_initial_temperature`: initial temperature of the printed material.

The supported geometry families are `cuboid`, `cylinder`, `cone`, `frustum`, `pyramid`, `triangular_frustum`, `hourglass`, `smooth_hourglass`, `half_ellipsoid`, `wedge`, `pipe` and `hollow_cuboid`.


## Current limitations and hard-coded parameters

Not every physical or numerical parameter is currently exposed through `dataset_config.json`. Several values remain hard-coded in `process_step.py`, including:

* the Ti6Al4V material properties;
* the heat-transfer increment limits;
* the baseplate film coefficient;
* the part film coefficient and ambient temperature;
* the radiation ambient temperature and emissivity;
* the absorptivity;
* the recoater time;
* the thermal element types and output requests.

The current implementation also assumes that the part has one planar contact surface with the baseplate.

These values can be moved into `dataset_config.json` if more flexibility is required. However, if parameters such as absorptivity, material properties, boundary conditions or laser settings are varied between samples, they must also be recorded as sample features and supplied to the MeshGraphNet. Otherwise, the model has no way to know which simulation conditions produced each temperature field.
