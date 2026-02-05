#!/usr/bin/env python3
"""
Generate 3D STL model of the PCB from Eagle .brd file.
Creates a simplified representation with board outline and mounting holes.
"""

import numpy as np
import trimesh
from trimesh.creation import box, cylinder
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
PCB_FILE = PROJECT_ROOT / 'pcb' / 'esplay_2.0.brd'
OUTPUT_DIR = PROJECT_ROOT / 'pcb'


def parse_eagle_brd(filepath: Path):
    """Parse Eagle .brd file and extract PCB outline."""
    tree = ET.parse(filepath)
    root = tree.getroot()

    dimension_wires = []
    holes = []

    board = root.find('.//board')
    if board is not None:
        plain = board.find('plain')
        if plain is not None:
            for wire in plain.findall('wire'):
                if wire.get('layer') == '20':
                    dimension_wires.append({
                        'x1': float(wire.get('x1')),
                        'y1': float(wire.get('y1')),
                        'x2': float(wire.get('x2')),
                        'y2': float(wire.get('y2')),
                        'curve': wire.get('curve')
                    })

        # Find mounting holes
        elements = board.find('elements')
        if elements is not None:
            for element in elements.findall('element'):
                name = element.get('name', '')
                if 'H' in name.upper() or 'MOUNT' in name.upper():
                    holes.append({
                        'name': name,
                        'x': float(element.get('x', 0)),
                        'y': float(element.get('y', 0))
                    })

    # Calculate bounding box
    all_x = []
    all_y = []
    for w in dimension_wires:
        all_x.extend([w['x1'], w['x2']])
        all_y.extend([w['y1'], w['y2']])

    if all_x and all_y:
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)

        return {
            'width': max_x - min_x,
            'height': max_y - min_y,
            'min_x': min_x,
            'max_x': max_x,
            'min_y': min_y,
            'max_y': max_y,
            'center_x': (min_x + max_x) / 2,
            'center_y': (min_y + max_y) / 2,
            'corner_radius': 4.336,
            'holes': holes
        }

    return None


def create_rounded_rect_2d(width, height, corner_radius, segments=16):
    """Create a 2D rounded rectangle as a polygon."""
    # Half dimensions
    hw = width / 2 - corner_radius
    hh = height / 2 - corner_radius

    points = []

    # Generate points for each corner (counter-clockwise from bottom-right)
    corners = [
        (hw, -hh, -90, 0),      # Bottom-right
        (hw, hh, 0, 90),        # Top-right
        (-hw, hh, 90, 180),     # Top-left
        (-hw, -hh, 180, 270),   # Bottom-left
    ]

    for cx, cy, start_angle, end_angle in corners:
        for i in range(segments + 1):
            angle = np.radians(start_angle + (end_angle - start_angle) * i / segments)
            x = cx + corner_radius * np.cos(angle)
            y = cy + corner_radius * np.sin(angle)
            points.append([x, y])

    return np.array(points)


def create_pcb_mesh(pcb_info, thickness=1.6, hole_diameter=3.2):
    """Create 3D mesh of PCB with holes."""
    width = pcb_info['width']
    height = pcb_info['height']
    corner_radius = pcb_info['corner_radius']

    print(f"Creating PCB mesh: {width:.2f} x {height:.2f} x {thickness} mm")
    print(f"Corner radius: {corner_radius:.2f} mm")

    # Create base board as a simple box (trimesh doesn't have easy rounded rect extrusion)
    # We'll use the full dimensions
    pcb_board = box(extents=[width, height, thickness])

    # Center at origin
    # pcb_board is already centered at origin by trimesh

    # Create mounting holes
    meshes_to_subtract = []
    for hole in pcb_info['holes']:
        # Hole position relative to PCB center
        hx = hole['x'] - pcb_info['center_x']
        hy = hole['y'] - pcb_info['center_y']

        hole_cyl = cylinder(
            radius=hole_diameter / 2,
            height=thickness + 2,  # Extend through PCB
            sections=32
        )
        # Move to correct position
        hole_cyl.apply_translation([hx, hy, 0])
        meshes_to_subtract.append(hole_cyl)
        print(f"  Hole at ({hx:.2f}, {hy:.2f})")

    # Subtract holes from PCB
    if meshes_to_subtract:
        for hole_mesh in meshes_to_subtract:
            try:
                pcb_board = pcb_board.difference(hole_mesh)
            except Exception as e:
                print(f"  Warning: Could not subtract hole: {e}")

    # Round the corners by creating corner cylinders and boolean operations
    # This is complex in trimesh, so we'll create a simplified version
    # with chamfered corners instead

    return pcb_board


def create_detailed_pcb(pcb_info, thickness=1.6, hole_diameter=3.2):
    """Create a more detailed PCB model with rounded corners using path extrusion."""
    width = pcb_info['width']
    height = pcb_info['height']
    corner_radius = pcb_info['corner_radius']

    # Create 2D outline polygon
    outline = create_rounded_rect_2d(width, height, corner_radius, segments=8)

    # Create a polygon path
    from trimesh.path.polygons import paths_to_polygons
    from trimesh.creation import extrude_polygon

    try:
        # Create shapely polygon if available
        from shapely.geometry import Polygon as ShapelyPolygon

        poly = ShapelyPolygon(outline)

        # Extrude the polygon
        pcb_mesh = extrude_polygon(poly, height=thickness)

        # Center vertically
        pcb_mesh.apply_translation([0, 0, -thickness/2])

    except ImportError:
        print("Shapely not available, using simple box")
        pcb_mesh = box(extents=[width, height, thickness])

    # Add mounting holes
    for hole in pcb_info['holes']:
        hx = hole['x'] - pcb_info['center_x']
        hy = hole['y'] - pcb_info['center_y']

        hole_cyl = cylinder(
            radius=hole_diameter / 2,
            height=thickness + 2,
            sections=32
        )
        hole_cyl.apply_translation([hx, hy, 0])

        try:
            pcb_mesh = pcb_mesh.difference(hole_cyl)
        except:
            pass

    return pcb_mesh


def main():
    print("=" * 60)
    print("PCB 3D MODEL GENERATOR")
    print("=" * 60)

    # Parse PCB file
    print(f"\nParsing: {PCB_FILE}")
    pcb_info = parse_eagle_brd(PCB_FILE)

    if not pcb_info:
        print("Error: Could not parse PCB file!")
        return 1

    print(f"\nPCB Dimensions:")
    print(f"  Width:  {pcb_info['width']:.2f} mm")
    print(f"  Height: {pcb_info['height']:.2f} mm")
    print(f"  Corner radius: {pcb_info['corner_radius']:.2f} mm")
    print(f"  Mounting holes: {len(pcb_info['holes'])}")

    # Create 3D model
    print(f"\nGenerating 3D model...")
    pcb_thickness = 1.6  # Standard PCB thickness
    hole_diameter = 3.2  # M3 screw hole

    # Try detailed version first
    try:
        pcb_mesh = create_detailed_pcb(pcb_info, pcb_thickness, hole_diameter)
    except Exception as e:
        print(f"Detailed model failed ({e}), using simple version")
        pcb_mesh = create_pcb_mesh(pcb_info, pcb_thickness, hole_diameter)

    # Verify mesh
    print(f"\nMesh info:")
    print(f"  Vertices: {len(pcb_mesh.vertices)}")
    print(f"  Faces: {len(pcb_mesh.faces)}")
    print(f"  Bounds: {pcb_mesh.bounds[0]} to {pcb_mesh.bounds[1]}")
    print(f"  Watertight: {pcb_mesh.is_watertight}")

    # Export STL
    output_path = OUTPUT_DIR / 'esplay_2.0_pcb.stl'
    pcb_mesh.export(str(output_path))
    print(f"\nExported to: {output_path}")

    # Also create a version centered at origin with Z=0 at bottom
    pcb_mesh_bottom = pcb_mesh.copy()
    # Move so Z=0 is at bottom of PCB
    z_offset = -pcb_mesh.bounds[0][2]
    pcb_mesh_bottom.apply_translation([0, 0, z_offset])

    output_path_bottom = OUTPUT_DIR / 'esplay_2.0_pcb_z0.stl'
    pcb_mesh_bottom.export(str(output_path_bottom))
    print(f"Exported (Z=0 at bottom): {output_path_bottom}")

    print("\nDone!")
    return 0


if __name__ == '__main__':
    exit(main())
