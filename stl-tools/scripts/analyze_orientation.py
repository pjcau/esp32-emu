#!/usr/bin/env python3
"""
Analyze orientation mismatch between PCB and case STL parts.
The case might be rotated or flipped relative to PCB orientation.
"""

import json
import numpy as np
import trimesh
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
FIXED_DIR = PROJECT_ROOT / 'stl-tools' / 'output' / 'fixed'

# PCB component positions (centered, from generate_detailed_pcb.py)
# These are in PCB coordinate system
PCB_COMPONENTS = {
    'DPAD': (-39.15, 8.02),
    'AB': (41.50, 7.58),
    'START_SELECT': (-39.15, -10.45),
    'MENU': (39.03, -10.52),
    'L_BTN': (-38.57, 20.72),
    'R_BTN': (38.90, 20.72),
    'POWER': (18.58, 10.56),
    'LCD': (1.56, 1.04),
}


def load_parts():
    parts = {}
    for stl_file in sorted(FIXED_DIR.glob('*.stl')):
        name = stl_file.stem
        mesh = trimesh.load(str(stl_file))
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate([g for g in mesh.geometry.values()])
        parts[name] = mesh
    return parts


def main():
    print("=" * 70)
    print("PCB vs CASE ORIENTATION ANALYSIS")
    print("=" * 70)

    parts = load_parts()

    print("\nSTL Part Centroids (XY):")
    print("-" * 50)
    stl_pos = {}
    for name, mesh in sorted(parts.items()):
        c = mesh.centroid
        stl_pos[name] = (c[0], c[1])
        print(f"  {name:15}: ({c[0]:7.2f}, {c[1]:7.2f})")

    print("\nPCB Component Positions:")
    print("-" * 50)
    for name, pos in PCB_COMPONENTS.items():
        print(f"  {name:15}: ({pos[0]:7.2f}, {pos[1]:7.2f})")

    # Try different transformations to find best match
    print("\n" + "=" * 70)
    print("TESTING TRANSFORMATIONS")
    print("=" * 70)

    # Mapping
    mapping = {
        'd_Pad': 'DPAD',
        'A_B': 'AB',
        'start_select': 'START_SELECT',
        'menu': 'MENU',
        'power': 'POWER',
    }

    def calc_error(transform_func):
        """Calculate total error for a transformation."""
        total_error = 0
        count = 0
        for stl_name, pcb_name in mapping.items():
            if stl_name not in stl_pos:
                continue
            stl_xy = stl_pos[stl_name]
            pcb_xy = PCB_COMPONENTS[pcb_name]

            # Apply transformation to STL position
            transformed = transform_func(stl_xy)
            error = np.sqrt((transformed[0] - pcb_xy[0])**2 + (transformed[1] - pcb_xy[1])**2)
            total_error += error
            count += 1
        return total_error / count if count > 0 else 999

    # Test transformations
    transformations = {
        'No change': lambda xy: xy,
        'Flip X': lambda xy: (-xy[0], xy[1]),
        'Flip Y': lambda xy: (xy[0], -xy[1]),
        'Flip XY': lambda xy: (-xy[0], -xy[1]),
        'Rotate 90° CW': lambda xy: (xy[1], -xy[0]),
        'Rotate 90° CCW': lambda xy: (-xy[1], xy[0]),
        'Rotate 180°': lambda xy: (-xy[0], -xy[1]),
        'Flip X + Rotate 90°': lambda xy: (xy[1], xy[0]),
        'Flip Y + Rotate 90°': lambda xy: (-xy[1], -xy[0]),
    }

    results = []
    for name, func in transformations.items():
        error = calc_error(func)
        results.append((error, name, func))
        print(f"  {name:25}: avg error = {error:.2f}mm")

    results.sort()
    best_error, best_name, best_func = results[0]

    print(f"\nBest transformation: {best_name} (error: {best_error:.2f}mm)")

    # Show detailed comparison with best transformation
    print("\n" + "=" * 70)
    print(f"DETAILED COMPARISON WITH '{best_name}'")
    print("=" * 70)

    for stl_name, pcb_name in mapping.items():
        if stl_name not in stl_pos:
            continue

        stl_xy = stl_pos[stl_name]
        pcb_xy = PCB_COMPONENTS[pcb_name]
        transformed = best_func(stl_xy)

        error = np.sqrt((transformed[0] - pcb_xy[0])**2 + (transformed[1] - pcb_xy[1])**2)
        status = "OK" if error < 5 else "OFFSET"

        print(f"\n  {pcb_name} ({stl_name}):")
        print(f"    STL original:    ({stl_xy[0]:7.2f}, {stl_xy[1]:7.2f})")
        print(f"    STL transformed: ({transformed[0]:7.2f}, {transformed[1]:7.2f})")
        print(f"    PCB position:    ({pcb_xy[0]:7.2f}, {pcb_xy[1]:7.2f})")
        print(f"    Error: {error:.2f}mm [{status}]")

    # Check L/R buttons specially
    print("\n" + "=" * 70)
    print("L/R BUTTON ANALYSIS")
    print("=" * 70)
    if 'L_R' in stl_pos:
        lr_pos = stl_pos['L_R']
        lr_ext = parts['L_R'].extents

        print(f"\n  L_R STL:")
        print(f"    Centroid: ({lr_pos[0]:.2f}, {lr_pos[1]:.2f})")
        print(f"    Extents: {lr_ext[0]:.1f} x {lr_ext[1]:.1f} x {lr_ext[2]:.1f}")

        # L/R are on opposite sides, so we check bounds
        lr_bounds = parts['L_R'].bounds
        print(f"    X range: [{lr_bounds[0][0]:.1f}, {lr_bounds[1][0]:.1f}]")
        print(f"    Y range: [{lr_bounds[0][1]:.1f}, {lr_bounds[1][1]:.1f}]")

        l_pcb = PCB_COMPONENTS['L_BTN']
        r_pcb = PCB_COMPONENTS['R_BTN']
        print(f"\n  PCB L button: ({l_pcb[0]:.2f}, {l_pcb[1]:.2f})")
        print(f"  PCB R button: ({r_pcb[0]:.2f}, {r_pcb[1]:.2f})")

        # Check if L/R part spans both positions
        l_in_range = lr_bounds[0][0] <= l_pcb[0] <= lr_bounds[1][0]
        r_in_range = lr_bounds[0][0] <= r_pcb[0] <= lr_bounds[1][0]
        print(f"\n  L button X in L_R range: {l_in_range}")
        print(f"  R button X in L_R range: {r_in_range}")


if __name__ == '__main__':
    main()
