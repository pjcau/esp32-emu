#!/usr/bin/env python3
"""
Download Reference Files Script
Downloads hardware reference files from esplay-hardware GitHub repo.
"""

import os
import logging
import subprocess
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

REFERENCE_DIR = Path('/app/reference')
GITHUB_REPO = "https://github.com/pebri86/esplay-hardware.git"


def download_reference_files():
    """Download reference files from esplay-hardware repo."""
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)

    repo_dir = REFERENCE_DIR / "esplay-hardware"

    if repo_dir.exists():
        logger.info("Reference repo already exists, pulling updates...")
        try:
            subprocess.run(
                ["git", "-C", str(repo_dir), "pull"],
                check=True,
                capture_output=True
            )
        except subprocess.CalledProcessError as e:
            logger.warning(f"Could not pull updates: {e}")
    else:
        logger.info(f"Cloning {GITHUB_REPO}...")
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", GITHUB_REPO, str(repo_dir)],
                check=True,
                capture_output=True
            )
            logger.info("Clone successful!")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clone repo: {e}")
            return False

    # List available files
    logger.info("\nAvailable reference files:")
    for f in repo_dir.rglob("*"):
        if f.is_file() and f.suffix.lower() in ['.stl', '.step', '.dxf', '.kicad_pcb', '.kicad_mod']:
            logger.info(f"  {f.relative_to(repo_dir)}")

    return True


if __name__ == '__main__':
    exit(0 if download_reference_files() else 1)
