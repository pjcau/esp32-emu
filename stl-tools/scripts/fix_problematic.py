#!/usr/bin/env python3
"""
Fix problematic STL files using simple vertex offset approach.
No external dependencies beyond trimesh/numpy.
"""

import os
import sys
import logging
import numpy as np
import trimesh
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

INPUT_DIR = Path('/app/input')
OUTPUT_DIR = Path('/app/output/fixed')
MIN_THICKNESS = float(os.environ.get('MIN_WALL_THICKNESS', 1.0))
MAX_THICKNESS = float(os.environ.get('MAX_WALL_THICKNESS', 1.8))

PROBLEMATIC_FILES = ['back_cover.stl', 'frame.stl', 'top_cover.stl']


def measure_thickness(mesh: trimesh.Trimesh, num_samples: int = 3000) -> tuple:
    """Measure wall thickness, return (5th percentile, min, mean)."""
    try:
        points, face_indices = trimesh.sample.sample_surface(mesh, num_samples)
        normals = mesh.face_normals[face_indices]
    except Exception as e:
        logger.warning(f"Sampling failed: {e}")
        return np.min(mesh.extents), np.min(mesh.extents), np.min(mesh.extents)

    offset = 0.01
    thicknesses = []

    # Cast rays in negative normal direction (inside)
    ray_origins = points - normals * offset
    try:
        locations, index_ray, _ = mesh.ray.intersects_location(
            ray_origins=ray_origins,
            ray_directions=-normals
        )

        for i in range(len(points)):
            hits = locations[index_ray == i]
            if len(hits) > 0:
                distances = np.linalg.norm(hits - points[i], axis=1)
                distances = distances[distances > offset]
                if len(distances) > 0:
                    thicknesses.append(np.min(distances))
    except Exception as e:
        logger.warning(f"Ray casting failed: {e}")

    if len(thicknesses) == 0:
        min_ext = np.min(mesh.extents)
        return min_ext, min_ext, min_ext

    thicknesses = np.array(thicknesses)
    return np.percentile(thicknesses, 5), np.min(thicknesses), np.mean(thicknesses)


def fix_mesh_with_offset(input_path: Path, output_path: Path):
    """Fix mesh by offsetting vertices along normals."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Fixing: {input_path.name}")
    logger.info(f"{'='*60}")

    mesh = trimesh.load(str(input_path))
    original_centroid = mesh.centroid.copy()

    logger.info(f"Vertices: {len(mesh.vertices)}, Faces: {len(mesh.faces)}")
    logger.info(f"Watertight: {mesh.is_watertight}")
    logger.info(f"Bounding box: {mesh.extents}")

    p5, min_t, mean_t = measure_thickness(mesh, 3000)
    logger.info(f"Initial thickness - P5: {p5:.3f}mm, Min: {min_t:.3f}mm, Mean: {mean_t:.3f}mm")

    if p5 >= MIN_THICKNESS:
        logger.info("Already meets thickness requirement")
        mesh.export(str(output_path))
        return True

    # Repair mesh first
    try:
        trimesh.repair.fill_holes(mesh)
        mesh.fix_normals()
        mesh.merge_vertices()
        logger.info("Mesh repaired")
    except Exception as e:
        logger.warning(f"Repair partial: {e}")

    # Apply iterative offset until target reached
    max_iterations = 5
    offset_per_iteration = 0.15  # mm per iteration

    for iteration in range(max_iterations):
        p5_current, _, _ = measure_thickness(mesh, 2000)
        logger.info(f"Iteration {iteration + 1}: current P5 = {p5_current:.3f}mm")

        if p5_current >= MIN_THICKNESS:
            logger.info("Target reached!")
            break

        logger.info(f"Applying offset: {offset_per_iteration:.3f}mm along vertex normals")

        # Get vertex normals
        vertex_normals = mesh.vertex_normals

        # Check for bad normals and fix
        norm_magnitudes = np.linalg.norm(vertex_normals, axis=1)
        bad_normals = norm_magnitudes < 0.5
        if np.any(bad_normals):
            for i in np.where(bad_normals)[0]:
                face_mask = np.any(mesh.faces == i, axis=1)
                if np.any(face_mask):
                    avg_normal = np.mean(mesh.face_normals[face_mask], axis=0)
                    norm = np.linalg.norm(avg_normal)
                    if norm > 0.1:
                        vertex_normals[i] = avg_normal / norm
                    else:
                        vertex_normals[i] = [0, 0, 1]

        # Apply offset
        mesh.vertices = mesh.vertices + vertex_normals * offset_per_iteration

    # Correct centroid drift after all iterations
    new_centroid = mesh.centroid
    drift = original_centroid - new_centroid
    mesh.apply_translation(drift)
    logger.info(f"Final centroid drift corrected: {np.linalg.norm(drift):.4f}mm")

    # Save
    mesh.export(str(output_path))
    logger.info(f"Saved to: {output_path}")

    # Verify
    mesh_verify = trimesh.load(str(output_path))
    p5_final, min_final, mean_final = measure_thickness(mesh_verify, 3000)
    logger.info(f"Final thickness - P5: {p5_final:.3f}mm, Min: {min_final:.3f}mm, Mean: {mean_final:.3f}mm")

    success = p5_final >= MIN_THICKNESS
    logger.info(f"Result: {'SUCCESS' if success else 'PARTIAL'}")

    return success


def main():
    logger.info("="*60)
    logger.info("Fixing Problematic STL Files")
    logger.info(f"Target: >= {MIN_THICKNESS}mm wall thickness")
    logger.info("="*60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {}

    for filename in PROBLEMATIC_FILES:
        input_path = INPUT_DIR / filename
        output_path = OUTPUT_DIR / filename

        if not input_path.exists():
            logger.warning(f"Not found: {input_path}")
            continue

        try:
            success = fix_mesh_with_offset(input_path, output_path)
            results[filename] = 'SUCCESS' if success else 'PARTIAL'
        except Exception as e:
            logger.error(f"Failed {filename}: {e}")
            import traceback
            traceback.print_exc()
            results[filename] = f'FAILED: {e}'

    # Summary
    logger.info("\n" + "="*60)
    logger.info("SUMMARY")
    logger.info("="*60)
    for filename, status in results.items():
        logger.info(f"  {filename}: {status}")

    # Count successes
    success_count = sum(1 for s in results.values() if s == 'SUCCESS')
    logger.info(f"\nTotal: {success_count}/{len(results)} succeeded")

    return 0


if __name__ == '__main__':
    sys.exit(main())
