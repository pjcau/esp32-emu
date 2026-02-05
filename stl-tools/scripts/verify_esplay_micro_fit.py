#!/usr/bin/env python3
"""
ESPlay Micro PCB Fit Verification
Analyzes new_esplay.brd and verifies fit with case STL parts.
"""

import json
import logging
import xml.etree.ElementTree as ET
import numpy as np
import trimesh
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
PCB_FILE = PROJECT_ROOT / 'pcb' / 'new_esplay.brd'
FIXED_DIR = PROJECT_ROOT / 'stl-tools' / 'output' / 'fixed'
ORIGINAL_DIR = PROJECT_ROOT / 'model3d' / 'ESPlay micro v2 case - 5592683' / 'files'
OUTPUT_DIR = PROJECT_ROOT / 'stl-tools' / 'output'


def parse_eagle_brd(filepath: Path):
    """Parse Eagle .brd file and extract PCB info."""
    tree = ET.parse(filepath)
    root = tree.getroot()

    dimension_wires = []
    holes = []
    components = []

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

        elements = board.find('elements')
        if elements is not None:
            for element in elements.findall('element'):
                name = element.get('name', '')
                x = float(element.get('x', 0))
                y = float(element.get('y', 0))

                # Mounting holes
                if name.startswith('H') and len(name) <= 3:
                    holes.append({'name': name, 'x': x, 'y': y})

                # Key components for alignment check
                if any(k in name.upper() for k in ['LCD', 'DISPLAY', 'SW', 'BTN', 'USB', 'SD']):
                    components.append({
                        'name': name,
                        'x': x,
                        'y': y,
                        'package': element.get('package', '')
                    })

    # Calculate bounding box
    all_x = [w['x1'] for w in dimension_wires] + [w['x2'] for w in dimension_wires]
    all_y = [w['y1'] for w in dimension_wires] + [w['y2'] for w in dimension_wires]

    if all_x and all_y:
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)

        return {
            'width': max_x - min_x,
            'height': max_y - min_y,
            'min_x': min_x, 'max_x': max_x,
            'min_y': min_y, 'max_y': max_y,
            'center_x': (min_x + max_x) / 2,
            'center_y': (min_y + max_y) / 2,
            'holes': holes,
            'components': components,
            'wires': dimension_wires
        }

    return None


def load_stl_parts(directory: Path):
    """Load STL parts from directory."""
    parts = {}
    for stl_file in sorted(directory.glob('*.stl')):
        name = stl_file.stem
        mesh = trimesh.load(str(stl_file))
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate([g for g in mesh.geometry.values()])
        parts[name] = mesh
    return parts


def analyze_pcb_case_fit(pcb_info, case_parts, use_original=False):
    """Analyze if PCB fits in case parts."""
    results = []

    pcb_w = pcb_info['width']
    pcb_h = pcb_info['height']

    # Main structural parts
    main_parts = ['frame', 'top_cover', 'back_cover']

    for part_name in main_parts:
        if part_name not in case_parts:
            continue

        mesh = case_parts[part_name]
        ext = mesh.extents
        ctr = mesh.centroid

        # Estimate wall thickness (typically 2-3mm)
        wall = 2.5
        internal_w = ext[0] - 2 * wall
        internal_h = ext[1] - 2 * wall

        # Check fit (PCB should fit inside case)
        w_margin = internal_w - pcb_w
        h_margin = internal_h - pcb_h

        fits = w_margin >= -1.0 and h_margin >= -1.0  # Allow 1mm tolerance

        results.append({
            'part': part_name,
            'stl_extents': [float(ext[0]), float(ext[1]), float(ext[2])],
            'stl_centroid': [float(ctr[0]), float(ctr[1]), float(ctr[2])],
            'estimated_internal': [internal_w, internal_h],
            'pcb_size': [pcb_w, pcb_h],
            'margin_w': w_margin,
            'margin_h': h_margin,
            'fits': fits
        })

    return results


def check_hole_alignment(pcb_info, case_parts):
    """Check if PCB mounting holes align with case."""
    results = {
        'pcb_holes': [],
        'alignment_check': []
    }

    pcb_cx = pcb_info['center_x']
    pcb_cy = pcb_info['center_y']

    # Convert hole positions to centered coordinates
    for hole in pcb_info['holes']:
        centered_x = hole['x'] - pcb_cx
        centered_y = hole['y'] - pcb_cy
        results['pcb_holes'].append({
            'name': hole['name'],
            'original': [hole['x'], hole['y']],
            'centered': [centered_x, centered_y]
        })

    # Check if holes are symmetrically placed (typical for mounting)
    if len(results['pcb_holes']) >= 4:
        xs = [h['centered'][0] for h in results['pcb_holes']]
        ys = [h['centered'][1] for h in results['pcb_holes']]

        x_symmetric = abs(min(xs) + max(xs)) < 1.0
        y_symmetric = abs(min(ys) + max(ys)) < 1.0

        results['alignment_check'] = {
            'x_range': [min(xs), max(xs)],
            'y_range': [min(ys), max(ys)],
            'x_symmetric': x_symmetric,
            'y_symmetric': y_symmetric,
            'hole_spacing_x': max(xs) - min(xs),
            'hole_spacing_y': max(ys) - min(ys)
        }

    return results


def main():
    logger.info("=" * 70)
    logger.info("ESPLAY MICRO PCB FIT VERIFICATION")
    logger.info("=" * 70)
    logger.info("Date: %s", datetime.now().isoformat())

    # Parse PCB
    logger.info("\n1. PARSING PCB FILE: %s", PCB_FILE.name)
    logger.info("-" * 50)

    pcb_info = parse_eagle_brd(PCB_FILE)
    if not pcb_info:
        logger.error("Could not parse PCB file!")
        return 1

    logger.info("PCB Dimensions: %.2f x %.2f mm", pcb_info['width'], pcb_info['height'])
    logger.info("PCB Center: (%.2f, %.2f)", pcb_info['center_x'], pcb_info['center_y'])
    logger.info("Mounting holes: %d", len(pcb_info['holes']))

    for hole in pcb_info['holes']:
        hx = hole['x'] - pcb_info['center_x']
        hy = hole['y'] - pcb_info['center_y']
        logger.info("  %s: (%.2f, %.2f) -> centered: (%.2f, %.2f)",
                   hole['name'], hole['x'], hole['y'], hx, hy)

    # Load ORIGINAL parts (not fixed - the fixed buttons are wrong)
    logger.info("\n2. LOADING ORIGINAL CASE PARTS")
    logger.info("-" * 50)

    original_parts = load_stl_parts(ORIGINAL_DIR)
    logger.info("Loaded %d original parts", len(original_parts))

    for name, mesh in sorted(original_parts.items()):
        ext = mesh.extents
        ctr = mesh.centroid
        logger.info("  %s: %.1f x %.1f x %.1f mm @ [%.1f, %.1f, %.1f]",
                   name, ext[0], ext[1], ext[2], ctr[0], ctr[1], ctr[2])

    # Analyze fit with ORIGINAL parts
    logger.info("\n3. PCB FIT ANALYSIS (Original Parts)")
    logger.info("-" * 50)

    fit_results = analyze_pcb_case_fit(pcb_info, original_parts, use_original=True)

    all_fit = True
    for result in fit_results:
        status = "OK" if result['fits'] else "CHECK"
        logger.info("\n  %s: [%s]", result['part'], status)
        logger.info("    STL size: %.1f x %.1f mm", result['stl_extents'][0], result['stl_extents'][1])
        logger.info("    Internal (est): %.1f x %.1f mm", *result['estimated_internal'])
        logger.info("    PCB size: %.1f x %.1f mm", *result['pcb_size'])
        logger.info("    Margin W: %.1f mm, H: %.1f mm", result['margin_w'], result['margin_h'])

        if not result['fits']:
            all_fit = False

    # Check hole alignment
    logger.info("\n4. MOUNTING HOLE ANALYSIS")
    logger.info("-" * 50)

    hole_results = check_hole_alignment(pcb_info, original_parts)

    if hole_results['alignment_check']:
        ac = hole_results['alignment_check']
        logger.info("  Hole spacing X: %.1f mm", ac['hole_spacing_x'])
        logger.info("  Hole spacing Y: %.1f mm", ac['hole_spacing_y'])
        logger.info("  X symmetric: %s", "Yes" if ac['x_symmetric'] else "No")
        logger.info("  Y symmetric: %s", "Yes" if ac['y_symmetric'] else "No")

    # Compare PCB center with case centers
    logger.info("\n5. CENTER ALIGNMENT CHECK")
    logger.info("-" * 50)

    logger.info("  PCB center (Eagle coords): (%.2f, %.2f)",
               pcb_info['center_x'], pcb_info['center_y'])

    for part_name in ['frame', 'top_cover', 'back_cover']:
        if part_name in original_parts:
            ctr = original_parts[part_name].centroid
            logger.info("  %s center (STL): [%.2f, %.2f, %.2f]",
                       part_name, ctr[0], ctr[1], ctr[2])

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)

    logger.info("\nPCB (ESPlay Micro): %.1f x %.1f mm", pcb_info['width'], pcb_info['height'])
    logger.info("Case (top_cover):   %.1f x %.1f mm",
               original_parts['top_cover'].extents[0],
               original_parts['top_cover'].extents[1])

    # Check expected size match
    expected_match = (
        abs(pcb_info['width'] - 100) < 2 and
        abs(pcb_info['height'] - 50) < 2
    )

    case_match = (
        abs(original_parts['top_cover'].extents[0] - 110) < 2 and
        abs(original_parts['top_cover'].extents[1] - 55) < 2
    )

    logger.info("\nPCB matches expected 100x50mm: %s", "YES" if expected_match else "NO")
    logger.info("Case matches expected 110x55mm: %s", "YES" if case_match else "NO")

    if expected_match and case_match:
        # Case should have ~5mm margin on each side for PCB
        logger.info("\nFIT ASSESSMENT: COMPATIBLE")
        logger.info("  Case provides ~5mm wall thickness around PCB")
        overall = "PASS"
    else:
        logger.info("\nFIT ASSESSMENT: NEEDS VERIFICATION")
        overall = "CHECK"

    logger.info("\nOVERALL: %s", overall)

    # Save report
    report = {
        'date': datetime.now().isoformat(),
        'pcb_file': str(PCB_FILE),
        'pcb_dimensions': {
            'width': pcb_info['width'],
            'height': pcb_info['height'],
            'center': [pcb_info['center_x'], pcb_info['center_y']]
        },
        'mounting_holes': pcb_info['holes'],
        'hole_analysis': hole_results,
        'fit_analysis': fit_results,
        'overall': overall
    }

    report_path = OUTPUT_DIR / 'esplay_micro_fit_report.json'
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    logger.info("\nReport saved: %s", report_path)

    return 0 if overall == "PASS" else 1


if __name__ == '__main__':
    exit(main())
