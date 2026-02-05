#!/usr/bin/env python3
"""Generate simple ESPlay Micro PCB model (no scipy needed)."""

import numpy as np
import trimesh
from trimesh.creation import box, cylinder
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent.parent / 'pcb'

# ESPlay Micro PCB specs
WIDTH = 100.0  # mm
HEIGHT = 50.0  # mm
THICKNESS = 1.6  # mm
CORNER_RADIUS = 2.0  # mm

# Mounting holes (centered coordinates)
HOLES = [
    {'name': 'H1', 'x': -46.95, 'y': -21.95},
    {'name': 'H2', 'x': -46.95, 'y': 21.86},
    {'name': 'H3', 'x': 46.90, 'y': 21.86},
    {'name': 'H4', 'x': 46.90, 'y': -21.95},
]


def create_rounded_box(width, height, depth, radius, segments=8):
    """Create a box with rounded corners."""
    mesh_h = box(extents=[width - 2*radius, height, depth])
    mesh_v = box(extents=[width, height - 2*radius, depth])
    mesh = trimesh.util.concatenate([mesh_h, mesh_v])

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
    print("Generating ESPlay Micro PCB model...")
    print(f"Size: {WIDTH} x {HEIGHT} x {THICKNESS} mm")

    # Create PCB
    pcb = create_rounded_box(WIDTH, HEIGHT, THICKNESS, CORNER_RADIUS)

    # Move Z=0 to bottom of PCB
    pcb.apply_translation([0, 0, THICKNESS/2])

    print(f"Bounds: {pcb.bounds}")

    # Export clean PCB
    output_path = OUTPUT_DIR / 'esplay_micro_pcb.stl'
    pcb.export(str(output_path))
    print(f"Exported: {output_path}")

    # Create version with hole markers
    meshes = [pcb]
    for hole in HOLES:
        marker = cylinder(radius=2.0, height=0.3, sections=32)
        marker.apply_translation([hole['x'], hole['y'], THICKNESS + 0.15])
        meshes.append(marker)

    combined = trimesh.util.concatenate(meshes)

    output_markers = OUTPUT_DIR / 'esplay_micro_pcb_with_holes.stl'
    combined.export(str(output_markers))
    print(f"Exported: {output_markers}")

    print("\nDone!")


if __name__ == '__main__':
    main()
