#!/usr/bin/env python3
"""
Local Assembly Fit Verification Script
Tests if all fixed parts fit together correctly and preserves centers.
"""

import json
import logging
import numpy as np
import trimesh
from pathlib import Path
from datetime import datetime
from typing import Dict, List

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
FIXED_DIR = PROJECT_ROOT / 'stl-tools' / 'output' / 'fixed'
ORIGINAL_DIR = PROJECT_ROOT / 'model3d' / 'ESPlay micro v2 case - 5592683' / 'files'
OUTPUT_DIR = PROJECT_ROOT / 'stl-tools' / 'output'


class AssemblyTester:
    """Tests assembly fit of fixed STL parts."""

    def __init__(self):
        self.fixed_parts: Dict[str, trimesh.Trimesh] = {}
        self.original_parts: Dict[str, trimesh.Trimesh] = {}

    def load_mesh(self, filepath: Path) -> trimesh.Trimesh:
        """Load STL file as trimesh."""
        mesh = trimesh.load(str(filepath))
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate(
                [g for g in mesh.geometry.values()]
            )
        return mesh

    def load_all_parts(self):
        """Load both fixed and original parts."""
        logger.info("Loading fixed parts from: %s", FIXED_DIR)
        for stl_file in sorted(FIXED_DIR.glob('*.stl')):
            name = stl_file.stem
            self.fixed_parts[name] = self.load_mesh(stl_file)
            logger.info("  Loaded fixed: %s", name)

        logger.info("\nLoading original parts from: %s", ORIGINAL_DIR)
        for stl_file in sorted(ORIGINAL_DIR.glob('*.stl')):
            name = stl_file.stem
            self.original_parts[name] = self.load_mesh(stl_file)
            logger.info("  Loaded original: %s", name)

    def compare_centroids(self) -> Dict:
        """Compare centroids between original and fixed parts."""
        results = {
            'comparisons': [],
            'max_drift': 0.0,
            'all_preserved': True
        }

        logger.info("\n" + "=" * 60)
        logger.info("CENTROID COMPARISON (Original vs Fixed)")
        logger.info("=" * 60)

        for name in sorted(self.fixed_parts.keys()):
            if name not in self.original_parts:
                continue

            fixed = self.fixed_parts[name]
            original = self.original_parts[name]

            orig_centroid = original.centroid
            fixed_centroid = fixed.centroid
            drift = np.linalg.norm(fixed_centroid - orig_centroid)

            orig_extents = original.extents
            fixed_extents = fixed.extents
            extent_change = fixed_extents - orig_extents

            preserved = drift < 0.1  # 0.1mm tolerance
            status = "OK" if preserved else "DRIFT!"

            logger.info("\n%s:", name)
            logger.info("  Original centroid: [%.3f, %.3f, %.3f]", *orig_centroid)
            logger.info("  Fixed centroid:    [%.3f, %.3f, %.3f]", *fixed_centroid)
            logger.info("  Drift: %.4f mm  [%s]", drift, status)
            logger.info("  Extent change: [%.3f, %.3f, %.3f] mm", *extent_change)

            comp = {
                'name': name,
                'original_centroid': orig_centroid.tolist(),
                'fixed_centroid': fixed_centroid.tolist(),
                'drift_mm': float(drift),
                'preserved': preserved,
                'original_extents': orig_extents.tolist(),
                'fixed_extents': fixed_extents.tolist(),
                'extent_change': extent_change.tolist()
            }
            results['comparisons'].append(comp)

            if drift > results['max_drift']:
                results['max_drift'] = float(drift)
            if not preserved:
                results['all_preserved'] = False

        return results

    def check_bounding_box_collisions(self, tolerance: float = 0.1) -> Dict:
        """Check for bounding box overlaps between parts."""
        results = {
            'pairs_checked': 0,
            'potential_collisions': [],
            'all_clear': True
        }

        logger.info("\n" + "=" * 60)
        logger.info("COLLISION CHECK (Bounding Box)")
        logger.info("=" * 60)

        part_names = sorted(self.fixed_parts.keys())

        expected_overlaps = {
            ('frame', 'd_Pad'), ('frame', 'A_B'), ('frame', 'L_R'),
            ('frame', 'start_select'), ('frame', 'menu'), ('frame', 'power'),
            ('top_cover', 'd_Pad'), ('top_cover', 'A_B'), ('top_cover', 'L_R'),
            ('top_cover', 'start_select'), ('top_cover', 'menu'), ('top_cover', 'power'),
        }

        for i in range(len(part_names)):
            for j in range(i + 1, len(part_names)):
                name1, name2 = part_names[i], part_names[j]
                mesh1 = self.fixed_parts[name1]
                mesh2 = self.fixed_parts[name2]

                bounds1 = mesh1.bounds
                bounds2 = mesh2.bounds

                overlap = (
                    bounds1[0][0] - tolerance <= bounds2[1][0] and
                    bounds1[1][0] + tolerance >= bounds2[0][0] and
                    bounds1[0][1] - tolerance <= bounds2[1][1] and
                    bounds1[1][1] + tolerance >= bounds2[0][1] and
                    bounds1[0][2] - tolerance <= bounds2[1][2] and
                    bounds1[1][2] + tolerance >= bounds2[0][2]
                )

                pair_key = (name1, name2)
                expected = pair_key in expected_overlaps or (name2, name1) in expected_overlaps

                results['pairs_checked'] += 1

                if overlap:
                    overlap_x = min(bounds1[1][0], bounds2[1][0]) - max(bounds1[0][0], bounds2[0][0])
                    overlap_y = min(bounds1[1][1], bounds2[1][1]) - max(bounds1[0][1], bounds2[0][1])
                    overlap_z = min(bounds1[1][2], bounds2[1][2]) - max(bounds1[0][2], bounds2[0][2])
                    overlap_depth = min(max(overlap_x, 0), max(overlap_y, 0), max(overlap_z, 0))

                    if expected:
                        logger.info("  %s <-> %s: OVERLAP (expected)", name1, name2)
                    else:
                        status = "WARNING" if overlap_depth > 1.0 else "minor"
                        logger.info("  %s <-> %s: OVERLAP depth=%.2fmm [%s]", name1, name2, overlap_depth, status)
                        results['potential_collisions'].append({
                            'parts': [name1, name2],
                            'overlap_depth': float(overlap_depth),
                            'expected': expected
                        })
                        if overlap_depth > 1.0 and not expected:
                            results['all_clear'] = False

        logger.info("\nPairs checked: %d", results['pairs_checked'])
        logger.info("Potential issues: %d", len(results['potential_collisions']))

        return results

    def verify_assembly_bounds(self) -> Dict:
        """Verify overall assembly dimensions."""
        logger.info("\n" + "=" * 60)
        logger.info("ASSEMBLY BOUNDS VERIFICATION")
        logger.info("=" * 60)

        all_vertices = np.vstack([m.vertices for m in self.fixed_parts.values()])
        min_bounds = np.min(all_vertices, axis=0)
        max_bounds = np.max(all_vertices, axis=0)
        extents = max_bounds - min_bounds
        center = (min_bounds + max_bounds) / 2

        logger.info("\nAssembly bounds:")
        logger.info("  Min: [%.2f, %.2f, %.2f]", *min_bounds)
        logger.info("  Max: [%.2f, %.2f, %.2f]", *max_bounds)
        logger.info("  Size: %.1f x %.1f x %.1f mm", *extents)
        logger.info("  Center: [%.2f, %.2f, %.2f]", *center)

        logger.info("\nPart dimensions:")
        for name in sorted(self.fixed_parts.keys()):
            mesh = self.fixed_parts[name]
            ext = mesh.extents
            ctr = mesh.centroid
            logger.info("  %s: %.1f x %.1f x %.1f @ [%.1f, %.1f, %.1f]",
                       name, ext[0], ext[1], ext[2], ctr[0], ctr[1], ctr[2])

        return {
            'min_bounds': min_bounds.tolist(),
            'max_bounds': max_bounds.tolist(),
            'extents': extents.tolist(),
            'center': center.tolist()
        }

    def run_full_test(self) -> Dict:
        """Run all assembly tests."""
        logger.info("\n" + "=" * 60)
        logger.info("ASSEMBLY FIT VERIFICATION TEST")
        logger.info("=" * 60)
        logger.info("Date: %s", datetime.now().isoformat())

        self.load_all_parts()

        report = {
            'test_date': datetime.now().isoformat(),
            'num_fixed_parts': len(self.fixed_parts),
            'num_original_parts': len(self.original_parts),
        }

        report['centroids'] = self.compare_centroids()
        report['collisions'] = self.check_bounding_box_collisions()
        report['bounds'] = self.verify_assembly_bounds()

        logger.info("\n" + "=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)

        centers_ok = report['centroids']['all_preserved']
        collisions_ok = report['collisions']['all_clear']

        logger.info("Centers preserved: %s (max drift: %.4f mm)",
                   "YES" if centers_ok else "NO",
                   report['centroids']['max_drift'])
        logger.info("No major collisions: %s", "YES" if collisions_ok else "NO")

        report['overall_pass'] = centers_ok and collisions_ok

        logger.info("\nOVERALL: %s", "PASS" if report['overall_pass'] else "FAIL")

        return report


def main():
    """Main entry point."""
    tester = AssemblyTester()
    report = tester.run_full_test()

    report_path = OUTPUT_DIR / 'local_assembly_test_report.json'
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    logger.info("\nReport saved to: %s", report_path)

    return 0 if report['overall_pass'] else 1


if __name__ == '__main__':
    exit(main())
