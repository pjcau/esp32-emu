#!/usr/bin/env python3
"""
Generate ESPlay Micro PCB model with visible 3D buttons and display.
Each component has distinct color and height for easy visualization.
"""

import numpy as np
import trimesh
from trimesh.creation import box, cylinder
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent.parent / 'pcb'

# PCB specs
PCB_WIDTH = 100.0
PCB_HEIGHT = 50.0
PCB_THICKNESS = 1.6
PCB_CENTER = (50.0, 25.0)

# Colors (RGBA)
COLORS = {
    'pcb': [34, 139, 34, 255],        # Forest green - PCB
    'display': [0, 100, 200, 255],    # Blue - LCD
    'dpad': [255, 50, 50, 255],       # Red - D-Pad
    'ab': [50, 255, 50, 255],         # Green - A/B buttons
    'start_select': [255, 165, 0, 255],  # Orange
    'menu': [255, 0, 255, 255],       # Magenta
    'lr': [255, 255, 0, 255],         # Yellow - L/R
    'power': [0, 255, 255, 255],      # Cyan
    'usb': [150, 150, 150, 255],      # Gray
    'sd': [100, 100, 100, 255],       # Dark gray
    'audio': [200, 200, 200, 255],    # Light gray
    'hole': [255, 215, 0, 255],       # Gold - mounting holes
}


def eagle_to_centered(x, y):
    return (x - PCB_CENTER[0], y - PCB_CENTER[1])


def create_rounded_box(width, height, depth, radius=2.0):
    mesh_h = box(extents=[width - 2*radius, height, depth])
    mesh_v = box(extents=[width, height - 2*radius, depth])
    mesh = trimesh.util.concatenate([mesh_h, mesh_v])
    for sx in [-1, 1]:
        for sy in [-1, 1]:
            corner = cylinder(radius=radius, height=depth, sections=8)
            corner.apply_translation([sx*(width/2-radius), sy*(height/2-radius), 0])
            mesh = trimesh.util.concatenate([mesh, corner])
    mesh.merge_vertices()
    return mesh


def create_button(x, y, diameter, height, color, z_base):
    """Create a cylindrical button."""
    btn = cylinder(radius=diameter/2, height=height, sections=32)
    btn.apply_translation([x, y, z_base + height/2])
    btn.visual.face_colors = color
    return btn


def create_rect_component(x, y, w, h, height, color, z_base):
    """Create a rectangular component."""
    comp = box(extents=[w, h, height])
    comp.apply_translation([x, y, z_base + height/2])
    comp.visual.face_colors = color
    return comp


def main():
    print("=" * 70)
    print("ESPLAY MICRO PCB WITH 3D BUTTONS")
    print("=" * 70)

    meshes = []
    z_base = PCB_THICKNESS  # Components sit on top of PCB

    # 1. PCB Base
    print("\n1. Creating PCB base...")
    pcb = create_rounded_box(PCB_WIDTH, PCB_HEIGHT, PCB_THICKNESS)
    pcb.apply_translation([0, 0, PCB_THICKNESS/2])
    pcb.visual.face_colors = COLORS['pcb']
    meshes.append(pcb)

    # 2. Display (raised rectangle)
    print("2. Adding display...")
    lcd_x, lcd_y = eagle_to_centered(51.56, 26.04)
    lcd = create_rect_component(lcd_x, lcd_y, 42, 32, 3.0, COLORS['display'], z_base)
    meshes.append(lcd)
    print(f"   LCD @ ({lcd_x:.1f}, {lcd_y:.1f})")

    # 3. D-Pad (4 buttons in cross pattern)
    print("3. Adding D-Pad...")
    dpad_center_x, dpad_center_y = eagle_to_centered(10.85, 33.02)
    dpad_spacing = 5.5
    dpad_positions = [
        (0, dpad_spacing),   # Up
        (0, -dpad_spacing),  # Down
        (-dpad_spacing, 0),  # Left
        (dpad_spacing, 0),   # Right
    ]
    for dx, dy in dpad_positions:
        btn = create_button(dpad_center_x + dx, dpad_center_y + dy, 5.0, 2.5, COLORS['dpad'], z_base)
        meshes.append(btn)
    # Center cross
    dpad_cross_h = box(extents=[12, 4, 1.5])
    dpad_cross_h.apply_translation([dpad_center_x, dpad_center_y, z_base + 0.75])
    dpad_cross_h.visual.face_colors = COLORS['dpad']
    meshes.append(dpad_cross_h)
    dpad_cross_v = box(extents=[4, 12, 1.5])
    dpad_cross_v.apply_translation([dpad_center_x, dpad_center_y, z_base + 0.75])
    dpad_cross_v.visual.face_colors = COLORS['dpad']
    meshes.append(dpad_cross_v)
    print(f"   D-Pad center @ ({dpad_center_x:.1f}, {dpad_center_y:.1f})")

    # 4. A/B Buttons
    print("4. Adding A/B buttons...")
    ab_x, ab_y = eagle_to_centered(91.50, 32.58)
    # A button (lower right)
    btn_a = create_button(ab_x + 3, ab_y - 3, 8.0, 3.0, COLORS['ab'], z_base)
    meshes.append(btn_a)
    # B button (upper left)
    btn_b = create_button(ab_x - 3, ab_y + 3, 8.0, 3.0, COLORS['ab'], z_base)
    meshes.append(btn_b)
    print(f"   A/B center @ ({ab_x:.1f}, {ab_y:.1f})")

    # 5. Start/Select
    print("5. Adding Start/Select...")
    ss_x, ss_y = eagle_to_centered(10.85, 14.55)
    # Start
    btn_start = create_button(ss_x - 4, ss_y, 5.0, 2.0, COLORS['start_select'], z_base)
    meshes.append(btn_start)
    # Select
    btn_select = create_button(ss_x + 4, ss_y, 5.0, 2.0, COLORS['start_select'], z_base)
    meshes.append(btn_select)
    print(f"   Start/Select @ ({ss_x:.1f}, {ss_y:.1f})")

    # 6. Menu button
    print("6. Adding Menu button...")
    menu_x, menu_y = eagle_to_centered(89.03, 14.48)
    btn_menu = create_button(menu_x, menu_y, 5.0, 2.0, COLORS['menu'], z_base)
    meshes.append(btn_menu)
    print(f"   Menu @ ({menu_x:.1f}, {menu_y:.1f})")

    # 7. L/R Shoulder buttons
    print("7. Adding L/R shoulder buttons...")
    l_x, l_y = eagle_to_centered(11.43, 45.72)
    r_x, r_y = eagle_to_centered(88.90, 45.72)
    btn_l = create_rect_component(l_x, l_y, 12, 6, 3.0, COLORS['lr'], z_base)
    btn_r = create_rect_component(r_x, r_y, 12, 6, 3.0, COLORS['lr'], z_base)
    meshes.append(btn_l)
    meshes.append(btn_r)
    print(f"   L @ ({l_x:.1f}, {l_y:.1f})")
    print(f"   R @ ({r_x:.1f}, {r_y:.1f})")

    # 8. Power switch
    print("8. Adding Power switch...")
    pwr_x, pwr_y = eagle_to_centered(68.58, 35.56)
    pwr = create_rect_component(pwr_x, pwr_y, 8, 4, 2.0, COLORS['power'], z_base)
    meshes.append(pwr)
    print(f"   Power @ ({pwr_x:.1f}, {pwr_y:.1f})")

    # 9. USB port
    print("9. Adding USB port...")
    usb_x, usb_y = eagle_to_centered(33.66, 2.03)
    usb = create_rect_component(usb_x, usb_y, 8, 5, 3.0, COLORS['usb'], z_base)
    meshes.append(usb)

    # 10. SD card slot
    print("10. Adding SD card slot...")
    sd_x, sd_y = eagle_to_centered(24.13, 17.78)
    sd = create_rect_component(sd_x, sd_y, 14, 15, 2.0, COLORS['sd'], z_base)
    meshes.append(sd)

    # 11. Audio jack
    print("11. Adding Audio jack...")
    audio_x, audio_y = eagle_to_centered(85.22, 3.68)
    audio = create_rect_component(audio_x, audio_y, 12, 6, 5.0, COLORS['audio'], z_base)
    meshes.append(audio)

    # 12. Mounting holes
    print("12. Adding mounting holes...")
    holes = [
        (3.05, 3.05), (3.05, 46.86),
        (96.90, 46.86), (96.90, 3.05)
    ]
    for hx, hy in holes:
        cx, cy = eagle_to_centered(hx, hy)
        ring = cylinder(radius=2.5, height=0.5, sections=32)
        ring.apply_translation([cx, cy, z_base + 0.25])
        ring.visual.face_colors = COLORS['hole']
        meshes.append(ring)

    # Combine all
    print("\n13. Combining meshes...")
    combined = trimesh.util.concatenate(meshes)

    print(f"\nMesh info:")
    print(f"   Vertices: {len(combined.vertices)}")
    print(f"   Faces: {len(combined.faces)}")
    print(f"   Bounds: {combined.bounds}")

    # Export
    output_path = OUTPUT_DIR / 'esplay_micro_pcb_3d.stl'
    combined.export(str(output_path))
    print(f"\nExported: {output_path}")

    print("\n" + "=" * 70)
    print("COLOR LEGEND:")
    print("=" * 70)
    print("  GREEN (dark)  - PCB base")
    print("  BLUE          - LCD Display")
    print("  RED           - D-Pad")
    print("  GREEN (light) - A/B buttons")
    print("  ORANGE        - Start/Select")
    print("  MAGENTA       - Menu button")
    print("  YELLOW        - L/R shoulder buttons")
    print("  CYAN          - Power switch")
    print("  GRAY          - USB/SD/Audio connectors")
    print("  GOLD          - Mounting holes")

    return 0


if __name__ == '__main__':
    exit(main())
