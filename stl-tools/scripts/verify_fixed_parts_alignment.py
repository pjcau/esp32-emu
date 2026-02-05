#!/usr/bin/env python3
"""
Verify alignment of FIXED STL parts with PCB component positions.
Checks if buttons, display cutouts, etc. align correctly.
"""

import json
import logging
import numpy as np
import trimesh
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
FIXED_DIR = PROJECT_ROOT / 'stl-tools' / 'output' / 'fixed'
PCB_POSITIONS = PROJECT_ROOT / 'pcb' / 'pcb_component_positions.json'
OUTPUT_DIR = PROJECT_ROOT / 'stl-tools' / 'output'

# Mapping between PCB components and STL part names
PCB_TO_STL_MAPPING = {
    'DPAD': 'd_Pad',
    'AB': 'A_B',
    'START_SELECT': 'start_select',
    'MENU': 'menu',
    'L_BTN': 'L_R',  # L/R are in same STL
    'R_BTN': 'L_R',
    'POWER': 'power',
}


def load_fixed_parts():
    """Load all fixed STL parts."""
    parts = {}
    for stl_file in sorted(FIXED_DIR.glob('*.stl')):
        name = stl_file.stem
        mesh = trimesh.load(str(stl_file))
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate([g for g in mesh.geometry.values()])
        parts[name] = mesh
    return parts


def main():
    logger.info("=" * 70)
    logger.info("FIXED PARTS ALIGNMENT VERIFICATION")
    logger.info("=" * 70)
    logger.info(f"Date: {datetime.now().isoformat()}")

    # Load PCB component positions
    logger.info("\n1. Loading PCB component positions...")
    with open(PCB_POSITIONS) as f:
        pcb_components = json.load(f)

    for name, pos in pcb_components.items():
        logger.info(f"   {name:15} PCB center: ({pos['center_x']:7.2f}, {pos['center_y']:7.2f})")

    # Load fixed STL parts
    logger.info("\n2. Loading FIXED STL parts...")
    fixed_parts = load_fixed_parts()

    logger.info(f"   Loaded {len(fixed_parts)} parts")

    # Extract centroids (XY only, ignore Z for button alignment)
    stl_centroids = {}
    for name, mesh in fixed_parts.items():
        centroid = mesh.centroid
        stl_centroids[name] = {
            'x': centroid[0],
            'y': centroid[1],
            'z': centroid[2],
            'extents': mesh.extents.tolist()
        }
        logger.info(f"   {name:15} STL center: ({centroid[0]:7.2f}, {centroid[1]:7.2f}, {centroid[2]:7.2f})")

    # Compare PCB positions with STL centroids
    logger.info("\n" + "=" * 70)
    logger.info("3. ALIGNMENT COMPARISON (PCB vs FIXED STL)")
    logger.info("=" * 70)

    results = []
    max_offset = 0

    for pcb_name, stl_name in PCB_TO_STL_MAPPING.items():
        if pcb_name not in pcb_components:
            continue
        if stl_name not in stl_centroids:
            continue

        pcb_pos = pcb_components[pcb_name]
        stl_pos = stl_centroids[stl_name]

        # Calculate XY offset
        offset_x = stl_pos['x'] - pcb_pos['center_x']
        offset_y = stl_pos['y'] - pcb_pos['center_y']
        offset_total = np.sqrt(offset_x**2 + offset_y**2)

        if offset_total > max_offset:
            max_offset = offset_total

        # Determine if alignment is acceptable
        # For buttons, we expect the STL part to be roughly centered on PCB component
        aligned = offset_total < 5.0  # 5mm tolerance

        status = "OK" if aligned else "OFFSET"

        logger.info(f"\n   {pcb_name} -> {stl_name}:")
        logger.info(f"      PCB position: ({pcb_pos['center_x']:7.2f}, {pcb_pos['center_y']:7.2f})")
        logger.info(f"      STL centroid: ({stl_pos['x']:7.2f}, {stl_pos['y']:7.2f})")
        logger.info(f"      Offset: X={offset_x:+.2f}, Y={offset_y:+.2f} (total: {offset_total:.2f}mm)")
        logger.info(f"      Status: [{status}]")

        results.append({
            'pcb_component': pcb_name,
            'stl_part': stl_name,
            'pcb_pos': [pcb_pos['center_x'], pcb_pos['center_y']],
            'stl_pos': [stl_pos['x'], stl_pos['y']],
            'offset_x': offset_x,
            'offset_y': offset_y,
            'offset_total': offset_total,
            'aligned': aligned
        })

    # Check structural parts
    logger.info("\n" + "=" * 70)
    logger.info("4. STRUCTURAL PARTS CHECK")
    logger.info("=" * 70)

    structural_parts = ['frame', 'top_cover', 'back_cover']
    for part_name in structural_parts:
        if part_name in stl_centroids:
            pos = stl_centroids[part_name]
            ext = pos['extents']
            # Check if centered near origin
            off_center = np.sqrt(pos['x']**2 + pos['y']**2)
            centered = off_center < 3.0

            logger.info(f"\n   {part_name}:")
            logger.info(f"      Centroid: ({pos['x']:7.2f}, {pos['y']:7.2f})")
            logger.info(f"      Extents: {ext[0]:.1f} x {ext[1]:.1f} x {ext[2]:.1f} mm")
            logger.info(f"      Distance from origin: {off_center:.2f}mm")
            logger.info(f"      Centered: {'YES' if centered else 'NO'}")

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)

    aligned_count = sum(1 for r in results if r['aligned'])
    total_count = len(results)

    logger.info(f"\n   Aligned components: {aligned_count}/{total_count}")
    logger.info(f"   Max offset: {max_offset:.2f}mm")

    # Check for systematic offset
    if results:
        avg_offset_x = np.mean([r['offset_x'] for r in results])
        avg_offset_y = np.mean([r['offset_y'] for r in results])
        logger.info(f"\n   Average offset: X={avg_offset_x:+.2f}, Y={avg_offset_y:+.2f}")

        if abs(avg_offset_x) > 2 or abs(avg_offset_y) > 2:
            logger.info(f"\n   NOTE: Systematic offset detected!")
            logger.info(f"   The STL parts may need to be shifted by ({-avg_offset_x:.1f}, {-avg_offset_y:.1f})")

    overall = "PASS" if aligned_count == total_count else "CHECK NEEDED"
    logger.info(f"\n   OVERALL: {overall}")

    # Save report
    report = {
        'date': datetime.now().isoformat(),
        'alignment_results': results,
        'stl_centroids': stl_centroids,
        'pcb_components': pcb_components,
        'aligned_count': aligned_count,
        'total_count': total_count,
        'max_offset': max_offset,
        'overall': overall
    }

    report_path = OUTPUT_DIR / 'fixed_parts_alignment_report.json'
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    logger.info(f"\n   Report saved: {report_path}")

    return 0 if overall == "PASS" else 1


if __name__ == '__main__':
    exit(main())
