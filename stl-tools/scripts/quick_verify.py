#!/usr/bin/env python3
"""Quick verification of center preservation."""

import numpy as np
import trimesh
from pathlib import Path

INPUT_DIR = Path('/app/input')
FIXED_DIR = Path('/app/output/fixed')

def main():
    print("=" * 60)
    print("CENTER PRESERVATION CHECK")
    print("=" * 60)
    print()

    stl_files = sorted(INPUT_DIR.glob('*.stl'))

    all_ok = True
    results = []

    for orig_file in stl_files:
        fixed_file = FIXED_DIR / orig_file.name

        if not fixed_file.exists():
            print(f"SKIP: {orig_file.name} (no fixed version)")
            continue

        # Load meshes
        orig_mesh = trimesh.load(str(orig_file))
        fixed_mesh = trimesh.load(str(fixed_file))

        # Get centroids
        orig_center = orig_mesh.centroid
        fixed_center = fixed_mesh.centroid

        # Calculate drift
        drift = np.linalg.norm(fixed_center - orig_center)

        # Check acceptable (< 1mm drift)
        ok = drift < 1.0
        if not ok:
            all_ok = False

        status = "OK" if ok else "DRIFT!"
        print(f"{orig_file.name}:")
        print(f"  Original center: [{orig_center[0]:.2f}, {orig_center[1]:.2f}, {orig_center[2]:.2f}]")
        print(f"  Fixed center:    [{fixed_center[0]:.2f}, {fixed_center[1]:.2f}, {fixed_center[2]:.2f}]")
        print(f"  Drift: {drift:.4f}mm - [{status}]")
        print()

        results.append({
            'file': orig_file.name,
            'drift': drift,
            'ok': ok
        })

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    ok_count = sum(1 for r in results if r['ok'])
    print(f"Files with acceptable drift (<1mm): {ok_count}/{len(results)}")

    if all_ok:
        print("\nALL CENTERS PRESERVED CORRECTLY")
    else:
        print("\nWARNING: Some files have excessive center drift!")

    return 0 if all_ok else 1

if __name__ == '__main__':
    exit(main())
