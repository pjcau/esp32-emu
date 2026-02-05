#!/usr/bin/env python3
"""
Fix Z positions so buttons are properly inside the case behind top_cover.

Assembly order (from back to front):
1. back_cover (Z min, back of console)
2. PCB (sits on back_cover)
3. Buttons (on PCB, inside case)
4. Frame (internal structure)
5. top_cover (front, with holes for buttons)
6. Button caps poke through top_cover holes slightly
"""

import numpy as np
import trimesh
from trimesh.creation import box, cylinder
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).parent.parent.parent
PRINT_READY_DIR = PROJECT_ROOT / 'stl-tools' / 'output' / 'print_ready'
RENDERS_DIR = PROJECT_ROOT / 'stl-tools' / 'output' / 'renders'
PCB_POSITIONS_FILE = PROJECT_ROOT / 'pcb' / 'pcb_component_positions.json'

PCB_WIDTH = 100.0
PCB_HEIGHT = 50.0
PCB_THICKNESS = 1.6

COLORS = {
    'pcb': [34, 139, 34, 255],
    'lcd': [0, 50, 100, 255],
    'frame': [120, 120, 120, 200],
    'top_cover': [70, 130, 180, 150],
    'back_cover': [100, 149, 237, 150],
    'd_Pad': [255, 50, 50, 255],
    'A_B': [50, 205, 50, 255],
    'start_select': [255, 165, 0, 255],
    'menu': [255, 0, 255, 255],
    'L': [255, 200, 0, 255],
    'R': [255, 255, 50, 255],
    'power': [0, 255, 255, 255],
}


def load_pcb_positions():
    with open(PCB_POSITIONS_FILE) as f:
        return json.load(f)


def main():
    print("=" * 70)
    print("FIX Z POSITIONS - BUTTONS BEHIND TOP COVER")
    print("=" * 70)

    # First, analyze current positions
    print("\n1. Analyzing current Z positions...")

    parts = {}
    for stl_file in sorted(PRINT_READY_DIR.glob('*.stl')):
        name = stl_file.stem
        mesh = trimesh.load(str(stl_file))
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate([g for g in mesh.geometry.values()])

        parts[name] = {
            'mesh': mesh,
            'z_min': mesh.bounds[0][2],
            'z_max': mesh.bounds[1][2],
            'z_center': mesh.centroid[2]
        }
        print(f"  {name:15}: Z=[{parts[name]['z_min']:7.2f}, {parts[name]['z_max']:7.2f}]")

    # Get top_cover reference
    top_cover = parts.get('top_cover', {})
    top_cover_z_max = top_cover.get('z_max', 0)

    print(f"\n  Top cover surface at Z = {top_cover_z_max:.2f}")

    # Calculate Z adjustments
    # Buttons should be inside the case, with tops at or slightly below top_cover surface
    # Target: button Z_max = top_cover_z_max - 1mm (recessed) to top_cover_z_max + 1mm (slight protrusion)

    print("\n2. Calculating Z adjustments...")

    button_parts = ['d_Pad', 'A_B', 'start_select', 'menu', 'L', 'R', 'power']

    z_adjustments = {}

    for name in button_parts:
        if name not in parts:
            continue

        current_z_max = parts[name]['z_max']
        # Button top should be at top_cover surface + small protrusion (1mm)
        target_z_max = top_cover_z_max + 1.0
        adjustment = target_z_max - current_z_max
        z_adjustments[name] = adjustment

        print(f"  {name:15}: current_max={current_z_max:7.2f} -> target={target_z_max:7.2f} (adjust {adjustment:+.2f})")

    # Frame should be inside, between buttons and top_cover
    if 'frame' in parts:
        frame_z_max = parts['frame']['z_max']
        target_frame_z = top_cover_z_max - 2.0  # 2mm below surface
        z_adjustments['frame'] = target_frame_z - frame_z_max
        print(f"  {'frame':15}: current_max={frame_z_max:7.2f} -> target={target_frame_z:7.2f} (adjust {z_adjustments['frame']:+.2f})")

    # Apply adjustments and save
    print("\n3. Applying Z adjustments...")

    corrected_parts = []

    for name, data in parts.items():
        mesh = data['mesh'].copy()

        if name in z_adjustments:
            mesh.vertices[:, 2] += z_adjustments[name]
            print(f"  {name}: adjusted by {z_adjustments[name]:+.2f}mm")

        # Apply color
        color = COLORS.get(name, [128, 128, 128, 255])
        mesh.visual.face_colors = color

        # Save corrected STL
        output_path = PRINT_READY_DIR / f"{name}.stl"
        mesh.export(str(output_path))

        corrected_parts.append((name, mesh))

    # Verify final positions
    print("\n4. Final Z positions:")
    print("-" * 60)

    for name, mesh in corrected_parts:
        z_min = mesh.bounds[0][2]
        z_max = mesh.bounds[1][2]
        print(f"  {name:15}: Z=[{z_min:7.2f}, {z_max:7.2f}]")

    # Create PCB model
    print("\n5. Creating PCB model...")
    pcb_positions = load_pcb_positions()
    pcb_meshes = create_pcb_model(pcb_positions, top_cover_z_max)

    # Generate renders
    print("\n6. Generating renders...")

    all_meshes = corrected_parts + pcb_meshes

    # Assembly view
    scene = trimesh.Scene()
    for mesh_name, mesh in all_meshes:
        scene.add_geometry(mesh, node_name=mesh_name)
    scene.export(str(RENDERS_DIR / 'assembly_colored.glb'))
    print("  - assembly_colored.glb")

    # Exploded view
    exploded = create_exploded_view(corrected_parts, pcb_meshes)
    scene = trimesh.Scene()
    for mesh_name, mesh in exploded:
        scene.add_geometry(mesh, node_name=mesh_name)
    scene.export(str(RENDERS_DIR / 'assembly_exploded.glb'))
    print("  - assembly_exploded.glb")

    # Case only
    scene = trimesh.Scene()
    for mesh_name, mesh in corrected_parts:
        scene.add_geometry(mesh, node_name=mesh_name)
    scene.export(str(RENDERS_DIR / 'case_only.glb'))
    print("  - case_only.glb")

    # PCB only
    scene = trimesh.Scene()
    for mesh_name, mesh in pcb_meshes:
        scene.add_geometry(mesh, node_name=mesh_name)
    scene.export(str(RENDERS_DIR / 'pcb_detailed.glb'))
    print("  - pcb_detailed.glb")

    print("\n" + "=" * 70)
    print("DONE! Buttons are now behind top_cover")
    print("=" * 70)

    return 0


def create_pcb_model(pcb_positions, reference_z):
    """Create PCB positioned inside the case."""
    meshes = []

    # PCB at a reasonable Z inside the case
    # Place it below the buttons
    pcb_z = reference_z - 8.0  # 8mm below top surface

    pcb = box(extents=[PCB_WIDTH, PCB_HEIGHT, PCB_THICKNESS])
    pcb.apply_translation([0, 0, pcb_z])
    pcb.visual.face_colors = COLORS['pcb']
    meshes.append(('pcb_base', pcb))

    # LCD
    lcd = pcb_positions.get('LCD', {})
    if lcd:
        lcd_mesh = box(extents=[lcd.get('width', 42), lcd.get('height', 32), 3])
        lcd_mesh.apply_translation([lcd['center_x'], lcd['center_y'], pcb_z + 2])
        lcd_mesh.visual.face_colors = COLORS['lcd']
        meshes.append(('lcd', lcd_mesh))

    # Button markers on PCB
    marker_colors = {
        'DPAD': COLORS['d_Pad'],
        'AB': COLORS['A_B'],
        'START_SELECT': COLORS['start_select'],
        'MENU': COLORS['menu'],
        'L_BTN': COLORS['L'],
        'R_BTN': COLORS['R'],
        'POWER': COLORS['power'],
    }

    for pcb_name in ['DPAD', 'AB', 'START_SELECT', 'MENU', 'L_BTN', 'R_BTN', 'POWER']:
        if pcb_name not in pcb_positions:
            continue
        pos = pcb_positions[pcb_name]
        marker = cylinder(radius=3, height=1, sections=32)
        marker.apply_translation([pos['center_x'], pos['center_y'], pcb_z + PCB_THICKNESS])
        marker.visual.face_colors = marker_colors.get(pcb_name, [150, 150, 150, 255])
        meshes.append((f'marker_{pcb_name}', marker))

    return meshes


def create_exploded_view(case_parts, pcb_meshes):
    """Create exploded view with proper Z separation."""
    exploded = []

    # Z offsets for exploded view (relative spacing)
    z_offsets = {
        'back_cover': -50,
        'pcb_base': -30,
        'lcd': -28,
        'd_Pad': 0,
        'A_B': 0,
        'start_select': 0,
        'menu': 0,
        'L': 5,
        'R': 5,
        'power': 10,
        'frame': 15,
        'top_cover': 35,
    }

    # Calculate center for XY explosion
    case_centroids = [p[1].centroid for p in case_parts]
    center = np.mean(case_centroids, axis=0)

    for name, mesh in case_parts:
        new_mesh = mesh.copy()

        z_off = z_offsets.get(name, 0)

        # XY explosion
        direction = mesh.centroid - center
        direction[2] = 0
        if np.linalg.norm(direction[:2]) > 0.1:
            direction[:2] = direction[:2] / np.linalg.norm(direction[:2]) * 15

        new_mesh.apply_translation([direction[0], direction[1], z_off])
        exploded.append((name, new_mesh))

    # PCB elements
    for name, mesh in pcb_meshes:
        new_mesh = mesh.copy()
        base_name = 'pcb_base' if name.startswith('marker_') else name
        z_off = z_offsets.get(base_name, -30)
        new_mesh.apply_translation([0, 0, z_off])
        exploded.append((name, new_mesh))

    return exploded


if __name__ == '__main__':
    exit(main())
