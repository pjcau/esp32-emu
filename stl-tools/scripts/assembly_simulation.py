#!/usr/bin/env python3
"""
Assembly Simulation Script
Creates animated assembly/disassembly simulation of all parts.
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

OUTPUT_DIR = Path('/app/output')
FIXED_DIR = OUTPUT_DIR / 'fixed'
INPUT_DIR = Path('/app/input')
SIMULATION_DIR = OUTPUT_DIR / 'simulation'


# Color palette for different parts
PART_COLORS = {
    'frame': [0.6, 0.6, 0.6, 1.0],        # Gray (main frame)
    'top_cover': [0.2, 0.6, 0.9, 1.0],    # Blue
    'back_cover': [0.2, 0.5, 0.8, 1.0],   # Darker blue
    'd_Pad': [0.9, 0.2, 0.2, 1.0],        # Red
    'A_B': [0.2, 0.9, 0.2, 1.0],          # Green
    'L_R': [0.9, 0.9, 0.2, 1.0],          # Yellow
    'start_select': [0.9, 0.5, 0.2, 1.0], # Orange
    'menu': [0.7, 0.2, 0.9, 1.0],         # Purple
    'power': [0.2, 0.9, 0.9, 1.0],        # Cyan
}


class AssemblySimulator:
    """Creates assembly/disassembly animations."""

    def __init__(self, resolution: Tuple[int, int] = (1920, 1080)):
        self.resolution = resolution
        self.parts: Dict[str, trimesh.Trimesh] = {}
        self.assembly_order = []  # Order in which parts are assembled

    def load_parts(self, directory: Path):
        """Load all STL parts from directory."""
        for stl_file in sorted(directory.glob('*.stl')):
            mesh = trimesh.load(str(stl_file))
            if isinstance(mesh, trimesh.Scene):
                mesh = trimesh.util.concatenate(
                    [g for g in mesh.geometry.values()]
                )

            name = stl_file.stem
            self.parts[name] = mesh
            logger.info(f"Loaded: {name}")

        # Define assembly order (typically from inside out)
        self.assembly_order = [
            'frame',       # Base frame first
            'd_Pad',       # D-pad into frame
            'A_B',         # A/B buttons
            'L_R',         # L/R shoulder buttons
            'start_select', # Start/select buttons
            'menu',        # Menu button
            'power',       # Power button
            'top_cover',   # Top cover
            'back_cover',  # Back cover last
        ]

        # Filter to only parts we have
        self.assembly_order = [p for p in self.assembly_order if p in self.parts]

        # Add any remaining parts not in the predefined order
        for name in self.parts:
            if name not in self.assembly_order:
                self.assembly_order.append(name)

    def get_part_color(self, name: str) -> List[float]:
        """Get color for a part."""
        if name in PART_COLORS:
            return PART_COLORS[name]
        # Default color based on hash
        hash_val = hash(name) % 1000
        return [
            0.3 + (hash_val % 7) * 0.1,
            0.3 + ((hash_val // 7) % 7) * 0.1,
            0.3 + ((hash_val // 49) % 7) * 0.1,
            1.0
        ]

    def calculate_explosion_positions(self, explosion_factor: float = 2.0) -> Dict[str, np.ndarray]:
        """Calculate exploded positions for each part."""
        positions = {}

        # Calculate assembly center
        all_vertices = np.vstack([m.vertices for m in self.parts.values()])
        assembly_center = np.mean(all_vertices, axis=0)

        for name, mesh in self.parts.items():
            part_center = mesh.centroid
            direction = part_center - assembly_center

            # Add vertical offset based on assembly order
            if name in self.assembly_order:
                order_idx = self.assembly_order.index(name)
                vertical_offset = np.array([0, 0, order_idx * 5])  # 5mm per part
            else:
                vertical_offset = np.array([0, 0, 0])

            if np.linalg.norm(direction) > 0.1:
                direction = direction / np.linalg.norm(direction)
                offset = direction * explosion_factor * 10 + vertical_offset
            else:
                offset = vertical_offset

            positions[name] = offset

        return positions

    def render_frame(self, visible_parts: List[str],
                     part_positions: Dict[str, np.ndarray],
                     angles: Tuple[float, float, float] = (45, 30, 0),
                     interpolation: float = 1.0) -> Optional[np.ndarray]:
        """
        Render a single frame of the assembly.

        Args:
            visible_parts: List of part names to render
            part_positions: Exploded position offsets
            angles: Camera angles
            interpolation: 0.0 = assembled, 1.0 = fully exploded
        """
        scene = trimesh.Scene()

        for name in visible_parts:
            if name not in self.parts:
                continue

            mesh = self.parts[name].copy()

            # Apply color
            color = self.get_part_color(name)
            mesh.visual.face_colors = np.array(color) * 255

            # Apply position interpolation
            if name in part_positions:
                offset = part_positions[name] * interpolation
                mesh.apply_translation(offset)

            scene.add_geometry(mesh, node_name=name)

        try:
            scene.set_camera(angles=angles)
            png_data = scene.save_image(resolution=self.resolution, visible=False)
            image = Image.open(io.BytesIO(png_data))
            return np.array(image)
        except Exception as e:
            logger.warning(f"Frame render failed: {e}")
            return None

    def create_assembly_animation(self, output_dir: Path,
                                   num_frames_per_part: int = 10,
                                   rotation_frames: int = 36) -> List[Path]:
        """
        Create assembly animation frames.
        Shows parts being added one by one.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        frames_saved = []

        explosion_positions = self.calculate_explosion_positions()
        frame_number = 0

        # Initial exploded view rotation
        logger.info("Creating initial exploded view rotation...")
        for i in range(rotation_frames):
            angle = (360 / rotation_frames) * i
            img = self.render_frame(
                self.assembly_order,
                explosion_positions,
                angles=(angle, 30, 0),
                interpolation=1.0
            )
            if img is not None:
                path = output_dir / f"frame_{frame_number:04d}.png"
                Image.fromarray(img).save(path)
                frames_saved.append(path)
                frame_number += 1

        # Assembly sequence
        logger.info("Creating assembly sequence...")
        visible_parts = []

        for part_name in self.assembly_order:
            visible_parts.append(part_name)
            logger.info(f"Adding part: {part_name}")

            # Animate this part coming in
            for i in range(num_frames_per_part):
                # Interpolation from exploded (1.0) to assembled (0.0)
                interp = 1.0 - (i / (num_frames_per_part - 1)) if num_frames_per_part > 1 else 0.0

                # Only interpolate the new part, others stay assembled
                current_positions = {}
                for name in visible_parts:
                    if name == part_name:
                        current_positions[name] = explosion_positions.get(name, np.zeros(3))
                    else:
                        current_positions[name] = np.zeros(3)

                img = self.render_frame(
                    visible_parts,
                    current_positions,
                    angles=(45, 30, 0),
                    interpolation=interp if name == part_name else 0.0
                )
                if img is not None:
                    path = output_dir / f"frame_{frame_number:04d}.png"
                    Image.fromarray(img).save(path)
                    frames_saved.append(path)
                    frame_number += 1

        # Final assembled view rotation
        logger.info("Creating final assembled rotation...")
        for i in range(rotation_frames):
            angle = (360 / rotation_frames) * i
            img = self.render_frame(
                self.assembly_order,
                explosion_positions,
                angles=(angle, 30, 0),
                interpolation=0.0
            )
            if img is not None:
                path = output_dir / f"frame_{frame_number:04d}.png"
                Image.fromarray(img).save(path)
                frames_saved.append(path)
                frame_number += 1

        return frames_saved

    def create_disassembly_animation(self, output_dir: Path,
                                      num_frames: int = 60) -> List[Path]:
        """
        Create smooth disassembly animation.
        All parts gradually move to exploded positions.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        frames_saved = []

        explosion_positions = self.calculate_explosion_positions()

        for i in range(num_frames):
            interp = i / (num_frames - 1) if num_frames > 1 else 1.0

            # Also rotate slightly during disassembly
            angle = 45 + (interp * 30)

            img = self.render_frame(
                list(self.parts.keys()),
                explosion_positions,
                angles=(angle, 30 - interp * 10, 0),
                interpolation=interp
            )
            if img is not None:
                path = output_dir / f"disassembly_{i:04d}.png"
                Image.fromarray(img).save(path)
                frames_saved.append(path)

        return frames_saved

    def create_rotation_animation(self, output_dir: Path,
                                   num_frames: int = 72,
                                   exploded: bool = False) -> List[Path]:
        """Create 360-degree rotation animation."""
        output_dir.mkdir(parents=True, exist_ok=True)
        frames_saved = []

        explosion_positions = self.calculate_explosion_positions()
        interp = 1.0 if exploded else 0.0

        for i in range(num_frames):
            angle = (360 / num_frames) * i

            img = self.render_frame(
                list(self.parts.keys()),
                explosion_positions,
                angles=(angle, 30, 0),
                interpolation=interp
            )
            if img is not None:
                suffix = "exploded" if exploded else "assembled"
                path = output_dir / f"rotation_{suffix}_{i:04d}.png"
                Image.fromarray(img).save(path)
                frames_saved.append(path)

        return frames_saved

    def create_gif(self, frames: List[Path], output_path: Path,
                   duration: int = 50):
        """Create animated GIF from frames."""
        if not frames:
            logger.warning("No frames to create GIF")
            return

        images = []
        for frame_path in frames:
            try:
                img = Image.open(frame_path)
                images.append(img.copy())
                img.close()
            except Exception as e:
                logger.warning(f"Could not load frame {frame_path}: {e}")

        if images:
            images[0].save(
                output_path,
                save_all=True,
                append_images=images[1:],
                duration=duration,
                loop=0
            )
            logger.info(f"Created GIF: {output_path}")


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Assembly Simulation Generator")
    logger.info("=" * 60)

    SIMULATION_DIR.mkdir(parents=True, exist_ok=True)

    simulator = AssemblySimulator(resolution=(1280, 720))

    # Load parts (prefer fixed, fall back to original)
    if FIXED_DIR.exists() and list(FIXED_DIR.glob('*.stl')):
        logger.info("Loading fixed parts...")
        simulator.load_parts(FIXED_DIR)
    elif INPUT_DIR.exists():
        logger.info("Loading original parts...")
        simulator.load_parts(INPUT_DIR)
    else:
        logger.error("No parts found!")
        return 1

    logger.info(f"Loaded {len(simulator.parts)} parts")
    logger.info(f"Assembly order: {simulator.assembly_order}")

    # Create various animations
    animations = {}

    # Rotation animation (assembled)
    logger.info("\n1. Creating assembled rotation animation...")
    rotation_dir = SIMULATION_DIR / "rotation_assembled"
    frames = simulator.create_rotation_animation(rotation_dir, num_frames=36, exploded=False)
    if frames:
        gif_path = SIMULATION_DIR / "rotation_assembled.gif"
        simulator.create_gif(frames, gif_path, duration=80)
        animations['rotation_assembled'] = str(gif_path)

    # Rotation animation (exploded)
    logger.info("\n2. Creating exploded rotation animation...")
    rotation_dir = SIMULATION_DIR / "rotation_exploded"
    frames = simulator.create_rotation_animation(rotation_dir, num_frames=36, exploded=True)
    if frames:
        gif_path = SIMULATION_DIR / "rotation_exploded.gif"
        simulator.create_gif(frames, gif_path, duration=80)
        animations['rotation_exploded'] = str(gif_path)

    # Disassembly animation
    logger.info("\n3. Creating disassembly animation...")
    disasm_dir = SIMULATION_DIR / "disassembly"
    frames = simulator.create_disassembly_animation(disasm_dir, num_frames=30)
    if frames:
        gif_path = SIMULATION_DIR / "disassembly.gif"
        simulator.create_gif(frames, gif_path, duration=100)
        animations['disassembly'] = str(gif_path)

    # Full assembly animation (longer, more detailed)
    logger.info("\n4. Creating full assembly animation...")
    assembly_dir = SIMULATION_DIR / "assembly"
    frames = simulator.create_assembly_animation(assembly_dir, num_frames_per_part=8, rotation_frames=18)
    if frames:
        gif_path = SIMULATION_DIR / "assembly.gif"
        simulator.create_gif(frames, gif_path, duration=60)
        animations['assembly'] = str(gif_path)

    # Save manifest
    manifest = {
        'generation_date': datetime.now().isoformat(),
        'num_parts': len(simulator.parts),
        'parts': list(simulator.parts.keys()),
        'assembly_order': simulator.assembly_order,
        'animations': animations
    }

    manifest_path = SIMULATION_DIR / "simulation_manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    # Create HTML viewer
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Assembly Simulation - ESPlay Micro V2</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }}
        h1, h2 {{ color: #00d9ff; }}
        .section {{ background: #16213e; padding: 20px; margin: 20px 0; border-radius: 8px; }}
        .animation {{ text-align: center; margin: 20px 0; }}
        .animation img {{ max-width: 100%; border: 2px solid #00d9ff; border-radius: 4px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }}
        .part-list {{ columns: 3; }}
        .part-list li {{ color: #888; }}
    </style>
</head>
<body>
    <h1>Assembly Simulation - ESPlay Micro V2 Case</h1>
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

    <div class="section">
        <h2>Parts ({len(simulator.parts)})</h2>
        <ul class="part-list">
            {"".join(f"<li>{name}</li>" for name in simulator.assembly_order)}
        </ul>
    </div>

    <div class="section">
        <h2>Animations</h2>
        <div class="grid">
            <div class="animation">
                <h3>Assembled View (360°)</h3>
                <img src="rotation_assembled.gif" alt="Assembled rotation">
            </div>
            <div class="animation">
                <h3>Exploded View (360°)</h3>
                <img src="rotation_exploded.gif" alt="Exploded rotation">
            </div>
            <div class="animation">
                <h3>Disassembly Animation</h3>
                <img src="disassembly.gif" alt="Disassembly">
            </div>
            <div class="animation">
                <h3>Assembly Sequence</h3>
                <img src="assembly.gif" alt="Assembly sequence">
            </div>
        </div>
    </div>
</body>
</html>
"""

    html_path = SIMULATION_DIR / "simulation_viewer.html"
    with open(html_path, 'w') as f:
        f.write(html_content)

    logger.info(f"\nSimulation files saved to: {SIMULATION_DIR}")
    logger.info(f"Open {html_path} in a browser to view animations")

    return 0


if __name__ == '__main__':
    exit(main())
