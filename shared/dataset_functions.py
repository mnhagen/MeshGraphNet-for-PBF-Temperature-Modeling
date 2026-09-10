import numpy as np
import os
from datetime import datetime
import subprocess
import sys
import csv
from scipy.spatial import cKDTree
from scipy.spatial import ConvexHull



def node_key(instance_name, node_label):
    """returns node key for a given instance and node label."""
    return (instance_name, node_label)

def build_coordinate_lookup(odb):
    """
    Returns {(instance_name, node_label): (x, y, z)}

    Could exclude baseplate as it is (for now) not used in the final dataset.
    """

    coords = {}

    for instance_name, instance in odb.rootAssembly.instances.items():
        for node in instance.nodes:
            xyz = list(node.coordinates)

            x, y, z = xyz[0], xyz[1], xyz[2]

            coords[node_key(instance_name, node.label)] = (x, y, z)

    return coords



def get_element_faces(element):
    """
    Return the node label tuples for each face of the element.
    The node labels are sorted so that the faces are consistent across elements.
    """
    conn = element.connectivity

    element_type = element.type.upper()

    if element_type.startswith("DC3D4"):
        face_indices = [(0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)]

    elif element_type.startswith("C3D8") or element_type.startswith("DC3D8"):
        face_indices = [
            (0, 1, 2, 3),
            (4, 5, 6, 7),
            (0, 1, 5, 4),
            (1, 2, 6, 5),
            (2, 3, 7, 6),
            (3, 0, 4, 7),
        ]

    else:
        raise ValueError("Unknown element type: {element_type}. Only DC3D4, C3D8, and DC3D8 elements are supported.".format(element_type=element_type))
    
    return [tuple(sorted(conn[i] for i in face)) for face in face_indices]


def build_exterior_faces(odb, instance_name):
    """
    Returns the exterior faces of one instance.

    Each face is represented by a tuple of node indices.
    A face is exterior if it occurs in a single volume element.
    """
    instance = odb.rootAssembly.instances[instance_name]

    face_count = {}
    face_owner = {}

    for element in instance.elements:
        for face in get_element_faces(element):
            face_count[face] = face_count.get(face, 0) + 1

            if face not in face_owner:
                face_owner[face] = element


    exterior_faces = []

    for face, count in face_count.items():
        if count == 1:
            exterior_faces.append((face, face_owner[face]))

    return exterior_faces


def classify_exterior_faces(exterior_faces, coords, instance_name, baseplate_height = 0.0, tolerance = 1e-5):
    """
    returns lists of faces that are in contact with the baseplate and faces that are 
    in contact with air.
    """

    baseplate_faces = []
    air_faces = []

    for face, element in exterior_faces:

        z_coords = []

        for node_label in face:
            key = node_key(instance_name, node_label)
            z_coords.append(coords[key][2])

        on_baseplate = np.all(np.isclose(z_coords, baseplate_height, atol = tolerance, rtol = 0.0))

        if on_baseplate:
            baseplate_faces.append((face, element))

        else:
            air_faces.append((face, element))

    return air_faces, baseplate_faces


def build_nodes_from_faces(faces, instance_name):
    """
    Returns the set of nodes belonging to any face in 'faces'.
    """

    nodes = set()

    for face, _ in faces:
        for node_label in face:
            nodes.add(node_key(instance_name, node_label))

    return nodes



def build_surface_normals(face_element_tuple, coords, instance_name):
    """
    Returns the surface normals for each face in 'faces'.
    """
    surface_normals = {}

    for face, element in face_element_tuple:
        face_points = np.array([coords[node_key(instance_name, node_label)] for node_label in face])

        p0 = face_points[0]
        p1 = face_points[1]
        p2 = face_points[2]

        v1 = p1 -p0
        v2 = p2 - p0

        normal = np.cross(v1, v2)
        normal_length = np.linalg.norm(normal)

        if normal_length < 1e-12:
            raise ValueError("Degenerate face encountered: {}".format(face))

        normal = normal / normal_length    # we now have a surface normal, but could point inwards or outwards since the nodes indices are sorted in ascending order

        face_center = face_points.mean(axis=0)
        element_points = np.array([coords[node_key(instance_name, node_label)] for node_label in element.connectivity])
        element_center = element_points.mean(axis=0)

        outward_direction = face_center - element_center

        if np.dot(normal, outward_direction) < 0:
            normal = -normal

        surface_normals[face] = normal

    return surface_normals



def build_node_surface_features(air_faces, surface_normals, instance_name):
    """
    Returns node-level surface features and normal variation.
    """
    node_face_normals = {}

    for face, _ in air_faces:
        face_normal = surface_normals[face]

        for node_label in face:
            key = node_key(instance_name, node_label)

            if key not in node_face_normals:
                node_face_normals[key] = []

            node_face_normals[key].append(face_normal)

    node_surface_normals = {}
    normal_variation = {}

    for key, normals in node_face_normals.items():

        normals = np.array(normals)

        mean_normal = normals.mean(axis = 0)
        mean_length = np.linalg.norm(mean_normal)
        normal_variation[key] = np.clip(1.0 - mean_length, 0.0, 1.0)

        if mean_length < 1e-12:
            raise ValueError("Mean surface normal is approx. zero for node {}".format(key))

        node_surface_normals[key] = mean_normal / mean_length

    return node_surface_normals, normal_variation








def get_element_edges(element):
    """
    Returns unique edges of for one element as tuples: (node1, node2)
    """

    conn = element.connectivity
    element_type = element.type.upper()

    if element_type.startswith("DC3D4") or element_type.startswith("C3D4"):
        edge_indices = [(0,1), (0,2), (0,3), (1,2), (1,3), (2,3)]
    
    elif element_type.startswith("DC3D8") or element_type.startswith("C3D8"):
        edge_indices = [
            # Bottom face
            (0, 1),
            (1, 2),
            (2, 3),
            (3, 0),

            # Top face
            (4, 5),
            (5, 6),
            (6, 7),
            (7, 4),

            # Vertical edges
            (0, 4),
            (1, 5),
            (2, 6),
            (3, 7),
        ]

    else:
        raise ValueError("Unknown element type: {element_type}. Only DC3D4, C3D8 and DC3D8 elements are supported.".format(element_type=element_type))
    
    return [tuple(sorted((conn[i], conn[j]))) for i, j in edge_indices]



def build_air_surface_displacement_lookup(coords, air_nodes, instance_name):
    """
    Builds a lookup table for the distance from each node to the closest air surface node.
    """

    distances = {}
    displacements = {}

    all_keys = [key for key in coords if key[0] == instance_name]
    air_keys = [key for key in air_nodes if key[0] == instance_name]
    boundary_xyz = np.array([coords[key] for key in air_keys])
    all_xyz = np.array([coords[key] for key in all_keys])

    tree = cKDTree(boundary_xyz)

    nearest_distances, nearest_indices = tree.query(all_xyz, k = 1)

    for key, distance, index in zip(all_keys, nearest_distances, nearest_indices):
        distances[key] = float(distance)
        displacements[key] = boundary_xyz[index] - coords[key]

    return distances, displacements


def calculate_planar_face_area(face, coords, instance_name):
    """
    Calculates the area of a planar face.
    """
    points = np.array([coords[node_key(instance_name, node_label)] for node_label in face])

    xy = points[:, :2]

    center = xy.mean(axis = 0)

    angles = np.arctan2(xy[:, 1] - center[1], xy[:, 0] - center[0])

    xy = xy[np.argsort(angles)]

    x = xy[:, 0]
    y = xy[:, 1]

    area = 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))

    return float(area)




def build_face_geometry_lookup(coords, faces, face_surface_normals, instance_name):
    """
    Builds a lookup of face geometry.
    """
    face_geometry = {}
    for face, _ in faces:
        face_points = np.array([coords[node_key(instance_name, node_label)] for node_label in face])

        face_geometry[face] = { "points": face_points, "center": face_points.mean(axis = 0),
                                "normal": face_surface_normals[face],
                                "xmin": face_points[:, 0].min(), "xmax": face_points[:, 0].max(),
                                "ymin": face_points[:, 1].min(), "ymax": face_points[:, 1].max(),
                                "zmin": face_points[:, 2].min(), "zmax": face_points[:, 2].max()}
    return face_geometry

def find_candidate_faces(node_xyz, direction_name, air_faces, face_geometry, tolerance = 1e-5):
    """
    Finds candidate faces for a given node and direction.
    """

    candidate_faces = []

    directions = ["+x", "-x", "+y", "-y", "+z", "-z"]

    if direction_name not in directions:
        raise ValueError("direction_name must be one of {}".format(directions))

    x, y, z = node_xyz

    if direction_name == "+x":

        for face, _ in air_faces:
            geom = face_geometry[face]

            if (
                geom["ymin"] - tolerance <= y <= geom["ymax"] + tolerance 
            and geom["xmax"] >= x - tolerance
            and geom["zmin"] - tolerance <= z <= geom["zmax"] + tolerance
            ):
                candidate_faces.append(face)


    elif direction_name == "-x":
        for face, _ in air_faces:
            geom = face_geometry[face]

            if (
                geom["ymin"] - tolerance <= y <= geom["ymax"] + tolerance 
            and geom["xmin"] <= x + tolerance
            and geom["zmin"] - tolerance <= z <= geom["zmax"] + tolerance
            ):
                candidate_faces.append(face)

    elif direction_name == "+y":

        for face, _ in air_faces:
            geom = face_geometry[face]

            if (
                geom["xmin"] - tolerance <= x <= geom["xmax"] + tolerance 
            and geom["ymax"] >= y - tolerance
            and geom["zmin"] - tolerance <= z <= geom["zmax"] + tolerance
            ):
                candidate_faces.append(face)


    elif direction_name == "-y":
        for face, _ in air_faces:
            geom = face_geometry[face]

            if (
                geom["xmin"] - tolerance <= x <= geom["xmax"] + tolerance 
            and geom["ymin"] <= y + tolerance
            and geom["zmin"] - tolerance <= z <= geom["zmax"] + tolerance
            ):
                candidate_faces.append(face)

    elif direction_name == "+z":
    
        for face, _ in air_faces:
            geom = face_geometry[face]

            if (
                geom["ymin"] - tolerance <= y <= geom["ymax"] + tolerance 
            and geom["zmax"] >= z - tolerance
            and geom["xmin"] - tolerance <= x <= geom["xmax"] + tolerance
            ):
                candidate_faces.append(face)


    elif direction_name == "-z":
        for face, _ in air_faces:
            geom = face_geometry[face]

            if (
                geom["ymin"] - tolerance <= y <= geom["ymax"] + tolerance 
            and geom["zmin"] <= z + tolerance
            and geom["xmin"] - tolerance <= x <= geom["xmax"] + tolerance
            ):
                candidate_faces.append(face)


    return candidate_faces

def order_face_points(points, normal):
    """
    Orders planar face vertices cyclically around the face center.
    """

    center = points.mean(axis = 0)

    drop_axis = np.argmax(np.abs(normal))

    projected = np.delete(points, drop_axis, axis = 1)

    projected_center = projected.mean(axis = 0)

    angles = np.arctan2(projected[:, 1] - projected_center[1],
                        projected[:, 0] - projected_center[0])

    order = np.argsort(angles)

    return points[order]

def triangulate_face(points, normal):
    if len(points) == 3:
        return [(points[0], points[1], points[2])]

    elif len(points) == 4:

        points = order_face_points(points, normal)
        return [(points[0], points[1], points[2]),
                (points[0], points[2], points[3])]

    else:
        raise ValueError("Faces must have 3 or 4 vertices.")

def build_directional_face_arrays(
    air_faces, face_geometry, parallel_tolerance = 1e-12
):
    """
    Converts air-face geometry to NumPy arrays and prefilters faces
    according to which axis-aligned rays can intersect them.

    Returns one array collection for x-rays, one for y-rays and one
    for z-rays.
    """

    triangle_faces = []
    centers = []
    normals = []
    bounds_min = []
    bounds_max = []
    vertices_0 = []
    vertices_1 = []
    vertices_2 = []

    for face, _ in air_faces:

        geom = face_geometry[face]
        points = geom["points"]
        normal = geom["normal"]

        triangles = triangulate_face(points, normal)

        for triangle in triangles:
            v0, v1, v2 = triangle

            triangle_normal = np.cross(
            v1 - v0,
            v2 - v0
            )

            triangle_normal_length = np.linalg.norm(
                triangle_normal
            )

            if triangle_normal_length < 1e-12:
                raise ValueError(
                    "Degenerate triangle generated from face {}".format(
                        face
                    )
                )

            triangle_normal = (
                triangle_normal
                / triangle_normal_length
            )

            # Make it point outward, using the original face normal
            # only as an orientation reference.
            if np.dot(
                triangle_normal,
                geom["normal"]
            ) < 0:
                triangle_normal = -triangle_normal

            vertices_0.append(v0)
            vertices_1.append(v1)
            vertices_2.append(v2)

            triangle_faces.append(face)
            centers.append(geom["center"])
            normals.append(triangle_normal)
            

            bounds_min.append([
                geom["xmin"],
                geom["ymin"],
                geom["zmin"],
            ])

            bounds_max.append([
                geom["xmax"],
                geom["ymax"],
                geom["zmax"],
            ])

    vertices_0 = np.asarray(
        vertices_0,
        dtype=float,
    )

    vertices_1 = np.asarray(
        vertices_1,
        dtype=float,
    )

    vertices_2 = np.asarray(
        vertices_2,
        dtype=float,
    )

    centers = np.asarray(
        centers,
        dtype=float,
    )

    normals = np.asarray(
        normals,
        dtype=float,
    )

    bounds_min = np.asarray(
        bounds_min,
        dtype=float,
    )

    bounds_max = np.asarray(
        bounds_max,
        dtype=float,
    )

    directional_faces = {}

    for axis in range(3):
        usable = (
            np.abs(normals[:, axis])
            > parallel_tolerance
        )

        directional_faces[axis] = {
            "faces": [
                face
                for face, keep
                in zip(triangle_faces, usable)
                if keep
            ],
            "centers": centers[usable],
            "normals": normals[usable],
            "bounds_min": bounds_min[usable],
            "bounds_max": bounds_max[usable],
            "v0": vertices_0[usable],
            "v1": vertices_1[usable],
            "v2": vertices_2[usable],
        }

    return directional_faces


def calculate_bbox(coords, instance_name):
    """
    Calculate the bounding box of a set of nodes.
"""

    points = np.array([xyz for key, xyz in coords.items() if key[0] == instance_name])

    lengths = (points.max(axis = 0) - points.min(axis = 0))

    return (float(lengths[0]),
            float(lengths[1]),
            float(lengths[2]),
            )



def calculate_element_volume(element, coords, instance_name):
    """
    Calculate the volume of an element.
"""
    points = np.array([coords[node_key(instance_name, node_label)] for node_label in element.connectivity])

    element_type = element.type.upper()

    if element_type.startswith("DC3D4") or element_type.startswith("C3D4"):

        volume = abs(np.dot(points[1] - points[0], np.cross(points[2] - points[0], points[3] - points[0]))) /6

        return float(volume)
    
    elif element_type.startswith("DC3D8") or element_type.startswith("C3D8"):
        hull = ConvexHull(points)
        return float(hull.volume)
    
    else:
        raise ValueError("Unknown element type: {element_type}. Only DC3D4, C3D8, and DC3D8 elements are supported.".format(element_type=element_type))



def calculate_mesh_volume(odb, coords, instance_name):
    """
    calculates total volume of all elements in a mesh."""
    instance = odb.rootAssembly.instances[instance_name]

    total_volume = 0.0

    for element in instance.elements:

        total_volume += calculate_element_volume(element, coords, instance_name)

    return total_volume



def calculate_air_face_area(face, face_geometry):
    """calculates the area of a face in contact with air."""
    geom = face_geometry[face]
    points = geom["points"]
    normal = geom["normal"]

    triangles = triangulate_face(points, normal)

    area = 0.0

    for triangle in triangles:

        p0, p1, p2 = triangle

        area += np.linalg.norm(np.cross(p1 - p0, p2 - p0)) / 2

    return float(area)


def find_vectorized_axis_distance(
    node_xyz,
    direction_name,
    directional_faces,
    baseplate_height,
    coordinate_tolerance=1e-4,
    parallel_tolerance=1e-12,
    barycentric_tolerance=1e-6,
):
    """
    Finds the nearest intersection between an axis-aligned ray and the
    air-exposed triangular surface mesh.

    Parameters
    ----------
    node_xyz
        Coordinates of the ray origin.

    direction_name
        One of:
        "+x", "-x", "+y", "-y", "+z", "-z".

    directional_faces
        Face arrays produced by build_directional_face_arrays().
        Each axis entry must contain:
            "v0", "v1", "v2", "normals", and "faces".

    baseplate_height
        Z-coordinate of the baseplate interface. The baseplate is not
        included in air_faces, so it is added explicitly for -z rays.

    coordinate_tolerance
        Distance tolerance, in the same units as the mesh coordinates.
        Used for forward and zero-distance tests.

    parallel_tolerance
        Threshold for treating a ray and triangle plane as parallel.
        This is dimensionless in this formulation and should be much
        smaller than the coordinate tolerance.

    barycentric_tolerance
        Dimensionless tolerance for intersections on triangle edges and
        vertices.

    Returns
    -------
    float
        Distance to the first valid boundary intersection.
    """

    directions = {
        "+x": (0, 1.0),
        "-x": (0, -1.0),
        "+y": (1, 1.0),
        "-y": (1, -1.0),
        "+z": (2, 1.0),
        "-z": (2, -1.0),
    }

    if direction_name not in directions:
        raise ValueError(
            "Unknown direction: {}. Expected one of {}.".format(
                direction_name,
                sorted(directions.keys()),
            )
        )

    axis, sign = directions[direction_name]

    data = directional_faces[axis]

    v0 = data["v0"]
    v1 = data["v1"]
    v2 = data["v2"]
    normals = data["normals"]

    if len(v0) == 0:
        if direction_name == "-z":
            return max(
                0.0,
                float(node_xyz[2] - baseplate_height),
            )

        raise ValueError(
            "No axis-compatible faces are available for "
            "direction {}.".format(direction_name)
        )

    node_xyz = np.asarray(
        node_xyz,
        dtype=float,
    )

    ray = np.zeros(
        3,
        dtype=float,
    )

    ray[axis] = sign

    # Triangle edge vectors:
    #
    # edge_1 = v1 - v0
    # edge_2 = v2 - v0
    edge_1 = (
        v1 - v0
    )

    edge_2 = (
        v2 - v0
    )

    # Moller-Trumbore:
    #
    # h = ray x edge_2
    #
    # np.cross broadcasts the single ray vector across all triangles.
    h = np.cross(
        ray,
        edge_2,
    )

    # determinant = edge_1 dot h
    #
    # A determinant near zero means the ray is parallel, or almost
    # parallel, to the triangle plane.
    determinant = np.sum(
        edge_1 * h,
        axis=1,
    )

    not_parallel = (
        np.abs(determinant)
        > parallel_tolerance
    )

    # Avoid division by zero for parallel faces. These entries remain
    # invalid because not_parallel is included in the final mask.
    safe_determinant = determinant.copy()

    safe_determinant[
        ~not_parallel
    ] = 1.0

    inverse_determinant = (
        1.0 / safe_determinant
    )

    # Vector from each triangle's first vertex to the ray origin.
    #
    # node_xyz[None, :] has shape (1, 3), while v0 has shape
    # (number_of_faces, 3). NumPy broadcasts the node across all faces.
    origin_offset = (
        node_xyz[None, :]
        - v0
    )

    # First barycentric coordinate:
    #
    # u = f * (origin_offset dot h)
    u = (
        inverse_determinant
        * np.sum(
            origin_offset * h,
            axis=1,
        )
    )

    # q = origin_offset x edge_1
    q = np.cross(
        origin_offset,
        edge_1,
    )

    # Second barycentric coordinate:
    #
    # v = f * (ray dot q)
    v = (
        inverse_determinant
        * np.sum(
            ray[None, :] * q,
            axis=1,
        )
    )

    # Ray distance:
    #
    # t = f * (edge_2 dot q)
    distances = (
        inverse_determinant
        * np.sum(
            edge_2 * q,
            axis=1,
        )
    )

    # Exact finite-triangle containment, with a small tolerance for
    # intersections lying on shared edges or vertices.
    inside_triangle = (
        (u >= -barycentric_tolerance)
        & (v >= -barycentric_tolerance)
        & (
            u + v
            <= 1.0 + barycentric_tolerance
        )
    )

    # Retain intersections in front of the node. Slight negative values
    # are accepted as numerical representations of zero.
    forward = (
        distances
        >= -coordinate_tolerance
    )

    # Determine whether the node already lies on a triangle.
    approximately_zero = (
        np.abs(distances)
        <= coordinate_tolerance
    )

    # dot(normal, ray) for every face. Normals are outward-facing.
    normal_ray_dot = np.sum(
        normals * ray[None, :],
        axis=1,
    )

    # When the ray points outward through a face containing the node,
    # the directional distance is zero.
    outward_zero = (
        approximately_zero
        & (normal_ray_dot > 0.0)
    )

    # When the ray points inward, ignore the starting face and continue
    # to the next surface intersection.
    inward_zero = (
        approximately_zero
        & (normal_ray_dot <= 0.0)
    )

    valid = (
        not_parallel
        & inside_triangle
        & forward
        & ~inward_zero
    )

    # Replace tiny numerical distances with an exact zero.
    distances[outward_zero] = 0.0

    valid_distances = (
        distances[valid]
    )

    # The baseplate-interface faces were intentionally removed from
    # air_faces. A -z ray may therefore terminate at the baseplate even
    # if it does not meet an air-exposed triangle first.
    if direction_name == "-z":
        baseplate_distance = max(
            0.0,
            float(
                node_xyz[2]
                - baseplate_height
            ),
        )

        if len(valid_distances) == 0:
            return baseplate_distance

        return min(
            float(
                valid_distances.min()
            ),
            baseplate_distance,
        )

    if len(valid_distances) == 0:
        print("FAILED NODE:", node_xyz)
        print("DIRECTION:", direction_name)
        print("total triangles:", len(v0))

        print(
            "not parallel:",
            np.count_nonzero(not_parallel)
        )

        print(
            "inside triangle:",
            np.count_nonzero(inside_triangle)
        )

        print(
            "forward:",
            np.count_nonzero(forward)
        )

        print(
            "zero distance:",
            np.count_nonzero(approximately_zero)
        )

        print(
            "not_parallel & inside:",
            np.count_nonzero(
                not_parallel & inside_triangle
            )
        )

        print(
            "not_parallel & inside & forward:",
            np.count_nonzero(
                not_parallel
                & inside_triangle
                & forward
            )
        )

        print("minimum distance:", distances.min())
        print("maximum distance:", distances.max())
        raise ValueError(
            "No triangle intersection found for direction {} "
            "from node {}. Tested {} axis-compatible "
            "triangles.".format(
                direction_name,
                tuple(node_xyz),
                len(v0),
            )
        )

    return float(
        valid_distances.min()
    )
    



        
            

def find_ray_plane_intersection(candidate_faces, node_xyz, direction_name,
                                 face_geometry, baseplate_height, tolerance = 1e-5):

    """Find the intersection of a ray with a face.
"""

    distances = []

    directions = {
    "+x": np.array([ 1.0,  0.0,  0.0]),
    "-x": np.array([-1.0,  0.0,  0.0]),
    "+y": np.array([ 0.0,  1.0,  0.0]),
    "-y": np.array([ 0.0, -1.0,  0.0]),
    "+z": np.array([ 0.0,  0.0,  1.0]),
    "-z": np.array([ 0.0,  0.0, -1.0]),
}

    if direction_name not in directions:
        raise ValueError(
        "Unknown direction_name: {}. Use one of: {}".format(direction_name, directions.keys())
    )

    ray = directions[direction_name]

    for face in candidate_faces:
        geom = face_geometry[face]

        plane_point = geom["center"]
        plane_normal = geom["normal"]

        denominator = np.dot(ray, plane_normal)
        if abs(denominator) < tolerance:
            continue

        distance = np.dot(plane_normal, plane_point - node_xyz) / denominator
        if distance < -tolerance:
            continue

        if abs(distance) <= tolerance:
            if denominator > 0:
                distance = 0.0
            else:
                continue

        intersection_point = node_xyz + ray*distance

        if (
            geom["xmin"] - tolerance <= intersection_point[0] <= geom["xmax"] + tolerance
            and geom["ymin"] - tolerance <= intersection_point[1] <= geom["ymax"] + tolerance
            and geom["zmin"] - tolerance <= intersection_point[2] <= geom["zmax"] + tolerance
        ):
            distances.append(float(distance)) #This is only approximate for sloped faces

    if direction_name == "-z":
        distances.append(
        node_xyz[2] - baseplate_height
    )

    elif direction_name != "-z" and len(distances) == 0:
        raise ValueError("No intersection found for direction {}. candidate faces: {}".format(direction_name, candidate_faces))

    return min(distances)


def get_minimum_coord(coords, instance_name, dimension):

    """
    finds the minimum coordinate in a given dimension for a given instance."""

    dim_dict = {"x": 0, "y": 1, "z": 2}

    return min(
        xyz[dim_dict[dimension]]
        for key, xyz in coords.items()
        if key[0] == instance_name
    )


def build_edge_set(odb, instance_name):
    """
    builds a set of edges for a given instance.
    """
    instance = odb.rootAssembly.instances[instance_name]
    edges = set()

    for element in instance.elements:
        for edge in get_element_edges(element):
            edges.add(edge)

    return edges


def log(message):
    """
    logs a message to the console.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("[{}] {}".format(timestamp, message))
    sys.stdout.flush()


def run_command(command, cwd = None):
    """
    runs a command as though it was entered in command prompt.
    
    raises an error if the command exits with a non-zero return code.
    """
    log("Running:")
    log(command)

    return_code = subprocess.call(command, cwd = cwd, shell = True)

    if return_code != 0:
        raise RuntimeError("Command failed with exit code {}: \n{}".format(return_code, command))


def update_metadata(metadata_path, new_row):
    """
    writes one metadata row per sample. If a row already exists with the same sample name, it is removed and replaced by new_row.
    """

    fieldnames = ["sample_name", "split", "number_of_nodes", "total_generation_time", "abaqus_solve_time", "status", "error"]

    existing_rows = []

    if os.path.isfile(metadata_path):
        with open(metadata_path, "r") as f:
            reader = csv.DictReader(f)

            for row in reader:
                if row.get("sample_name") != new_row["sample_name"]:
                    existing_rows.append(row)

    existing_rows.append(new_row)

    with open(metadata_path, "w") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for row in existing_rows:
            writer.writerow(row)


def cleanup_dir(sample_dir, sample_name):
    """
    removes files present in the sample directory that are no longer needed once the csv file has been created to save space.
    """

    keep_filenames = set([
    "{}.csv".format(sample_name),
    "{}_edges.csv".format(sample_name),
    "{}_global.json".format(sample_name),
    "{}_extraction_metadata.json".format(sample_name),
])
    
    missing = []

    for filename in keep_filenames:
        path = os.path.join(sample_dir, filename)

        if not os.path.isfile(path):
            missing.append(path)

    if missing:
        raise RuntimeError("Cleanup skipped because the following files are missing:\n{}".format("\n".join(missing)))

    for filename in os.listdir(sample_dir):
        path = os.path.join(sample_dir, filename)

        if filename in keep_filenames:
            continue

        if filename not in keep_filenames:
            os.remove(path)


def parse_bool(value):
    value = value.lower()

    if value in ["true", "1", "yes", "y"]:
        return True

    if value in ["false", "0", "no", "n"]:
        return False

    raise ValueError("Invalid boolean value: {}".format(value))


def export_exterior_faces_to_stl(exterior_faces, coords, exterior_face_normals, instance_name, output_path):

    """
    Exports the exterior faces of a mesh to an STL file. Currently not in use.
"""
    triangles = []

    for face, _ in exterior_faces:
        points = np.array([coords[node_key(instance_name, node_label)] for node_label in face])

        normal = (exterior_face_normals[face] if face in exterior_face_normals else (0.0,0.0,-1.0))

        if len(points) == 3:
            triangles.append(points)

        elif len(points) == 4:
            ordered = order_face_points(points, normal)

            test_normal = np.cross(ordered[1] - ordered[0], ordered[2] - ordered[0])

            if np.dot(test_normal, normal) < 0:
                ordered = ordered[::-1]

            triangles.append(ordered[[0,1,2]])

            triangles.append(ordered[[0,2,3]])

        else:
            raise ValueError("Unsupported exterior face with {} nodes".format(len(points)))

    with open(output_path, "w") as f:
        f.write("solid odb_part\n")

        for triangle in triangles:

            p0, p1, p2 = triangle

            normal = np.cross(p1 - p0, p2 - p0)

            norm = np.linalg.norm(normal)

            if norm > 0:
                normal /= norm

            else:
                normal = np.zeros(3)

            f.write("facet normal {} {} {}\n".format(normal[0], normal[1], normal[2]))

            f.write("   outer loop\n")

            for point in triangle:
                f.write("       vertex {} {} {}\n".format(point[0], point[1], point[2]))


            f.write("   endloop\n")
            f.write("endfacet\n")

        f.write("endsolid odb_part\n")

def rotate_coords(coords, target_instance_name, angle):
    """
    applies a rotation to the coordinates in a mesh. This was used for a diagnostic experiment,
    but is currently not in use anywhere. If using, make sure to apply it before performing
    feature engineering."""
    angle = np.radians(angle)

    c = np.cos(angle)
    s = np.sin(angle)

    instance_points = np.array([
        xyz
        for key, xyz in coords.items()
        if key[0] == target_instance_name
    ])

    print("instance_name:", target_instance_name)
    print("coord instances:", set(key[0] for key in coords.keys()))
    print("instance_points shape:", instance_points.shape)
    print(instance_points[0])

    center_x = (
        instance_points[:, 0].min()
        + instance_points[:, 0].max()
    ) / 2

    center_y = (
        instance_points[:, 1].min()
        + instance_points[:, 1].max()
    ) / 2

    rotated_coords = dict(coords)

    for key, xyz in coords.items():

        if key[0] != target_instance_name:
            continue

        x, y, z = xyz

        x -= center_x
        y -= center_y

        x_rot = c * x - s * y
        y_rot = s * x + c * y

        rotated_coords[key] = (
            x_rot + center_x,
            y_rot + center_y,
            z
        )

    return rotated_coords