#!/usr/bin/env python3
"""
Generate detailed ESPlay Micro PCB model with all key components marked.
For assembly verification and visual simulation.
"""

import numpy as np
import trimesh
from trimesh.creation import box, cylinder
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent.parent / 'pcb'

# PCB dimensions (from new_esplay.brd)
PCB_WIDTH = 100.0  # mm
PCB_HEIGHT = 50.0  # mm
PCB_THICKNESS = 1.6  # mm
PCB_CENTER = (50.0, 25.0)  # Eagle coordinates center

# Component positions (from Eagle, will be centered)
COMPONENTS = {
    # Display
    'LCD': {'x': 51.56, 'y': 26.04, 'w': 42.0, 'h': 32.0, 'color': [0, 100, 255]},  # Blue

    # D-Pad area (S2, S3, S4, S5)
    'DPAD': {'x': 10.85, 'y': 33.02, 'w': 15.0, 'h': 15.0, 'color': [255, 50, 50]},  # Red

    # A/B buttons area (S8, S9)
    'AB': {'x': 91.50, 'y': 32.58, 'w': 12.0, 'h': 15.0, 'color': [50, 255, 50]},  # Green

    # Start/Select (S6, S7)
    'START_SELECT': {'x': 10.85, 'y': 14.55, 'w': 15.0, 'h': 5.0, 'color': [255, 165, 0]},  # Orange

    # Menu button (S11)
    'MENU': {'x': 89.03, 'y': 14.48, 'w': 6.0, 'h': 6.0, 'color': [255, 0, 255]},  # Magenta

    # L shoulder (S10)
    'L_BTN': {'x': 11.43, 'y': 45.72, 'w': 10.0, 'h': 6.0, 'color': [255, 255, 0]},  # Yellow

    # R shoulder (S12)
    'R_BTN': {'x': 88.90, 'y': 45.72, 'w': 10.0, 'h': 6.0, 'color': [255, 255, 0]},  # Yellow

    # Power switch (S1)
    'POWER': {'x': 68.58, 'y': 35.56, 'w': 8.0, 'h': 4.0, 'color': [0, 255, 255]},  # Cyan

    # USB port (J3)
    'USB': {'x': 33.66, 'y': 2.03, 'w': 8.0, 'h': 5.0, 'color': [128, 128, 128]},  # Gray

    # SD card (J1)
    'SD': {'x': 24.13, 'y': 17.78, 'w': 14.0, 'h': 15.0, 'color': [100, 100, 100]},  # Dark gray

    # Audio jack (J5)
    'AUDIO': {'x': 85.22, 'y': 3.68, 'w': 12.0, 'h': 6.0, 'color': [150, 150, 150]},  # Light gray
}

# Mounting holes
HOLES = [
    {'name': 'H1', 'x': 3.05, 'y': 3.05},
    {'name': 'H2', 'x': 3.05, 'y': 46.86},
    {'name': 'H3', 'x': 96.90, 'y': 46.86},
    {'name': 'H4', 'x': 96.90, 'y': 3.05},
]


def create_rounded_box(width, height, depth, radius=2.0, segments=8):
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


def eagle_to_centered(x, y):
    """Convert Eagle coordinates to centered (0,0) coordinates."""
    return (x - PCB_CENTER[0], y - PCB_CENTER[1])


def main():
    print("=" * 70)
    print("DETAILED ESPLAY MICRO PCB MODEL GENERATOR")
    print("=" * 70)
    print(f"\nPCB Size: {PCB_WIDTH} x {PCB_HEIGHT} x {PCB_THICKNESS} mm")
    print(f"PCB Center (Eagle): {PCB_CENTER}")

    meshes = []

    # 1. Create PCB base (green)
    print("\n1. Creating PCB base...")
    pcb_base = create_rounded_box(PCB_WIDTH, PCB_HEIGHT, PCB_THICKNESS)
    pcb_base.visual.face_colors = [34, 139, 34, 255]  # Forest green
    pcb_base.apply_translation([0, 0, PCB_THICKNESS/2])
    meshes.append(pcb_base)

    # 2. Add component markers
    print("\n2. Adding component markers:")
    marker_height = 0.5

    for name, comp in COMPONENTS.items():
        cx, cy = eagle_to_centered(comp['x'], comp['y'])
        w, h = comp['w'], comp['h']
        color = comp['color'] + [255]  # Add alpha

        marker = box(extents=[w, h, marker_height])
        marker.apply_translation([cx, cy, PCB_THICKNESS + marker_height/2])
        marker.visual.face_colors = color

        meshes.append(marker)
        print(f"   {name:15} @ ({cx:7.2f}, {cy:7.2f}) size {w}x{h}")

    # 3. Add mounting hole markers
    print("\n3. Adding mounting hole markers:")
    for hole in HOLES:
        hx, hy = eagle_to_centered(hole['x'], hole['y'])

        # Gold ring for hole
        ring = cylinder(radius=2.5, height=0.3, sections=32)
        ring.apply_translation([hx, hy, PCB_THICKNESS + 0.15])
        ring.visual.face_colors = [255, 215, 0, 255]  # Gold

        meshes.append(ring)
        print(f"   {hole['name']} @ ({hx:7.2f}, {hy:7.2f})")

    # 4. Combine all meshes
    print("\n4. Combining meshes...")
    combined = trimesh.util.concatenate(meshes)

    print(f"\nMesh stats:")
    print(f"   Vertices: {len(combined.vertices)}")
    print(f"   Faces: {len(combined.faces)}")
    print(f"   Bounds: X [{combined.bounds[0][0]:.1f}, {combined.bounds[1][0]:.1f}]")
    print(f"           Y [{combined.bounds[0][1]:.1f}, {combined.bounds[1][1]:.1f}]")
    print(f"           Z [{combined.bounds[0][2]:.1f}, {combined.bounds[1][2]:.1f}]")

    # 5. Export
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_path = OUTPUT_DIR / 'esplay_micro_pcb_detailed.stl'
    combined.export(str(output_path))
    print(f"\nExported: {output_path}")

    # Also export component positions as JSON for verification
    import json
    positions = {}
    for name, comp in COMPONENTS.items():
        cx, cy = eagle_to_centered(comp['x'], comp['y'])
        positions[name] = {
            'center_x': cx,
            'center_y': cy,
            'width': comp['w'],
            'height': comp['h']
        }

    json_path = OUTPUT_DIR / 'pcb_component_positions.json'
    with open(json_path, 'w') as f:
        json.dump(positions, f, indent=2)
    print(f"Exported: {json_path}")

    print("\n" + "=" * 70)
    print("COMPONENT LEGEND:")
    print("=" * 70)
    print("  LCD (Blue)      - Display area")
    print("  DPAD (Red)      - D-Pad buttons")
    print("  AB (Green)      - A/B buttons")
    print("  START_SELECT    - Start/Select buttons (Orange)")
    print("  MENU (Magenta)  - Menu button")
    print("  L_BTN/R_BTN     - Shoulder buttons (Yellow)")
    print("  POWER (Cyan)    - Power switch")
    print("  USB/SD/AUDIO    - Connectors (Gray)")
    print("  Holes (Gold)    - Mounting holes")

    return 0


if __name__ == '__main__':
    exit(main())
