from odbAccess import openOdb
from abaqusConstants import NODAL

import csv
import json
import os
import sys

from dataset_functions import (
    build_air_surface_displacement_lookup,
    build_coordinate_lookup,
    build_directional_face_arrays,
    build_edge_set,
    build_exterior_faces,
    build_face_geometry_lookup,
    build_node_surface_features,
    build_nodes_from_faces,
    build_surface_normals,
    classify_exterior_faces,
    find_vectorized_axis_distance,
    get_minimum_coord,
    node_key,
)


TARGET_INSTANCE_NAME = "AMPART-1"
STEP_NAME = "LPBF_thermal"


def read_abaqus_cpu_time(dat_path):
    """Return the total CPU time reported in an Abaqus DAT file."""
    cpu_time = None

    with open(dat_path, "r") as dat_file:
        for line in dat_file:
            if "TOTAL CPU TIME" in line:
                cpu_time = float(line.split()[-1])

    if cpu_time is None:
        raise ValueError(
            "Could not find TOTAL CPU TIME in {}".format(dat_path)
        )

    return cpu_time


def postprocess_sample(job_name):
    """Convert one completed NURD Abaqus job to MeshGraphNet CSV files."""
    if "__" not in job_name:
        raise ValueError(
            "Expected a job name such as train__cuboid_000, got {}".format(
                job_name
            )
        )

    split, sample_name = job_name.split("__", 1)

    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    odb_path = os.path.join(script_dir, job_name + ".odb")
    dat_path = os.path.join(script_dir, job_name + ".dat")
    global_path = os.path.join(
        script_dir,
        job_name + "_global.json",
    )
    csv_path = os.path.join(script_dir, job_name + ".csv")
    edge_path = os.path.join(
        script_dir,
        job_name + "_edges.csv",
    )
    metadata_path = os.path.join(
        script_dir,
        job_name + "_metadata.json",
    )

    abaqus_cpu_time = read_abaqus_cpu_time(dat_path)

    with open(global_path, "r") as global_file:
        global_data = json.load(global_file)

    odb = openOdb(path=odb_path, readOnly=True)

    try:
        existing_instances = [
            instance_name
            for instance_name, _ in odb.rootAssembly.instances.items()
        ]

        if TARGET_INSTANCE_NAME not in existing_instances:
            raise ValueError(
                "Target instance {} not found. Valid instances are: {}".format(
                    TARGET_INSTANCE_NAME,
                    existing_instances,
                )
            )

        coords = build_coordinate_lookup(odb)
        baseplate_height = get_minimum_coord(
            coords,
            TARGET_INSTANCE_NAME,
            "z",
        )
        min_x = get_minimum_coord(coords, TARGET_INSTANCE_NAME, "x")
        min_y = get_minimum_coord(coords, TARGET_INSTANCE_NAME, "y")

        exterior_faces = build_exterior_faces(
            odb,
            TARGET_INSTANCE_NAME,
        )
        air_faces, baseplate_faces = classify_exterior_faces(
            exterior_faces,
            coords,
            TARGET_INSTANCE_NAME,
            baseplate_height=baseplate_height,
        )

        air_nodes = build_nodes_from_faces(
            air_faces,
            TARGET_INSTANCE_NAME,
        )
        baseplate_nodes = build_nodes_from_faces(
            baseplate_faces,
            TARGET_INSTANCE_NAME,
        )
        face_surface_normals = build_surface_normals(
            air_faces,
            coords,
            TARGET_INSTANCE_NAME,
        )
        node_surface_normals, normal_variation = (
            build_node_surface_features(
                air_faces,
                face_surface_normals,
                TARGET_INSTANCE_NAME,
            )
        )

        air_distance, air_displacement = (
            build_air_surface_displacement_lookup(
                coords,
                air_nodes,
                TARGET_INSTANCE_NAME,
            )
        )
        face_geometry = build_face_geometry_lookup(
            coords,
            air_faces,
            face_surface_normals,
            TARGET_INSTANCE_NAME,
        )
        directional_faces = build_directional_face_arrays(
            air_faces,
            face_geometry,
        )
        edges = build_edge_set(odb, TARGET_INSTANCE_NAME)

        with open(edge_path, "w") as edge_file:
            writer = csv.writer(edge_file)
            writer.writerow(["node_label_1", "node_label_2"])

            for node_label_1, node_label_2 in sorted(edges):
                writer.writerow([node_label_1, node_label_2])

        step = odb.steps[STEP_NAME]
        peak_temperature = {}

        for frame in step.frames:
            if "NT11" not in frame.fieldOutputs:
                continue

            temperature_field = frame.fieldOutputs["NT11"].getSubset(
                position=NODAL
            )

            for value in temperature_field.values:
                if value.instance.name != TARGET_INSTANCE_NAME:
                    continue

                key = node_key(value.instance.name, value.nodeLabel)
                temperature = value.dataDouble

                if (
                    key not in peak_temperature
                    or temperature > peak_temperature[key]
                ):
                    peak_temperature[key] = temperature

        with open(csv_path, "w") as csv_file:
            writer = csv.writer(csv_file)
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

            for key in sorted(peak_temperature):
                temperature = peak_temperature[key]
                _, node_label = key
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

                distances = [
                    find_vectorized_axis_distance(
                        coords[key],
                        direction,
                        directional_faces,
                        baseplate_height,
                    )
                    for direction in (
                        "+x",
                        "-x",
                        "+y",
                        "-y",
                        "+z",
                        "-z",
                    )
                ]

                writer.writerow([
                    sample_name,
                    node_label,
                    x,
                    y,
                    z,
                    (x - min_x) / global_data["bbox_x"],
                    (y - min_y) / global_data["bbox_y"],
                    (z - baseplate_height) / global_data["bbox_z"],
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
                    distances[0],
                    distances[1],
                    distances[2],
                    distances[3],
                    distances[4],
                    distances[5],
                    global_data["volume"],
                    global_data["baseplate_contact_area"],
                    global_data["air_exposed_area"],
                    global_data["air_surface_volume_ratio"],
                    global_data["baseplate_interface_volume_ratio"],
                    global_data["bbox_x"],
                    global_data["bbox_y"],
                    global_data["bbox_z"],
                ])

        number_of_nodes = len(
            odb.rootAssembly.instances[TARGET_INSTANCE_NAME].nodes
        )

    finally:
        odb.close()

    with open(metadata_path, "w") as metadata_file:
        json.dump(
            {
                "sample_name": sample_name,
                "split": split,
                "number_of_nodes": number_of_nodes,
                "abaqus_solve_time": abaqus_cpu_time,
                "status": "completed",
            },
            metadata_file,
            indent=4,
        )

    print(
        "Finished postprocessing {} / {}.".format(
            split,
            sample_name,
        )
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise RuntimeError(
            "Usage: abaqus python postprocess_sample.py <job_name>"
        )

    postprocess_sample(sys.argv[-1])
