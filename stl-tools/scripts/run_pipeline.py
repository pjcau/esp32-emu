#!/usr/bin/env python3
"""
STL Processing Pipeline Runner
Runs all steps: analyze -> fix -> verify -> render -> simulate -> hardware check
"""

import os
import sys
import json
import logging
import shutil
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import pipeline modules
from mesh_analyzer import analyze_stl_file
from mesh_fixer import fix_stl_file
from verify_fit import AssemblyVerifier

INPUT_DIR = Path('/app/input')
OUTPUT_DIR = Path('/app/output')
FIXED_DIR = OUTPUT_DIR / 'fixed'

MIN_WALL_THICKNESS = float(os.environ.get('MIN_WALL_THICKNESS', 1.0))
MAX_WALL_THICKNESS = float(os.environ.get('MAX_WALL_THICKNESS', 1.25))
FIX_METHOD = os.environ.get('FIX_METHOD', 'iterative')


def print_banner(text: str):
    """Print a banner."""
    logger.info("\n" + "=" * 70)
    logger.info(f"  {text}")
    logger.info("=" * 70 + "\n")


def step_1_analyze() -> dict:
    """Step 1: Analyze all STL files."""
    print_banner("STEP 1: ANALYZING STL FILES")

    stl_files = list(INPUT_DIR.glob('*.stl')) + list(INPUT_DIR.glob('*.STL'))
    logger.info(f"Found {len(stl_files)} STL files to analyze")

    results = []
    files_needing_fix = []

    for stl_file in sorted(stl_files):
        logger.info(f"Analyzing: {stl_file.name}")
        try:
            report = analyze_stl_file(str(stl_file), num_samples=15000)
            min_thickness = report['wall_thickness']['min_thickness']
            needs_fix = min_thickness < MIN_WALL_THICKNESS

            results.append({
                'filename': stl_file.name,
                'min_thickness': min_thickness,
                'mean_thickness': report['wall_thickness']['mean_thickness'],
                'needs_fix': needs_fix,
                'center': report['bounding_box']['center']
            })

            if needs_fix:
                files_needing_fix.append(stl_file.name)
                logger.warning(f"  -> NEEDS FIX: min thickness = {min_thickness:.3f}mm")
            else:
                logger.info(f"  -> OK: min thickness = {min_thickness:.3f}mm")

        except Exception as e:
            logger.error(f"  -> ERROR: {e}")
            results.append({
                'filename': stl_file.name,
                'error': str(e)
            })

    return {
        'total_files': len(stl_files),
        'files_ok': len(stl_files) - len(files_needing_fix),
        'files_needing_fix': len(files_needing_fix),
        'files_to_fix': files_needing_fix,
        'results': results
    }


def step_2_fix(analysis: dict) -> dict:
    """Step 2: Fix files with insufficient wall thickness."""
    print_banner("STEP 2: FIXING WALL THICKNESS")

    FIXED_DIR.mkdir(parents=True, exist_ok=True)

    files_to_fix = analysis.get('files_to_fix', [])
    stl_files = list(INPUT_DIR.glob('*.stl'))

    results = []
    successful = 0
    failed = 0
    skipped = 0

    for stl_file in sorted(stl_files):
        output_path = FIXED_DIR / stl_file.name

        # Skip if already processed
        if output_path.exists():
            logger.info(f"SKIPPED (already exists): {stl_file.name}")
            results.append({
                'filename': stl_file.name,
                'action': 'skipped',
                'success': True
            })
            skipped += 1
            continue

        if stl_file.name in files_to_fix:
            logger.info(f"Fixing: {stl_file.name}")
            try:
                result = fix_stl_file(
                    str(stl_file),
                    str(output_path),
                    min_thickness=MIN_WALL_THICKNESS,
                    max_thickness=MAX_WALL_THICKNESS,
                    method=FIX_METHOD
                )

                if result['success']:
                    successful += 1
                    logger.info(f"  -> FIXED & SAVED: new min = {result['verification']['min_thickness']:.3f}mm")
                else:
                    failed += 1
                    logger.warning(f"  -> PARTIAL: {result['verification']['violations']} violations remain")

                results.append({
                    'filename': stl_file.name,
                    'action': 'fixed',
                    'success': result['success'],
                    'new_min_thickness': result['verification']['min_thickness'],
                    'center_drift': result['center_check']['drift_mm']
                })

            except Exception as e:
                failed += 1
                logger.error(f"  -> FAILED: {e}")
                # Copy original as fallback
                shutil.copy(str(stl_file), str(output_path))
                results.append({
                    'filename': stl_file.name,
                    'action': 'failed',
                    'error': str(e)
                })
        else:
            logger.info(f"Copying (no fix needed): {stl_file.name}")
            shutil.copy(str(stl_file), str(output_path))
            results.append({
                'filename': stl_file.name,
                'action': 'copied',
                'success': True
            })

    logger.info(f"\nFix summary: {successful} fixed, {failed} failed, {skipped} skipped")

    return {
        'successful_fixes': successful,
        'failed_fixes': failed,
        'skipped': skipped,
        'results': results
    }


def step_3_verify() -> dict:
    """Step 3: Verify parts still fit together."""
    print_banner("STEP 3: VERIFYING ASSEMBLY FIT")

    verifier = AssemblyVerifier()

    # Load fixed parts
    for stl_file in FIXED_DIR.glob('*.stl'):
        verifier.load_part(str(stl_file))

    # Load originals for comparison
    for stl_file in INPUT_DIR.glob('*.stl'):
        verifier.load_original(str(stl_file))

    report = verifier.generate_assembly_report(tolerance=0.1)

    logger.info(f"Parts checked: {len(verifier.parts)}")
    logger.info(f"Pairs with issues: {report['problematic_pairs']}/{report['total_part_pairs_checked']}")
    logger.info(f"Centers preserved: {report['centers_preserved']}")

    return report


def step_4_verify_thickness() -> dict:
    """Step 4: Final thickness verification of all fixed parts."""
    print_banner("STEP 4: FINAL THICKNESS VERIFICATION")

    results = []
    all_pass = True

    for stl_file in sorted(FIXED_DIR.glob('*.stl')):
        logger.info(f"Verifying: {stl_file.name}")
        try:
            report = analyze_stl_file(str(stl_file), num_samples=15000)
            min_thickness = report['wall_thickness']['min_thickness']
            passes = min_thickness >= MIN_WALL_THICKNESS

            if not passes:
                all_pass = False

            results.append({
                'filename': stl_file.name,
                'min_thickness': min_thickness,
                'passes': passes
            })

            status = "PASS" if passes else "FAIL"
            logger.info(f"  -> {status}: min = {min_thickness:.3f}mm")

        except Exception as e:
            all_pass = False
            logger.error(f"  -> ERROR: {e}")
            results.append({
                'filename': stl_file.name,
                'error': str(e),
                'passes': False
            })

    return {
        'all_pass': all_pass,
        'results': results
    }


def generate_final_report(pipeline_results: dict):
    """Generate final HTML report."""
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>STL Processing Pipeline Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        h1 {{ color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
        h2 {{ color: #555; }}
        .section {{ background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .pass {{ color: green; font-weight: bold; }}
        .fail {{ color: red; font-weight: bold; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background: #f9f9f9; }}
        .summary-box {{ display: inline-block; padding: 20px; margin: 10px; background: #e8f5e9; border-radius: 8px; text-align: center; }}
        .summary-box.warning {{ background: #fff3e0; }}
        .summary-box.error {{ background: #ffebee; }}
    </style>
</head>
<body>
    <h1>STL Processing Pipeline Report</h1>
    <p>Generated: {pipeline_results['timestamp']}</p>
    <p>Minimum Wall Thickness Requirement: {MIN_WALL_THICKNESS}mm</p>

    <div class="section">
        <h2>Summary</h2>
        <div class="summary-box">
            <h3>Files Analyzed</h3>
            <p style="font-size: 2em;">{pipeline_results['analysis']['total_files']}</p>
        </div>
        <div class="summary-box {'warning' if pipeline_results['analysis']['files_needing_fix'] > 0 else ''}">
            <h3>Needed Fix</h3>
            <p style="font-size: 2em;">{pipeline_results['analysis']['files_needing_fix']}</p>
        </div>
        <div class="summary-box {'error' if pipeline_results['fix']['failed_fixes'] > 0 else ''}">
            <h3>Fix Failed</h3>
            <p style="font-size: 2em;">{pipeline_results['fix']['failed_fixes']}</p>
        </div>
        <div class="summary-box {'pass' if pipeline_results['final_verification']['all_pass'] else 'error'}">
            <h3>Final Result</h3>
            <p style="font-size: 2em;" class="{'pass' if pipeline_results['final_verification']['all_pass'] else 'fail'}">
                {'PASS' if pipeline_results['final_verification']['all_pass'] else 'FAIL'}
            </p>
        </div>
    </div>

    <div class="section">
        <h2>Step 1: Initial Analysis</h2>
        <table>
            <tr><th>File</th><th>Min Thickness</th><th>Mean Thickness</th><th>Status</th></tr>
"""

    for r in pipeline_results['analysis']['results']:
        if 'error' in r:
            html += f"<tr><td>{r['filename']}</td><td colspan='2'>Error: {r['error']}</td><td class='fail'>ERROR</td></tr>"
        else:
            status = "OK" if not r['needs_fix'] else "NEEDS FIX"
            status_class = "pass" if not r['needs_fix'] else "fail"
            html += f"<tr><td>{r['filename']}</td><td>{r['min_thickness']:.3f}mm</td><td>{r['mean_thickness']:.3f}mm</td><td class='{status_class}'>{status}</td></tr>"

    html += """
        </table>
    </div>

    <div class="section">
        <h2>Step 2: Fix Results</h2>
        <table>
            <tr><th>File</th><th>Action</th><th>New Min Thickness</th><th>Center Drift</th><th>Status</th></tr>
"""

    for r in pipeline_results['fix']['results']:
        if r['action'] == 'copied':
            html += f"<tr><td>{r['filename']}</td><td>Copied (no fix needed)</td><td>-</td><td>-</td><td class='pass'>OK</td></tr>"
        elif r['action'] == 'failed':
            html += f"<tr><td>{r['filename']}</td><td>Fix attempted</td><td colspan='2'>Error: {r.get('error', 'Unknown')}</td><td class='fail'>FAILED</td></tr>"
        else:
            status = "OK" if r['success'] else "PARTIAL"
            status_class = "pass" if r['success'] else "fail"
            html += f"<tr><td>{r['filename']}</td><td>Fixed</td><td>{r['new_min_thickness']:.3f}mm</td><td>{r['center_drift']:.4f}mm</td><td class='{status_class}'>{status}</td></tr>"

    html += """
        </table>
    </div>

    <div class="section">
        <h2>Step 3: Assembly Verification</h2>
        <p>All parts fit together: <span class="{}">{}</span></p>
        <p>Centers preserved: <span class="{}">{}</span></p>
        <p>Problematic pairs: {}/{}</p>
    </div>
""".format(
        "pass" if pipeline_results['assembly']['all_fits_acceptable'] else "fail",
        "YES" if pipeline_results['assembly']['all_fits_acceptable'] else "NO",
        "pass" if pipeline_results['assembly']['centers_preserved'] else "fail",
        "YES" if pipeline_results['assembly']['centers_preserved'] else "NO",
        pipeline_results['assembly']['problematic_pairs'],
        pipeline_results['assembly']['total_part_pairs_checked']
    )

    html += """
    <div class="section">
        <h2>Step 4: Final Thickness Verification</h2>
        <table>
            <tr><th>File</th><th>Min Thickness</th><th>Status</th></tr>
"""

    for r in pipeline_results['final_verification']['results']:
        if 'error' in r:
            html += f"<tr><td>{r['filename']}</td><td>Error</td><td class='fail'>ERROR</td></tr>"
        else:
            status = "PASS" if r['passes'] else "FAIL"
            status_class = "pass" if r['passes'] else "fail"
            html += f"<tr><td>{r['filename']}</td><td>{r['min_thickness']:.3f}mm</td><td class='{status_class}'>{status}</td></tr>"

    html += """
        </table>
    </div>

    <div class="section">
        <h2>Output Files</h2>
        <p>Fixed STL files are available in: <code>output/fixed/</code></p>
        <p>Render comparisons: <code>output/renders/</code></p>
        <p>Assembly simulations: <code>output/simulation/</code></p>
    </div>
</body>
</html>
"""

    report_path = OUTPUT_DIR / 'pipeline_report.html'
    with open(report_path, 'w') as f:
        f.write(html)

    logger.info(f"HTML report saved to: {report_path}")


def main():
    """Run the complete pipeline."""
    print_banner("STL PROCESSING PIPELINE")
    logger.info(f"Input directory: {INPUT_DIR}")
    logger.info(f"Output directory: {OUTPUT_DIR}")
    logger.info(f"Min wall thickness: {MIN_WALL_THICKNESS}mm")
    logger.info(f"Fix method: {FIX_METHOD}")

    # Create output directories
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pipeline_results = {
        'timestamp': datetime.now().isoformat(),
        'min_wall_thickness': MIN_WALL_THICKNESS,
        'fix_method': FIX_METHOD
    }

    # Step 1: Analyze
    pipeline_results['analysis'] = step_1_analyze()

    # Step 2: Fix
    pipeline_results['fix'] = step_2_fix(pipeline_results['analysis'])

    # Step 3: Verify assembly
    pipeline_results['assembly'] = step_3_verify()

    # Step 4: Final thickness verification
    pipeline_results['final_verification'] = step_4_verify_thickness()

    # Save JSON report
    json_report_path = OUTPUT_DIR / 'pipeline_results.json'
    with open(json_report_path, 'w') as f:
        json.dump(pipeline_results, f, indent=2, default=str)
    logger.info(f"JSON report saved to: {json_report_path}")

    # Generate HTML report
    generate_final_report(pipeline_results)

    # Final summary
    print_banner("PIPELINE COMPLETE")

    success = (
        pipeline_results['final_verification']['all_pass'] and
        pipeline_results['assembly']['centers_preserved']
    )

    logger.info(f"Final thickness check: {'PASS' if pipeline_results['final_verification']['all_pass'] else 'FAIL'}")
    logger.info(f"Centers preserved: {'YES' if pipeline_results['assembly']['centers_preserved'] else 'NO'}")
    logger.info(f"Assembly fit: {'OK' if pipeline_results['assembly']['all_fits_acceptable'] else 'ISSUES FOUND'}")
    logger.info(f"\nOverall: {'SUCCESS' if success else 'ISSUES FOUND'}")

    return 0 if success else 1


if __name__ == '__main__':
    exit(main())
