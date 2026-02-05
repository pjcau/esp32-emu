#!/usr/bin/env python3
"""
Generate 3D model of ESPlay Micro PCB with all components.
Parses Eagle .brd file for accurate component positions.
Based on the reference image from A3602.pdf
"""

import numpy as np
import trimesh
from trimesh.creation import box, cylinder
from pathlib import Path
import json
import xml.etree.ElementTree as ET
import re

# Paths
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR.parent / 'output'
PCB_DIR = SCRIPT_DIR.parent.parent / 'pcb'
BRD_FILE = PCB_DIR / 'new_esplay.brd'

# PCB Dimensions
PCB_THICKNESS = 1.6  # mm

# Colors (RGBA)
COLORS = {
    'pcb': [34, 139, 34, 255],           # Green PCB
    'copper': [184, 134, 11, 255],        # Gold/copper pads
    'button': [192, 192, 192, 255],       # Silver tactile buttons
    'button_cap': [255, 215, 0, 255],     # Gold button center
    'lcd_frame': [220, 220, 220, 255],    # Silver LCD frame
    'lcd_screen': [40, 40, 50, 255],      # Dark LCD screen
    'lcd_ribbon': [30, 60, 180, 255],     # Blue ribbon cable
    'usb': [200, 200, 200, 255],          # USB connector
    'audio': [50, 50, 50, 255],           # Audio jack
    'mounting_hole': [200, 170, 80, 255], # Mounting holes (brass)
    'led': [255, 0, 0, 255],              # Red LED
    'switch': [255, 50, 50, 255],         # Red switch
    'ic': [30, 30, 30, 255],              # Black IC
    'esp32': [40, 40, 40, 255],           # ESP32 module
    'capacitor': [180, 140, 80, 255],     # Tan capacitor
    'resistor': [30, 30, 30, 255],        # Black resistor
    'connector': [250, 250, 240, 255],    # White connector
}


def parse_eagle_brd(brd_file):
    """Parse Eagle .brd file to extract PCB dimensions and component positions."""
    print(f"Parsing Eagle file: {brd_file}")

    tree = ET.parse(brd_file)
    root = tree.getroot()

    # Find board dimensions from plain/wire elements on dimension layer (20)
    x_coords = []
    y_coords = []

    # Look for wires on dimension layer
    for wire in root.findall('.//plain/wire'):
        if wire.get('layer') == '20':  # Dimension layer
            x1 = float(wire.get('x1', 0))
            y1 = float(wire.get('y1', 0))
            x2 = float(wire.get('x2', 0))
            y2 = float(wire.get('y2', 0))
            x_coords.extend([x1, x2])
            y_coords.extend([y1, y2])

    if x_coords and y_coords:
        pcb_width = max(x_coords) - min(x_coords)
        pcb_height = max(y_coords) - min(y_coords)
        pcb_center_x = (max(x_coords) + min(x_coords)) / 2
        pcb_center_y = (max(y_coords) + min(y_coords)) / 2
    else:
        pcb_width = 100.0
        pcb_height = 50.0
        pcb_center_x = 50.0
        pcb_center_y = 25.0

    print(f"  PCB dimensions: {pcb_width:.1f} x {pcb_height:.1f} mm")
    print(f"  PCB center: ({pcb_center_x:.1f}, {pcb_center_y:.1f})")

    # Extract component positions
    components = []

    for element in root.findall('.//elements/element'):
        name = element.get('name', '')
        package = element.get('package', '')
        x = float(element.get('x', 0))
        y = float(element.get('y', 0))
        rot = element.get('rot', 'R0')

        # Parse rotation and layer
        # Components with 'M' prefix in rotation (MR0, MR90, etc.) are on BOTTOM layer
        rotation = 0
        layer = 'TOP'  # Default to TOP
        if rot:
            if rot.startswith('M'):
                layer = 'BOTTOM'
            match = re.search(r'R(\d+)', rot)
            if match:
                rotation = int(match.group(1))

        # Center coordinates relative to PCB center
        rel_x = x - pcb_center_x
        rel_y = y - pcb_center_y

        # Determine component type from name/package
        comp_type = classify_component(name, package)

        components.append({
            'name': name,
            'package': package,
            'x': rel_x,
            'y': rel_y,
            'rotation': rotation,
            'rot_raw': rot,  # Keep raw rotation for debugging
            'layer': layer,  # TOP or BOTTOM
            'type': comp_type,
            'abs_x': x,
            'abs_y': y,
        })

    # Count components by layer
    top_count = sum(1 for c in components if c['layer'] == 'TOP')
    bottom_count = sum(1 for c in components if c['layer'] == 'BOTTOM')
    print(f"  Found {len(components)} components")
    print(f"    TOP layer: {top_count}")
    print(f"    BOTTOM layer: {bottom_count}")

    # Print TOP components for verification
    print("\n  TOP layer components:")
    for c in components:
        if c['layer'] == 'TOP':
            print(f"    - {c['name']} ({c['type']}) at ({c['abs_x']:.1f}, {c['abs_y']:.1f})")

    return {
        'width': pcb_width,
        'height': pcb_height,
        'center_x': pcb_center_x,
        'center_y': pcb_center_y,
        'components': components,
    }


def classify_component(name, package):
    """Classify component type based on name and package."""
    name_upper = name.upper()
    package_upper = package.upper()

    # ESP32 module (A1 with ESP32-WROVER package)
    if 'ESP32' in package_upper or 'WROVER' in package_upper or 'WROOM' in package_upper:
        return 'esp32'

    # Tactile buttons (S1-S9, S11 with TACTILE_SWITCH package)
    if name_upper.startswith('S') and 'TACTILE' in package_upper:
        if 'RIGHT_ANGLE' in package_upper:
            return 'shoulder_button'  # S10, S12 - L/R shoulder buttons
        else:
            return 'button'

    # Power switch (S13 with SPST package)
    if name_upper.startswith('S') and 'SPST' in package_upper:
        return 'slide_switch'

    # LCD display
    if 'LCD' in name_upper or 'ILI9341' in package_upper:
        return 'lcd'

    # USB connector (J3) - but not USB_LOGO
    if 'USB' in package_upper and 'LOGO' not in package_upper:
        return 'usb'

    # Audio jack (J5)
    if 'AUDIO' in package_upper:
        return 'audio_jack'

    # SD card slot (J1)
    if 'MICROSD' in package_upper:
        return 'sd_card'

    # Mounting holes (H1-H4)
    if name_upper.startswith('H') and 'MOUNTING' in package_upper:
        return 'mounting_hole'

    # LEDs (D1 with LED package)
    if 'LED' in package_upper:
        return 'led'

    # Capacitors (C1-C27)
    if name_upper.startswith('C') and len(name_upper) <= 3:
        return 'capacitor'

    # Resistors (R1-R43)
    if name_upper.startswith('R') and len(name_upper) <= 3:
        return 'resistor'

    # Crystals
    if name_upper.startswith('Y') or 'CRYSTAL' in package_upper:
        return 'crystal'

    # ICs (U1-U8, but not U$1 logos)
    if name_upper.startswith('U') and not name_upper.startswith('U$'):
        return 'ic'

    # Battery connector (J4 with JST)
    if 'JST' in package_upper:
        return 'battery_connector'

    # Logos/silkscreen - skip these
    if 'LOGO' in package_upper or name_upper.startswith('U$'):
        return 'logo'

    # Test points
    if name_upper.startswith('TP'):
        return 'testpoint'

    # Transistors (T1-T3)
    if name_upper.startswith('T') and 'SOT' in package_upper:
        return 'transistor'

    # Diodes (D2)
    if name_upper.startswith('D') and 'DIODE' in package_upper:
        return 'diode'

    # Jumpers
    if name_upper.startswith('JP'):
        return 'jumper'

    # Generic connectors
    if name_upper.startswith('J'):
        return 'connector'

    return 'generic_smd'


def create_pcb_board(width, height):
    """Create the main PCB board."""
    pcb = box(extents=[width, height, PCB_THICKNESS])
    pcb.visual.face_colors = COLORS['pcb']
    return pcb


def create_tactile_button(size=6.0):
    """Create a tactile button."""
    parts = []

    # Button body
    body = box(extents=[size, size, 3.5])
    body.visual.face_colors = COLORS['button']
    parts.append(body)

    # Button cap
    cap = cylinder(radius=1.5, height=1.0, sections=16)
    cap.apply_translation([0, 0, 2.25])
    cap.visual.face_colors = COLORS['button_cap']
    parts.append(cap)

    return trimesh.util.concatenate(parts)


def create_shoulder_button():
    """Create L/R shoulder button."""
    parts = []

    body = box(extents=[10, 6, 4])
    body.visual.face_colors = COLORS['button']
    parts.append(body)

    actuator = box(extents=[3, 4, 1.5])
    actuator.apply_translation([0, 0, 2.75])
    actuator.visual.face_colors = COLORS['button_cap']
    parts.append(actuator)

    return trimesh.util.concatenate(parts)


def create_lcd(width=42, height=32):
    """Create LCD display."""
    parts = []

    # Metal frame
    frame = box(extents=[width + 4, height + 4, 2.5])
    frame.visual.face_colors = COLORS['lcd_frame']
    parts.append(frame)

    # Screen
    screen = box(extents=[width, height - 4, 0.5])
    screen.apply_translation([0, 0, 1.5])
    screen.visual.face_colors = COLORS['lcd_screen']
    parts.append(screen)

    # Ribbon cable
    ribbon = box(extents=[18, 6, 1])
    ribbon.apply_translation([0, -(height/2 + 5), -0.5])
    ribbon.visual.face_colors = COLORS['lcd_ribbon']
    parts.append(ribbon)

    return trimesh.util.concatenate(parts)


def create_esp32():
    """Create ESP32-WROVER module."""
    parts = []

    # Module body
    body = box(extents=[18, 25.5, 3.2])
    body.visual.face_colors = COLORS['esp32']
    parts.append(body)

    # Metal shield
    shield = box(extents=[16, 16, 2.5])
    shield.apply_translation([0, 3, 0.5])
    shield.visual.face_colors = [80, 80, 80, 255]
    parts.append(shield)

    # Antenna area (ceramic)
    antenna = box(extents=[16, 5, 0.5])
    antenna.apply_translation([0, -8, 1.6])
    antenna.visual.face_colors = [200, 180, 150, 255]
    parts.append(antenna)

    return trimesh.util.concatenate(parts)


def create_usb_micro():
    """Create micro USB connector."""
    parts = []

    body = box(extents=[7.5, 5.5, 2.7])
    body.visual.face_colors = COLORS['usb']
    parts.append(body)

    # Opening
    opening = box(extents=[7, 2.5, 1.5])
    opening.apply_translation([0, 1.5, 0])
    opening.visual.face_colors = [40, 40, 40, 255]
    parts.append(opening)

    return trimesh.util.concatenate(parts)


def create_audio_jack():
    """Create 3.5mm audio jack."""
    body = cylinder(radius=3, height=11, sections=32)
    body.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2, [0, 1, 0]))
    body.visual.face_colors = COLORS['audio']
    return body


def create_sd_card():
    """Create micro SD card slot."""
    body = box(extents=[14, 15, 2])
    body.visual.face_colors = [80, 80, 80, 255]
    return body


def create_slide_switch():
    """Create power slide switch."""
    parts = []

    body = box(extents=[8, 3, 3.5])
    body.visual.face_colors = [50, 50, 50, 255]
    parts.append(body)

    slider = box(extents=[3, 2, 1.5])
    slider.apply_translation([1.5, 0, 2.25])
    slider.visual.face_colors = COLORS['switch']
    parts.append(slider)

    return trimesh.util.concatenate(parts)


def create_led(color='red'):
    """Create SMD LED."""
    led = box(extents=[1.6, 0.8, 0.6])
    if color == 'red':
        led.visual.face_colors = [255, 50, 50, 200]
    elif color == 'green':
        led.visual.face_colors = [50, 255, 50, 200]
    else:
        led.visual.face_colors = [255, 200, 50, 200]
    return led


def create_capacitor(package):
    """Create SMD capacitor."""
    # Determine size from package
    if '0402' in package:
        size = [1.0, 0.5, 0.5]
    elif '0603' in package:
        size = [1.6, 0.8, 0.8]
    elif '0805' in package:
        size = [2.0, 1.25, 1.0]
    elif '1206' in package:
        size = [3.2, 1.6, 1.2]
    else:
        size = [2.0, 1.25, 1.0]

    cap = box(extents=size)
    cap.visual.face_colors = COLORS['capacitor']
    return cap


def create_resistor(package):
    """Create SMD resistor."""
    if '0402' in package:
        size = [1.0, 0.5, 0.35]
    elif '0603' in package:
        size = [1.6, 0.8, 0.45]
    elif '0805' in package:
        size = [2.0, 1.25, 0.6]
    else:
        size = [1.6, 0.8, 0.45]

    res = box(extents=size)
    res.visual.face_colors = COLORS['resistor']
    return res


def create_ic(package):
    """Create generic IC."""
    # Estimate size from package name
    if 'QFP' in package or 'TQFP' in package:
        size = [7, 7, 1.2]
    elif 'SOP' in package or 'SOIC' in package:
        size = [5, 4, 1.5]
    elif 'QFN' in package:
        size = [4, 4, 0.9]
    else:
        size = [3, 3, 1.0]

    ic = box(extents=size)
    ic.visual.face_colors = COLORS['ic']
    return ic


def create_connector(package):
    """Create generic connector."""
    conn = box(extents=[8, 2.5, 6])
    conn.visual.face_colors = COLORS['connector']
    return conn


def create_crystal():
    """Create crystal oscillator."""
    body = box(extents=[3.2, 1.5, 0.9])
    body.visual.face_colors = [180, 180, 180, 255]
    return body


def create_mounting_hole():
    """Create mounting hole ring."""
    ring = cylinder(radius=2.5, height=0.1, sections=32)
    ring.visual.face_colors = COLORS['mounting_hole']
    return ring


def create_generic_smd():
    """Create generic small SMD component."""
    smd = box(extents=[1.5, 1.0, 0.5])
    smd.visual.face_colors = [60, 60, 60, 255]
    return smd


def create_battery_connector():
    """Create JST battery connector."""
    body = box(extents=[8, 4, 5])
    body.visual.face_colors = [240, 240, 230, 255]
    return body


def create_transistor():
    """Create SOT-23 transistor."""
    body = box(extents=[2.9, 1.3, 1.0])
    body.visual.face_colors = [30, 30, 30, 255]
    return body


def create_diode():
    """Create SMD diode."""
    body = box(extents=[3.5, 1.5, 1.2])
    body.visual.face_colors = [30, 30, 30, 255]
    return body


def create_jumper():
    """Create SMD jumper."""
    body = box(extents=[1.5, 1.0, 0.3])
    body.visual.face_colors = [184, 134, 11, 255]  # Gold
    return body


def create_component_mesh(comp):
    """Create mesh for a component based on its type."""
    comp_type = comp['type']
    package = comp.get('package', '')

    if comp_type == 'button':
        return create_tactile_button()
    elif comp_type == 'shoulder_button':
        return create_shoulder_button()
    elif comp_type == 'lcd':
        return create_lcd()
    elif comp_type == 'esp32':
        return create_esp32()
    elif comp_type == 'usb':
        return create_usb_micro()
    elif comp_type == 'audio_jack':
        return create_audio_jack()
    elif comp_type == 'sd_card':
        return create_sd_card()
    elif comp_type == 'slide_switch':
        return create_slide_switch()
    elif comp_type == 'led':
        return create_led()
    elif comp_type == 'capacitor':
        return create_capacitor(package)
    elif comp_type == 'resistor':
        return create_resistor(package)
    elif comp_type == 'ic':
        return create_ic(package)
    elif comp_type == 'connector':
        return create_connector(package)
    elif comp_type == 'crystal':
        return create_crystal()
    elif comp_type == 'mounting_hole':
        return create_mounting_hole()
    elif comp_type == 'battery_connector':
        return create_battery_connector()
    elif comp_type == 'transistor':
        return create_transistor()
    elif comp_type == 'diode':
        return create_diode()
    elif comp_type == 'jumper':
        return create_jumper()
    elif comp_type == 'logo':
        return None  # Skip logos
    elif comp_type == 'testpoint':
        return None  # Skip test points
    else:
        return create_generic_smd()


def assemble_pcb(pcb_data):
    """Assemble complete PCB with all components."""
    parts = []

    width = pcb_data['width']
    height = pcb_data['height']

    # Main PCB
    print("Creating PCB board...")
    pcb = create_pcb_board(width, height)
    parts.append(('pcb', pcb))

    # Component heights for Z positioning
    z_heights = {
        'button': 1.75,
        'shoulder_button': 2.0,
        'lcd': 1.5,
        'esp32': 1.6,
        'usb': 1.35,
        'audio_jack': 1.5,
        'sd_card': 1.0,
        'slide_switch': 1.75,
        'led': 0.3,
        'capacitor': 0.5,
        'resistor': 0.3,
        'ic': 0.6,
        'connector': 3.0,
        'crystal': 0.45,
        'mounting_hole': PCB_THICKNESS / 2,
        'generic_smd': 0.25,
        'battery_connector': 2.5,
        'transistor': 0.5,
        'diode': 0.6,
        'jumper': 0.15,
    }

    # Add components
    print("Adding components...")
    added_top = 0
    added_bottom = 0
    skipped = 0

    for comp in pcb_data['components']:
        try:
            mesh = create_component_mesh(comp)

            # Skip if mesh is None (logos, testpoints)
            if mesh is None:
                skipped += 1
                continue

            # Apply rotation
            if comp['rotation'] != 0:
                rot_rad = np.radians(comp['rotation'])
                mesh.apply_transform(trimesh.transformations.rotation_matrix(rot_rad, [0, 0, 1]))

            # Position component based on layer (TOP or BOTTOM)
            z_height = z_heights.get(comp['type'], 0.5)

            if comp['layer'] == 'TOP':
                # TOP components: above PCB surface
                z_offset = PCB_THICKNESS / 2 + z_height
                added_top += 1
            else:
                # BOTTOM components: below PCB surface (flip Z and mirror mesh)
                # Flip the mesh upside down for bottom side
                mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0]))
                z_offset = -PCB_THICKNESS / 2 - z_height
                added_bottom += 1

            mesh.apply_translation([comp['x'], comp['y'], z_offset])

            parts.append((comp['name'], mesh))

        except Exception as e:
            skipped += 1

    print(f"  Added TOP: {added_top} components")
    print(f"  Added BOTTOM: {added_bottom} components")
    print(f"  Skipped: {skipped} components")

    return parts


def export_model(parts, output_dir):
    """Export assembled model."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create scene
    scene = trimesh.Scene()
    for name, mesh in parts:
        scene.add_geometry(mesh, node_name=name)

    # Export GLB
    glb_path = output_dir / 'esplay_micro_pcb.glb'
    scene.export(str(glb_path))
    print(f"Exported: {glb_path}")

    # Export combined STL
    combined = trimesh.util.concatenate([mesh for _, mesh in parts])
    stl_path = output_dir / 'esplay_micro_pcb.stl'
    combined.export(str(stl_path))
    print(f"Exported: {stl_path}")

    # Create HTML viewer
    create_viewer(output_dir)

    return glb_path


def create_viewer(output_dir):
    """Create HTML viewer."""
    html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ESPlay Micro PCB 3D Model</title>
    <script type="module" src="https://unpkg.com/@google/model-viewer/dist/model-viewer.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px;
        }
        h1 { color: #00d9ff; margin-bottom: 20px; }
        model-viewer {
            width: 100%;
            max-width: 900px;
            height: 650px;
            background: #0d1b2a;
            border-radius: 12px;
            border: 2px solid #0f3460;
        }
        .info { color: #aaa; margin-top: 20px; text-align: center; }
    </style>
</head>
<body>
    <h1>ESPlay Micro PCB - 3D Model</h1>
    <model-viewer
        src="esplay_micro_pcb.glb"
        camera-controls
        auto-rotate
        shadow-intensity="1"
        environment-image="neutral"
        camera-orbit="30deg 60deg 180mm"
        alt="ESPlay Micro PCB">
    </model-viewer>
    <div class="info">
        <p>Drag to rotate | Scroll to zoom | Shift+Drag to pan</p>
        <p><strong>Flip the PCB to see components on both sides!</strong></p>
        <p>TOP: Buttons, LED, Mounting holes | BOTTOM: ESP32, SD card, USB, ICs</p>
        <p>Generated from Eagle .brd file - ESPlay Micro Hardware</p>
    </div>
</body>
</html>'''

    with open(output_dir / 'viewer.html', 'w') as f:
        f.write(html)
    print(f"Created viewer: {output_dir / 'viewer.html'}")


def main():
    print("=" * 60)
    print("ESPlay Micro PCB 3D Model Generator")
    print("=" * 60)

    # Parse Eagle file
    if not BRD_FILE.exists():
        print(f"ERROR: Eagle file not found: {BRD_FILE}")
        return 1

    pcb_data = parse_eagle_brd(BRD_FILE)

    # Save component data for reference
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_DIR / 'components.json', 'w') as f:
        json.dump(pcb_data, f, indent=2)
    print(f"\nComponent data saved to: {OUTPUT_DIR / 'components.json'}")

    # Assemble PCB
    parts = assemble_pcb(pcb_data)
    print(f"\nTotal parts in model: {len(parts)}")

    # Export
    print("\nExporting models...")
    export_model(parts, OUTPUT_DIR)

    print("\n" + "=" * 60)
    print("DONE!")
    print("=" * 60)
    print(f"\nView the model:")
    print(f"  python3 -m http.server 8083 --directory {OUTPUT_DIR}")
    print(f"  Open: http://localhost:8083/viewer.html")

    return 0


if __name__ == '__main__':
    exit(main())
