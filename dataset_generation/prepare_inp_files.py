import json
import subprocess
from pathlib import Path


script_dir = Path(__file__).resolve().parent
config_path = script_dir / "dataset_config.json"
process_step_path = script_dir / "process_step.py"

with config_path.open("r", encoding="utf-8") as config_file:
    config = json.load(config_file)


dataset_path = (
    Path(config["dataset_dir"])
    / config["dataset_name"]
)

abaqus_command = config["abaqus_command"]

splits = ["train", "val", "test"]


for split in splits:
    split_dir = dataset_path / split

    if not split_dir.is_dir():
        print("Split directory not found; skipping: {}".format(split_dir))
        continue

    sample_dirs = sorted(
        path
        for path in split_dir.iterdir()
        if path.is_dir()
    )

    for sample_dir in sample_dirs:
        sample_name = sample_dir.name
        step_path = sample_dir / "{}.step".format(sample_name)
        inp_path = sample_dir / "{}.inp".format(sample_name)

        if not step_path.is_file():
            print("STEP file not found; skipping: {}".format(step_path))
            continue

        print(
            "Preparing INP: {} / {}".format(
                split,
                sample_name,
            )
        )

        command = (
            '{abaqus} cae noGUI="{script}" -- "{step}"'
        ).format(
            abaqus=abaqus_command,
            script=process_step_path,
            step=step_path,
        )

        result = subprocess.run(
            command,
            cwd=sample_dir,
            shell=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                "INP preparation failed for {}.".format(
                    step_path
                )
            )

        if not inp_path.is_file():
            raise RuntimeError(
                "Expected INP file was not created: {}".format(
                    inp_path
                )
            )

        print("Created: {}".format(inp_path))


print("Finished preparing Abaqus input files.")