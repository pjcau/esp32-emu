#!/usr/bin/env python3
"""Compare original vs fixed STL dimensions to understand the changes."""

import numpy as np
import trimesh
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
FIXED_DIR = PROJECT_ROOT / 'stl-tools' / 'output' / 'fixed'
ORIGINAL_DIR = PROJECT_ROOT / 'model3d' / 'ESPlay micro v2 case - 5592683' / 'files'

def load_mesh(filepath):
    mesh = trimesh.load(str(filepath))
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate([g for g in mesh.geometry.values()])
    return mesh

print("=" * 80)
print("DIMENSION COMPARISON: Original vs Fixed STL Parts")
print("=" * 80)
print()

# PCB dimensions from Eagle file
print("PCB Dimensions (from esplay_2.0.brd):")
print("  Width:  75.87 mm")
print("  Height: 97.78 mm")
print("  Mounting holes at corners: 3.81mm and 72.39mm from edges")
print()

print("-" * 80)
print(f"{'Part':<15} {'Original (X x Y x Z)':<30} {'Fixed (X x Y x Z)':<30} {'Change'}")
print("-" * 80)

for stl_file in sorted(ORIGINAL_DIR.glob('*.stl')):
    name = stl_file.stem
    orig_mesh = load_mesh(stl_file)

    fixed_path = FIXED_DIR / f"{name}.stl"
    if fixed_path.exists():
        fixed_mesh = load_mesh(fixed_path)

        orig_ext = orig_mesh.extents
        fixed_ext = fixed_mesh.extents
        change = fixed_ext - orig_ext

        orig_str = f"{orig_ext[0]:.1f} x {orig_ext[1]:.1f} x {orig_ext[2]:.1f}"
        fixed_str = f"{fixed_ext[0]:.1f} x {fixed_ext[1]:.1f} x {fixed_ext[2]:.1f}"
        change_str = f"[{change[0]:+.1f}, {change[1]:+.1f}, {change[2]:+.1f}]"

        print(f"{name:<15} {orig_str:<30} {fixed_str:<30} {change_str}")

print()
print("=" * 80)
print("ORIGINAL PARTS DETAIL (for PCB compatibility check):")
print("=" * 80)
print()

main_parts = ['frame', 'top_cover', 'back_cover']
for part_name in main_parts:
    orig_path = ORIGINAL_DIR / f"{part_name}.stl"
    if orig_path.exists():
        mesh = load_mesh(orig_path)
        print(f"{part_name}:")
        print(f"  Extents: {mesh.extents[0]:.2f} x {mesh.extents[1]:.2f} x {mesh.extents[2]:.2f} mm")
        print(f"  Centroid: [{mesh.centroid[0]:.2f}, {mesh.centroid[1]:.2f}, {mesh.centroid[2]:.2f}]")
        print(f"  Bounds X: [{mesh.bounds[0][0]:.2f}, {mesh.bounds[1][0]:.2f}]")
        print(f"  Bounds Y: [{mesh.bounds[0][1]:.2f}, {mesh.bounds[1][1]:.2f}]")
        print(f"  Bounds Z: [{mesh.bounds[0][2]:.2f}, {mesh.bounds[1][2]:.2f}]")
        print()

# Check if case can fit PCB
print("=" * 80)
print("PCB FIT ANALYSIS (using ORIGINAL parts):")
print("=" * 80)
print()

pcb_width = 75.87  # mm
pcb_height = 97.78  # mm

for part_name in main_parts:
    orig_path = ORIGINAL_DIR / f"{part_name}.stl"
    if orig_path.exists():
        mesh = load_mesh(orig_path)
        ext = mesh.extents

        # The case XY should accommodate PCB
        # Note: STL X axis might be PCB width or height depending on orientation
        print(f"{part_name}:")
        print(f"  STL size: {ext[0]:.1f} x {ext[1]:.1f} mm (XY plane)")

        # Check both orientations
        margin1_x = ext[0] - pcb_width
        margin1_y = ext[1] - pcb_height
        margin2_x = ext[0] - pcb_height
        margin2_y = ext[1] - pcb_width

        print(f"  If PCB oriented as W x H:")
        print(f"    Width margin:  {margin1_x:.1f} mm {'(OK)' if margin1_x > 0 else '(TOO SMALL)'}")
        print(f"    Height margin: {margin1_y:.1f} mm {'(OK)' if margin1_y > 0 else '(TOO SMALL)'}")
        print(f"  If PCB rotated 90°:")
        print(f"    Width margin:  {margin2_x:.1f} mm {'(OK)' if margin2_x > 0 else '(TOO SMALL)'}")
        print(f"    Height margin: {margin2_y:.1f} mm {'(OK)' if margin2_y > 0 else '(TOO SMALL)'}")
        print()
