import cadquery as cq
import random
from pathlib import Path
import json
import numpy as np


def get_baseplate_faces(part, baseplate_z, tolerance = 1e-6):

    baseplate_faces = []

    for face in part.faces("-Z").vals():
        bbox = face.BoundingBox()
        if abs(bbox.zmax - baseplate_z) < tolerance and abs(bbox.zmin - baseplate_z) < tolerance:
            baseplate_faces.append(face)
        else:
            print(f"no bueno, bbox.zmax - baseplate_z = {bbox.zmax - baseplate_z}")
    return baseplate_faces


def get_global_data(part, baseplate_z):
    """
    Generate and save global data file for a given geometry.
    """

    data = {}
    shape = part.val()
    volume = shape.Volume()
    total_area = shape.Area()

    bottom_faces = get_baseplate_faces(part, baseplate_z)
    baseplate_contact_area = sum(       
        face.Area()
        for face in bottom_faces
    )

    air_exposed_area = total_area - baseplate_contact_area

    air_surface_volume_ratio = air_exposed_area / volume
    baseplate_interface_volume_ratio = baseplate_contact_area / volume

    bbox = shape.BoundingBox()
    bbox_x, bbox_y, bbox_z = bbox.xlen, bbox.ylen, bbox.zlen

    data["volume"] = float(volume)
    data["baseplate_contact_area"] = float(baseplate_contact_area)
    data["air_exposed_area"] = float(air_exposed_area)
    data["air_surface_volume_ratio"] = float(air_surface_volume_ratio)
    data["baseplate_interface_volume_ratio"] = float(baseplate_interface_volume_ratio)
    data["bbox_x"] = float(bbox_x)
    data["bbox_y"] = float(bbox_y)
    data["bbox_z"] = float(bbox_z)

    return data


def generate_cuboid(rng, maxsize, minsize = 5):
    w = rng.uniform(minsize, maxsize)
    l = rng.uniform(minsize, maxsize)
    h = rng.uniform(minsize, maxsize)

    part = (cq.Workplane("XY").box(w, l, h, centered = (True, True, False)))

    return part, 0.0


def generate_cylinder(rng, maxsize, minsize = 5):
    radius = rng.uniform(minsize/2, maxsize/2)
    height = rng.uniform(minsize, maxsize)

    part = (cq.Workplane("XY").circle(radius).extrude(height))

    return part, 0.0

def generate_cone(rng, maxsize, minsize = 5, peak_size = 5):
    bottom_radius = rng.uniform(minsize/2, maxsize/2)
    height = rng.uniform(minsize, maxsize)

    part = (cq.Workplane("XY").circle(bottom_radius).workplane(offset = height).circle(peak_size).loft(combine = True))

    return part, 0.0

def generate_frustum(rng, maxsize, minsize = 5, peak_size = 1):
    bottom_radius = rng.uniform(minsize/2, maxsize/2)
    height = rng.uniform(minsize, maxsize)

    top_radius = rng.uniform(peak_size, bottom_radius + height)

    part = (cq.Workplane("XY").circle(bottom_radius).workplane(offset = height).circle(top_radius).loft(combine = True))

    return part, 0.0

def generate_pyramid(rng, maxsize, minsize = 5, peak_size = 1):
    w = rng.uniform(minsize, maxsize)
    l = rng.uniform(minsize, maxsize)
    h = rng.uniform(minsize, maxsize)

    part = (cq.Workplane("XY").rect(w, l).workplane(offset = h).rect(peak_size, peak_size).loft(combine = True))

    return part, 0.0

def generate_triangular_frustum(rng, maxsize, minsize = 5):
    bottom_width = rng.uniform(minsize, maxsize)
    height = rng.uniform(minsize, maxsize)
    max_top_width = min(
    maxsize,
    bottom_width + 2 * height
)

    top_width = rng.uniform(
    1,
    max_top_width
)
    triangle_height = (np.sqrt(3) / 2 * bottom_width)

    top_triangle_height = (np.sqrt(3) / 2 * top_width)

    bottom_points = [
        (-bottom_width / 2, -triangle_height / 3),
        ( bottom_width / 2, -triangle_height / 3),
        (0, 2 * triangle_height / 3),
    ]

    top_points = [
        (-top_width / 2, -top_triangle_height / 3),
        ( top_width / 2, -top_triangle_height / 3),
        (0, 2 * top_triangle_height / 3),
    ]

    part = (
        cq.Workplane("XY")
        .polyline(bottom_points)
        .close()
        .workplane(offset=height)
        .polyline(top_points)
        .close()
        .loft(combine=True)
    )

    return part, 0.0


def generate_hourglass(rng, maxsize, minsize = 5):
    height = rng.uniform(minsize, maxsize)
    bottom_radius = rng.uniform(minsize/2, maxsize/2)
    top_radius = rng.uniform(minsize/2, maxsize/2)    
    waist_z = rng.uniform(0.3*height, 0.7*height)
    minimum_waist = max(bottom_radius - waist_z, top_radius - (height - waist_z), 1)
    waist_radius = rng.uniform(minimum_waist, min(bottom_radius, top_radius))

    part = (cq.Workplane("XY").circle(bottom_radius).workplane(offset = waist_z).circle(waist_radius).workplane(offset = height - waist_z).circle(top_radius).loft(combine = True, ruled = True))

    return part, 0.0

def generate_smooth_hourglass(rng, maxsize, minsize=10):
    height = rng.uniform(minsize, maxsize)

    bottom_radius = rng.uniform(minsize / 2, maxsize / 2)

    top_radius = rng.uniform(
        minsize / 2,
        maxsize / 2)

    waist_z = rng.uniform(
        0.3 * height,
        0.7 * height)

    minimum_waist = max(
        bottom_radius - waist_z,
        top_radius - (height - waist_z),
        1
    )

    maximum_waist = min(
        bottom_radius,
        top_radius
    )

    waist_radius = rng.uniform(
        minimum_waist,
        maximum_waist
    )

    lower_mid_radius = (
        bottom_radius
        + waist_radius
    ) / 2

    upper_mid_radius = (
        top_radius
        + waist_radius
    ) / 2

    lower_mid_z = waist_z / 2

    upper_mid_z = (
        waist_z
        + (height - waist_z) / 2
    )

    part = (
        cq.Workplane("XY")
        .circle(bottom_radius)
        .workplane(offset=lower_mid_z)
        .circle(lower_mid_radius)
        .workplane(offset=waist_z - lower_mid_z)
        .circle(waist_radius)
        .workplane(offset=upper_mid_z - waist_z)
        .circle(upper_mid_radius)
        .workplane(offset=height - upper_mid_z)
        .circle(top_radius)
        .loft(
            combine=True,
            ruled=False
        )
    )

    return part, 0.0

def generate_half_ellipsoid(rng, maxsize, minsize = 5, peak_size = 1):
    radius = rng.uniform(minsize/2,maxsize/2)
    height = rng.uniform(minsize, maxsize)

    num_sections = 8

    z_values = np.linspace(0, height, num_sections)

    part = (cq.Workplane("XY").circle(radius))

    previous_z = 0.0

    for z in z_values[1:-1]:
        section_radius = radius * np.sqrt(1 - (z / height) ** 2)
        part = (
            part
            .workplane(offset=z - previous_z)
            .circle(section_radius)
        )
        previous_z = z

    part = (part.workplane(offset = height - previous_z).circle(peak_size).loft(combine = True))

    return part, 0.0


def generate_wedge(rng, maxsize, minsize = 5):
    bottom_x = rng.uniform(minsize, maxsize)
    y = rng.uniform(minsize, maxsize)
    height = rng.uniform(minsize, maxsize)

    max_expansion = min(height, maxsize - bottom_x)
    expansion = rng.uniform(0, max_expansion)

    top_x = bottom_x + expansion

    part = (cq.Workplane("XY").rect(bottom_x, y).workplane(offset = height).center(expansion/2, 0).rect(top_x, y).loft(combine = True))

    return part, 0.0

def generate_pipe(rng, maxsize, minsize = 5, min_thickness = 1):
    outer_radius = rng.uniform(minsize/2, maxsize/2)
    inner_radius = rng.uniform(0.5*outer_radius, outer_radius - min_thickness)
    height = rng.uniform(minsize, maxsize)

    outer = (cq.Workplane("XY").circle(outer_radius).extrude(height))
    inner = (cq.Workplane("XY").circle(inner_radius).extrude(height))

    part = outer.cut(inner)

    return part, 0.0


def generate_hollow_cuboid(rng, maxsize, minsize = 5, min_thickness = 1):
    outer_x = rng.uniform(minsize, maxsize)
    outer_y = rng.uniform(minsize, maxsize)
    z = rng.uniform(minsize, maxsize)
    inner_x = rng.uniform(0.5 * outer_x, outer_x - min_thickness)
    inner_y = rng.uniform(0.5 * outer_y, outer_y - min_thickness)

    outer = (cq.Workplane("XY").box(outer_x, outer_y, z, centered = (True, True, False)))
    inner = (cq.Workplane("XY").box(inner_x, inner_y, z, centered = (True, True, False)))

    part = outer.cut(inner)

    return part, 0.0



def generate_geometry_dataset(
        dataset_root,
        enabled_families,
        family_generators,
        num_per_family = None,
        family_counts = None,
        train_fraction = 0.8,
        val_fraction = 0.1,
        test_fraction = 0.1,
        seed = 0,
        maxsize = 50,
        shuffle = False
):
    if family_counts is None:
        family_counts = {}

    if abs(train_fraction + val_fraction + test_fraction - 1.0) > 1e-8:
        raise ValueError("train_fraction, val_fraction, and test_fraction must sum to 1.0")

    rng = random.Random(seed)

    dataset_root = Path(dataset_root)
    dataset_root.mkdir(parents = True, exist_ok = True)

    for split in ["train", "val", "test"]:
        (dataset_root / split).mkdir(parents = True, exist_ok = True)

    for family in enabled_families:
        if family not in family_generators:
            raise ValueError("No generator for family '{}'".format(family))
        
        if family in family_counts:
            num_samples = family_counts[family]
        elif num_per_family is not None:
            num_samples = num_per_family

        else:
            raise ValueError("No number of samples specified for family: {}".format(family))

        num_train = int(num_samples * train_fraction)
        num_val = int(num_samples * val_fraction)
        num_test = num_samples - num_train - num_val

        splits = (["train"]*num_train + ["val"]*num_val + ["test"]*num_test)

        if shuffle:
            rng.shuffle(splits)

        generator = family_generators[family]

        for i in range(num_samples):
            split = splits[i]
            sample_name = "{}_{:03d}".format(family, i)

            print("Generating {} in {}".format(sample_name, split))

            part, baseplate_z = generator(rng, maxsize)

            global_data = get_global_data(part, baseplate_z)

            sample_directory = (dataset_root / split / sample_name)

            sample_directory.mkdir(parents = True, exist_ok = False)

            step_path = (sample_directory / "{}.step".format(sample_name))
            global_path = (sample_directory / "{}_global.json".format(sample_name))

            cq.exporters.export(part, str(step_path))

            with open(global_path, "w") as f:
                json.dump(global_data, f)




