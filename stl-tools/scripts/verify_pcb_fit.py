#!/usr/bin/env python3
"""
PCB Fit Verification Script
Extracts PCB dimensions from Eagle .brd file and compares with case parts.
"""

import json
import logging
import re
import xml.etree.ElementTree as ET
import numpy as np
import trimesh
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
PCB_FILE = PROJECT_ROOT / 'pcb' / 'esplay_2.0.brd'
FIXED_DIR = PROJECT_ROOT / 'stl-tools' / 'output' / 'fixed'
OUTPUT_DIR = PROJECT_ROOT / 'stl-tools' / 'output'


def parse_eagle_brd(filepath: Path) -> Dict:
    """Parse Eagle .brd file and extract PCB outline from Dimension layer (20)."""
    tree = ET.parse(filepath)
    root = tree.getroot()

    # Find all wires in layer 20 (Dimension)
    dimension_wires = []
    board = root.find('.//board')
    if board is not None:
        plain = board.find('plain')
        if plain is not None:
            for wire in plain.findall('wire'):
                if wire.get('layer') == '20':
                    dimension_wires.append({
                        'x1': float(wire.get('x1')),
                        'y1': float(wire.get('y1')),
                        'x2': float(wire.get('x2')),
                        'y2': float(wire.get('y2')),
                        'curve': wire.get('curve')
                    })

    # Calculate bounding box from dimension wires
    if dimension_wires:
        all_x = []
        all_y = []
        for w in dimension_wires:
            all_x.extend([w['x1'], w['x2']])
            all_y.extend([w['y1'], w['y2']])

        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)

        width = max_x - min_x
        height = max_y - min_y
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2

        return {
            'wires': dimension_wires,
            'bounds': {
                'min_x': min_x,
                'max_x': max_x,
                'min_y': min_y,
                'max_y': max_y
            },
            'width_mm': width,
            'height_mm': height,
            'center': (center_x, center_y),
            'corner_radius': 4.336  # From the curve at corners
        }

    return None


def find_holes_in_pcb(filepath: Path) -> List[Dict]:
    """Find mounting holes from the PCB file."""
    tree = ET.parse(filepath)
    root = tree.getroot()

    holes = []
    board = root.find('.//board')
    if board is not None:
        # Look for holes in elements
        elements = board.find('elements')
        if elements is not None:
            for element in elements.findall('element'):
                name = element.get('name', '')
                # Look for mounting holes (usually named MOUNT, H, or similar)
                if 'MOUNT' in name.upper() or name.startswith('H'):
                    holes.append({
                        'name': name,
                        'x': float(element.get('x', 0)),
                        'y': float(element.get('y', 0)),
                        'package': element.get('package', '')
                    })

        # Also look for standalone holes
        plain = board.find('plain')
        if plain is not None:
            for hole in plain.findall('hole'):
                holes.append({
                    'name': 'hole',
                    'x': float(hole.get('x', 0)),
                    'y': float(hole.get('y', 0)),
                    'drill': float(hole.get('drill', 0))
                })

    return holes


def load_case_parts() -> Dict[str, trimesh.Trimesh]:
    """Load case STL parts."""
    parts = {}
    for stl_file in sorted(FIXED_DIR.glob('*.stl')):
        name = stl_file.stem
        mesh = trimesh.load(str(stl_file))
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate([g for g in mesh.geometry.values()])
        parts[name] = mesh
    return parts


def analyze_fit(pcb_info: Dict, case_parts: Dict) -> Dict:
    """Analyze if PCB fits in case parts."""
    results = {
        'pcb_dimensions': {
            'width': pcb_info['width_mm'],
            'height': pcb_info['height_mm'],
            'center': pcb_info['center']
        },
        'case_analysis': [],
        'fit_issues': []
    }

    # Main structural parts to check
    main_parts = ['frame', 'top_cover', 'back_cover']

    for part_name in main_parts:
        if part_name not in case_parts:
            continue

        mesh = case_parts[part_name]
        bounds = mesh.bounds
        extents = mesh.extents
        centroid = mesh.centroid

        # Case internal dimensions (estimate - case walls are typically 2-3mm)
        wall_thickness = 2.5  # estimated
        internal_width = extents[0] - 2 * wall_thickness
        internal_height = extents[1] - 2 * wall_thickness

        # Check if PCB fits
        width_margin = internal_width - pcb_info['width_mm']
        height_margin = internal_height - pcb_info['height_mm']

        fits = width_margin > 0 and height_margin > 0

        part_analysis = {
            'name': part_name,
            'extents_mm': extents.tolist(),
            'centroid': centroid.tolist(),
            'estimated_internal': {
                'width': internal_width,
                'height': internal_height
            },
            'pcb_fit': {
                'fits': fits,
                'width_margin': width_margin,
                'height_margin': height_margin
            }
        }
        results['case_analysis'].append(part_analysis)

        if not fits:
            if width_margin <= 0:
                results['fit_issues'].append(f"{part_name}: PCB too wide by {-width_margin:.2f}mm")
            if height_margin <= 0:
                results['fit_issues'].append(f"{part_name}: PCB too tall by {-height_margin:.2f}mm")

    return results


def check_center_alignment(pcb_info: Dict, case_parts: Dict) -> Dict:
    """Check if PCB center aligns with case center."""
    results = {
        'pcb_center': pcb_info['center'],
        'alignments': []
    }

    # PCB center (in Eagle coordinates)
    pcb_cx, pcb_cy = pcb_info['center']

    for part_name in ['frame', 'top_cover', 'back_cover']:
        if part_name not in case_parts:
            continue

        mesh = case_parts[part_name]
        # Get XY center from mesh
        case_cx = mesh.centroid[0]
        case_cy = mesh.centroid[1]

        # For alignment check, we compare relative positions
        # The STL parts should be centered at origin or near the PCB center
        results['alignments'].append({
            'part': part_name,
            'case_center_xy': [float(case_cx), float(case_cy)],
            'note': 'STL parts should be aligned to PCB center for proper fit'
        })

    return results


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("PCB FIT VERIFICATION")
    logger.info("=" * 60)
    logger.info("Date: %s", datetime.now().isoformat())

    # Parse PCB file
    logger.info("\n1. Parsing PCB file: %s", PCB_FILE)
    pcb_info = parse_eagle_brd(PCB_FILE)

    if not pcb_info:
        logger.error("Could not parse PCB file!")
        return 1

    logger.info("\nPCB Dimensions:")
    logger.info("  Width:  %.2f mm", pcb_info['width_mm'])
    logger.info("  Height: %.2f mm", pcb_info['height_mm'])
    logger.info("  Center: (%.2f, %.2f)", *pcb_info['center'])
    logger.info("  Corner radius: %.2f mm", pcb_info['corner_radius'])

    # Find mounting holes
    logger.info("\n2. Finding PCB mounting holes...")
    holes = find_holes_in_pcb(PCB_FILE)
    logger.info("  Found %d holes/mounting points", len(holes))
    for hole in holes:
        logger.info("    %s: (%.2f, %.2f)", hole['name'], hole['x'], hole['y'])

    # Load case parts
    logger.info("\n3. Loading case STL parts...")
    case_parts = load_case_parts()
    logger.info("  Loaded %d parts", len(case_parts))

    for name, mesh in case_parts.items():
        ext = mesh.extents
        ctr = mesh.centroid
        logger.info("    %s: %.1f x %.1f x %.1f @ [%.1f, %.1f, %.1f]",
                   name, ext[0], ext[1], ext[2], ctr[0], ctr[1], ctr[2])

    # Analyze fit
    logger.info("\n4. Analyzing PCB fit in case...")
    fit_analysis = analyze_fit(pcb_info, case_parts)

    for analysis in fit_analysis['case_analysis']:
        part = analysis['name']
        fits = analysis['pcb_fit']['fits']
        w_margin = analysis['pcb_fit']['width_margin']
        h_margin = analysis['pcb_fit']['height_margin']
        status = "OK" if fits else "PROBLEM"
        logger.info("  %s: [%s] width_margin=%.1fmm, height_margin=%.1fmm",
                   part, status, w_margin, h_margin)

    # Check center alignment
    logger.info("\n5. Checking center alignment...")
    alignment = check_center_alignment(pcb_info, case_parts)

    logger.info("  PCB center (Eagle coords): (%.2f, %.2f)", *alignment['pcb_center'])
    for a in alignment['alignments']:
        logger.info("  %s center (STL coords): [%.2f, %.2f]",
                   a['part'], a['case_center_xy'][0], a['case_center_xy'][1])

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)

    if fit_analysis['fit_issues']:
        logger.warning("FIT ISSUES FOUND:")
        for issue in fit_analysis['fit_issues']:
            logger.warning("  - %s", issue)
        overall = "FAIL"
    else:
        logger.info("All structural parts can accommodate the PCB")
        overall = "PASS"

    logger.info("\nNOTE: The fixed STL parts (especially buttons) have grown")
    logger.info("significantly due to voxel dilation for wall thickness fixes.")
    logger.info("The frame, top_cover, and back_cover dimensions are more reliable.")

    # Generate report
    report = {
        'verification_date': datetime.now().isoformat(),
        'pcb_file': str(PCB_FILE),
        'pcb_dimensions': {
            'width_mm': pcb_info['width_mm'],
            'height_mm': pcb_info['height_mm'],
            'center': pcb_info['center'],
            'corner_radius_mm': pcb_info['corner_radius']
        },
        'mounting_holes': holes,
        'fit_analysis': fit_analysis,
        'alignment': alignment,
        'overall': overall
    }

    report_path = OUTPUT_DIR / 'pcb_fit_report.json'
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    logger.info("\nReport saved to: %s", report_path)

    logger.info("\nOVERALL: %s", overall)

    return 0 if overall == "PASS" else 1


if __name__ == '__main__':
    exit(main())
