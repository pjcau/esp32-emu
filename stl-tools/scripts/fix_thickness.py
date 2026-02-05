#!/usr/bin/env python3
"""
STL Thickness Fixer Script
Fixes all STL files that have wall thickness below minimum.
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from mesh_analyzer import analyze_stl_file
from mesh_fixer import fix_stl_file

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
MAX_WALL_THICKNESS = float(os.environ.get('MAX_WALL_THICKNESS', 1.25))
FIX_METHOD = os.environ.get('FIX_METHOD', 'iterative')


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("STL Wall Thickness Fixer")
    logger.info(f"Target wall thickness: {MIN_WALL_THICKNESS}-{MAX_WALL_THICKNESS} mm")
    logger.info(f"Fix method: {FIX_METHOD}")
    logger.info("=" * 60)

    # Create output directories
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fixed_dir = OUTPUT_DIR / 'fixed'
    fixed_dir.mkdir(exist_ok=True)

    # Check if analysis report exists
    analysis_report_path = OUTPUT_DIR / 'analysis_report.json'
    if analysis_report_path.exists():
        logger.info("Loading existing analysis report...")
        with open(analysis_report_path, 'r') as f:
            analysis = json.load(f)
        files_to_fix = [f['filename'] for f in analysis.get('files_to_fix', [])]
    else:
        logger.info("No analysis report found, analyzing all files...")
        files_to_fix = None

    # Find all STL files
    stl_files = list(INPUT_DIR.glob('*.stl')) + list(INPUT_DIR.glob('*.STL'))
    logger.info(f"Found {len(stl_files)} STL files")

    if not stl_files:
        logger.error("No STL files found!")
        return 1

    # Process each file
    fix_results = []
    successful_fixes = 0
    failed_fixes = 0

    for stl_file in sorted(stl_files):
        logger.info(f"\n{'='*50}")
        logger.info(f"Processing: {stl_file.name}")
        logger.info('=' * 50)

        # First analyze if we don't have analysis data
        if files_to_fix is None:
            logger.info("Analyzing file...")
            analysis = analyze_stl_file(str(stl_file), num_samples=10000)
            needs_fix = analysis['wall_thickness']['min_thickness'] < MIN_WALL_THICKNESS
        else:
            needs_fix = stl_file.name in files_to_fix

        output_path = fixed_dir / stl_file.name

        if needs_fix:
            logger.info(f"File needs fixing, applying thickness correction...")
            try:
                result = fix_stl_file(
                    str(stl_file),
                    str(output_path),
                    min_thickness=MIN_WALL_THICKNESS,
                    max_thickness=MAX_WALL_THICKNESS,
                    method=FIX_METHOD
                )

                fix_results.append(result)

                if result['success']:
                    successful_fixes += 1
                    logger.info(f"SUCCESS: Fixed {stl_file.name}")
                    logger.info(f"  New min thickness: {result['verification']['min_thickness']:.3f}mm")
                    logger.info(f"  Center drift: {result['center_check']['drift_mm']:.4f}mm")
                else:
                    failed_fixes += 1
                    logger.warning(f"PARTIAL: {stl_file.name} may still have issues")
                    logger.warning(f"  Min thickness: {result['verification']['min_thickness']:.3f}mm")
                    logger.warning(f"  Violations: {result['verification']['violations']}")

            except Exception as e:
                failed_fixes += 1
                logger.error(f"FAILED: {stl_file.name} - {e}")
                fix_results.append({
                    'input_file': str(stl_file),
                    'error': str(e),
                    'success': False
                })
        else:
            logger.info(f"File OK, copying without modification...")
            # Just copy the file as-is
            import shutil
            shutil.copy(str(stl_file), str(output_path))

            fix_results.append({
                'input_file': str(stl_file),
                'output_file': str(output_path),
                'needed_fix': False,
                'success': True,
                'action': 'copied'
            })

    # Save fix report
    fix_report = {
        'fix_date': datetime.now().isoformat(),
        'min_wall_thickness': MIN_WALL_THICKNESS,
        'fix_method': FIX_METHOD,
        'total_files': len(stl_files),
        'successful_fixes': successful_fixes,
        'failed_fixes': failed_fixes,
        'results': fix_results
    }

    report_path = OUTPUT_DIR / 'fix_report.json'
    with open(report_path, 'w') as f:
        json.dump(fix_report, f, indent=2)

    # Save summary
    summary_path = OUTPUT_DIR / 'fix_summary.txt'
    with open(summary_path, 'w') as f:
        f.write("STL Wall Thickness Fix Summary\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Fix Date: {fix_report['fix_date']}\n")
        f.write(f"Min Wall Thickness: {MIN_WALL_THICKNESS}mm\n")
        f.write(f"Method: {FIX_METHOD}\n\n")
        f.write(f"Total Files: {len(stl_files)}\n")
        f.write(f"Successful Fixes: {successful_fixes}\n")
        f.write(f"Failed Fixes: {failed_fixes}\n\n")

        f.write("Results:\n")
        f.write("-" * 50 + "\n")
        for result in fix_results:
            filename = Path(result['input_file']).name
            if result.get('error'):
                f.write(f"  {filename}: FAILED - {result['error']}\n")
            elif result.get('action') == 'copied':
                f.write(f"  {filename}: OK (no fix needed)\n")
            elif result['success']:
                f.write(f"  {filename}: FIXED\n")
                f.write(f"    Min thickness: {result['verification']['min_thickness']:.3f}mm\n")
                f.write(f"    Center drift: {result['center_check']['drift_mm']:.4f}mm\n")
            else:
                f.write(f"  {filename}: PARTIAL FIX\n")
                f.write(f"    Min thickness: {result['verification']['min_thickness']:.3f}mm\n")
                f.write(f"    Remaining violations: {result['verification']['violations']}\n")

    logger.info(f"\nFix report saved to: {report_path}")
    logger.info(f"Summary saved to: {summary_path}")
    logger.info(f"Fixed files saved to: {fixed_dir}")

    # Final summary
    logger.info("\n" + "=" * 60)
    logger.info("FIX COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Successful: {successful_fixes}")
    logger.info(f"Failed: {failed_fixes}")

    return 0 if failed_fixes == 0 else 1


if __name__ == '__main__':
    exit(main())
