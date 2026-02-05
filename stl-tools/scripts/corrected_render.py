#!/usr/bin/env python3
"""
Corrected render with proper PCB overlay based on actual PCB image.
The PCB image shows:
- L/R: top corners (Y max in PCB coords)
- D-Pad: left side, upper area
- Select/Start: left side, below D-Pad
- A/B: right side, upper area (horizontal)
- Menu: right side, below A/B

STL coordinate system has Y inverted relative to PCB.
"""

import numpy as np
import trimesh
from trimesh.creation import box, cylinder
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).parent.parent.parent
FIXED_V2_DIR = PROJECT_ROOT / 'stl-tools' / 'output' / 'fixed_v2'
OUTPUT_DIR = PROJECT_ROOT / 'stl-tools' / 'output' / 'renders'
PCB_POSITIONS_FILE = PROJECT_ROOT / 'pcb' / 'pcb_component_positions.json'

# PCB specs
PCB_WIDTH = 100.0
PCB_HEIGHT = 50.0
PCB_THICKNESS = 1.6

# Colors
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
    'L_R': [255, 255, 0, 255],
    'power': [0, 255, 255, 255],
}

# PCB marker colors (slightly different shades to distinguish from STL parts)
PCB_MARKER_COLORS = {
    'DPAD': [200, 0, 0, 255],
    'AB': [0, 150, 0, 255],
    'START_SELECT': [200, 130, 0, 255],
    'MENU': [200, 0, 200, 255],
    'L_BTN': [200, 200, 0, 255],
    'R_BTN': [200, 200, 0, 255],
    'POWER': [0, 200, 200, 255],
}


def load_pcb_positions():
    """Load PCB positions."""
    with open(PCB_POSITIONS_FILE) as f:
        return json.load(f)


def transform_pcb_to_stl(x, y):
    """Transform PCB coordinates to STL coordinate system.

    PCB: Y+ = top (towards L/R buttons)
    STL: Y+ = bottom (towards Start/Select in STL)

    So we invert Y.
    """
    return x, -y


def load_stl_parts():
    """Load STL parts."""
    parts = []
    for stl_file in sorted(FIXED_V2_DIR.glob('*.stl')):
        name = stl_file.stem
        mesh = trimesh.load(str(stl_file))
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate([g for g in mesh.geometry.values()])

        color = COLORS.get(name, [128, 128, 128, 255])
        mesh.visual.face_colors = color
        parts.append((name, mesh))
    return parts


def create_pcb_with_markers(pcb_positions):
    """Create PCB base with button position markers in STL coordinate system."""
    meshes = []

    # PCB base - positioned to match STL case
    # STL case center is roughly at origin
    pcb = box(extents=[PCB_WIDTH, PCB_HEIGHT, PCB_THICKNESS])
    pcb.apply_translation([0, 0, -PCB_THICKNESS/2])
    pcb.visual.face_colors = COLORS['pcb']
    meshes.append(('pcb_base', pcb))

    # LCD screen
    lcd = pcb_positions.get('LCD', {})
    if lcd:
        stl_x, stl_y = transform_pcb_to_stl(lcd['center_x'], lcd['center_y'])
        lcd_mesh = box(extents=[lcd.get('width', 42), lcd.get('height', 32), 0.5])
        lcd_mesh.apply_translation([stl_x, stl_y, 0.25])
        lcd_mesh.visual.face_colors = COLORS['lcd']
        meshes.append(('lcd_screen', lcd_mesh))

    # Button markers
    for pcb_name in ['DPAD', 'AB', 'START_SELECT', 'MENU', 'L_BTN', 'R_BTN', 'POWER']:
        if pcb_name not in pcb_positions:
            continue

        pos = pcb_positions[pcb_name]
        stl_x, stl_y = transform_pcb_to_stl(pos['center_x'], pos['center_y'])

        # Create marker cylinder
        marker = cylinder(radius=5, height=2, sections=32)
        marker.apply_translation([stl_x, stl_y, 1])
        marker.visual.face_colors = PCB_MARKER_COLORS.get(pcb_name, [150, 150, 150, 255])
        meshes.append((f'pcb_marker_{pcb_name}', marker))

        # Add smaller marker on top for visibility
        top_marker = cylinder(radius=3, height=1, sections=32)
        top_marker.apply_translation([stl_x, stl_y, 2.5])
        top_marker.visual.face_colors = [255, 255, 255, 200]
        meshes.append((f'pcb_top_{pcb_name}', top_marker))

    return meshes


def create_exploded_view(parts):
    """Create exploded view."""
    exploded = []

    all_centroids = [p[1].centroid for p in parts]
    center = np.mean(all_centroids, axis=0)

    z_offsets = {
        'back_cover': -40,
        'pcb_base': -20,
        'lcd_screen': -19,
        'frame': 0,
        'd_Pad': 20,
        'A_B': 20,
        'start_select': 20,
        'menu': 20,
        'L_R': 25,
        'power': 30,
        'top_cover': 45,
    }

    for name, mesh in parts:
        new_mesh = mesh.copy()

        # PCB markers follow their base
        base_name = name
        if name.startswith('pcb_marker_') or name.startswith('pcb_ring_'):
            base_name = 'pcb_base'

        z_off = z_offsets.get(base_name, 0)

        # XY explosion for non-PCB parts
        if not name.startswith('pcb_'):
            direction = mesh.centroid - center
            direction[2] = 0
            if np.linalg.norm(direction[:2]) > 0.1:
                direction[:2] = direction[:2] / np.linalg.norm(direction[:2]) * 15
            new_mesh.apply_translation([direction[0], direction[1], z_off])
        else:
            new_mesh.apply_translation([0, 0, z_off])

        exploded.append((name, new_mesh))

    return exploded


def calculate_alignment(stl_parts, pcb_positions):
    """Calculate alignment between STL parts and PCB markers."""
    print("\n" + "=" * 70)
    print("ALIGNMENT VERIFICATION")
    print("=" * 70)

    mapping = {
        'd_Pad': 'DPAD',
        'A_B': 'AB',
        'start_select': 'START_SELECT',
        'menu': 'MENU',
    }

    results = []

    for stl_name, pcb_name in mapping.items():
        stl_part = next((p for p in stl_parts if p[0] == stl_name), None)
        if not stl_part or pcb_name not in pcb_positions:
            continue

        stl_center = stl_part[1].centroid[:2]
        pcb_pos = pcb_positions[pcb_name]
        pcb_stl_x, pcb_stl_y = transform_pcb_to_stl(pcb_pos['center_x'], pcb_pos['center_y'])

        offset_x = stl_center[0] - pcb_stl_x
        offset_y = stl_center[1] - pcb_stl_y
        offset_total = np.sqrt(offset_x**2 + offset_y**2)

        print(f"\n{stl_name} <-> {pcb_name}:")
        print(f"  STL center:    ({stl_center[0]:7.2f}, {stl_center[1]:7.2f})")
        print(f"  PCB (in STL):  ({pcb_stl_x:7.2f}, {pcb_stl_y:7.2f})")
        print(f"  Offset: {offset_total:.2f}mm")

        results.append({
            'stl': stl_name,
            'pcb': pcb_name,
            'offset': offset_total
        })

    # L/R special case
    print("\nL_R (special case):")
    lr_part = next((p for p in stl_parts if p[0] == 'L_R'), None)
    if lr_part:
        lr_center = lr_part[1].centroid
        lr_bounds = lr_part[1].bounds
        print(f"  STL center: ({lr_center[0]:.1f}, {lr_center[1]:.1f})")
        print(f"  STL X range: [{lr_bounds[0][0]:.1f}, {lr_bounds[1][0]:.1f}]")

        l_pcb = pcb_positions.get('L_BTN', {})
        r_pcb = pcb_positions.get('R_BTN', {})
        if l_pcb:
            l_stl_x, l_stl_y = transform_pcb_to_stl(l_pcb['center_x'], l_pcb['center_y'])
            print(f"  PCB L_BTN (in STL): ({l_stl_x:.1f}, {l_stl_y:.1f})")
        if r_pcb:
            r_stl_x, r_stl_y = transform_pcb_to_stl(r_pcb['center_x'], r_pcb['center_y'])
            print(f"  PCB R_BTN (in STL): ({r_stl_x:.1f}, {r_stl_y:.1f})")

    return results


def export_glb(meshes, output_path):
    """Export meshes to GLB."""
    scene = trimesh.Scene()
    for name, mesh in meshes:
        scene.add_geometry(mesh, node_name=name)
    scene.export(str(output_path))


def main():
    print("=" * 70)
    print("CORRECTED RENDER - PCB OVERLAY")
    print("=" * 70)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load data
    print("\nLoading PCB positions...")
    pcb_positions = load_pcb_positions()

    print("Loading STL parts...")
    stl_parts = load_stl_parts()
    print(f"Loaded {len(stl_parts)} STL parts")

    # Calculate alignment
    calculate_alignment(stl_parts, pcb_positions)

    # Create PCB with markers
    print("\n" + "=" * 70)
    print("CREATING RENDERS")
    print("=" * 70)

    print("\nCreating PCB with markers (in STL coordinate system)...")
    pcb_meshes = create_pcb_with_markers(pcb_positions)
    print(f"Created {len(pcb_meshes)} PCB elements")

    # 1. Assembly view
    print("\n1. Assembly view...")
    all_meshes = stl_parts + pcb_meshes
    export_glb(all_meshes, OUTPUT_DIR / 'assembly_colored.glb')

    # 2. Exploded view
    print("2. Exploded view...")
    exploded = create_exploded_view(all_meshes)
    export_glb(exploded, OUTPUT_DIR / 'assembly_exploded.glb')

    # 3. PCB only
    print("3. PCB detailed view...")
    export_glb(pcb_meshes, OUTPUT_DIR / 'pcb_detailed.glb')

    # 4. Case only
    print("4. Case only view...")
    export_glb(stl_parts, OUTPUT_DIR / 'case_only.glb')

    print("\n" + "=" * 70)
    print("DONE!")
    print("=" * 70)
    print(f"\nRenders saved to: {OUTPUT_DIR}")
    print("\nView at: http://localhost:8082/viewer.html")

    return 0


if __name__ == '__main__':
    exit(main())
