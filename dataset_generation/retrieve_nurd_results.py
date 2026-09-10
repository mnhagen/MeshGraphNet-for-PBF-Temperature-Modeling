import csv
import json
import shutil
import sys
from pathlib import Path


script_dir = Path(__file__).resolve().parent
config_path = script_dir / "dataset_config.json"

with config_path.open("r", encoding="utf-8") as config_file:
    config = json.load(config_file)


dataset_path = (
    Path(config["dataset_dir"])
    / config["dataset_name"]
)


def retrieve_sample(nurd_results_dir, split, sample_dir):
    """Copy one completed sample from NURD into its dataset folder."""
    sample_name = sample_dir.name
    job_name = "{}__{}".format(split, sample_name)

    file_names = {
        "{}.csv".format(job_name): "{}.csv".format(sample_name),
        "{}_edges.csv".format(job_name): "{}_edges.csv".format(sample_name),
        "{}_global.json".format(job_name): "{}_global.json".format(sample_name),
        "{}_metadata.json".format(job_name): "{}_metadata.json".format(sample_name),
    }

    missing_files = [
        nurd_results_dir / source_name
        for source_name in file_names
        if not (nurd_results_dir / source_name).is_file()
    ]

    if missing_files:
        print("Incomplete {} / {}".format(split, sample_name))

        for missing_file in missing_files:
            print("  Missing: {}".format(missing_file.name))

        return False

    for source_name, destination_name in file_names.items():
        shutil.copy2(
            nurd_results_dir / source_name,
            sample_dir / destination_name,
        )

    print("Retrieved {} / {}".format(split, sample_name))
    return True


def write_dataset_metadata():
    """Build dataset_metadata.csv from the retrieved sample metadata."""
    sample_metadata = []

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
            metadata_path = (
                sample_dir
                / "{}_metadata.json".format(sample_dir.name)
            )

            if not metadata_path.is_file():
                continue

            with metadata_path.open("r", encoding="utf-8") as metadata_file:
                sample_metadata.append(json.load(metadata_file))

    field_names = [
        "sample_name",
        "split",
        "number_of_nodes",
        "abaqus_solve_time",
        "status",
    ]

    metadata_path = dataset_path / "dataset_metadata.csv"

    with metadata_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as metadata_file:
        writer = csv.DictWriter(
            metadata_file,
            fieldnames=field_names,
        )
        writer.writeheader()

        for metadata in sample_metadata:
            writer.writerow({
                field_name: metadata[field_name]
                for field_name in field_names
            })

    print("Dataset metadata written to {}".format(metadata_path))


def main():
    if len(sys.argv) != 2:
        raise RuntimeError(
            "Usage: python retrieve_nurd_results.py <NURD results directory>"
        )

    nurd_results_dir = Path(sys.argv[1]).resolve()

    if not nurd_results_dir.is_dir():
        raise FileNotFoundError(
            "NURD results directory not found: {}".format(
                nurd_results_dir
            )
        )

    if not dataset_path.is_dir():
        raise FileNotFoundError(
            "Dataset directory not found: {}".format(dataset_path)
        )

    expected_samples = 0
    retrieved_samples = 0

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
            expected_samples += 1

            if retrieve_sample(
                nurd_results_dir,
                split,
                sample_dir,
            ):
                retrieved_samples += 1

    write_dataset_metadata()

    print()
    print(
        "Retrieved {} of {} expected samples.".format(
            retrieved_samples,
            expected_samples,
        )
    )

    if retrieved_samples != expected_samples:
        sys.exit(1)


if __name__ == "__main__":
    main()
