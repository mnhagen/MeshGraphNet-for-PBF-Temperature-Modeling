import subprocess
import sys
from pathlib import Path


script_dir = Path(__file__).resolve().parent
project_dir = script_dir.parent


def main():
    if len(sys.argv) != 2:
        raise RuntimeError(
            "Usage: python finalize_dataset.py <NURD results directory>"
        )

    nurd_results_dir = sys.argv[1]

    print("Stage 1/2: retrieving NURD results")

    retrieval = subprocess.run(
        [
            sys.executable,
            str(script_dir / "retrieve_nurd_results.py"),
            nurd_results_dir,
        ],
        cwd=project_dir,
    )

    if retrieval.returncode != 0:
        print()
        print("Retrieval was incomplete. Cleanup was not performed.")
        sys.exit(retrieval.returncode)

    print()
    print("Stage 2/2: cleaning local dataset directories")

    subprocess.run(
        [
            sys.executable,
            str(script_dir / "cleanup_directory.py"),
        ],
        cwd=project_dir,
        check=True,
    )

    print()
    print("Dataset retrieval and cleanup completed.")
    print("The remote NURD results directory was not deleted.")


if __name__ == "__main__":
    main()
