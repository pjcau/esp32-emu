#!/usr/bin/env python3
"""
Render Comparison Script
Generates before/after visualizations and assembly renders.
"""

import os
import json
import logging
import numpy as np
import trimesh
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from PIL import Image
import io

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

INPUT_DIR = Path('/app/input')
OUTPUT_DIR = Path('/app/output')
FIXED_DIR = OUTPUT_DIR / 'fixed'
RENDER_DIR = OUTPUT_DIR / 'renders'


class MeshRenderer:
    """Renders 3D meshes to images using trimesh."""

    # Color palette for different parts (RGBA)
    COLORS = [
        [0.8, 0.2, 0.2, 1.0],   # Red
        [0.2, 0.8, 0.2, 1.0],   # Green
        [0.2, 0.2, 0.8, 1.0],   # Blue
        [0.8, 0.8, 0.2, 1.0],   # Yellow
        [0.8, 0.2, 0.8, 1.0],   # Magenta
        [0.2, 0.8, 0.8, 1.0],   # Cyan
        [0.9, 0.5, 0.2, 1.0],   # Orange
        [0.5, 0.2, 0.9, 1.0],   # Purple
        [0.2, 0.9, 0.5, 1.0],   # Teal
    ]

    def __init__(self, resolution: Tuple[int, int] = (1920, 1080)):
        self.resolution = resolution

    def load_mesh(self, filepath: str) -> trimesh.Trimesh:
        """Load mesh from file."""
        mesh = trimesh.load(filepath)
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate(
                [g for g in mesh.geometry.values()]
            )
        return mesh

    def render_mesh(self, mesh: trimesh.Trimesh,
                    color: List[float] = None,
                    angles: Tuple[float, float, float] = (45, 30, 0),
                    background: List[float] = [1, 1, 1, 1]) -> Optional[np.ndarray]:
        """
        Render a single mesh from given angles.
        Returns image as numpy array or None if rendering fails.
        """
        if color:
            mesh.visual.face_colors = np.array(color) * 255

        # Create scene
        scene = trimesh.Scene(mesh)

        # Set camera to view the entire model
        scene.set_camera(angles=angles, distance=mesh.scale * 3)

        try:
            # Try to render using pyrender if available
            png_data = scene.save_image(resolution=self.resolution, visible=False)
            image = Image.open(io.BytesIO(png_data))
            return np.array(image)
        except Exception as e:
            logger.warning(f"Rendering failed: {e}")
            return None

    def render_comparison(self, original_mesh: trimesh.Trimesh,
                          fixed_mesh: trimesh.Trimesh,
                          angles: Tuple[float, float, float] = (45, 30, 0)) -> Optional[np.ndarray]:
        """
        Render side-by-side comparison of original and fixed mesh.
        Original in red, fixed in green.
        """
        # Render original
        original_img = self.render_mesh(
            original_mesh.copy(),
            color=[0.9, 0.3, 0.3, 1.0],
            angles=angles
        )

        # Render fixed
        fixed_img = self.render_mesh(
            fixed_mesh.copy(),
            color=[0.3, 0.9, 0.3, 1.0],
            angles=angles
        )

        if original_img is None or fixed_img is None:
            return None

        # Combine side by side
        combined = np.hstack([original_img, fixed_img])
        return combined

    def render_assembly(self, meshes: Dict[str, trimesh.Trimesh],
                        angles: Tuple[float, float, float] = (45, 30, 0)) -> Optional[np.ndarray]:
        """
        Render all parts together as an assembly.
        Each part gets a different color.
        """
        scene = trimesh.Scene()

        for i, (name, mesh) in enumerate(meshes.items()):
            color_idx = i % len(self.COLORS)
            colored_mesh = mesh.copy()
            colored_mesh.visual.face_colors = np.array(self.COLORS[color_idx]) * 255
            scene.add_geometry(colored_mesh, node_name=name)

        try:
            scene.set_camera(angles=angles)
            png_data = scene.save_image(resolution=self.resolution, visible=False)
            image = Image.open(io.BytesIO(png_data))
            return np.array(image)
        except Exception as e:
            logger.warning(f"Assembly rendering failed: {e}")
            return None

    def render_exploded_view(self, meshes: Dict[str, trimesh.Trimesh],
                             explosion_factor: float = 1.5,
                             angles: Tuple[float, float, float] = (45, 30, 0)) -> Optional[np.ndarray]:
        """
        Render exploded view of assembly.
        Parts are moved away from center based on their position.
        """
        scene = trimesh.Scene()

        # Calculate assembly center
        all_vertices = np.vstack([m.vertices for m in meshes.values()])
        assembly_center = np.mean(all_vertices, axis=0)

        for i, (name, mesh) in enumerate(meshes.items()):
            color_idx = i % len(self.COLORS)
            colored_mesh = mesh.copy()
            colored_mesh.visual.face_colors = np.array(self.COLORS[color_idx]) * 255

            # Move part away from center
            part_center = mesh.centroid
            direction = part_center - assembly_center
            if np.linalg.norm(direction) > 0.1:
                direction = direction / np.linalg.norm(direction)
                explosion_distance = np.linalg.norm(part_center - assembly_center) * explosion_factor
                colored_mesh.apply_translation(direction * explosion_distance)

            scene.add_geometry(colored_mesh, node_name=name)

        try:
            scene.set_camera(angles=angles)
            png_data = scene.save_image(resolution=self.resolution, visible=False)
            image = Image.open(io.BytesIO(png_data))
            return np.array(image)
        except Exception as e:
            logger.warning(f"Exploded view rendering failed: {e}")
            return None

    def create_animation_frames(self, meshes: Dict[str, trimesh.Trimesh],
                                 num_frames: int = 36) -> List[np.ndarray]:
        """
        Create frames for a rotating assembly animation.
        """
        frames = []
        for i in range(num_frames):
            angle = (360 / num_frames) * i
            angles = (angle, 30, 0)
            frame = self.render_assembly(meshes, angles)
            if frame is not None:
                frames.append(frame)
        return frames


def generate_html_report(renders: Dict, output_path: Path):
    """Generate HTML report with all renders embedded."""
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>STL Analysis - Render Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        h1, h2, h3 { color: #333; }
        .section { background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .comparison { display: flex; gap: 20px; align-items: center; }
        .comparison img { max-width: 48%; }
        .assembly img { max-width: 100%; }
        .label { text-align: center; font-weight: bold; margin-bottom: 10px; }
        .original { color: #d33; }
        .fixed { color: #3d3; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background: #4CAF50; color: white; }
        .status-ok { color: green; font-weight: bold; }
        .status-fix { color: red; font-weight: bold; }
    </style>
</head>
<body>
    <h1>STL Wall Thickness Analysis - Visual Report</h1>
    <p>Generated: """ + datetime.now().isoformat() + """</p>
"""

    # Add comparisons section
    if renders.get('comparisons'):
        html += """
    <div class="section">
        <h2>Before / After Comparisons</h2>
        <p>Left: Original (red) | Right: Fixed (green)</p>
"""
        for name, img_path in renders['comparisons'].items():
            html += f"""
        <h3>{name}</h3>
        <img src="{img_path}" style="max-width: 100%;">
"""
        html += "</div>"

    # Add assembly section
    if renders.get('assembly'):
        html += """
    <div class="section">
        <h2>Assembly View</h2>
        <img src=\"""" + renders['assembly'] + """" style="max-width: 100%;">
    </div>
"""

    # Add exploded view
    if renders.get('exploded'):
        html += """
    <div class="section">
        <h2>Exploded View</h2>
        <img src=\"""" + renders['exploded'] + """" style="max-width: 100%;">
    </div>
"""

    # Add multiple angle views
    if renders.get('angles'):
        html += """
    <div class="section">
        <h2>Multiple Angle Views</h2>
        <div style="display: flex; flex-wrap: wrap; gap: 10px;">
"""
        for angle_name, img_path in renders['angles'].items():
            html += f"""
            <div style="flex: 1; min-width: 300px;">
                <h4>{angle_name}</h4>
                <img src="{img_path}" style="max-width: 100%;">
            </div>
"""
        html += "</div></div>"

    html += """
</body>
</html>
"""
    with open(output_path, 'w') as f:
        f.write(html)


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("STL Render Comparison Generator")
    logger.info("=" * 60)

    # Create render directory
    RENDER_DIR.mkdir(parents=True, exist_ok=True)

    renderer = MeshRenderer(resolution=(1280, 720))

    renders = {
        'comparisons': {},
        'angles': {}
    }

    # Load original and fixed parts
    original_parts = {}
    fixed_parts = {}

    if INPUT_DIR.exists():
        for stl_file in INPUT_DIR.glob('*.stl'):
            original_parts[stl_file.stem] = renderer.load_mesh(str(stl_file))
            logger.info(f"Loaded original: {stl_file.name}")

    if FIXED_DIR.exists():
        for stl_file in FIXED_DIR.glob('*.stl'):
            fixed_parts[stl_file.stem] = renderer.load_mesh(str(stl_file))
            logger.info(f"Loaded fixed: {stl_file.name}")

    if not original_parts and not fixed_parts:
        logger.error("No parts found to render!")
        return 1

    # Generate comparison renders for each part
    logger.info("\nGenerating comparison renders...")
    for name in original_parts:
        if name in fixed_parts:
            logger.info(f"Rendering comparison for: {name}")

            # Multiple angles for comparison
            for angle_name, angles in [
                ('front', (0, 0, 0)),
                ('side', (90, 0, 0)),
                ('top', (0, 90, 0)),
                ('iso', (45, 30, 0))
            ]:
                comparison = renderer.render_comparison(
                    original_parts[name],
                    fixed_parts[name],
                    angles=angles
                )
                if comparison is not None:
                    img_path = RENDER_DIR / f"{name}_comparison_{angle_name}.png"
                    Image.fromarray(comparison).save(img_path)
                    renders['comparisons'][f"{name}_{angle_name}"] = img_path.name

    # Generate assembly render
    parts_to_render = fixed_parts if fixed_parts else original_parts

    if parts_to_render:
        logger.info("\nRendering assembly view...")
        assembly_img = renderer.render_assembly(parts_to_render, angles=(45, 30, 0))
        if assembly_img is not None:
            img_path = RENDER_DIR / "assembly_view.png"
            Image.fromarray(assembly_img).save(img_path)
            renders['assembly'] = img_path.name

        # Multiple assembly angles
        for angle_name, angles in [
            ('front', (0, 0, 0)),
            ('back', (180, 0, 0)),
            ('left', (90, 0, 0)),
            ('right', (-90, 0, 0)),
            ('top', (0, 90, 0)),
            ('bottom', (0, -90, 0)),
        ]:
            img = renderer.render_assembly(parts_to_render, angles=angles)
            if img is not None:
                img_path = RENDER_DIR / f"assembly_{angle_name}.png"
                Image.fromarray(img).save(img_path)
                renders['angles'][angle_name] = img_path.name

        # Exploded view
        logger.info("Rendering exploded view...")
        exploded_img = renderer.render_exploded_view(parts_to_render, explosion_factor=1.5)
        if exploded_img is not None:
            img_path = RENDER_DIR / "assembly_exploded.png"
            Image.fromarray(exploded_img).save(img_path)
            renders['exploded'] = img_path.name

    # Generate HTML report
    html_path = RENDER_DIR / "render_report.html"
    generate_html_report(renders, html_path)
    logger.info(f"HTML report saved to: {html_path}")

    # Save render manifest
    manifest_path = RENDER_DIR / "render_manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump({
            'render_date': datetime.now().isoformat(),
            'renders': renders,
            'num_parts_rendered': len(parts_to_render),
            'resolution': renderer.resolution
        }, f, indent=2)

    logger.info(f"\nRenders saved to: {RENDER_DIR}")
    logger.info(f"Total comparison renders: {len(renders['comparisons'])}")
    logger.info(f"Assembly views: {len(renders['angles'])}")

    return 0


if __name__ == '__main__':
    exit(main())
