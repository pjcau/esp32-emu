#!/usr/bin/env python3
"""
Controlled thickness fix for STL parts.
Uses vertex normal offset with strict size limits.
"""

import numpy as np
import trimesh
from pathlib import Path
from datetime import datetime
import json

PROJECT_ROOT = Path(__file__).parent.parent.parent
ORIGINAL_DIR = PROJECT_ROOT / 'model3d' / 'ESPlay micro v2 case - 5592683' / 'files'
OUTPUT_DIR = PROJECT_ROOT / 'stl-tools' / 'output' / 'fixed_v2'

# Target minimum wall thickness
MIN_THICKNESS = 1.0  # mm

# Maximum allowed size increase per axis
MAX_SIZE_INCREASE = 2.0  # mm total (1mm per side)

# Maximum centroid drift allowed
MAX_CENTROID_DRIFT = 0.1  # mm


def estimate_wall_thickness(mesh):
    """Estimate minimum wall thickness using ray casting."""
    if not mesh.is_watertight:
        # For non-watertight meshes, use a simpler estimate
        return estimate_thickness_simple(mesh)

    # Sample points on surface
    points, face_idx = trimesh.sample.sample_surface(mesh, 5000)
    normals = mesh.face_normals[face_idx]

    thicknesses = []

    for i in range(min(1000, len(points))):
        point = points[i]
        normal = normals[i]

        # Cast ray inward
        ray_origin = point - normal * 0.001  # Slightly inside
        ray_dir = -normal

        locations, index_ray, index_tri = mesh.ray.intersects_location(
            ray_origins=[ray_origin],
            ray_directions=[ray_dir]
        )

        if len(locations) > 0:
            # Find closest intersection (excluding self)
            distances = np.linalg.norm(locations - point, axis=1)
            valid_distances = distances[distances > 0.01]  # Ignore self-intersection
            if len(valid_distances) > 0:
                thicknesses.append(np.min(valid_distances))

    if thicknesses:
        return np.percentile(thicknesses, 5)  # 5th percentile
    return 0.5  # Default fallback


def estimate_thickness_simple(mesh):
    """Simple thickness estimate based on minimum extent."""
    return np.min(mesh.extents) * 0.3  # Rough estimate


def fix_thickness_offset(mesh, target_thickness, max_increase):
    """
    Fix thickness by offsetting vertices along normals.
    Controlled to not exceed max_increase.
    """
    original_centroid = mesh.centroid.copy()
    original_extents = mesh.extents.copy()

    # Estimate current thickness
    current_thickness = estimate_wall_thickness(mesh)

    if current_thickness >= target_thickness:
        print(f"    Already OK: {current_thickness:.2f}mm >= {target_thickness}mm")
        return mesh, current_thickness, 0

    # Calculate needed offset
    needed_offset = (target_thickness - current_thickness) / 2

    # Limit offset to not exceed max size increase
    max_offset = max_increase / 2
    actual_offset = min(needed_offset, max_offset)

    print(f"    Current: {current_thickness:.2f}mm, needed offset: {needed_offset:.2f}mm")
    print(f"    Applying offset: {actual_offset:.2f}mm (limited by max {max_offset:.2f}mm)")

    # Create copy and offset vertices
    fixed_mesh = mesh.copy()

    # Compute vertex normals
    vertex_normals = fixed_mesh.vertex_normals

    # Offset vertices outward
    fixed_mesh.vertices += vertex_normals * actual_offset

    # Re-center to preserve centroid
    new_centroid = fixed_mesh.centroid
    drift = new_centroid - original_centroid
    if np.linalg.norm(drift) > 0.001:
        fixed_mesh.vertices -= drift

    # Verify
    final_centroid = fixed_mesh.centroid
    centroid_drift = np.linalg.norm(final_centroid - original_centroid)

    final_extents = fixed_mesh.extents
    size_increase = final_extents - original_extents

    # Estimate new thickness
    new_thickness = estimate_wall_thickness(fixed_mesh)

    return fixed_mesh, new_thickness, actual_offset


def fix_thickness_scale(mesh, target_thickness, max_increase):
    """
    Fix thickness by uniform scaling from centroid.
    For very thin parts where offset doesn't work well.
    """
    original_centroid = mesh.centroid.copy()
    original_extents = mesh.extents.copy()

    current_thickness = estimate_wall_thickness(mesh)

    if current_thickness >= target_thickness:
        return mesh, current_thickness, 0

    # Calculate scale factor needed
    scale_factor = target_thickness / current_thickness

    # Limit scale factor based on max size increase
    max_scale = 1 + (max_increase / np.min(original_extents))
    scale_factor = min(scale_factor, max_scale)

    print(f"    Scaling by {scale_factor:.3f}x")

    # Scale from centroid
    fixed_mesh = mesh.copy()
    fixed_mesh.vertices = (fixed_mesh.vertices - original_centroid) * scale_factor + original_centroid

    new_thickness = current_thickness * scale_factor

    return fixed_mesh, new_thickness, (scale_factor - 1) * np.min(original_extents)


def process_part(filepath, output_dir):
    """Process a single part with controlled fix."""
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
    original_bounds = mesh.bounds.copy()

    print(f"  Original:")
    print(f"    Extents: {original_extents[0]:.2f} x {original_extents[1]:.2f} x {original_extents[2]:.2f} mm")
    print(f"    Centroid: [{original_centroid[0]:.2f}, {original_centroid[1]:.2f}, {original_centroid[2]:.2f}]")
    print(f"    Watertight: {mesh.is_watertight}")

    # Estimate thickness
    thickness = estimate_wall_thickness(mesh)
    print(f"    Est. thickness (P5): {thickness:.2f}mm")

    # Determine fix method
    if thickness >= MIN_THICKNESS:
        print(f"  Result: Already OK, no fix needed")
        fixed_mesh = mesh
        method = "none"
    else:
        # Try offset method first
        fixed_mesh, new_thickness, offset_applied = fix_thickness_offset(
            mesh, MIN_THICKNESS, MAX_SIZE_INCREASE
        )
        method = "offset"

        # If offset wasn't enough, try scaling
        if new_thickness < MIN_THICKNESS * 0.9:
            print(f"    Offset insufficient, trying scale...")
            fixed_mesh, new_thickness, _ = fix_thickness_scale(
                mesh, MIN_THICKNESS, MAX_SIZE_INCREASE
            )
            method = "scale"

    # Verify results
    final_centroid = fixed_mesh.centroid
    final_extents = fixed_mesh.extents

    centroid_drift = np.linalg.norm(final_centroid - original_centroid)
    size_change = final_extents - original_extents

    print(f"  Final:")
    print(f"    Extents: {final_extents[0]:.2f} x {final_extents[1]:.2f} x {final_extents[2]:.2f} mm")
    print(f"    Size change: [{size_change[0]:+.2f}, {size_change[1]:+.2f}, {size_change[2]:+.2f}] mm")
    print(f"    Centroid drift: {centroid_drift:.4f}mm")

    # Validate
    valid = True
    issues = []

    if centroid_drift > MAX_CENTROID_DRIFT:
        issues.append(f"Centroid drift {centroid_drift:.2f}mm > {MAX_CENTROID_DRIFT}mm")
        valid = False

    if np.max(np.abs(size_change)) > MAX_SIZE_INCREASE * 1.1:
        issues.append(f"Size increase {np.max(np.abs(size_change)):.2f}mm > {MAX_SIZE_INCREASE}mm")
        valid = False

    if valid:
        print(f"  Status: VALID")
    else:
        print(f"  Status: ISSUES - {', '.join(issues)}")

    # Save
    output_path = output_dir / f"{name}.stl"
    fixed_mesh.export(str(output_path))
    print(f"  Saved: {output_path}")

    return {
        'name': name,
        'method': method,
        'original_extents': original_extents.tolist(),
        'final_extents': final_extents.tolist(),
        'size_change': size_change.tolist(),
        'original_centroid': original_centroid.tolist(),
        'final_centroid': final_centroid.tolist(),
        'centroid_drift': float(centroid_drift),
        'original_thickness': float(thickness),
        'valid': valid,
        'issues': issues
    }


def main():
    print("=" * 70)
    print("CONTROLLED THICKNESS FIX")
    print("=" * 70)
    print(f"Date: {datetime.now().isoformat()}")
    print(f"Target thickness: >= {MIN_THICKNESS}mm")
    print(f"Max size increase: {MAX_SIZE_INCREASE}mm")
    print(f"Max centroid drift: {MAX_CENTROID_DRIFT}mm")

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Process all parts
    results = []
    for stl_file in sorted(ORIGINAL_DIR.glob('*.stl')):
        result = process_part(stl_file, OUTPUT_DIR)
        results.append(result)

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(f"\n{'Part':<15} {'Method':<8} {'Size Change':<25} {'Drift':<8} {'Status'}")
    print("-" * 70)

    for r in results:
        sc = r['size_change']
        size_str = f"[{sc[0]:+.1f}, {sc[1]:+.1f}, {sc[2]:+.1f}]"
        status = "OK" if r['valid'] else "CHECK"
        print(f"{r['name']:<15} {r['method']:<8} {size_str:<25} {r['centroid_drift']:.3f}mm  {status}")

    # Save report
    report = {
        'date': datetime.now().isoformat(),
        'settings': {
            'min_thickness': MIN_THICKNESS,
            'max_size_increase': MAX_SIZE_INCREASE,
            'max_centroid_drift': MAX_CENTROID_DRIFT
        },
        'results': results
    }

    report_path = OUTPUT_DIR / 'fix_report.json'
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved: {report_path}")

    valid_count = sum(1 for r in results if r['valid'])
    print(f"\nValid: {valid_count}/{len(results)}")

    return 0


if __name__ == '__main__':
    exit(main())
