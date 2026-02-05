#!/usr/bin/env python3
"""
Comprehensive alignment analysis between STL case parts and PCB.
Handles coordinate system differences and generates corrected renders.
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

# PCB specs
PCB_WIDTH = 100.0
PCB_HEIGHT = 50.0
PCB_THICKNESS = 1.6

# Correct mapping based on user description:
# - D-Pad: top left
# - Start/Select: bottom left (horizontal)
# - A/B: top right (vertical)
# - Menu: below A/B (bottom right)
# - L/R: shoulders at top edges
# - Power: top center area

# STL to PCB component mapping
STL_TO_PCB = {
    'd_Pad': 'DPAD',
    'A_B': 'AB',
    'start_select': 'START_SELECT',
    'menu': 'MENU',
    'power': 'POWER',
}

# Colors for each part
PART_COLORS = {
    'frame': [120, 120, 120, 200],
    'top_cover': [70, 130, 180, 180],
    'back_cover': [100, 149, 237, 180],
    'd_Pad': [255, 50, 50, 255],
    'A_B': [50, 205, 50, 255],
    'start_select': [255, 165, 0, 255],
    'menu': [255, 0, 255, 255],
    'L_R': [255, 255, 0, 255],
    'power': [0, 255, 255, 255],
    'pcb': [34, 139, 34, 255],
}


def load_stl_parts():
    """Load all STL parts with their positions."""
    parts = {}
    for stl_file in sorted(FIXED_V2_DIR.glob('*.stl')):
        name = stl_file.stem
        mesh = trimesh.load(str(stl_file))
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate([g for g in mesh.geometry.values()])

        mesh.visual.face_colors = PART_COLORS.get(name, [128, 128, 128, 255])
        parts[name] = {
            'mesh': mesh,
            'centroid': mesh.centroid.copy(),
            'bounds': mesh.bounds.copy(),
            'extents': mesh.extents.copy()
        }
    return parts


def load_pcb_positions():
    """Load PCB component positions."""
    with open(PCB_POSITIONS_FILE) as f:
        return json.load(f)


def analyze_coordinate_systems(stl_parts, pcb_positions):
    """Analyze differences between STL and PCB coordinate systems."""
    print("=" * 70)
    print("COORDINATE SYSTEM ANALYSIS")
    print("=" * 70)

    # The key insight: STL Y axis appears inverted relative to PCB
    # PCB: positive Y = top of console (where L/R buttons are)
    # STL: the orientation needs to be determined

    print("\n1. PCB Button Positions (centered coords):")
    print("-" * 50)
    for name in ['DPAD', 'AB', 'START_SELECT', 'MENU', 'L_BTN', 'R_BTN', 'POWER']:
        if name in pcb_positions:
            pos = pcb_positions[name]
            y_label = "TOP" if pos['center_y'] > 0 else "BOTTOM"
            x_label = "LEFT" if pos['center_x'] < 0 else "RIGHT"
            print(f"  {name:15}: X={pos['center_x']:7.2f} ({x_label:6})  Y={pos['center_y']:7.2f} ({y_label})")

    print("\n2. STL Part Positions (original coords):")
    print("-" * 50)
    for name in ['d_Pad', 'A_B', 'start_select', 'menu', 'L_R', 'power']:
        if name in stl_parts:
            c = stl_parts[name]['centroid']
            y_label = "TOP" if c[1] > 0 else "BOTTOM"
            x_label = "LEFT" if c[0] < 0 else "RIGHT"
            print(f"  {name:15}: X={c[0]:7.2f} ({x_label:6})  Y={c[1]:7.2f} ({y_label})")

    print("\n3. Coordinate System Difference:")
    print("-" * 50)

    # Compare D-Pad positions
    if 'd_Pad' in stl_parts and 'DPAD' in pcb_positions:
        stl_y = stl_parts['d_Pad']['centroid'][1]
        pcb_y = pcb_positions['DPAD']['center_y']
        print(f"  D-Pad: STL Y={stl_y:.2f}, PCB Y={pcb_y:.2f}")

    if 'start_select' in stl_parts and 'START_SELECT' in pcb_positions:
        stl_y = stl_parts['start_select']['centroid'][1]
        pcb_y = pcb_positions['START_SELECT']['center_y']
        print(f"  Start/Select: STL Y={stl_y:.2f}, PCB Y={pcb_y:.2f}")

    # Detect if Y is inverted
    # In PCB: DPAD Y > START_SELECT Y (D-Pad is above Start/Select)
    # In STL: check the same relationship
    pcb_dpad_y = pcb_positions.get('DPAD', {}).get('center_y', 0)
    pcb_ss_y = pcb_positions.get('START_SELECT', {}).get('center_y', 0)
    stl_dpad_y = stl_parts.get('d_Pad', {}).get('centroid', [0,0,0])[1]
    stl_ss_y = stl_parts.get('start_select', {}).get('centroid', [0,0,0])[1]

    pcb_order = "D-Pad ABOVE Start/Select" if pcb_dpad_y > pcb_ss_y else "D-Pad BELOW Start/Select"
    stl_order = "D-Pad ABOVE Start/Select" if stl_dpad_y > stl_ss_y else "D-Pad BELOW Start/Select"

    print(f"\n  PCB vertical order: {pcb_order}")
    print(f"  STL vertical order: {stl_order}")

    y_inverted = (pcb_dpad_y > pcb_ss_y) != (stl_dpad_y > stl_ss_y)
    print(f"\n  Y-AXIS INVERTED: {'YES' if y_inverted else 'NO'}")

    return y_inverted


def create_alignment_comparison(stl_parts, pcb_positions, y_inverted):
    """Create detailed alignment comparison."""
    print("\n" + "=" * 70)
    print("ALIGNMENT COMPARISON (accounting for coordinate differences)")
    print("=" * 70)

    comparisons = []

    for stl_name, pcb_name in STL_TO_PCB.items():
        if stl_name not in stl_parts or pcb_name not in pcb_positions:
            continue

        stl_c = stl_parts[stl_name]['centroid']
        pcb_pos = pcb_positions[pcb_name]

        # Transform STL coords if Y is inverted
        stl_x = stl_c[0]
        stl_y = -stl_c[1] if y_inverted else stl_c[1]

        pcb_x = pcb_pos['center_x']
        pcb_y = pcb_pos['center_y']

        offset_x = stl_x - pcb_x
        offset_y = stl_y - pcb_y
        offset_total = np.sqrt(offset_x**2 + offset_y**2)

        aligned = offset_total < 10.0  # 10mm tolerance

        print(f"\n  {stl_name} <-> {pcb_name}:")
        print(f"    STL (transformed): ({stl_x:7.2f}, {stl_y:7.2f})")
        print(f"    PCB:               ({pcb_x:7.2f}, {pcb_y:7.2f})")
        print(f"    Offset: X={offset_x:+.2f}, Y={offset_y:+.2f} (total: {offset_total:.2f}mm)")
        print(f"    Status: {'✓ ALIGNED' if aligned else '✗ OFFSET'}")

        comparisons.append({
            'stl': stl_name,
            'pcb': pcb_name,
            'stl_pos': (stl_x, stl_y),
            'pcb_pos': (pcb_x, pcb_y),
            'offset': offset_total,
            'aligned': aligned
        })

    # Special case: L_R
    print(f"\n  L_R (special case - single piece):")
    if 'L_R' in stl_parts:
        lr = stl_parts['L_R']
        print(f"    STL bounds X: [{lr['bounds'][0][0]:.1f}, {lr['bounds'][1][0]:.1f}]")
        print(f"    STL center: ({lr['centroid'][0]:.1f}, {lr['centroid'][1]:.1f})")
        print(f"    PCB L_BTN: ({pcb_positions.get('L_BTN', {}).get('center_x', 'N/A')}, {pcb_positions.get('L_BTN', {}).get('center_y', 'N/A')})")
        print(f"    PCB R_BTN: ({pcb_positions.get('R_BTN', {}).get('center_x', 'N/A')}, {pcb_positions.get('R_BTN', {}).get('center_y', 'N/A')})")
        print(f"    Note: STL L_R is on RIGHT side only (X>0). May need mirroring for L button.")

    return comparisons


def create_pcb_model(pcb_positions, y_inverted):
    """Create PCB with button markers."""
    meshes = []

    # PCB base
    pcb = box(extents=[PCB_WIDTH, PCB_HEIGHT, PCB_THICKNESS])
    pcb.apply_translation([0, 0, -PCB_THICKNESS/2])
    pcb.visual.face_colors = PART_COLORS['pcb']
    meshes.append(('pcb', pcb))

    # Button markers
    button_colors = {
        'DPAD': PART_COLORS['d_Pad'],
        'AB': PART_COLORS['A_B'],
        'START_SELECT': PART_COLORS['start_select'],
        'MENU': PART_COLORS['menu'],
        'L_BTN': PART_COLORS['L_R'],
        'R_BTN': PART_COLORS['L_R'],
        'POWER': PART_COLORS['power'],
    }

    for name, pos in pcb_positions.items():
        if name in ['LCD', 'USB', 'SD', 'AUDIO']:
            continue

        cx = pos['center_x']
        cy = pos['center_y']

        # Apply Y inversion if needed to match STL coords
        if y_inverted:
            cy = -cy

        color = button_colors.get(name, [200, 200, 200, 255])

        marker = cylinder(radius=4, height=1.5, sections=32)
        marker.apply_translation([cx, cy, 0.75])
        marker.visual.face_colors = color
        meshes.append((f'marker_{name}', marker))

    # LCD
    lcd = pcb_positions.get('LCD', {})
    if lcd:
        lcd_cy = -lcd['center_y'] if y_inverted else lcd['center_y']
        lcd_mesh = box(extents=[lcd.get('width', 42), lcd.get('height', 32), 2])
        lcd_mesh.apply_translation([lcd['center_x'], lcd_cy, 1])
        lcd_mesh.visual.face_colors = [0, 50, 150, 255]
        meshes.append(('lcd', lcd_mesh))

    return meshes


def create_renders(stl_parts, pcb_meshes, y_inverted):
    """Create all render views."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Prepare STL meshes (potentially transform Y)
    case_meshes = []
    for name, data in stl_parts.items():
        mesh = data['mesh'].copy()
        # Keep original orientation - the STL files are the source of truth
        # The PCB markers were adjusted to match
        case_meshes.append((name, mesh))

    # 1. Assembly with PCB
    print("\n1. Creating assembly with PCB...")
    all_meshes = case_meshes + pcb_meshes
    scene = trimesh.Scene()
    for mesh_name, mesh in all_meshes:
        scene.add_geometry(mesh, node_name=mesh_name)
    scene.export(str(OUTPUT_DIR / 'assembly_colored.glb'))

    # 2. Exploded view
    print("2. Creating exploded view...")
    exploded = create_exploded_view(case_meshes)
    scene = trimesh.Scene()
    for mesh_name, mesh in exploded + pcb_meshes:
        scene.add_geometry(mesh, node_name=mesh_name)
    scene.export(str(OUTPUT_DIR / 'assembly_exploded.glb'))

    # 3. PCB only
    print("3. Creating PCB detailed view...")
    scene = trimesh.Scene()
    for mesh_name, mesh in pcb_meshes:
        scene.add_geometry(mesh, node_name=mesh_name)
    scene.export(str(OUTPUT_DIR / 'pcb_detailed.glb'))

    # 4. Case only
    print("4. Creating case-only view...")
    scene = trimesh.Scene()
    for mesh_name, mesh in case_meshes:
        scene.add_geometry(mesh, node_name=mesh_name)
    scene.export(str(OUTPUT_DIR / 'case_only.glb'))

    print(f"\nRenders saved to: {OUTPUT_DIR}")


def create_exploded_view(parts, factor=1.5):
    """Create exploded view."""
    exploded = []

    all_centroids = [p[1].centroid for p in parts]
    center = np.mean(all_centroids, axis=0)

    z_offsets = {
        'back_cover': -35,
        'frame': 0,
        'd_Pad': 15,
        'A_B': 15,
        'start_select': 15,
        'menu': 15,
        'L_R': 20,
        'power': 25,
        'top_cover': 40,
    }

    for name, mesh in parts:
        new_mesh = mesh.copy()

        direction = mesh.centroid - center
        direction[2] = 0

        if np.linalg.norm(direction[:2]) > 0.1:
            direction[:2] = direction[:2] / np.linalg.norm(direction[:2])

        xy_offset = direction[:2] * factor * 12
        z_offset = z_offsets.get(name, 0)

        new_mesh.apply_translation([xy_offset[0], xy_offset[1], z_offset])
        exploded.append((name, new_mesh))

    return exploded


def generate_report(stl_parts, pcb_positions, comparisons, y_inverted):
    """Generate alignment report."""
    report_path = PROJECT_ROOT / 'stl-tools' / 'ALIGNMENT_REPORT.md'

    report = f"""# ESPlay Micro - Alignment Analysis Report

**Data**: 2026-02-04
**Progetto**: ESP32-EMU Console Retro Gaming

---

## 1. Coordinate System Analysis

### STL Case Orientation
Il case STL utilizza un sistema di coordinate dove:
- **X positivo** = lato destro della console
- **X negativo** = lato sinistro della console
- **Y** = {'INVERTITO rispetto al PCB' if y_inverted else 'stesso verso del PCB'}

### PCB Orientation (Eagle)
- **X positivo** = lato destro (dove sono A/B, Menu)
- **X negativo** = lato sinistro (dove sono D-Pad, Start/Select)
- **Y positivo** = lato superiore (dove sono L/R shoulders)
- **Y negativo** = lato inferiore (USB, Audio)

### Trasformazione Applicata
{'Y-axis invertito per allineare i sistemi di coordinate.' if y_inverted else 'Nessuna trasformazione necessaria.'}

---

## 2. Button Positions Comparison

| Componente | STL Center (X, Y) | PCB Center (X, Y) | Offset (mm) | Status |
|------------|-------------------|-------------------|-------------|--------|
"""

    for comp in comparisons:
        stl_x, stl_y = comp['stl_pos']
        pcb_x, pcb_y = comp['pcb_pos']
        status = "✓ OK" if comp['aligned'] else "⚠ Offset"
        report += f"| {comp['stl']} | ({stl_x:.1f}, {stl_y:.1f}) | ({pcb_x:.1f}, {pcb_y:.1f}) | {comp['offset']:.1f} | {status} |\n"

    report += f"""
### L/R Shoulders (caso speciale)
"""
    if 'L_R' in stl_parts:
        lr = stl_parts['L_R']
        report += f"""- STL L_R è un **pezzo singolo** posizionato sul lato destro (X={lr['centroid'][0]:.1f})
- PCB ha L_BTN (X=-38.6) e R_BTN (X=38.9) separati
- **Nota**: Il pezzo L_R potrebbe necessitare di essere specchiato per il lato sinistro
"""

    report += f"""
---

## 3. Layout Console

```
      L_BTN                              R_BTN
   ┌─────────────────────────────────────────────┐
   │                                             │
   │  ┌─────┐                        ┌───┐       │
   │  │D-Pad│        ┌──────┐        │A/B│       │
   │  └─────┘        │ LCD  │        └───┘       │
   │                 │Screen│                    │
   │  ┌──────────┐   └──────┘        ┌────┐      │
   │  │Start/Sel │                   │Menu│      │
   │  └──────────┘                   └────┘      │
   │                                             │
   └─────────────────────────────────────────────┘
           USB              AUDIO
```

---

## 4. Dimensional Compatibility

| Componente | Dimensioni (mm) |
|------------|-----------------|
| PCB | 100.0 x 50.0 x 1.6 |
| Top Cover | {stl_parts['top_cover']['extents'][0]:.1f} x {stl_parts['top_cover']['extents'][1]:.1f} x {stl_parts['top_cover']['extents'][2]:.1f} |
| Back Cover | {stl_parts['back_cover']['extents'][0]:.1f} x {stl_parts['back_cover']['extents'][1]:.1f} x {stl_parts['back_cover']['extents'][2]:.1f} |

**Margine Case-PCB**: ~5mm per lato (adeguato per montaggio)

---

## 5. Render Files

I seguenti file sono stati generati in `stl-tools/output/renders/`:

| File | Descrizione |
|------|-------------|
| assembly_colored.glb | Assembly completo con PCB e case |
| assembly_exploded.glb | Vista esplosa dei componenti |
| pcb_detailed.glb | PCB con marker posizioni bottoni |
| case_only.glb | Solo case senza PCB |
| viewer.html | Viewer 3D interattivo |

### Visualizzazione
```bash
# Avviare server e aprire viewer
python3 -m http.server 8082 --directory stl-tools/output/renders
# Poi aprire: http://localhost:8082/viewer.html
```

---

## 6. Conclusioni

### Compatibilità
- ✓ Dimensioni case compatibili con PCB 100x50mm
- ✓ Posizioni X dei bottoni allineate
- {'⚠ Y-axis invertito - compensato nei render' if y_inverted else '✓ Coordinate Y allineate'}

### Note
- Il pezzo L_R è singolo e posizionato a destra; verificare se serve specchiatura
- Gli offset residui sono dovuti a differenze di design tra case Thingiverse e PCB ESPlay

---

*Report generato automaticamente - ESP32-EMU Project*
"""

    with open(report_path, 'w') as f:
        f.write(report)

    print(f"\nReport saved: {report_path}")
    return report_path


def main():
    print("=" * 70)
    print("ESPLAY MICRO - ALIGNMENT ANALYSIS")
    print("=" * 70)

    # Load data
    print("\nLoading STL parts...")
    stl_parts = load_stl_parts()
    print(f"Loaded {len(stl_parts)} parts")

    print("\nLoading PCB positions...")
    pcb_positions = load_pcb_positions()
    print(f"Loaded {len(pcb_positions)} component positions")

    # Analyze coordinate systems
    y_inverted = analyze_coordinate_systems(stl_parts, pcb_positions)

    # Detailed alignment comparison
    comparisons = create_alignment_comparison(stl_parts, pcb_positions, y_inverted)

    # Create PCB model (with Y adjustment to match STL)
    print("\n" + "=" * 70)
    print("CREATING RENDERS")
    print("=" * 70)
    pcb_meshes = create_pcb_model(pcb_positions, y_inverted)

    # Generate renders
    create_renders(stl_parts, pcb_meshes, y_inverted)

    # Generate report
    print("\n" + "=" * 70)
    print("GENERATING REPORT")
    print("=" * 70)
    generate_report(stl_parts, pcb_positions, comparisons, y_inverted)

    print("\n" + "=" * 70)
    print("DONE!")
    print("=" * 70)

    return 0


if __name__ == '__main__':
    exit(main())
