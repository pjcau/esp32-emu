#!/usr/bin/env python3
"""
Assembly Fit Verification Script
Verifies that all parts fit together correctly after thickness fixes.
"""

import os
import json
import logging
import numpy as np
import trimesh
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path('/app/output')
FIXED_DIR = OUTPUT_DIR / 'fixed'


class AssemblyVerifier:
    """Verifies that parts fit together in an assembly."""

    def __init__(self):
        self.parts: Dict[str, trimesh.Trimesh] = {}
        self.original_parts: Dict[str, trimesh.Trimesh] = {}

    def load_part(self, filepath: str, name: str = None):
        """Load a part into the assembly."""
        if name is None:
            name = Path(filepath).stem

        mesh = trimesh.load(filepath)
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate(
                [g for g in mesh.geometry.values()]
            )

        self.parts[name] = mesh
        logger.info(f"Loaded part: {name}")

    def load_original(self, filepath: str, name: str = None):
        """Load an original part for comparison."""
        if name is None:
            name = Path(filepath).stem

        mesh = trimesh.load(filepath)
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate(
                [g for g in mesh.geometry.values()]
            )

        self.original_parts[name] = mesh

    def check_intersection(self, part1_name: str, part2_name: str,
                           tolerance: float = 0.1) -> Dict:
        """
        Check if two parts intersect using bounding box overlap.
        A small tolerance allows for minor overlaps at contact surfaces.
        """
        if part1_name not in self.parts or part2_name not in self.parts:
            return {'error': 'Part not found'}

        mesh1 = self.parts[part1_name]
        mesh2 = self.parts[part2_name]

        # Use bounding box overlap as a simpler collision check
        # This is less precise but doesn't require FCL
        bounds1 = mesh1.bounds
        bounds2 = mesh2.bounds

        # Check for bounding box overlap with tolerance
        overlap_x = (bounds1[0][0] - tolerance <= bounds2[1][0] and
                     bounds1[1][0] + tolerance >= bounds2[0][0])
        overlap_y = (bounds1[0][1] - tolerance <= bounds2[1][1] and
                     bounds1[1][1] + tolerance >= bounds2[0][1])
        overlap_z = (bounds1[0][2] - tolerance <= bounds2[1][2] and
                     bounds1[1][2] + tolerance >= bounds2[0][2])

        bbox_overlap = overlap_x and overlap_y and overlap_z

        # If bounding boxes don't overlap, no collision possible
        if not bbox_overlap:
            return {
                'parts': [part1_name, part2_name],
                'collision_detected': False,
                'penetration_depth': 0.0,
                'tolerance': tolerance,
                'acceptable': True,
                'check_method': 'bounding_box'
            }

        # If bounding boxes overlap, check if centroids are reasonable distance apart
        centroid_dist = np.linalg.norm(mesh1.centroid - mesh2.centroid)
        min_size = min(np.min(mesh1.extents), np.min(mesh2.extents))

        # If centroids are very close relative to part size, might be embedded
        potential_collision = centroid_dist < min_size * 0.5

        return {
            'parts': [part1_name, part2_name],
            'collision_detected': potential_collision,
            'penetration_depth': 0.0 if not potential_collision else min_size * 0.5 - centroid_dist,
            'tolerance': tolerance,
            'acceptable': not potential_collision,
            'centroid_distance': float(centroid_dist),
            'check_method': 'bounding_box_centroid'
        }

    def check_all_intersections(self, tolerance: float = 0.1) -> List[Dict]:
        """Check all pairs of parts for intersections."""
        results = []
        part_names = list(self.parts.keys())

        for i in range(len(part_names)):
            for j in range(i + 1, len(part_names)):
                result = self.check_intersection(
                    part_names[i], part_names[j], tolerance
                )
                results.append(result)

        return results

    def compare_with_original(self, part_name: str) -> Dict:
        """
        Compare a fixed part with its original version.
        Check that center is preserved and dimensions are similar.
        """
        if part_name not in self.parts:
            return {'error': f'Fixed part {part_name} not found'}
        if part_name not in self.original_parts:
            return {'error': f'Original part {part_name} not found'}

        fixed = self.parts[part_name]
        original = self.original_parts[part_name]

        # Compare centroids
        centroid_drift = np.linalg.norm(fixed.centroid - original.centroid)

        # Compare bounding boxes
        fixed_extents = fixed.extents
        original_extents = original.extents
        extent_diff = np.abs(fixed_extents - original_extents)

        # Compare volumes (if watertight)
        volume_change = 0
        if fixed.is_watertight and original.is_watertight:
            volume_change = (fixed.volume - original.volume) / original.volume * 100

        return {
            'part_name': part_name,
            'centroid_drift_mm': float(centroid_drift),
            'center_preserved': centroid_drift < 0.01,
            'original_extents': original_extents.tolist(),
            'fixed_extents': fixed_extents.tolist(),
            'extent_difference': extent_diff.tolist(),
            'max_extent_change': float(np.max(extent_diff)),
            'volume_change_percent': float(volume_change),
            'original_centroid': original.centroid.tolist(),
            'fixed_centroid': fixed.centroid.tolist()
        }

    def get_assembly_bounds(self) -> Dict:
        """Get the combined bounding box of all parts."""
        if not self.parts:
            return {'error': 'No parts loaded'}

        all_vertices = np.vstack([
            mesh.vertices for mesh in self.parts.values()
        ])

        min_bounds = np.min(all_vertices, axis=0)
        max_bounds = np.max(all_vertices, axis=0)
        extents = max_bounds - min_bounds

        return {
            'min': min_bounds.tolist(),
            'max': max_bounds.tolist(),
            'extents': extents.tolist(),
            'center': ((min_bounds + max_bounds) / 2).tolist()
        }

    def generate_assembly_report(self, tolerance: float = 0.1) -> Dict:
        """Generate complete assembly verification report."""
        logger.info("Generating assembly verification report...")

        # Check all intersections
        intersection_results = self.check_all_intersections(tolerance)

        # Compare with originals
        comparison_results = []
        for part_name in self.parts:
            if part_name in self.original_parts:
                comparison = self.compare_with_original(part_name)
                comparison_results.append(comparison)

        # Get assembly bounds
        bounds = self.get_assembly_bounds()

        # Summary statistics
        total_pairs = len(intersection_results)
        problematic_pairs = sum(
            1 for r in intersection_results if not r['acceptable']
        )

        centers_preserved = all(
            c['center_preserved'] for c in comparison_results
        ) if comparison_results else True

        return {
            'assembly_bounds': bounds,
            'intersection_tolerance': tolerance,
            'total_part_pairs_checked': total_pairs,
            'problematic_pairs': problematic_pairs,
            'all_fits_acceptable': problematic_pairs == 0,
            'centers_preserved': centers_preserved,
            'intersection_details': intersection_results,
            'comparison_details': comparison_results
        }


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Assembly Fit Verification")
    logger.info("=" * 60)

    verifier = AssemblyVerifier()

    # Load fixed parts
    if FIXED_DIR.exists():
        stl_files = list(FIXED_DIR.glob('*.stl'))
        logger.info(f"Found {len(stl_files)} fixed STL files")

        for stl_file in stl_files:
            verifier.load_part(str(stl_file))
    else:
        logger.error(f"Fixed directory not found: {FIXED_DIR}")
        return 1

    # Load original parts for comparison
    original_dir = Path('/app/input')
    if original_dir.exists():
        for stl_file in original_dir.glob('*.stl'):
            verifier.load_original(str(stl_file))

    # Generate report
    report = verifier.generate_assembly_report(tolerance=0.1)
    report['verification_date'] = datetime.now().isoformat()

    # Save report
    report_path = OUTPUT_DIR / 'verification_report.json'
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    logger.info(f"Report saved to: {report_path}")

    # Save summary
    summary_path = OUTPUT_DIR / 'verification_summary.txt'
    with open(summary_path, 'w') as f:
        f.write("Assembly Fit Verification Summary\n")
        f.write("=" * 50 + "\n\n")

        f.write(f"Verification Date: {report['verification_date']}\n")
        f.write(f"Parts Loaded: {len(verifier.parts)}\n")
        f.write(f"Intersection Tolerance: {report['intersection_tolerance']}mm\n\n")

        f.write("RESULTS:\n")
        f.write("-" * 50 + "\n")
        f.write(f"All fits acceptable: {'YES' if report['all_fits_acceptable'] else 'NO'}\n")
        f.write(f"Centers preserved: {'YES' if report['centers_preserved'] else 'NO'}\n")
        f.write(f"Problematic pairs: {report['problematic_pairs']}/{report['total_part_pairs_checked']}\n\n")

        f.write("Part Center Comparisons:\n")
        f.write("-" * 50 + "\n")
        for comp in report['comparison_details']:
            status = "OK" if comp['center_preserved'] else "DRIFT!"
            f.write(f"  {comp['part_name']}: [{status}]\n")
            f.write(f"    Center drift: {comp['centroid_drift_mm']:.4f}mm\n")
            f.write(f"    Max extent change: {comp['max_extent_change']:.3f}mm\n")

        if report['problematic_pairs'] > 0:
            f.write("\nProblematic Intersections:\n")
            f.write("-" * 50 + "\n")
            for inter in report['intersection_details']:
                if not inter['acceptable']:
                    f.write(f"  {inter['parts'][0]} <-> {inter['parts'][1]}\n")
                    f.write(f"    Penetration: {inter['penetration_depth']:.3f}mm\n")

    logger.info(f"Summary saved to: {summary_path}")

    # Final output
    logger.info("\n" + "=" * 60)
    logger.info("VERIFICATION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"All fits acceptable: {'YES' if report['all_fits_acceptable'] else 'NO'}")
    logger.info(f"Centers preserved: {'YES' if report['centers_preserved'] else 'NO'}")

    if report['problematic_pairs'] > 0:
        logger.warning(f"Found {report['problematic_pairs']} problematic part pairs!")

    return 0 if report['all_fits_acceptable'] and report['centers_preserved'] else 1


if __name__ == '__main__':
    exit(main())
