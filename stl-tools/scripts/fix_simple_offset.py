#!/usr/bin/env python3
"""
Simple vertex offset fix for STL parts.
Applies a fixed small offset to thicken walls without changing dimensions drastically.
"""

import numpy as np
import trimesh
from pathlib import Path
from datetime import datetime
import json

PROJECT_ROOT = Path(__file__).parent.parent.parent
ORIGINAL_DIR = PROJECT_ROOT / 'model3d' / 'ESPlay micro v2 case - 5592683' / 'files'
OUTPUT_DIR = PROJECT_ROOT / 'stl-tools' / 'output' / 'fixed_v2'

# Fixed offset to apply (half of desired thickness increase)
# 0.4mm offset = ~0.8mm thickness increase
OFFSET_AMOUNT = 0.4  # mm

# Parts that need fixing (thin walls)
PARTS_TO_FIX = ['A_B', 'L_R', 'd_Pad', 'menu', 'power', 'start_select']

# Parts that are OK or need minimal fix
PARTS_MINIMAL = ['frame', 'top_cover']

# Parts that don't need any fix
PARTS_OK = ['back_cover']


def compute_vertex_normals_simple(mesh):
    """Compute vertex normals using face normals averaging."""
    vertex_normals = np.zeros(mesh.vertices.shape)

    for i, face in enumerate(mesh.faces):
        for vertex_idx in face:
            vertex_normals[vertex_idx] += mesh.face_normals[i]

    # Normalize
    norms = np.linalg.norm(vertex_normals, axis=1, keepdims=True)
    norms[norms == 0] = 1  # Avoid division by zero
    vertex_normals = vertex_normals / norms

    return vertex_normals


def apply_offset(mesh, offset):
    """Apply vertex offset along normals."""
    normals = compute_vertex_normals_simple(mesh)
    mesh.vertices += normals * offset
    return mesh


def process_part(filepath, output_dir):
    """Process a single part."""
    name = filepath.stem
    print(f"\n{'='*60}")
    print(f"Processing: {name}")
    print(f"{'='*60}")

    # Load mesh
    mesh = trimesh.load(str(filepath))
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate([g for g in mesh.geometry.values()])

    original_centroid = mesh.centroid.copy()
    original_extents = mesh.extents.copy()

    print(f"  Original:")
    print(f"    Extents: {original_extents[0]:.2f} x {original_extents[1]:.2f} x {original_extents[2]:.2f} mm")
    print(f"    Centroid: [{original_centroid[0]:.2f}, {original_centroid[1]:.2f}, {original_centroid[2]:.2f}]")

    # Determine offset amount based on part type
    if name in PARTS_OK:
        offset = 0
        method = "none"
    elif name in PARTS_MINIMAL:
        offset = OFFSET_AMOUNT / 2  # Smaller offset for larger parts
        method = "minimal_offset"
    elif name in PARTS_TO_FIX:
        offset = OFFSET_AMOUNT
        method = "offset"
    else:
        offset = OFFSET_AMOUNT / 2
        method = "auto_offset"

    print(f"  Applying offset: {offset:.2f}mm ({method})")

    if offset > 0:
        # Apply offset
        fixed_mesh = mesh.copy()
        apply_offset(fixed_mesh, offset)

        # Re-center to preserve centroid
        new_centroid = fixed_mesh.centroid
        drift = new_centroid - original_centroid
        fixed_mesh.vertices -= drift
    else:
        fixed_mesh = mesh

    # Calculate results
    final_centroid = fixed_mesh.centroid
    final_extents = fixed_mesh.extents
    centroid_drift = np.linalg.norm(final_centroid - original_centroid)
    size_change = final_extents - original_extents

    print(f"  Final:")
    print(f"    Extents: {final_extents[0]:.2f} x {final_extents[1]:.2f} x {final_extents[2]:.2f} mm")
    print(f"    Size change: [{size_change[0]:+.2f}, {size_change[1]:+.2f}, {size_change[2]:+.2f}] mm")
    print(f"    Centroid drift: {centroid_drift:.4f}mm")

    # Save
    output_path = output_dir / f"{name}.stl"
    fixed_mesh.export(str(output_path))
    print(f"  Saved: {output_path}")

    return {
        'name': name,
        'method': method,
        'offset_applied': offset,
        'original_extents': original_extents.tolist(),
        'final_extents': final_extents.tolist(),
        'size_change': size_change.tolist(),
        'original_centroid': original_centroid.tolist(),
        'final_centroid': final_centroid.tolist(),
        'centroid_drift': float(centroid_drift),
    }


def main():
    print("=" * 70)
    print("SIMPLE OFFSET THICKNESS FIX")
    print("=" * 70)
    print(f"Date: {datetime.now().isoformat()}")
    print(f"Offset amount: {OFFSET_AMOUNT}mm")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    for stl_file in sorted(ORIGINAL_DIR.glob('*.stl')):
        result = process_part(stl_file, OUTPUT_DIR)
        results.append(result)

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(f"\n{'Part':<15} {'Method':<15} {'Offset':<8} {'Size Change':<25} {'Drift'}")
    print("-" * 80)

    for r in results:
        sc = r['size_change']
        size_str = f"[{sc[0]:+.1f}, {sc[1]:+.1f}, {sc[2]:+.1f}]"
        print(f"{r['name']:<15} {r['method']:<15} {r['offset_applied']:.2f}mm   {size_str:<25} {r['centroid_drift']:.3f}mm")

    # Save report
    report = {
        'date': datetime.now().isoformat(),
        'offset_amount': OFFSET_AMOUNT,
        'results': results
    }

    report_path = OUTPUT_DIR / 'fix_report.json'
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved: {report_path}")

    return 0


if __name__ == '__main__':
    exit(main())
