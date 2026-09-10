from odbAccess import openOdb
from abaqusConstants import NODAL
from pathlib import Path
import csv
import sys
import os
import json
from shared.dataset_functions import *

script_directory = Path(__file__).resolve().parent

with open(script_directory / "conversion_config.json", "r") as f:
    config = json.load(f)

sample_name = config["sample_name"]
split = config["split"]
dataset = config["dataset_name"]
target_instance_name = config["target_instance_name"]
step_name = config["step_name"]

root = script_directory.parent

odb_path = r"{root}\datasets\{dataset}\{split}\{sample_name}\{sample_name}.odb".format(root = root, sample_name=sample_name, split = split, dataset = dataset)
csv_path = r"{root}\datasets\{dataset}\{split}\{sample_name}\{sample_name}.csv".format(root = root, sample_name=sample_name, split = split, dataset = dataset)
global_path = r"{root}\datasets\{dataset}\{split}\{sample_name}\{sample_name}_global.json".format(root = root, sample_name=sample_name, split = split, dataset = dataset)
csv_edge_path = r"{root}\datasets\{dataset}\{split}\{sample_name}\{sample_name}_edges.csv".format(root = root, sample_name=sample_name, split = split, dataset = dataset)
#stl_path = r"{root}\datasets\{dataset}\{split}\{sample_name}\{sample_name}.stl".format(root = root, sample_name=sample_name, split = split, dataset = dataset)

odb = openOdb(path=odb_path, readOnly = True)


existing_instances = [instance_name for instance_name, _ in odb.rootAssembly.instances.items()]

if step_name not in odb.steps.keys():
    raise ValueError("Step name '{}' not found in ODB. Valid steps are: {}".format(step_name, odb.steps.keys()))

if target_instance_name not in existing_instances:
    raise ValueError("Target instance name not found in ODB. Valid instances are: {}".format(existing_instances))

coords = build_coordinate_lookup(odb)
baseplate_height = get_minimum_coord(coords, target_instance_name, "z")
min_x = get_minimum_coord(coords, target_instance_name, "x")
min_y = get_minimum_coord(coords, target_instance_name, "y")
exterior_faces = build_exterior_faces(odb, target_instance_name)
air_faces, baseplate_faces = classify_exterior_faces(exterior_faces, coords, target_instance_name, baseplate_height = baseplate_height)

air_nodes = build_nodes_from_faces(air_faces, target_instance_name)
baseplate_nodes = build_nodes_from_faces(baseplate_faces, target_instance_name)
face_surface_normals = build_surface_normals(air_faces, coords, target_instance_name)

#print("Exporting exterior faces to STL file...")
#export_exterior_faces_to_stl(exterior_faces, coords, face_surface_normals, target_instance_name, stl_path)
#print("Finished exporting exterior faces to STL file.")

node_surface_normals, normal_variation = build_node_surface_features(air_faces, face_surface_normals, target_instance_name)

air_distance, air_displacement = build_air_surface_displacement_lookup(coords, air_nodes, target_instance_name)

face_geometry = build_face_geometry_lookup(coords, air_faces, face_surface_normals, target_instance_name)
directional_faces = build_directional_face_arrays(
    air_faces,
    face_geometry,
)

edges = build_edge_set(odb, target_instance_name)

if not os.path.exists(global_path):
    print("No global file found. Generating...")
    bbox_x, bbox_y, bbox_z = calculate_bbox(coords, target_instance_name)
    baseplate_contact_area = sum(calculate_planar_face_area(face, coords, target_instance_name)
                            for face, _ in baseplate_faces)
    face_surface_area = sum(calculate_air_face_area(face, face_geometry) for face, _ in air_faces)
    volume = calculate_mesh_volume(odb, coords, target_instance_name)

    global_data = {
        "volume": volume,
        "baseplate_contact_area": baseplate_contact_area,
        "air_exposed_area": face_surface_area,
        "air_surface_volume_ratio": face_surface_area / volume,
        "baseplate_interface_volume_ratio": baseplate_contact_area / volume,
        "bbox_x": bbox_x,
        "bbox_y": bbox_y,
        "bbox_z": bbox_z,
    }

    with open(global_path, "w") as f:
        json.dump(global_data, f)

with open(global_path, "r") as f:
     global_data = json.load(f)

required_global_features = [
    "volume",
    "baseplate_contact_area",
    "air_exposed_area",
    "air_surface_volume_ratio",
    "baseplate_interface_volume_ratio",
    "bbox_x",
    "bbox_y",
    "bbox_z",
]

missing_features = [
    name for name in required_global_features
    if name not in global_data
]

if missing_features:
    raise ValueError(
        "Missing global features in {}: {}".format(
            global_path,
            missing_features,
        )
    )

for dimension in ["bbox_x", "bbox_y", "bbox_z"]:
    if global_data[dimension] <= 0:
        raise ValueError(
            "{} must be positive, got {}".format(
                dimension,
                global_data[dimension],
            )
        )

with open(csv_edge_path, "w") as f:
    writer = csv.writer(f)
    writer.writerow(["node_label_1", "node_label_2"])

    for node_label_1, node_label_2 in edges:
        writer.writerow([node_label_1, node_label_2])

step = odb.steps[step_name]


peak_temperature = {}

for frame in step.frames:
    if "NT11" not in frame.fieldOutputs:
        continue


    temperature_field = frame.fieldOutputs["NT11"].getSubset(position=NODAL)

    for value in temperature_field.values:
        
        if value.instance.name != target_instance_name:
            continue
        
        key = node_key(value.instance.name, value.nodeLabel)
        temperature = value.dataDouble

        if key not in peak_temperature:
            peak_temperature[key] = temperature
        elif temperature > peak_temperature[key]:
            peak_temperature[key] = temperature

if not os.path.exists(csv_path):
    with open(csv_path, "w") as f:
        writer = csv.writer(f)
        writer.writerow([
            "sample",
            "node_label",
            "x",
            "y",
            "z",
            "x_normalized",
            "y_normalized",
            "z_normalized",
            "peak_temperature",
            "is_air_boundary",
            "is_baseplate_interface",
            "surface_normal_x",
            "surface_normal_y",
            "surface_normal_z",
            "normal_variation",
            "nearest_air_distance",
            "nearest_air_dx",
            "nearest_air_dy",
            "nearest_air_dz",
            "d_pos_x",
            "d_neg_x",
            "d_pos_y",
            "d_neg_y",
            "d_pos_z",
            "d_neg_z",
            "volume",
            "baseplate_contact_area",
            "air_exposed_area",
            "air_surface_volume_ratio",
            "baseplate_interface_volume_ratio",
            "bbox_x",
            "bbox_y",
            "bbox_z",
        ])

        for i, (key, temperature) in enumerate(
        peak_temperature.items()
    ):

            if i % 100 == 0:
                print(
                    "Processing node {} / {}".format(
                        i,
                        len(peak_temperature)
                    )
                )
                sys.stdout.flush()
            instance_name, node_label = key
            x, y, z = coords[key]

            if key in air_nodes:
                surface_normal_x = node_surface_normals[key][0]
                surface_normal_y = node_surface_normals[key][1]
                surface_normal_z = node_surface_normals[key][2]

                node_normal_variation = normal_variation[key]

            else:
                surface_normal_x = 0.0
                surface_normal_y = 0.0
                surface_normal_z = 0.0

                node_normal_variation = 0.0

            d_pos_x = find_vectorized_axis_distance(
                coords[key],
                "+x",
                directional_faces,
                baseplate_height,
            )

            d_neg_x = find_vectorized_axis_distance(
                coords[key],
                "-x",
                directional_faces,
                baseplate_height,
            )

            d_pos_y = find_vectorized_axis_distance(
                coords[key],
                "+y",
                directional_faces,
                baseplate_height,
            )

            d_neg_y = find_vectorized_axis_distance(
                coords[key],
                "-y",
                directional_faces,
                baseplate_height,
            )

            d_pos_z = find_vectorized_axis_distance(
                coords[key],
                "+z",
                directional_faces,
                baseplate_height,
            )

            d_neg_z = find_vectorized_axis_distance(
                coords[key],
                "-z",
                directional_faces,
                baseplate_height,
            )

            


            writer.writerow([
                sample_name,
                node_label,
                x,
                y,
                z,
                (x - min_x)/global_data["bbox_x"],
                (y - min_y)/global_data["bbox_y"],
                (z - baseplate_height)/global_data["bbox_z"],
                temperature,
                int(key in air_nodes),
                int(key in baseplate_nodes),
                surface_normal_x,
                surface_normal_y,
                surface_normal_z,
                node_normal_variation,
                air_distance[key],
                air_displacement[key][0],
                air_displacement[key][1],
                air_displacement[key][2],
                d_pos_x,
                d_neg_x,
                d_pos_y,
                d_neg_y,
                d_pos_z,
                d_neg_z,
                global_data["volume"],
                global_data["baseplate_contact_area"],
                global_data["air_exposed_area"],
                global_data["air_surface_volume_ratio"],
                global_data["baseplate_interface_volume_ratio"],
                global_data["bbox_x"],
                global_data["bbox_y"],
                global_data["bbox_z"],
            ])

    num_nodes = len(odb.rootAssembly.instances[target_instance_name].nodes)

    num_nodes_path = os.path.join(
        r"{root}\datasets\{dataset}\{split}\{sample_name}".format(root = Path.cwd(), dataset = dataset, sample_name=sample_name, split = split), "{}_extraction_metadata.json".format(sample_name))

    with open(num_nodes_path, "w") as f:
        json.dump({
            "num_nodes": num_nodes,
        }, f
        )

    print("Finished generating dataset for sample {sample_name}.".format(sample_name = sample_name))

else:
    print("csv already exists, skipping generation.")

odb.close()