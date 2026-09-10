import geometry_functions as geom
import json
from pathlib import Path

script_dir = Path(__file__).resolve().parent

with open(Path(script_dir, "dataset_config.json"), "r") as f:
    config = json.load(f)

dataset_dir = config["dataset_dir"]
dataset_name = config["dataset_name"]
num_per_family = config["num_per_family"]
disabled_families = config["disabled_families"]
train_fraction = config["train_fraction"]
val_fraction = config["val_fraction"]
test_fraction = config["test_fraction"]
seed = config["seed"]
maxsize = config["maxsize"]
shuffle = config["shuffle"]

dataset_path = Path(dataset_dir, dataset_name)

default_families = [
    "cuboid",
    "cylinder",
    "cone",
    "frustum",
    "pyramid",
    "triangular_frustum",
    "hourglass",
    "smooth_hourglass",
    "half_ellipsoid",
    "wedge",
    "pipe",
    "hollow_cuboid",
]

enabled_families = [
    family for family in default_families if family not in disabled_families
]

family_generators = {
    "cuboid": geom.generate_cuboid,
    "cylinder": geom.generate_cylinder,
    "cone": geom.generate_cone,
    "frustum": geom.generate_frustum,
    "pyramid": geom.generate_pyramid,
    "triangular_frustum": geom.generate_triangular_frustum,
    "hourglass": geom.generate_hourglass,
    "smooth_hourglass": geom.generate_smooth_hourglass,
    "half_ellipsoid": geom.generate_half_ellipsoid,
    "wedge": geom.generate_wedge,
    "pipe": geom.generate_pipe,
    "hollow_cuboid": geom.generate_hollow_cuboid,
}


geom.generate_geometry_dataset(
        dataset_path,
        enabled_families,
        family_generators,
        num_per_family = num_per_family,
        train_fraction = train_fraction,
        val_fraction = val_fraction,
        test_fraction = test_fraction,
        seed = seed,
        maxsize = maxsize,
        shuffle = shuffle)



#"C:\PBF-MeshGraphNet\.venv\Scripts\python.exe" C:\PBF-MeshGraphNet\dataset_generation\geometry_generation.py