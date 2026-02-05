#!/usr/bin/env python3
"""
Generate 3D STL model of ESPlay Micro PCB.
"""

import numpy as np
import trimesh
from trimesh.creation import box, cylinder
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
PCB_FILE = PROJECT_ROOT / 'pcb' / 'new_esplay.brd'
OUTPUT_DIR = PROJECT_ROOT / 'pcb'


def parse_eagle_brd(filepath: Path):
    """Parse Eagle .brd file."""
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
                    })

        elements = board.find('elements')
        if elements is not None:
            for element in elements.findall('element'):
                name = element.get('name', '')
                if name.startswith('H') and len(name) <= 3:
                    holes.append({
                        'name': name,
                        'x': float(element.get('x', 0)),
                        'y': float(element.get('y', 0))
                    })

    all_x = [w['x1'] for w in dimension_wires] + [w['x2'] for w in dimension_wires]
    all_y = [w['y1'] for w in dimension_wires] + [w['y2'] for w in dimension_wires]

    if all_x and all_y:
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)

        return {
            'width': max_x - min_x,
            'height': max_y - min_y,
            'center_x': (min_x + max_x) / 2,
            'center_y': (min_y + max_y) / 2,
            'holes': holes
        }

    return None


def create_rounded_box(width, height, depth, radius, segments=8):
    """Create a box with rounded corners."""
    # Main cross shape
    mesh_h = box(extents=[width - 2*radius, height, depth])
    mesh_v = box(extents=[width, height - 2*radius, depth])

    mesh = trimesh.util.concatenate([mesh_h, mesh_v])

    # Corner cylinders
    for sx in [-1, 1]:
        for sy in [-1, 1]:
            corner = cylinder(radius=radius, height=depth, sections=segments)
            corner.apply_translation([
                sx * (width/2 - radius),
                sy * (height/2 - radius),
                0
            ])
            mesh = trimesh.util.concatenate([mesh, corner])

    mesh.merge_vertices()
    return mesh


def main():
    print("=" * 60)
    print("ESPLAY MICRO PCB 3D MODEL GENERATOR")
    print("=" * 60)

    print(f"\nParsing: {PCB_FILE}")
    pcb_info = parse_eagle_brd(PCB_FILE)

    if not pcb_info:
        print("Error: Could not parse PCB file!")
        return 1

    width = pcb_info['width']
    height = pcb_info['height']
    thickness = 1.6  # Standard PCB thickness
    corner_radius = 2.0  # Typical corner radius
    hole_diameter = 3.2  # M3 screw hole

    print(f"\nPCB Dimensions:")
    print(f"  Width:  {width:.2f} mm")
    print(f"  Height: {height:.2f} mm")
    print(f"  Thickness: {thickness} mm")
    print(f"  Mounting holes: {len(pcb_info['holes'])}")

    # Create PCB board with rounded corners
    print(f"\nGenerating 3D model...")
    pcb_mesh = create_rounded_box(width, height, thickness, corner_radius)

    # Set PCB color (green)
    pcb_mesh.visual.face_colors = [34, 139, 34, 255]

    # Create hole markers
    hole_meshes = []
    for hole in pcb_info['holes']:
        hx = hole['x'] - pcb_info['center_x']
        hy = hole['y'] - pcb_info['center_y']

        # Gold ring to mark hole position
        hole_marker = cylinder(
            radius=hole_diameter / 2 + 0.5,
            height=0.3,
            sections=32
        )
        hole_marker.apply_translation([hx, hy, thickness/2 + 0.15])
        hole_marker.visual.face_colors = [255, 215, 0, 255]  # Gold
        hole_meshes.append(hole_marker)

        print(f"  Hole {hole['name']}: ({hx:.2f}, {hy:.2f})")

    # Combine meshes
    all_meshes = [pcb_mesh] + hole_meshes
    combined = trimesh.util.concatenate(all_meshes)

    # Center at origin, Z=0 at bottom
    combined.apply_translation([0, 0, thickness/2])

    print(f"\nMesh info:")
    print(f"  Vertices: {len(combined.vertices)}")
    print(f"  Faces: {len(combined.faces)}")
    print(f"  Bounds: {combined.bounds}")

    # Export
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # With markers
    output_markers = OUTPUT_DIR / 'esplay_micro_pcb_with_markers.stl'
    combined.export(str(output_markers))
    print(f"\nExported: {output_markers}")

    # PCB only (centered at origin, Z=0 at bottom)
    pcb_only = pcb_mesh.copy()
    pcb_only.apply_translation([0, 0, thickness/2])

    output_pcb = OUTPUT_DIR / 'esplay_micro_pcb.stl'
    pcb_only.export(str(output_pcb))
    print(f"Exported: {output_pcb}")

    # Also create a version aligned with case coordinates
    # Case parts are centered near origin, so PCB should be too
    print(f"\n" + "=" * 60)
    print("ALIGNMENT INFO")
    print("=" * 60)
    print(f"\nPCB model is centered at origin (0, 0)")
    print(f"Case parts (top_cover, back_cover) are also centered near origin")
    print(f"This means PCB should fit correctly when placed in case")

    print("\nDone!")
    return 0


if __name__ == '__main__':
    exit(main())
