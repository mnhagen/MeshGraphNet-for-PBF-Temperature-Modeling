import json
import shutil
from pathlib import Path


script_dir = Path(__file__).resolve().parent
config_path = script_dir / "dataset_config.json"

with config_path.open("r", encoding="utf-8") as config_file:
    config = json.load(config_file)


dataset_path = (
    Path(config["dataset_dir"])
    / config["dataset_name"]
)

nurd_job_dir = (
    script_dir
    / "nurd_jobs"
    / config["dataset_name"]
)


# Do not mix newly prepared files with files from an older job.
if nurd_job_dir.exists() and any(nurd_job_dir.iterdir()):
    raise RuntimeError(
        "The NURD job directory is not empty:\n{}\n"
        "Empty or rename this directory before preparing a new job.".format(
            nurd_job_dir
        )
    )

nurd_job_dir.mkdir(parents=True, exist_ok=True)


postprocessor_source = script_dir / "postprocess_sample.py"
feature_functions_source = (
    script_dir.parent
    / "shared"
    / "dataset_functions.py"
)

if not postprocessor_source.is_file():
    raise FileNotFoundError(
        "Postprocessing script not found: {}".format(
            postprocessor_source
        )
    )

if not feature_functions_source.is_file():
    raise FileNotFoundError(
        "Dataset-functions module not found: {}".format(
            feature_functions_source
        )
    )

shutil.copy2(
    postprocessor_source,
    nurd_job_dir / "postprocess_sample.py",
)

shutil.copy2(
    feature_functions_source,
    nurd_job_dir / "dataset_functions.py",
)


number_of_samples = 0

for split in ("train", "val", "test"):
    split_dir = dataset_path / split

    if not split_dir.is_dir():
        continue

    sample_dirs = sorted(
        path
        for path in split_dir.iterdir()
        if path.is_dir()
    )

    for sample_dir in sample_dirs:
        sample_name = sample_dir.name

        inp_source = (
            sample_dir
            / "{}.inp".format(sample_name)
        )

        global_source = (
            sample_dir
            / "{}_global.json".format(sample_name)
        )

        if not inp_source.is_file():
            raise FileNotFoundError(
                "Missing INP file: {}".format(inp_source)
            )

        if not global_source.is_file():
            raise FileNotFoundError(
                "Missing global-feature file: {}".format(
                    global_source
                )
            )

        job_name = "{}__{}".format(
            split,
            sample_name,
        )

        inp_destination = (
            nurd_job_dir
            / "{}.inp".format(job_name)
        )

        global_destination = (
            nurd_job_dir
            / "{}_global.json".format(job_name)
        )

        shutil.copy2(
            inp_source,
            inp_destination,
        )

        shutil.copy2(
            global_source,
            global_destination,
        )

        number_of_samples += 1

        print(
            "Collected {} / {}".format(
                split,
                sample_name,
            )
        )


print()
print(
    "Prepared NURD job containing {} samples.".format(
        number_of_samples
    )
)
print(
    "NURD job directory: {}".format(
        nurd_job_dir
    )
)