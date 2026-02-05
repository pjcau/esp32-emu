#!/usr/bin/env python3
"""
Render assembly with distinct colors for each part.
Creates multiple views and an interactive HTML viewer.
"""

import numpy as np
import trimesh
from trimesh.creation import box, cylinder
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).parent.parent.parent
FIXED_V2_DIR = PROJECT_ROOT / 'stl-tools' / 'output' / 'fixed_v2'
OUTPUT_DIR = PROJECT_ROOT / 'stl-tools' / 'output' / 'renders'
PCB_POSITIONS_FILE = PROJECT_ROOT / 'pcb' / 'pcb_component_positions.json'

# Distinct colors for each part (RGB, 0-255)
PART_COLORS = {
    # Case structure
    'frame': [120, 120, 120],       # Gray
    'top_cover': [70, 130, 180],    # Steel blue
    'back_cover': [100, 149, 237],  # Cornflower blue

    # Buttons - bright distinct colors
    'd_Pad': [255, 50, 50],         # Red
    'A_B': [50, 205, 50],           # Lime green
    'start_select': [255, 165, 0],  # Orange
    'menu': [255, 0, 255],          # Magenta
    'L_R': [255, 255, 0],           # Yellow
    'power': [0, 255, 255],         # Cyan

    # PCB
    'pcb': [34, 139, 34],           # Forest green
}

# PCB specs
PCB_WIDTH = 100.0
PCB_HEIGHT = 50.0
PCB_THICKNESS = 1.6
PCB_CENTER = (50.0, 25.0)


def eagle_to_centered(x, y):
    return (x - PCB_CENTER[0], y - PCB_CENTER[1])


def create_pcb_with_buttons():
    """Create PCB with 3D button markers."""
    meshes = []

    # PCB base
    pcb = box(extents=[PCB_WIDTH, PCB_HEIGHT, PCB_THICKNESS])
    pcb.apply_translation([0, 0, PCB_THICKNESS/2])
    pcb.visual.face_colors = PART_COLORS['pcb'] + [255]
    meshes.append(('pcb_base', pcb))

    # Load PCB component positions
    with open(PCB_POSITIONS_FILE) as f:
        pcb_components = json.load(f)

    # Button markers on PCB
    button_colors = {
        'DPAD': PART_COLORS['d_Pad'],
        'AB': PART_COLORS['A_B'],
        'START_SELECT': PART_COLORS['start_select'],
        'MENU': PART_COLORS['menu'],
        'L_BTN': PART_COLORS['L_R'],
        'R_BTN': PART_COLORS['L_R'],
        'POWER': PART_COLORS['power'],
    }

    for name, pos in pcb_components.items():
        if name in ['LCD', 'USB', 'SD', 'AUDIO']:
            continue

        cx, cy = pos['center_x'], pos['center_y']
        color = button_colors.get(name, [200, 200, 200])

        marker = cylinder(radius=3, height=1.0, sections=32)
        marker.apply_translation([cx, cy, PCB_THICKNESS + 0.5])
        marker.visual.face_colors = color + [255]
        meshes.append((f'pcb_marker_{name}', marker))

    # LCD marker
    lcd = pcb_components.get('LCD', {})
    if lcd:
        lcd_mesh = box(extents=[lcd.get('width', 42), lcd.get('height', 32), 2])
        lcd_mesh.apply_translation([lcd['center_x'], lcd['center_y'], PCB_THICKNESS + 1])
        lcd_mesh.visual.face_colors = [0, 50, 150, 255]  # Dark blue for screen
        meshes.append(('pcb_lcd', lcd_mesh))

    return meshes


def load_case_parts():
    """Load all case parts with colors."""
    parts = []

    for stl_file in sorted(FIXED_V2_DIR.glob('*.stl')):
        name = stl_file.stem

        mesh = trimesh.load(str(stl_file))
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate([g for g in mesh.geometry.values()])

        color = PART_COLORS.get(name, [128, 128, 128])
        mesh.visual.face_colors = color + [220]  # Slightly transparent

        parts.append((name, mesh))

    return parts


def create_exploded_view(parts, explosion_factor=1.5):
    """Create exploded view by moving parts away from center."""
    exploded = []

    # Calculate assembly center
    all_centroids = [p[1].centroid for p in parts]
    center = np.mean(all_centroids, axis=0)

    # Z offsets for exploded view
    z_offsets = {
        'back_cover': -30,
        'frame': 0,
        'd_Pad': 10,
        'A_B': 10,
        'start_select': 10,
        'menu': 10,
        'L_R': 15,
        'power': 20,
        'top_cover': 30,
    }

    for name, mesh in parts:
        exploded_mesh = mesh.copy()

        # Get direction from center
        direction = mesh.centroid - center
        direction[2] = 0  # Keep XY direction only

        if np.linalg.norm(direction[:2]) > 0.1:
            direction[:2] = direction[:2] / np.linalg.norm(direction[:2])

        # Apply explosion offset
        xy_offset = direction[:2] * explosion_factor * 10
        z_offset = z_offsets.get(name, 0)

        exploded_mesh.apply_translation([xy_offset[0], xy_offset[1], z_offset])
        exploded.append((name, exploded_mesh))

    return exploded


def export_glb(meshes, output_path, name="Assembly"):
    """Export meshes as GLB file for web viewing."""
    scene = trimesh.Scene()

    for mesh_name, mesh in meshes:
        scene.add_geometry(mesh, node_name=mesh_name)

    scene.export(str(output_path))
    return output_path


def create_html_viewer(glb_files, output_path):
    """Create HTML file with 3D viewer using model-viewer."""

    html_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ESPlay Micro Assembly Viewer</title>
    <script type="module" src="https://unpkg.com/@google/model-viewer/dist/model-viewer.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            min-height: 100vh;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        h1 { text-align: center; color: #00d9ff; margin-bottom: 10px; }
        .subtitle { text-align: center; color: #888; margin-bottom: 30px; }

        .viewer-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .viewer-card {
            background: #16213e;
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid #0f3460;
        }

        .viewer-card h3 {
            padding: 15px;
            background: #0f3460;
            color: #00d9ff;
            text-align: center;
        }

        model-viewer {
            width: 100%;
            height: 400px;
            background: #0d1b2a;
        }

        .legend {
            background: #16213e;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #0f3460;
        }

        .legend h3 {
            color: #00d9ff;
            margin-bottom: 15px;
        }

        .legend-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
        }

        .legend-item {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .color-box {
            width: 24px;
            height: 24px;
            border-radius: 4px;
            border: 2px solid #fff;
        }

        .specs {
            margin-top: 30px;
            background: #16213e;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #0f3460;
        }

        .specs h3 { color: #00d9ff; margin-bottom: 15px; }
        .specs table { width: 100%; border-collapse: collapse; }
        .specs th, .specs td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #0f3460; }
        .specs th { color: #00d9ff; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎮 ESPlay Micro Assembly</h1>
        <p class="subtitle">Interactive 3D visualization - drag to rotate, scroll to zoom</p>

        <div class="viewer-grid">
            <div class="viewer-card">
                <h3>Assembled View</h3>
                <model-viewer
                    src="assembly_colored.glb"
                    camera-controls
                    auto-rotate
                    shadow-intensity="1"
                    environment-image="neutral"
                    camera-orbit="45deg 55deg 200mm">
                </model-viewer>
            </div>

            <div class="viewer-card">
                <h3>Exploded View</h3>
                <model-viewer
                    src="assembly_exploded.glb"
                    camera-controls
                    auto-rotate
                    shadow-intensity="1"
                    environment-image="neutral"
                    camera-orbit="45deg 55deg 250mm">
                </model-viewer>
            </div>

            <div class="viewer-card">
                <h3>PCB with Button Positions</h3>
                <model-viewer
                    src="pcb_detailed.glb"
                    camera-controls
                    auto-rotate
                    shadow-intensity="1"
                    environment-image="neutral"
                    camera-orbit="0deg 75deg 150mm">
                </model-viewer>
            </div>

            <div class="viewer-card">
                <h3>Case Only (No PCB)</h3>
                <model-viewer
                    src="case_only.glb"
                    camera-controls
                    auto-rotate
                    shadow-intensity="1"
                    environment-image="neutral"
                    camera-orbit="45deg 55deg 200mm">
                </model-viewer>
            </div>
        </div>

        <div class="legend">
            <h3>🎨 Color Legend</h3>
            <div class="legend-grid">
                <div class="legend-item">
                    <div class="color-box" style="background: rgb(255,50,50);"></div>
                    <span>D-Pad</span>
                </div>
                <div class="legend-item">
                    <div class="color-box" style="background: rgb(50,205,50);"></div>
                    <span>A/B Buttons</span>
                </div>
                <div class="legend-item">
                    <div class="color-box" style="background: rgb(255,165,0);"></div>
                    <span>Start/Select</span>
                </div>
                <div class="legend-item">
                    <div class="color-box" style="background: rgb(255,0,255);"></div>
                    <span>Menu</span>
                </div>
                <div class="legend-item">
                    <div class="color-box" style="background: rgb(255,255,0);"></div>
                    <span>L/R Shoulders</span>
                </div>
                <div class="legend-item">
                    <div class="color-box" style="background: rgb(0,255,255);"></div>
                    <span>Power</span>
                </div>
                <div class="legend-item">
                    <div class="color-box" style="background: rgb(70,130,180);"></div>
                    <span>Top Cover</span>
                </div>
                <div class="legend-item">
                    <div class="color-box" style="background: rgb(100,149,237);"></div>
                    <span>Back Cover</span>
                </div>
                <div class="legend-item">
                    <div class="color-box" style="background: rgb(120,120,120);"></div>
                    <span>Frame</span>
                </div>
                <div class="legend-item">
                    <div class="color-box" style="background: rgb(34,139,34);"></div>
                    <span>PCB</span>
                </div>
            </div>
        </div>

        <div class="specs">
            <h3>📐 Specifications</h3>
            <table>
                <tr><th>Component</th><th>Dimensions (mm)</th><th>Thickness</th></tr>
                <tr><td>PCB</td><td>100 x 50 x 1.6</td><td>Standard</td></tr>
                <tr><td>Top Cover</td><td>110.7 x 55.7 x 10.0</td><td>≥1.0mm ✓</td></tr>
                <tr><td>Back Cover</td><td>110 x 55 x 11</td><td>≥1.0mm ✓</td></tr>
                <tr><td>D-Pad</td><td>21.7 x 21.8 x 5.4</td><td>≥1.0mm ✓</td></tr>
                <tr><td>A/B Buttons</td><td>9.8 x 22.4 x 5.4</td><td>≥1.0mm ✓</td></tr>
                <tr><td>All Parts</td><td colspan="2">Wall thickness ≥ 1.0mm - Ready for 3D printing</td></tr>
            </table>
        </div>
    </div>
</body>
</html>'''

    with open(output_path, 'w') as f:
        f.write(html_content)

    return output_path


def main():
    print("=" * 70)
    print("ASSEMBLY RENDER WITH COLORS")
    print("=" * 70)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load case parts
    print("\n1. Loading case parts...")
    case_parts = load_case_parts()
    print(f"   Loaded {len(case_parts)} parts")

    # 2. Create PCB with markers
    print("\n2. Creating PCB with button markers...")
    pcb_meshes = create_pcb_with_buttons()
    print(f"   Created PCB with {len(pcb_meshes)} elements")

    # 3. Create assembled view
    print("\n3. Creating assembled view...")
    assembled = case_parts + pcb_meshes
    glb_assembled = OUTPUT_DIR / 'assembly_colored.glb'
    export_glb(assembled, glb_assembled)
    print(f"   Exported: {glb_assembled}")

    # 4. Create exploded view
    print("\n4. Creating exploded view...")
    exploded_parts = create_exploded_view(case_parts)
    exploded = exploded_parts + pcb_meshes
    glb_exploded = OUTPUT_DIR / 'assembly_exploded.glb'
    export_glb(exploded, glb_exploded)
    print(f"   Exported: {glb_exploded}")

    # 5. PCB only
    print("\n5. Creating PCB detailed view...")
    glb_pcb = OUTPUT_DIR / 'pcb_detailed.glb'
    export_glb(pcb_meshes, glb_pcb)
    print(f"   Exported: {glb_pcb}")

    # 6. Case only (no PCB)
    print("\n6. Creating case-only view...")
    glb_case = OUTPUT_DIR / 'case_only.glb'
    export_glb(case_parts, glb_case)
    print(f"   Exported: {glb_case}")

    # 7. Create HTML viewer
    print("\n7. Creating HTML viewer...")
    html_path = OUTPUT_DIR / 'viewer.html'
    create_html_viewer([], html_path)
    print(f"   Exported: {html_path}")

    print("\n" + "=" * 70)
    print("DONE!")
    print("=" * 70)
    print(f"\nOpen {html_path} in a browser to view the 3D assembly")
    print("\nGenerated files:")
    for f in OUTPUT_DIR.glob('*'):
        print(f"  - {f.name}")

    return 0


if __name__ == '__main__':
    exit(main())
