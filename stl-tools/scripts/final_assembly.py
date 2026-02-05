#!/usr/bin/env python3
"""
Final assembly: buttons at ORIGINAL positions (matching case holes),
L/R at back_cover side holes, frame in front of top_cover.
PCB positioned inside for reference.
"""

import numpy as np
import trimesh
from trimesh.creation import box, cylinder
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).parent.parent.parent
FIXED_V2_DIR = PROJECT_ROOT / 'stl-tools' / 'output' / 'fixed_v2'
OUTPUT_DIR = PROJECT_ROOT / 'stl-tools' / 'output' / 'print_ready'
RENDERS_DIR = PROJECT_ROOT / 'stl-tools' / 'output' / 'renders'
PCB_POSITIONS_FILE = PROJECT_ROOT / 'pcb' / 'pcb_component_positions.json'

PCB_WIDTH = 100.0
PCB_HEIGHT = 50.0
PCB_THICKNESS = 1.6

COLORS = {
    'pcb': [34, 139, 34, 255],
    'lcd': [0, 50, 100, 255],
    'frame': [120, 120, 120, 220],
    'top_cover': [70, 130, 180, 160],
    'back_cover': [100, 149, 237, 160],
    'd_Pad': [255, 50, 50, 255],
    'A_B': [50, 205, 50, 255],
    'start_select': [255, 165, 0, 255],
    'menu': [255, 0, 255, 255],
    'L_R': [255, 255, 0, 255],
    'L': [255, 200, 0, 255],
    'R': [255, 255, 50, 255],
    'power': [0, 255, 255, 255],
}

# Top cover hole positions (from ray-casting analysis)
HOLES = {
    'd_Pad': {'center': (-38, 6), 'size': (20, 18)},
    'select': {'center': (-45, -12), 'size': (7, 7)},
    'start': {'center': (-32, -12), 'size': (7, 7)},
    'lcd': {'center': (0, 2), 'size': (49, 37)},
    'B': {'center': (40, 2), 'size': (6, 6)},
    'A': {'center': (42, 14), 'size': (7, 7)},
    'menu': {'center': (40, -10), 'size': (7, 7)},
}

# Back cover L/R side holes
LR_HOLES = {
    'L': {'center_x': -36, 'center_z': -20},
    'R': {'center_x': 38, 'center_z': -22},
}


def load_mesh(filepath):
    mesh = trimesh.load(str(filepath))
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate([g for g in mesh.geometry.values()])
    return mesh


def load_pcb_positions():
    with open(PCB_POSITIONS_FILE) as f:
        return json.load(f)


def main():
    print("=" * 70)
    print("FINAL ASSEMBLY - BUTTONS IN HOLES, L/R ON BACK_COVER")
    print("=" * 70)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RENDERS_DIR.mkdir(parents=True, exist_ok=True)
    pcb_positions = load_pcb_positions()

    # Reference positions from covers
    top_cover = load_mesh(FIXED_V2_DIR / 'top_cover.stl')
    back_cover = load_mesh(FIXED_V2_DIR / 'back_cover.stl')

    TOP_Z_MAX = top_cover.bounds[1][2]   # 0.33
    TOP_Z_MIN = top_cover.bounds[0][2]   # -9.71
    BACK_Z_MAX = back_cover.bounds[1][2] # -19.0
    BACK_Z_MIN = back_cover.bounds[0][2] # -30.0

    print(f"\nReference Z positions:")
    print(f"  top_cover: [{TOP_Z_MIN:.1f}, {TOP_Z_MAX:.1f}]")
    print(f"  back_cover: [{BACK_Z_MIN:.1f}, {BACK_Z_MAX:.1f}]")

    corrected_parts = []

    # === COVERS (keep original) ===
    top_cover.visual.face_colors = COLORS['top_cover']
    corrected_parts.append(('top_cover', top_cover))

    back_cover.visual.face_colors = COLORS['back_cover']
    corrected_parts.append(('back_cover', back_cover))

    # === FRAME (in front of top_cover) ===
    frame = load_mesh(FIXED_V2_DIR / 'frame.stl')
    # Frame bottom sits on top_cover surface
    frame_z_adj = TOP_Z_MAX + 0.2 - frame.bounds[0][2]
    frame.vertices[:, 2] += frame_z_adj
    frame.visual.face_colors = COLORS['frame']
    corrected_parts.append(('frame', frame))
    print(f"\nframe: Z=[{frame.bounds[0][2]:.1f}, {frame.bounds[1][2]:.1f}] (in front of top_cover)")

    # === MAIN BUTTONS ===
    # Keep ORIGINAL XY positions (they match the holes in top_cover)
    # Only adjust Z so buttons are inside case with caps flush with top_cover

    print("\nMain buttons (original XY, Z adjusted to fit holes):")

    for btn_name in ['d_Pad', 'A_B', 'start_select', 'menu', 'power']:
        mesh = load_mesh(FIXED_V2_DIR / f'{btn_name}.stl')

        # Keep original XY position
        orig_center = mesh.centroid.copy()

        # Z adjustment: button top should be flush with top_cover surface
        # Button caps protrude ~0.5mm above surface
        target_z_top = TOP_Z_MAX + 0.5
        z_adj = target_z_top - mesh.bounds[1][2]
        mesh.vertices[:, 2] += z_adj

        mesh.visual.face_colors = COLORS[btn_name]
        corrected_parts.append((btn_name, mesh))

        print(f"  {btn_name:15}: XY=({orig_center[0]:6.1f}, {orig_center[1]:6.1f}) "
              f"Z=[{mesh.bounds[0][2]:.1f}, {mesh.bounds[1][2]:.1f}]")

    # === L/R SHOULDER BUTTONS ===
    # L/R go through holes on the sides/top edge of back_cover
    # They should be at the top edge (Y max) and side openings

    print("\nL/R shoulder buttons (at back_cover side holes):")

    lr_original = load_mesh(FIXED_V2_DIR / 'L_R.stl')

    # R button - keep original X but position Y at top edge, Z at back_cover hole
    r_mesh = lr_original.copy()
    # Move to back_cover top edge: Y near back_cover Y max (27.9)
    r_y_target = back_cover.bounds[1][1] - r_mesh.extents[1] / 2  # Near top edge
    r_mesh.vertices[:, 1] += r_y_target - r_mesh.centroid[1]
    # Z: at back_cover level, slightly above back_cover top
    r_z_target = BACK_Z_MAX + r_mesh.extents[2] / 2 - 1.0  # Straddle the edge
    r_mesh.vertices[:, 2] += r_z_target - r_mesh.centroid[2]
    r_mesh.visual.face_colors = COLORS['R']
    corrected_parts.append(('R', r_mesh))
    print(f"  R: center=({r_mesh.centroid[0]:.1f}, {r_mesh.centroid[1]:.1f}, {r_mesh.centroid[2]:.1f})")

    # L button - mirror of R
    l_mesh = lr_original.copy()
    # Mirror X
    l_mesh.vertices[:, 0] = -l_mesh.vertices[:, 0]
    l_mesh.faces = l_mesh.faces[:, ::-1]
    # Position Y and Z same as R
    l_mesh.vertices[:, 1] += r_y_target - l_mesh.centroid[1]
    l_mesh.vertices[:, 2] += r_z_target - l_mesh.centroid[2]
    l_mesh.visual.face_colors = COLORS['L']
    corrected_parts.append(('L', l_mesh))
    print(f"  L: center=({l_mesh.centroid[0]:.1f}, {l_mesh.centroid[1]:.1f}, {l_mesh.centroid[2]:.1f})")

    # === SAVE STL FILES ===
    print("\nSaving STL files...")
    for name, mesh in corrected_parts:
        out = OUTPUT_DIR / f"{name}.stl"
        mesh.export(str(out))

    # === PCB MODEL ===
    print("\nCreating PCB model...")
    # PCB inside the case, between back_cover and buttons
    pcb_z = (BACK_Z_MAX + TOP_Z_MIN) / 2  # Middle of internal space
    pcb_meshes = create_pcb_model(pcb_positions, pcb_z)

    # === RENDERS ===
    print("\nGenerating renders...")

    all_parts = corrected_parts + pcb_meshes

    export_scene(all_parts, RENDERS_DIR / 'assembly_colored.glb')
    print("  assembly_colored.glb")

    exploded = create_exploded_view(corrected_parts, pcb_meshes)
    export_scene(exploded, RENDERS_DIR / 'assembly_exploded.glb')
    print("  assembly_exploded.glb")

    export_scene(corrected_parts, RENDERS_DIR / 'case_only.glb')
    print("  case_only.glb")

    export_scene(pcb_meshes, RENDERS_DIR / 'pcb_detailed.glb')
    print("  pcb_detailed.glb")

    # === FINAL SUMMARY ===
    print("\n" + "=" * 70)
    print("FINAL ASSEMBLY SUMMARY")
    print("=" * 70)

    print(f"\n{'Part':15} {'X':>7} {'Y':>7} {'Z range':>16} {'Layer'}")
    print("-" * 60)
    for name, mesh in corrected_parts:
        c = mesh.centroid
        z_range = f"[{mesh.bounds[0][2]:.1f}, {mesh.bounds[1][2]:.1f}]"

        if name == 'back_cover':
            layer = "BACK"
        elif name in ['L', 'R']:
            layer = "SHOULDER"
        elif name == 'top_cover':
            layer = "FRONT"
        elif name == 'frame':
            layer = "BEZEL"
        else:
            layer = "BUTTON"

        print(f"  {name:15} {c[0]:7.1f} {c[1]:7.1f} {z_range:>16} {layer}")

    print(f"\n  Assembly order (back to front):")
    print(f"    1. back_cover  Z=[{BACK_Z_MIN:.1f}, {BACK_Z_MAX:.1f}]")
    print(f"    2. L/R shoulders Z=[{l_mesh.bounds[0][2]:.1f}, {l_mesh.bounds[1][2]:.1f}]")
    print(f"    3. PCB         Z~{pcb_z:.1f}")
    print(f"    4. Buttons     Z~[{TOP_Z_MAX-5:.1f}, {TOP_Z_MAX+0.5:.1f}]")
    print(f"    5. top_cover   Z=[{TOP_Z_MIN:.1f}, {TOP_Z_MAX:.1f}]")
    print(f"    6. frame       Z=[{frame.bounds[0][2]:.1f}, {frame.bounds[1][2]:.1f}]")

    print("\n" + "=" * 70)
    print("DONE!")
    print("=" * 70)

    return 0


def create_pcb_model(pcb_positions, pcb_z):
    meshes = []

    pcb = box(extents=[PCB_WIDTH, PCB_HEIGHT, PCB_THICKNESS])
    pcb.apply_translation([0, 0, pcb_z])
    pcb.visual.face_colors = COLORS['pcb']
    meshes.append(('pcb_base', pcb))

    lcd = pcb_positions.get('LCD', {})
    if lcd:
        lcd_mesh = box(extents=[lcd.get('width', 42), lcd.get('height', 32), 2])
        lcd_mesh.apply_translation([lcd['center_x'], lcd['center_y'], pcb_z + 1.5])
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
    exploded = []

    z_offsets = {
        'back_cover': -45,
        'L': -25,
        'R': -25,
        'pcb_base': -15,
        'lcd': -13,
        'd_Pad': 10,
        'A_B': 10,
        'start_select': 10,
        'menu': 10,
        'power': 15,
        'top_cover': 30,
        'frame': 45,
    }

    case_centroids = [p[1].centroid for p in case_parts]
    center = np.mean(case_centroids, axis=0)

    for name, mesh in case_parts:
        new_mesh = mesh.copy()
        z_off = z_offsets.get(name, 0)

        direction = mesh.centroid - center
        direction[2] = 0
        norm = np.linalg.norm(direction[:2])
        if norm > 0.1:
            direction[:2] = direction[:2] / norm * 12

        new_mesh.apply_translation([direction[0], direction[1], z_off])
        exploded.append((name, new_mesh))

    for name, mesh in pcb_meshes:
        new_mesh = mesh.copy()
        z_off = z_offsets.get(name, -15)
        new_mesh.apply_translation([0, 0, z_off])
        exploded.append((name, new_mesh))

    return exploded


def export_scene(meshes, output_path):
    scene = trimesh.Scene()
    for name, mesh in meshes:
        scene.add_geometry(mesh, node_name=name)
    scene.export(str(output_path))


if __name__ == '__main__':
    exit(main())
