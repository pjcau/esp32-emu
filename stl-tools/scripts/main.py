#!/usr/bin/env python3
"""
Main STL Analysis Script
Analyzes all STL files in the input directory for wall thickness.
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from mesh_analyzer import analyze_stl_file

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

INPUT_DIR = Path('/app/input')
OUTPUT_DIR = Path('/app/output')
LOGS_DIR = Path('/app/logs')

MIN_WALL_THICKNESS = float(os.environ.get('MIN_WALL_THICKNESS', 1.0))
NUM_SAMPLES = int(os.environ.get('NUM_SAMPLES', 15000))


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("STL Wall Thickness Analyzer")
    logger.info(f"Minimum wall thickness requirement: {MIN_WALL_THICKNESS} mm")
    logger.info("=" * 60)

    # Find all STL files
    stl_files = list(INPUT_DIR.glob('*.stl')) + list(INPUT_DIR.glob('*.STL'))
    logger.info(f"Found {len(stl_files)} STL files to analyze")

    if not stl_files:
        logger.error("No STL files found in input directory!")
        return 1

    # Analyze each file
    results = []
    files_needing_fix = []

    for stl_file in sorted(stl_files):
        logger.info(f"\n{'='*40}")
        logger.info(f"Analyzing: {stl_file.name}")
        logger.info('=' * 40)

        try:
            report = analyze_stl_file(str(stl_file), NUM_SAMPLES)

            # Check if file needs fixing
            min_thickness = report['wall_thickness']['min_thickness']
            below_1mm_pct = report['wall_thickness']['below_1mm_percentage']

            needs_fix = min_thickness < MIN_WALL_THICKNESS

            report['needs_fix'] = needs_fix
            report['min_thickness_requirement'] = MIN_WALL_THICKNESS

            results.append(report)

            # Summary for this file
            status = "NEEDS FIX" if needs_fix else "OK"
            logger.info(f"\nResult: [{status}]")
            logger.info(f"  Min thickness: {min_thickness:.3f} mm")
            logger.info(f"  Mean thickness: {report['wall_thickness']['mean_thickness']:.3f} mm")
            logger.info(f"  Below 1mm: {below_1mm_pct:.1f}%")
            logger.info(f"  Thin areas found: {report['wall_thickness']['thin_areas_count']}")

            if needs_fix:
                files_needing_fix.append({
                    'filename': stl_file.name,
                    'min_thickness': min_thickness,
                    'below_1mm_percentage': below_1mm_pct,
                    'thin_areas_count': report['wall_thickness']['thin_areas_count']
                })

        except Exception as e:
            logger.error(f"Error analyzing {stl_file.name}: {e}")
            results.append({
                'filepath': str(stl_file),
                'filename': stl_file.name,
                'error': str(e)
            })

    # Generate summary report
    summary = {
        'analysis_date': datetime.now().isoformat(),
        'min_wall_thickness_requirement': MIN_WALL_THICKNESS,
        'total_files': len(stl_files),
        'files_ok': len(stl_files) - len(files_needing_fix),
        'files_needing_fix': len(files_needing_fix),
        'files_to_fix': files_needing_fix,
        'detailed_results': results
    }

    # Save results
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    report_path = OUTPUT_DIR / 'analysis_report.json'
    with open(report_path, 'w') as f:
        json.dump(summary, f, indent=2)
    logger.info(f"\nReport saved to: {report_path}")

    # Save simple summary
    summary_path = OUTPUT_DIR / 'analysis_summary.txt'
    with open(summary_path, 'w') as f:
        f.write("STL Wall Thickness Analysis Summary\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Analysis Date: {summary['analysis_date']}\n")
        f.write(f"Min Wall Thickness Requirement: {MIN_WALL_THICKNESS} mm\n\n")
        f.write(f"Total Files Analyzed: {summary['total_files']}\n")
        f.write(f"Files OK: {summary['files_ok']}\n")
        f.write(f"Files Needing Fix: {summary['files_needing_fix']}\n\n")

        if files_needing_fix:
            f.write("Files that need thickness adjustment:\n")
            f.write("-" * 50 + "\n")
            for file_info in files_needing_fix:
                f.write(f"  {file_info['filename']}:\n")
                f.write(f"    Min thickness: {file_info['min_thickness']:.3f} mm\n")
                f.write(f"    Below 1mm: {file_info['below_1mm_percentage']:.1f}%\n")
                f.write(f"    Thin areas: {file_info['thin_areas_count']}\n\n")

        f.write("\nDetailed Results per File:\n")
        f.write("-" * 50 + "\n")
        for result in results:
            if 'error' in result:
                f.write(f"  {result['filename']}: ERROR - {result['error']}\n")
            else:
                status = "NEEDS FIX" if result['needs_fix'] else "OK"
                wt = result['wall_thickness']
                f.write(f"  {result['filename']}: [{status}]\n")
                f.write(f"    Min: {wt['min_thickness']:.3f}mm | ")
                f.write(f"Mean: {wt['mean_thickness']:.3f}mm | ")
                f.write(f"Max: {wt['max_thickness']:.3f}mm\n")
                f.write(f"    Center: {result['bounding_box']['center']}\n")

    logger.info(f"Summary saved to: {summary_path}")

    # Final summary
    logger.info("\n" + "=" * 60)
    logger.info("ANALYSIS COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total files: {summary['total_files']}")
    logger.info(f"Files OK: {summary['files_ok']}")
    logger.info(f"Files needing fix: {summary['files_needing_fix']}")

    if files_needing_fix:
        logger.info("\nFiles to fix:")
        for f in files_needing_fix:
            logger.info(f"  - {f['filename']} (min: {f['min_thickness']:.3f}mm)")

    return 0 if len(files_needing_fix) == 0 else 1


if __name__ == '__main__':
    exit(main())
