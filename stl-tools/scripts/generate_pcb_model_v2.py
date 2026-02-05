#!/usr/bin/env python3
"""
Generate 3D STL model of the PCB - V2 with visual holes.
Creates PCB board with mounting hole markers.
"""

import numpy as np
import trimesh
from trimesh.creation import box, cylinder, annulus
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
PCB_FILE = PROJECT_ROOT / 'pcb' / 'esplay_2.0.brd'
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
                        'curve': wire.get('curve')
                    })

        elements = board.find('elements')
        if elements is not None:
            for element in elements.findall('element'):
                name = element.get('name', '')
                if name.startswith('H') and name[1:].isdigit():
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
            'min_x': min_x,
            'max_x': max_x,
            'min_y': min_y,
            'max_y': max_y,
            'center_x': (min_x + max_x) / 2,
            'center_y': (min_y + max_y) / 2,
            'corner_radius': 4.336,
            'holes': holes,
            'wires': dimension_wires
        }

    return None


def create_rounded_box(width, height, depth, radius, segments=8):
    """Create a box with rounded corners in XY plane."""
    # Create the main rectangular mesh with chamfered corners
    # Using trimesh primitives

    # Start with a basic box
    mesh = box(extents=[width - 2*radius, height, depth])

    # Add corner pieces
    corner_box = box(extents=[width, height - 2*radius, depth])

    # Combine center cross
    mesh = trimesh.util.concatenate([mesh, corner_box])

    # Add rounded corner cylinders
    for sx in [-1, 1]:
        for sy in [-1, 1]:
            corner_cyl = cylinder(
                radius=radius,
                height=depth,
                sections=segments
            )
            corner_cyl.apply_translation([
                sx * (width/2 - radius),
                sy * (height/2 - radius),
                0
            ])
            mesh = trimesh.util.concatenate([mesh, corner_cyl])

    # Merge vertices and clean up
    mesh.merge_vertices()

    return mesh


def create_pcb_with_holes_visual(pcb_info, thickness=1.6, hole_diameter=3.2):
    """Create PCB with holes shown as rings on top surface."""
    width = pcb_info['width']
    height = pcb_info['height']
    corner_radius = pcb_info['corner_radius']

    print(f"Creating PCB: {width:.2f} x {height:.2f} x {thickness} mm")

    # Create main board
    pcb_mesh = create_rounded_box(width, height, thickness, corner_radius)

    # Color the PCB green
    pcb_mesh.visual.face_colors = [34, 139, 34, 255]  # Forest green

    # Create hole rings for visualization
    hole_meshes = []
    for hole in pcb_info['holes']:
        hx = hole['x'] - pcb_info['center_x']
        hy = hole['y'] - pcb_info['center_y']

        # Create a small cylinder to represent hole location
        hole_marker = cylinder(
            radius=hole_diameter / 2 + 0.5,
            height=0.2,
            sections=32
        )
        hole_marker.apply_translation([hx, hy, thickness/2 + 0.1])
        hole_marker.visual.face_colors = [255, 215, 0, 255]  # Gold color for holes

        hole_meshes.append(hole_marker)
        print(f"  Hole marker at ({hx:.2f}, {hy:.2f})")

    # Combine all meshes
    all_meshes = [pcb_mesh] + hole_meshes
    combined = trimesh.util.concatenate(all_meshes)

    return combined, pcb_mesh


def main():
    print("=" * 60)
    print("PCB 3D MODEL GENERATOR V2")
    print("=" * 60)

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

    for hole in pcb_info['holes']:
        print(f"    {hole['name']}: ({hole['x']:.2f}, {hole['y']:.2f})")

    # Create 3D model
    print(f"\nGenerating 3D model...")
    pcb_thickness = 1.6

    combined_mesh, pcb_only = create_pcb_with_holes_visual(
        pcb_info, pcb_thickness, hole_diameter=3.2
    )

    # Center Z at 0 (bottom of PCB at Z=0)
    z_offset = pcb_thickness / 2
    combined_mesh.apply_translation([0, 0, z_offset])
    pcb_only.apply_translation([0, 0, z_offset])

    print(f"\nMesh info:")
    print(f"  Vertices: {len(combined_mesh.vertices)}")
    print(f"  Faces: {len(combined_mesh.faces)}")
    print(f"  Bounds: {combined_mesh.bounds}")

    # Export
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Combined with hole markers
    output_combined = OUTPUT_DIR / 'esplay_2.0_pcb_with_markers.stl'
    combined_mesh.export(str(output_combined))
    print(f"\nExported (with markers): {output_combined}")

    # PCB only (cleaner)
    output_pcb = OUTPUT_DIR / 'esplay_2.0_pcb.stl'
    pcb_only.export(str(output_pcb))
    print(f"Exported (PCB only): {output_pcb}")

    # Also export a GLTF/GLB for better visualization with colors
    try:
        output_glb = OUTPUT_DIR / 'esplay_2.0_pcb.glb'
        combined_mesh.export(str(output_glb))
        print(f"Exported (GLB with colors): {output_glb}")
    except Exception as e:
        print(f"GLB export failed: {e}")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"PCB: {pcb_info['width']:.2f} x {pcb_info['height']:.2f} x {pcb_thickness} mm")
    print(f"4 mounting holes at corners (M3 screws)")
    print(f"\nNote: This PCB (esplay_2.0) is DIFFERENT from ESPlay Micro!")
    print(f"  - esplay_2.0:    {pcb_info['width']:.1f} x {pcb_info['height']:.1f} mm")
    print(f"  - ESPlay Micro:  100 x 50 mm (from README)")
    print(f"\nThe case STLs are designed for ESPlay Micro, not esplay_2.0")

    return 0


if __name__ == '__main__':
    exit(main())
