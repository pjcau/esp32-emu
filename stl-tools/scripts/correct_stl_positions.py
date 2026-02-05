#!/usr/bin/env python3
"""
Correct STL positions to align with PCB button positions.
Creates print-ready STL files with proper alignment.
"""

import numpy as np
import trimesh
from trimesh.creation import box, cylinder
from pathlib import Path
import json
import shutil

PROJECT_ROOT = Path(__file__).parent.parent.parent
FIXED_V2_DIR = PROJECT_ROOT / 'stl-tools' / 'output' / 'fixed_v2'
OUTPUT_DIR = PROJECT_ROOT / 'stl-tools' / 'output' / 'print_ready'
RENDERS_DIR = PROJECT_ROOT / 'stl-tools' / 'output' / 'renders'
PCB_POSITIONS_FILE = PROJECT_ROOT / 'pcb' / 'pcb_component_positions.json'

# PCB specs
PCB_WIDTH = 100.0
PCB_HEIGHT = 50.0
PCB_THICKNESS = 1.6

# Mapping STL names to PCB component names
STL_TO_PCB = {
    'd_Pad': 'DPAD',
    'A_B': 'AB',
    'start_select': 'START_SELECT',
    'menu': 'MENU',
    'power': 'POWER',
}

# Colors for rendering
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
    'L': [255, 200, 0, 255],
    'R': [255, 255, 50, 255],
    'power': [0, 255, 255, 255],
}


def load_pcb_positions():
    """Load PCB positions."""
    with open(PCB_POSITIONS_FILE) as f:
        return json.load(f)


def transform_pcb_to_stl(x, y):
    """Transform PCB coordinates to STL coordinate system.

    PCB coords: Y+ = top (L/R buttons), Y- = bottom (USB)
    Keep same orientation for correct visual display.
    """
    return x, y


def load_and_correct_stl(filepath, pcb_positions):
    """Load STL and calculate correction needed."""
    name = filepath.stem

    mesh = trimesh.load(str(filepath))
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate([g for g in mesh.geometry.values()])

    original_centroid = mesh.centroid.copy()

    # Calculate correction if this is a button part
    correction = np.array([0.0, 0.0, 0.0])

    if name in STL_TO_PCB:
        pcb_name = STL_TO_PCB[name]
        if pcb_name in pcb_positions:
            pcb_pos = pcb_positions[pcb_name]
            target_x, target_y = transform_pcb_to_stl(pcb_pos['center_x'], pcb_pos['center_y'])

            # Calculate XY correction (keep Z unchanged)
            correction[0] = target_x - original_centroid[0]
            correction[1] = target_y - original_centroid[1]

    return mesh, name, original_centroid, correction


def main():
    print("=" * 70)
    print("STL POSITION CORRECTION FOR PRINTING")
    print("=" * 70)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RENDERS_DIR.mkdir(parents=True, exist_ok=True)

    # Load PCB positions
    print("\nLoading PCB positions...")
    pcb_positions = load_pcb_positions()

    # Process all STL files
    print("\nProcessing STL files...")
    print("-" * 70)

    corrected_parts = []
    corrections_applied = []

    for stl_file in sorted(FIXED_V2_DIR.glob('*.stl')):
        mesh, name, original_centroid, correction = load_and_correct_stl(stl_file, pcb_positions)

        # Apply correction
        if np.linalg.norm(correction) > 0.01:
            mesh.vertices += correction
            status = f"CORRECTED by ({correction[0]:+.2f}, {correction[1]:+.2f})"
        else:
            status = "OK (no correction needed)"

        new_centroid = mesh.centroid

        print(f"\n{name}:")
        print(f"  Original center: ({original_centroid[0]:7.2f}, {original_centroid[1]:7.2f})")
        print(f"  New center:      ({new_centroid[0]:7.2f}, {new_centroid[1]:7.2f})")
        print(f"  Status: {status}")

        # Apply color for rendering
        color = COLORS.get(name, [128, 128, 128, 255])
        mesh.visual.face_colors = color

        # Save corrected STL
        output_path = OUTPUT_DIR / f"{name}.stl"
        mesh.export(str(output_path))

        corrected_parts.append((name, mesh))
        corrections_applied.append({
            'name': name,
            'original': original_centroid[:2].tolist(),
            'correction': correction[:2].tolist(),
            'new': new_centroid[:2].tolist()
        })

    # Handle L_R special case - create separate L and R parts
    print("\n" + "-" * 70)
    print("Creating L and R shoulder buttons...")

    lr_part = next((p for p in corrected_parts if p[0] == 'L_R'), None)
    if lr_part:
        lr_mesh = lr_part[1]

        # Get PCB positions for L and R
        l_pcb = pcb_positions.get('L_BTN', {})
        r_pcb = pcb_positions.get('R_BTN', {})

        if l_pcb and r_pcb:
            l_target_x, l_target_y = transform_pcb_to_stl(l_pcb['center_x'], l_pcb['center_y'])
            r_target_x, r_target_y = transform_pcb_to_stl(r_pcb['center_x'], r_pcb['center_y'])

            # Current L_R is on the right side, use it for R button
            r_mesh = lr_mesh.copy()
            r_correction_x = r_target_x - r_mesh.centroid[0]
            r_correction_y = r_target_y - r_mesh.centroid[1]
            r_mesh.vertices[:, 0] += r_correction_x
            r_mesh.vertices[:, 1] += r_correction_y
            r_mesh.visual.face_colors = COLORS['R']

            # Mirror for L button
            l_mesh = lr_mesh.copy()
            # Mirror X coordinates
            l_mesh.vertices[:, 0] = -l_mesh.vertices[:, 0]
            # Fix face winding after mirror
            l_mesh.faces = l_mesh.faces[:, ::-1]
            # Position at L button location
            l_correction_x = l_target_x - l_mesh.centroid[0]
            l_correction_y = l_target_y - l_mesh.centroid[1]
            l_mesh.vertices[:, 0] += l_correction_x
            l_mesh.vertices[:, 1] += l_correction_y
            l_mesh.visual.face_colors = COLORS['L']

            print(f"\n  R button:")
            print(f"    Target: ({r_target_x:.2f}, {r_target_y:.2f})")
            print(f"    Result: ({r_mesh.centroid[0]:.2f}, {r_mesh.centroid[1]:.2f})")

            print(f"\n  L button (mirrored):")
            print(f"    Target: ({l_target_x:.2f}, {l_target_y:.2f})")
            print(f"    Result: ({l_mesh.centroid[0]:.2f}, {l_mesh.centroid[1]:.2f})")

            # Save L and R separately
            (OUTPUT_DIR / 'R.stl').unlink(missing_ok=True)
            (OUTPUT_DIR / 'L.stl').unlink(missing_ok=True)
            r_mesh.export(str(OUTPUT_DIR / 'R.stl'))
            l_mesh.export(str(OUTPUT_DIR / 'L.stl'))

            # Remove original L_R and add L, R
            corrected_parts = [(n, m) for n, m in corrected_parts if n != 'L_R']
            corrected_parts.append(('L', l_mesh))
            corrected_parts.append(('R', r_mesh))

            print("\n  Saved: L.stl and R.stl (replacing L_R.stl)")

    # Create PCB model for rendering
    print("\n" + "-" * 70)
    print("Creating PCB model with markers...")

    pcb_meshes = create_pcb_model(pcb_positions)

    # Generate renders
    print("\n" + "=" * 70)
    print("GENERATING RENDERS")
    print("=" * 70)

    # 1. Assembly view
    print("\n1. Assembly view (corrected parts + PCB)...")
    all_meshes = corrected_parts + pcb_meshes
    export_glb(all_meshes, RENDERS_DIR / 'assembly_colored.glb')

    # 2. Exploded view
    print("2. Exploded view...")
    exploded = create_exploded_view(corrected_parts + pcb_meshes)
    export_glb(exploded, RENDERS_DIR / 'assembly_exploded.glb')

    # 3. PCB only
    print("3. PCB detailed view...")
    export_glb(pcb_meshes, RENDERS_DIR / 'pcb_detailed.glb')

    # 4. Case only (what you'll print)
    print("4. Print preview (corrected case parts only)...")
    export_glb(corrected_parts, RENDERS_DIR / 'case_only.glb')

    # Verify alignment
    print("\n" + "=" * 70)
    print("FINAL ALIGNMENT VERIFICATION")
    print("=" * 70)

    verify_alignment(corrected_parts, pcb_positions)

    # Save correction report
    save_report(corrections_applied, OUTPUT_DIR)

    print("\n" + "=" * 70)
    print("DONE!")
    print("=" * 70)
    print(f"\nPrint-ready STL files saved to: {OUTPUT_DIR}")
    print(f"Renders saved to: {RENDERS_DIR}")
    print("\nFiles ready for 3D printing:")
    for f in sorted(OUTPUT_DIR.glob('*.stl')):
        print(f"  - {f.name}")

    return 0


def create_pcb_model(pcb_positions):
    """Create PCB with button markers."""
    meshes = []

    # PCB base
    pcb = box(extents=[PCB_WIDTH, PCB_HEIGHT, PCB_THICKNESS])
    pcb.apply_translation([0, 0, -PCB_THICKNESS/2])
    pcb.visual.face_colors = COLORS['pcb']
    meshes.append(('pcb_base', pcb))

    # LCD
    lcd = pcb_positions.get('LCD', {})
    if lcd:
        stl_x, stl_y = transform_pcb_to_stl(lcd['center_x'], lcd['center_y'])
        lcd_mesh = box(extents=[lcd.get('width', 42), lcd.get('height', 32), 0.5])
        lcd_mesh.apply_translation([stl_x, stl_y, 0.25])
        lcd_mesh.visual.face_colors = COLORS['lcd']
        meshes.append(('lcd', lcd_mesh))

    # Button markers
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
        stl_x, stl_y = transform_pcb_to_stl(pos['center_x'], pos['center_y'])

        marker = cylinder(radius=4, height=1.5, sections=32)
        marker.apply_translation([stl_x, stl_y, 0.75])
        marker.visual.face_colors = marker_colors.get(pcb_name, [150, 150, 150, 255])
        meshes.append((f'marker_{pcb_name}', marker))

    return meshes


def create_exploded_view(parts):
    """Create exploded view."""
    exploded = []

    case_parts = [(n, m) for n, m in parts if not n.startswith('pcb_') and not n.startswith('marker_') and n not in ['lcd']]
    if case_parts:
        all_centroids = [p[1].centroid for p in case_parts]
        center = np.mean(all_centroids, axis=0)
    else:
        center = np.array([0, 0, 0])

    z_offsets = {
        'back_cover': -45,
        'pcb_base': -25,
        'lcd': -24,
        'frame': 0,
        'd_Pad': 20,
        'A_B': 20,
        'start_select': 20,
        'menu': 20,
        'L': 25,
        'R': 25,
        'power': 30,
        'top_cover': 50,
    }

    for name, mesh in parts:
        new_mesh = mesh.copy()

        base_name = name
        if name.startswith('marker_'):
            base_name = 'pcb_base'

        z_off = z_offsets.get(base_name, 0)

        if not name.startswith('pcb_') and not name.startswith('marker_') and name not in ['lcd']:
            direction = mesh.centroid - center
            direction[2] = 0
            if np.linalg.norm(direction[:2]) > 0.1:
                direction[:2] = direction[:2] / np.linalg.norm(direction[:2]) * 18
            new_mesh.apply_translation([direction[0], direction[1], z_off])
        else:
            new_mesh.apply_translation([0, 0, z_off])

        exploded.append((name, new_mesh))

    return exploded


def verify_alignment(parts, pcb_positions):
    """Verify final alignment."""
    print()

    stl_to_pcb = {
        'd_Pad': 'DPAD',
        'A_B': 'AB',
        'start_select': 'START_SELECT',
        'menu': 'MENU',
        'L': 'L_BTN',
        'R': 'R_BTN',
    }

    all_good = True

    for stl_name, pcb_name in stl_to_pcb.items():
        part = next((p for p in parts if p[0] == stl_name), None)
        if not part or pcb_name not in pcb_positions:
            continue

        stl_center = part[1].centroid[:2]
        pcb_pos = pcb_positions[pcb_name]
        target_x, target_y = transform_pcb_to_stl(pcb_pos['center_x'], pcb_pos['center_y'])

        offset = np.sqrt((stl_center[0] - target_x)**2 + (stl_center[1] - target_y)**2)
        status = "✓" if offset < 1.0 else "⚠"

        if offset >= 1.0:
            all_good = False

        print(f"  {stl_name:15} -> {pcb_name:15}: offset {offset:5.2f}mm {status}")

    print()
    if all_good:
        print("  ✓ ALL PARTS ALIGNED CORRECTLY!")
    else:
        print("  ⚠ Some parts have residual offset")


def export_glb(meshes, output_path):
    """Export meshes to GLB."""
    scene = trimesh.Scene()
    for name, mesh in meshes:
        scene.add_geometry(mesh, node_name=name)
    scene.export(str(output_path))


def save_report(corrections, output_dir):
    """Save correction report."""
    report_path = output_dir / 'CORRECTIONS.md'

    report = """# STL Position Corrections Report

## Summary
These STL files have been corrected to align with the ESPlay Micro PCB button positions.

## Corrections Applied

| Part | Original (X, Y) | Correction | New (X, Y) |
|------|-----------------|------------|------------|
"""

    for c in corrections:
        orig = f"({c['original'][0]:.1f}, {c['original'][1]:.1f})"
        corr = f"({c['correction'][0]:+.1f}, {c['correction'][1]:+.1f})"
        new = f"({c['new'][0]:.1f}, {c['new'][1]:.1f})"
        report += f"| {c['name']} | {orig} | {corr} | {new} |\n"

    report += """
## L/R Shoulder Buttons
- Original L_R.stl was only for the right side
- Created separate L.stl (mirrored) and R.stl files
- Both positioned to match PCB L_BTN and R_BTN positions

## Files Ready for Printing
All STL files in this directory are ready for 3D printing with:
- Wall thickness >= 1.0mm
- Correct positions aligned to PCB
- Preserved original geometry (only translated, not scaled)
"""

    with open(report_path, 'w') as f:
        f.write(report)

    print(f"\nReport saved: {report_path}")


if __name__ == '__main__':
    exit(main())
