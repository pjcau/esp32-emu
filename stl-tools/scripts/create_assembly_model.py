#!/usr/bin/env python3
"""
Create combined assembly model with PCB and all case parts.
For visual verification of fit.
"""

import numpy as np
import trimesh
from trimesh.creation import box, cylinder
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
FIXED_V2_DIR = PROJECT_ROOT / 'stl-tools' / 'output' / 'fixed_v2'
OUTPUT_DIR = PROJECT_ROOT / 'stl-tools' / 'output'

# PCB specs
PCB_WIDTH = 100.0
PCB_HEIGHT = 50.0
PCB_THICKNESS = 1.6
PCB_CENTER = (50.0, 25.0)

# Colors
COLORS = {
    'pcb': [34, 139, 34, 255],
    'frame': [150, 150, 150, 200],
    'top_cover': [100, 149, 237, 180],
    'back_cover': [70, 130, 180, 180],
    'd_Pad': [255, 50, 50, 255],
    'A_B': [50, 255, 50, 255],
    'start_select': [255, 165, 0, 255],
    'menu': [255, 0, 255, 255],
    'L_R': [255, 255, 0, 255],
    'power': [0, 255, 255, 255],
}

# PCB button positions (Eagle coords centered)
PCB_BUTTONS = {
    'DPAD': (-39.15, 8.02),
    'AB': (41.50, 7.58),
    'START_SELECT': (-39.15, -10.45),
    'MENU': (39.03, -10.52),
    'L': (-38.57, 20.72),
    'R': (38.90, 20.72),
    'POWER': (18.58, 10.56),
}


def eagle_to_centered(x, y):
    return (x - PCB_CENTER[0], y - PCB_CENTER[1])


def create_pcb_with_markers():
    """Create PCB base with button position markers."""
    # PCB base
    pcb = box(extents=[PCB_WIDTH, PCB_HEIGHT, PCB_THICKNESS])
    pcb.apply_translation([0, 0, PCB_THICKNESS/2])
    pcb.visual.face_colors = COLORS['pcb']

    meshes = [pcb]

    # Add button markers on PCB
    marker_height = 0.5
    marker_colors = {
        'DPAD': [255, 50, 50, 255],
        'AB': [50, 255, 50, 255],
        'START_SELECT': [255, 165, 0, 255],
        'MENU': [255, 0, 255, 255],
        'L': [255, 255, 0, 255],
        'R': [255, 255, 0, 255],
        'POWER': [0, 255, 255, 255],
    }

    for name, pos in PCB_BUTTONS.items():
        cx, cy = eagle_to_centered(pos[0], pos[1])
        marker = cylinder(radius=3, height=marker_height, sections=32)
        marker.apply_translation([cx, cy, PCB_THICKNESS + marker_height/2])
        marker.visual.face_colors = marker_colors.get(name, [200, 200, 200, 255])
        meshes.append(marker)

    return trimesh.util.concatenate(meshes)


def load_case_part(name, z_offset=0):
    """Load a case part and apply color and offset."""
    filepath = FIXED_V2_DIR / f"{name}.stl"
    if not filepath.exists():
        return None

    mesh = trimesh.load(str(filepath))
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate([g for g in mesh.geometry.values()])

    # Apply color
    color = COLORS.get(name, [128, 128, 128, 255])
    mesh.visual.face_colors = color

    # Apply Z offset if specified
    if z_offset != 0:
        mesh.apply_translation([0, 0, z_offset])

    return mesh


def main():
    print("=" * 70)
    print("CREATING ASSEMBLY MODEL")
    print("=" * 70)

    meshes = []

    # 1. PCB with button markers (at Z=0)
    print("\n1. Creating PCB with button position markers...")
    pcb = create_pcb_with_markers()
    meshes.append(pcb)
    print(f"   PCB bounds: {pcb.bounds}")

    # 2. Load case parts
    # Position them relative to PCB
    # PCB is at Z=0 to Z=1.6mm
    # Buttons sit on top of PCB, roughly at Z=1.6 to Z=6mm
    # top_cover goes above buttons
    # back_cover goes below PCB

    parts_config = [
        # (name, z_offset, description)
        ('frame', 0, 'Internal frame'),
        ('d_Pad', 0, 'D-Pad button'),
        ('A_B', 0, 'A/B buttons'),
        ('start_select', 0, 'Start/Select'),
        ('menu', 0, 'Menu button'),
        ('L_R', 0, 'L/R shoulder buttons'),
        ('power', 0, 'Power switch'),
        ('top_cover', 0, 'Top cover'),
        ('back_cover', 0, 'Back cover'),
    ]

    print("\n2. Loading case parts...")
    for name, z_off, desc in parts_config:
        part = load_case_part(name, z_off)
        if part:
            meshes.append(part)
            ctr = part.centroid
            ext = part.extents
            print(f"   {name:15}: center ({ctr[0]:6.1f}, {ctr[1]:6.1f}, {ctr[2]:6.1f}) - {desc}")

    # 3. Combine all
    print("\n3. Combining meshes...")
    assembly = trimesh.util.concatenate(meshes)

    print(f"\nAssembly info:")
    print(f"   Vertices: {len(assembly.vertices)}")
    print(f"   Faces: {len(assembly.faces)}")
    print(f"   Bounds: X [{assembly.bounds[0][0]:.1f}, {assembly.bounds[1][0]:.1f}]")
    print(f"           Y [{assembly.bounds[0][1]:.1f}, {assembly.bounds[1][1]:.1f}]")
    print(f"           Z [{assembly.bounds[0][2]:.1f}, {assembly.bounds[1][2]:.1f}]")

    # 4. Export
    output_path = OUTPUT_DIR / 'assembly_complete.stl'
    assembly.export(str(output_path))
    print(f"\nExported: {output_path}")

    # Also create PCB-only for comparison
    pcb_only_path = OUTPUT_DIR / 'pcb_with_markers.stl'
    pcb.export(str(pcb_only_path))
    print(f"Exported: {pcb_only_path}")

    print("\n" + "=" * 70)
    print("ASSEMBLY NOTES")
    print("=" * 70)
    print("""
The assembly shows:
- GREEN base: PCB (100x50mm)
- Colored cylinders on PCB: Button position markers from PCB design
- Colored case parts: STL parts from fixed_v2

If buttons don't align with PCB markers, the original case design
may have different reference coordinates than the PCB.

The STL parts maintain their ORIGINAL positions - the fix only
added thickness without moving them.
""")

    return 0


if __name__ == '__main__':
    exit(main())
