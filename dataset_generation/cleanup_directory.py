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


def get_sample_directories():
    """Return all sample directories in train, validation, and test splits."""
    sample_directories = []

    for split in ("train", "val", "test"):
        split_dir = dataset_path / split

        if not split_dir.is_dir():
            continue

        sample_directories.extend(
            sorted(
                path
                for path in split_dir.iterdir()
                if path.is_dir()
            )
        )

    return sample_directories


def final_file_names(sample_name):
    """Return the files retained in a completed sample directory."""
    return {
        "{}.csv".format(sample_name),
        "{}_edges.csv".format(sample_name),
        "{}_global.json".format(sample_name),
        "{}_metadata.json".format(sample_name),
    }


def main():
    sample_directories = get_sample_directories()
    missing_files = []

    for sample_dir in sample_directories:
        for file_name in final_file_names(sample_dir.name):
            file_path = sample_dir / file_name

            if not file_path.is_file():
                missing_files.append(file_path)

    dataset_metadata_path = dataset_path / "dataset_metadata.csv"

    if not dataset_metadata_path.is_file():
        missing_files.append(dataset_metadata_path)

    if missing_files:
        raise RuntimeError(
            "Cleanup was not performed because final dataset files are missing:\n{}".format(
                "\n".join(str(path) for path in missing_files)
            )
        )

    for sample_dir in sample_directories:
        keep_files = final_file_names(sample_dir.name)

        for path in sample_dir.iterdir():
            if path.is_file() and path.name not in keep_files:
                path.unlink()

        print("Cleaned {}".format(sample_dir))

    if nurd_job_dir.exists():
        shutil.rmtree(nurd_job_dir)
        print("Removed NURD staging directory: {}".format(nurd_job_dir))

    print()
    print("Dataset cleanup completed.")


if __name__ == "__main__":
    main()
