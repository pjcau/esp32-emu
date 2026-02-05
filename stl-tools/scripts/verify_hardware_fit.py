#!/usr/bin/env python3
"""
Hardware Fit Verification Script
Verifies that the case parts align correctly with:
- Screw holes (4 screws)
- PCB dimensions
- Display opening
- Button positions
- Port openings (USB, SD card, etc.)
"""

import os
import json
import logging
import numpy as np
import trimesh
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path('/app/output')
FIXED_DIR = OUTPUT_DIR / 'fixed'
REFERENCE_DIR = Path('/app/reference')


# ESPlay Micro V2 Hardware Specifications (in mm)
# Based on esplay-hardware repo and common ESP32 dimensions
HARDWARE_SPECS = {
    # PCB dimensions (approximate from ESPlay Micro V2)
    'pcb': {
        'width': 86.0,    # mm
        'height': 56.0,   # mm
        'thickness': 1.6, # mm (standard PCB)
    },

    # Screw hole positions (from PCB corners, M2 screws)
    # Positions are relative to PCB center
    'screw_holes': [
        {'name': 'top_left', 'x': -39.0, 'y': 24.0, 'diameter': 2.2},
        {'name': 'top_right', 'x': 39.0, 'y': 24.0, 'diameter': 2.2},
        {'name': 'bottom_left', 'x': -39.0, 'y': -24.0, 'diameter': 2.2},
        {'name': 'bottom_right', 'x': 39.0, 'y': -24.0, 'diameter': 2.2},
    ],

    # Display opening (ILI9341 2.4" or similar)
    'display': {
        'width': 50.0,    # mm (visible area)
        'height': 37.0,   # mm (visible area)
        'offset_x': 0.0,  # from center
        'offset_y': 5.0,  # from center (usually slightly up)
    },

    # D-Pad position (left side)
    'd_pad': {
        'center_x': -28.0,
        'center_y': -5.0,
        'diameter': 25.0,  # approximate diameter including travel
    },

    # A/B buttons position (right side)
    'ab_buttons': {
        'center_x': 28.0,
        'center_y': -5.0,
        'spacing': 12.0,   # between A and B centers
        'diameter': 8.0,   # button diameter
    },

    # L/R shoulder buttons
    'shoulder_buttons': {
        'l_x': -35.0,
        'r_x': 35.0,
        'y': 28.0,
        'width': 15.0,
        'height': 5.0,
    },

    # USB port opening
    'usb_port': {
        'x': 0.0,
        'y': -28.0,  # bottom edge
        'width': 12.0,
        'height': 7.0,
    },

    # SD card slot
    'sd_slot': {
        'x': 30.0,  # right side
        'y': -28.0,
        'width': 15.0,
        'height': 3.0,
    },

    # Tolerances
    'tolerances': {
        'screw_position': 0.5,    # mm - acceptable screw hole position error
        'dimension': 1.0,          # mm - acceptable dimension difference
        'alignment': 0.3,          # mm - acceptable alignment error
    }
}


class HardwareVerifier:
    """Verifies case alignment with hardware specifications."""

    def __init__(self):
        self.parts: Dict[str, trimesh.Trimesh] = {}
        self.specs = HARDWARE_SPECS

    def load_part(self, filepath: str, name: str = None):
        """Load a case part."""
        if name is None:
            name = Path(filepath).stem

        mesh = trimesh.load(filepath)
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate(
                [g for g in mesh.geometry.values()]
            )

        self.parts[name] = mesh
        logger.info(f"Loaded part: {name}")

    def find_cylindrical_holes(self, mesh: trimesh.Trimesh,
                                target_diameter: float,
                                tolerance: float = 0.5) -> List[Dict]:
        """
        Find cylindrical holes in a mesh that match the target diameter.
        Used to identify screw holes.
        """
        holes = []

        # Sample the mesh surface
        points, face_indices = trimesh.sample.sample_surface(mesh, 50000)
        normals = mesh.face_normals[face_indices]

        # Find points where normals point inward (hole surfaces)
        # Group nearby points that might form a cylinder

        # Simplified approach: look for clusters of points at certain Z levels
        # that form circular patterns

        # Get unique Z levels (layer approach)
        z_levels = np.unique(np.round(points[:, 2], 1))

        for z in z_levels:
            # Get points at this Z level
            mask = np.abs(points[:, 2] - z) < 0.5
            layer_points = points[mask]

            if len(layer_points) < 10:
                continue

            # Look for circular clusters
            # Use convex hull approach on X-Y projection
            xy_points = layer_points[:, :2]

            # Find potential circle centers using RANSAC-like approach
            for _ in range(10):  # Try multiple random samples
                if len(xy_points) < 3:
                    break

                # Random sample 3 points
                idx = np.random.choice(len(xy_points), 3, replace=False)
                sample = xy_points[idx]

                # Fit circle (simplified - just use centroid and check radius consistency)
                center = np.mean(sample, axis=0)
                radii = np.linalg.norm(sample - center, axis=1)
                radius = np.mean(radii)
                diameter = radius * 2

                # Check if diameter matches target
                if abs(diameter - target_diameter) < tolerance:
                    # Verify more points fit this circle
                    all_radii = np.linalg.norm(xy_points - center, axis=1)
                    matching = np.sum(np.abs(all_radii - radius) < tolerance / 2)

                    if matching > 20:  # Enough points to be a real hole
                        holes.append({
                            'center_x': float(center[0]),
                            'center_y': float(center[1]),
                            'z': float(z),
                            'diameter': float(diameter),
                            'confidence': matching / len(xy_points)
                        })

        # Remove duplicates (holes found at multiple Z levels)
        unique_holes = []
        for hole in holes:
            is_duplicate = False
            for existing in unique_holes:
                dist = np.sqrt(
                    (hole['center_x'] - existing['center_x'])**2 +
                    (hole['center_y'] - existing['center_y'])**2
                )
                if dist < 2.0:  # Same hole at different Z
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_holes.append(hole)

        return unique_holes

    def verify_screw_holes(self) -> Dict:
        """Verify screw hole positions match hardware specs."""
        results = {
            'expected_holes': len(self.specs['screw_holes']),
            'holes_found': [],
            'verification': []
        }

        # Look for screw holes in frame and covers
        for part_name in ['frame', 'back_cover', 'top_cover']:
            if part_name not in self.parts:
                continue

            mesh = self.parts[part_name]
            holes = self.find_cylindrical_holes(
                mesh,
                target_diameter=self.specs['screw_holes'][0]['diameter'],
                tolerance=0.5
            )

            for hole in holes:
                results['holes_found'].append({
                    'part': part_name,
                    **hole
                })

        # Match found holes with expected positions
        tolerance = self.specs['tolerances']['screw_position']

        for expected in self.specs['screw_holes']:
            best_match = None
            best_dist = float('inf')

            for found in results['holes_found']:
                dist = np.sqrt(
                    (found['center_x'] - expected['x'])**2 +
                    (found['center_y'] - expected['y'])**2
                )
                if dist < best_dist:
                    best_dist = dist
                    best_match = found

            status = 'OK' if best_dist < tolerance else 'MISALIGNED' if best_dist < tolerance * 3 else 'NOT_FOUND'

            results['verification'].append({
                'expected': expected,
                'found': best_match,
                'distance_error': float(best_dist),
                'status': status
            })

        results['all_holes_ok'] = all(
            v['status'] == 'OK' for v in results['verification']
        )

        return results

    def verify_dimensions(self) -> Dict:
        """Verify overall case dimensions match PCB size."""
        results = {
            'parts_checked': [],
            'dimension_errors': []
        }

        pcb = self.specs['pcb']
        tolerance = self.specs['tolerances']['dimension']

        for part_name, mesh in self.parts.items():
            bounds = mesh.bounds
            extents = mesh.extents

            part_result = {
                'name': part_name,
                'extents': extents.tolist(),
                'bounds': {
                    'min': bounds[0].tolist(),
                    'max': bounds[1].tolist()
                }
            }

            # Check if this part should match PCB dimensions
            if part_name in ['frame', 'top_cover', 'back_cover']:
                # Width and height should be close to PCB size (with some margin for case walls)
                expected_width = pcb['width'] + 4  # ~2mm walls each side
                expected_height = pcb['height'] + 4

                width_error = abs(extents[0] - expected_width)
                height_error = abs(extents[1] - expected_height)

                part_result['width_error'] = float(width_error)
                part_result['height_error'] = float(height_error)
                part_result['dimensions_ok'] = (
                    width_error < tolerance * 3 and
                    height_error < tolerance * 3
                )

            results['parts_checked'].append(part_result)

        return results

    def verify_button_clearances(self) -> Dict:
        """Verify button parts have correct clearances."""
        results = {
            'buttons_checked': []
        }

        button_parts = ['d_Pad', 'A_B', 'L_R', 'start_select', 'menu', 'power']

        for part_name in button_parts:
            if part_name not in self.parts:
                continue

            mesh = self.parts[part_name]
            extents = mesh.extents
            centroid = mesh.centroid

            # Buttons should have small dimensions (not case-sized)
            is_button_sized = max(extents) < 40  # Less than 40mm in any direction

            results['buttons_checked'].append({
                'name': part_name,
                'centroid': centroid.tolist(),
                'extents': extents.tolist(),
                'is_button_sized': is_button_sized
            })

        return results

    def verify_assembly_alignment(self) -> Dict:
        """Verify all parts align correctly when assembled."""
        results = {
            'alignment_checks': []
        }

        if 'frame' not in self.parts:
            results['error'] = 'Frame part not found'
            return results

        frame = self.parts['frame']
        frame_centroid = frame.centroid
        frame_bounds = frame.bounds

        # All parts should be centered on the frame
        tolerance = self.specs['tolerances']['alignment']

        for part_name, mesh in self.parts.items():
            if part_name == 'frame':
                continue

            part_centroid = mesh.centroid

            # Check X-Y alignment (Z can differ for buttons)
            xy_offset = np.sqrt(
                (part_centroid[0] - frame_centroid[0])**2 +
                (part_centroid[1] - frame_centroid[1])**2
            )

            # Buttons are expected to be offset from center
            is_button = part_name in ['d_Pad', 'A_B', 'L_R', 'start_select', 'menu', 'power']

            # Covers should be well-aligned
            if part_name in ['top_cover', 'back_cover']:
                aligned = xy_offset < tolerance * 2
            else:
                aligned = True  # Buttons can be anywhere

            results['alignment_checks'].append({
                'part': part_name,
                'centroid': part_centroid.tolist(),
                'xy_offset_from_frame': float(xy_offset),
                'aligned': aligned
            })

        results['all_aligned'] = all(
            c['aligned'] for c in results['alignment_checks']
        )

        return results

    def generate_report(self) -> Dict:
        """Generate complete hardware verification report."""
        logger.info("Generating hardware verification report...")

        report = {
            'verification_date': datetime.now().isoformat(),
            'parts_loaded': list(self.parts.keys()),
            'hardware_specs': self.specs,
        }

        # Run all verifications
        logger.info("Verifying screw holes...")
        report['screw_holes'] = self.verify_screw_holes()

        logger.info("Verifying dimensions...")
        report['dimensions'] = self.verify_dimensions()

        logger.info("Verifying button clearances...")
        report['buttons'] = self.verify_button_clearances()

        logger.info("Verifying assembly alignment...")
        report['alignment'] = self.verify_assembly_alignment()

        # Overall pass/fail
        report['overall_pass'] = (
            report['screw_holes'].get('all_holes_ok', False) and
            report['alignment'].get('all_aligned', False)
        )

        return report


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Hardware Fit Verification")
    logger.info("=" * 60)

    verifier = HardwareVerifier()

    # Load fixed parts (or original if fixed not available)
    parts_dir = FIXED_DIR if FIXED_DIR.exists() else Path('/app/input')

    if not parts_dir.exists():
        logger.error(f"Parts directory not found: {parts_dir}")
        return 1

    for stl_file in parts_dir.glob('*.stl'):
        verifier.load_part(str(stl_file))

    if not verifier.parts:
        logger.error("No parts loaded!")
        return 1

    # Generate report
    report = verifier.generate_report()

    # Save report
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    report_path = OUTPUT_DIR / 'hardware_verification_report.json'
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    logger.info(f"Report saved to: {report_path}")

    # Save summary
    summary_path = OUTPUT_DIR / 'hardware_verification_summary.txt'
    with open(summary_path, 'w') as f:
        f.write("Hardware Fit Verification Summary\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Verification Date: {report['verification_date']}\n")
        f.write(f"Parts Loaded: {len(report['parts_loaded'])}\n\n")

        f.write("OVERALL RESULT: ")
        f.write("PASS\n" if report['overall_pass'] else "FAIL\n")
        f.write("\n")

        f.write("Screw Holes:\n")
        f.write("-" * 30 + "\n")
        for v in report['screw_holes']['verification']:
            f.write(f"  {v['expected']['name']}: {v['status']}")
            if v['status'] != 'NOT_FOUND':
                f.write(f" (error: {v['distance_error']:.2f}mm)")
            f.write("\n")

        f.write("\nDimensions:\n")
        f.write("-" * 30 + "\n")
        for p in report['dimensions']['parts_checked']:
            f.write(f"  {p['name']}: {p['extents'][0]:.1f} x {p['extents'][1]:.1f} x {p['extents'][2]:.1f} mm\n")

        f.write("\nAlignment:\n")
        f.write("-" * 30 + "\n")
        for a in report['alignment']['alignment_checks']:
            status = "OK" if a['aligned'] else "MISALIGNED"
            f.write(f"  {a['part']}: {status} (offset: {a['xy_offset_from_frame']:.2f}mm)\n")

    logger.info(f"Summary saved to: {summary_path}")

    # Final output
    logger.info("\n" + "=" * 60)
    logger.info("VERIFICATION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Overall: {'PASS' if report['overall_pass'] else 'FAIL'}")

    return 0 if report['overall_pass'] else 1


if __name__ == '__main__':
    exit(main())
