#!/usr/bin/env python3
"""
Verify alignment of fixed_v2 parts with PCB.
"""

import json
import numpy as np
import trimesh
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
FIXED_V2_DIR = PROJECT_ROOT / 'stl-tools' / 'output' / 'fixed_v2'
PCB_POSITIONS = PROJECT_ROOT / 'pcb' / 'pcb_component_positions.json'

# Mapping PCB components to STL parts
MAPPING = {
    'DPAD': 'd_Pad',
    'AB': 'A_B',
    'START_SELECT': 'start_select',
    'MENU': 'menu',
    'POWER': 'power',
}


def main():
    print("=" * 70)
    print("ALIGNMENT VERIFICATION - FIXED V2 PARTS")
    print("=" * 70)

    # Load PCB positions
    with open(PCB_POSITIONS) as f:
        pcb_components = json.load(f)

    # Load fixed parts
    stl_centroids = {}
    print("\nSTL Parts (fixed_v2):")
    print("-" * 50)

    for stl_file in sorted(FIXED_V2_DIR.glob('*.stl')):
        name = stl_file.stem
        mesh = trimesh.load(str(stl_file))
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate([g for g in mesh.geometry.values()])

        c = mesh.centroid
        ext = mesh.extents
        stl_centroids[name] = (c[0], c[1])
        print(f"  {name:15}: center ({c[0]:7.2f}, {c[1]:7.2f}) size {ext[0]:.1f}x{ext[1]:.1f}x{ext[2]:.1f}")

    print("\nPCB Components:")
    print("-" * 50)
    for name, pos in pcb_components.items():
        if name in ['LCD', 'USB', 'SD', 'AUDIO']:
            continue
        print(f"  {name:15}: ({pos['center_x']:7.2f}, {pos['center_y']:7.2f})")

    print("\n" + "=" * 70)
    print("ALIGNMENT COMPARISON")
    print("=" * 70)

    all_aligned = True
    results = []

    for pcb_name, stl_name in MAPPING.items():
        if stl_name not in stl_centroids:
            continue
        if pcb_name not in pcb_components:
            continue

        pcb_pos = pcb_components[pcb_name]
        stl_pos = stl_centroids[stl_name]

        offset_x = stl_pos[0] - pcb_pos['center_x']
        offset_y = stl_pos[1] - pcb_pos['center_y']
        offset_total = np.sqrt(offset_x**2 + offset_y**2)

        aligned = offset_total < 5.0
        status = "OK" if aligned else "OFFSET"

        if not aligned:
            all_aligned = False

        print(f"\n  {pcb_name} -> {stl_name}:")
        print(f"    PCB: ({pcb_pos['center_x']:7.2f}, {pcb_pos['center_y']:7.2f})")
        print(f"    STL: ({stl_pos[0]:7.2f}, {stl_pos[1]:7.2f})")
        print(f"    Offset: X={offset_x:+.2f}, Y={offset_y:+.2f} (total: {offset_total:.2f}mm) [{status}]")

        results.append({
            'pcb': pcb_name,
            'stl': stl_name,
            'offset': offset_total,
            'aligned': aligned
        })

    # L/R special case
    print("\n  L/R Buttons (special case - single STL for both):")
    if 'L_R' in stl_centroids:
        lr_mesh = trimesh.load(str(FIXED_V2_DIR / 'L_R.stl'))
        if isinstance(lr_mesh, trimesh.Scene):
            lr_mesh = trimesh.util.concatenate([g for g in lr_mesh.geometry.values()])

        bounds = lr_mesh.bounds
        print(f"    L_R bounds X: [{bounds[0][0]:.1f}, {bounds[1][0]:.1f}]")
        print(f"    L_R bounds Y: [{bounds[0][1]:.1f}, {bounds[1][1]:.1f}]")

        l_pcb = pcb_components.get('L_BTN', {})
        r_pcb = pcb_components.get('R_BTN', {})
        if l_pcb and r_pcb:
            print(f"    PCB L: ({l_pcb['center_x']:.1f}, {l_pcb['center_y']:.1f})")
            print(f"    PCB R: ({r_pcb['center_x']:.1f}, {r_pcb['center_y']:.1f})")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    aligned_count = sum(1 for r in results if r['aligned'])
    print(f"\n  Aligned: {aligned_count}/{len(results)}")

    if all_aligned:
        print("\n  OVERALL: PASS - All buttons align with PCB positions!")
    else:
        print("\n  OVERALL: CHECK NEEDED - Some offsets detected")

        # Calculate average offset for correction hint
        avg_x = np.mean([r['offset'] for r in results if not r['aligned']]) if results else 0
        print(f"\n  Note: The STL case may have different origin than PCB")
        print(f"  This is expected if case was designed with different reference point")


if __name__ == '__main__':
    main()
