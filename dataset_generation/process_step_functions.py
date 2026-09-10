import math

def horizontal_faces(instance, tol=1e-6):
    """Return [(face, z_level), ...] for faces parallel to the XY plane."""
    candidates = []

    for face in instance.faces:
        vertex_ids = face.getVertices()

        z_values = []

        for vertex_id in vertex_ids:
            vertex = instance.vertices[vertex_id]
            z_values.append(vertex.pointOn[0][2])

        z_min = min(z_values)
        z_max = max(z_values)

        if abs(z_max - z_min) < tol:
            candidates.append((face, z_min))

    return candidates

def estimate_time_period(height, patch_x, patch_y, layer_height = 0.5, hatch_spacing = 0.13, scan_speed = 855.0, on_time_frac = 0.8106, cooling_time = 60, recoater_time = 8.83):
    """helper function for estimating the print time based on the part size and laser parameters."""

    n_layers = math.ceil(height / layer_height)

    patch_area = patch_x * patch_y

    laser_on_time_per_layer = patch_area / (hatch_spacing * scan_speed)

    scan_time_per_layer = laser_on_time_per_layer / on_time_frac

    elapsed_time_per_layer = scan_time_per_layer + recoater_time

    printing_time = n_layers * elapsed_time_per_layer

    total_time = printing_time + cooling_time

    return total_time

def part_bbox(part):
    """helper function for getting the bounding box of a part."""
    x_vals = []
    y_vals = []
    z_vals = []
    
    for vertex in part.vertices:
        x, y, z = vertex.pointOn[0]

        x_vals.append(x)
        y_vals.append(y)
        z_vals.append(z)

    return{
        "low": (min(x_vals), min(y_vals), min(z_vals)),
        "high": (max(x_vals), max(y_vals), max(z_vals)),
    }


def replace_between_markers(lines, start_marker1, end_marker1, start_marker2, end_marker2, insert_marker, replacement_lines):
    """Replace lines between start_marker and end_marker with replacement_lines. Used for pattern-based scan patterns for .inp files."""
    
    new_lines = []
    inside_old_block1 = False
    inside_old_block2 = False

    found_start1 = False
    found_end1 = False
    found_start2 = False
    found_end2 = False
    found_insert = False

    for line in lines:
        stripped = line.strip()

        if stripped == start_marker1:
            inside_old_block1 = True
            found_start1 = True


            new_lines.append(line)

            new_lines.extend(replacement_lines[0])
            
            continue

        if stripped == start_marker2:
            found_start2 = True
            inside_old_block2 = True

            new_lines.extend(replacement_lines[2])
            
            continue
        
        if stripped == insert_marker:
            found_insert = True
            new_lines.append(line)
            new_lines.extend(replacement_lines[1])

            continue

        if stripped == end_marker1:
            found_end1 = True
            inside_old_block1 = False

            continue

        if stripped == end_marker2:
            found_end2 = True
            inside_old_block2 = False

            new_lines.append(line)

            continue
        
        if not inside_old_block1 and not inside_old_block2:
            new_lines.append(line)
            continue

    if not found_start1:
        raise ValueError("start_marker1 not found")

    if not found_end1:
        raise ValueError("end_marker1 not found")

    if not found_start2:
        raise ValueError("start_marker2 not found")

    if not found_end2:
        raise ValueError("end_marker2 not found")

    if not found_insert:
        raise ValueError("insert_marker not found")

    return new_lines



