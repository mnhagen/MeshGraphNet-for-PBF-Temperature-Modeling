import json
import subprocess
import sys
from pathlib import Path


script_dir = Path(__file__).resolve().parent
project_dir = script_dir.parent
config_path = script_dir / "dataset_config.json"

with config_path.open("r", encoding="utf-8") as config_file:
    config = json.load(config_file)


nurd_job_dir = (
    script_dir
    / "nurd_jobs"
    / config["dataset_name"]
)

nurd_batch_file = script_dir / "nurd" / "NURD.bat"


def run_python_script(script_name, stage_name):
    """Run one dataset-generation stage with the current Python interpreter."""
    print()
    print(stage_name)

    subprocess.run(
        [
            sys.executable,
            str(script_dir / script_name),
        ],
        cwd=project_dir,
        check=True,
    )


def main():
    # Check this before generating anything because prepare_nurd_job.py
    # intentionally refuses to mix files from separate submissions.
    if nurd_job_dir.exists() and any(nurd_job_dir.iterdir()):
        raise RuntimeError(
            "The NURD job directory is not empty:\n{}\n"
            "Empty or rename this directory before generating a new dataset.".format(
                nurd_job_dir
            )
        )

    run_python_script(
        "geometry_generation.py",
        "Stage 1/4: generating geometries",
    )

    run_python_script(
        "prepare_inp_files.py",
        "Stage 2/4: preparing Abaqus INP files",
    )

    run_python_script(
        "prepare_nurd_job.py",
        "Stage 3/4: collecting the NURD job files",
    )

    print()
    print("Stage 4/4: submitting the NURD job")

    subprocess.run(
        [
            "cmd",
            "/c",
            "call",
            str(nurd_batch_file),
        ],
        cwd=nurd_job_dir,
        check=True,
    )

    print()
    print("The dataset was prepared and submitted to NURD.")


if __name__ == "__main__":
    main()
