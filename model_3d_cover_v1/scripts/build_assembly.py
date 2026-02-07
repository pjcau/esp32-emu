#!/usr/bin/env python3
"""
Build colored GLB assembly from model_3d_cover_v1 STL parts.
- Colorizes board using GLB reference component positions
- Colors case parts (top, bottom, buttons)
- Creates: individual colored GLBs, closed assembly, open/exploded assembly
- Adds battery visualization in back shell
- Verifies all dimensions and clearances
"""

import json
import numpy as np
import trimesh
from pathlib import Path


# ─── COLORS ──────────────────────────────────────────────────────────
COLORS = {
    # Board
    "pcb_top":       [  0, 100,  30, 255],
    "pcb_bottom":    [  0,  80,  25, 255],
    "pcb_edge":      [  0,  90,  28, 255],
    "screen":        [ 20,  20,  25, 255],
    "screen_bezel":  [ 40,  40,  45, 255],
    "button_gold":   [200, 170,  40, 255],
    "dpad_gold":     [210, 180,  50, 255],
    "usbc_metal":    [160, 165, 170, 255],
    "audio_metal":   [140, 140, 145, 255],
    "hole_ring":     [200, 170,  80, 255],
    "hole_inner":    [ 50,  50,  55, 255],
    "ic_black":      [ 15,  15,  20, 255],
    "sd_slot":       [120, 120, 125, 255],
    "shoulder_btn":  [200, 170,  40, 255],
    # Case
    "case_top":      [230, 230, 235, 255],   # Light gray/white
    "case_top_inner":[210, 210, 215, 255],
    "case_bottom":   [ 45,  45,  50, 255],   # Dark gray/black
    "case_bot_inner":[ 55,  55,  60, 255],
    # Buttons
    "btn_dpad":      [ 50,  50,  55, 255],   # Dark gray D-pad
    "btn_action":    [ 50,  50,  55, 255],   # Dark gray action btns
    # Battery
    "battery":       [ 60, 120, 200, 200],   # Blue semi-transparent
    "battery_label": [255, 200,  50, 255],   # Gold label
}

# Battery 955565: 65 x 55 x 9.5 mm
BATTERY_SIZE = [65.0, 55.0, 9.5]


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.bool_, np.integer, np.floating)):
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def load_mesh(filepath):
    mesh = trimesh.load(filepath, force='mesh')
    if isinstance(mesh, trimesh.Scene):
        meshes = [g for g in mesh.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if meshes:
            return trimesh.util.concatenate(meshes)
    return mesh


def get_glb_components(glb_path):
    """Extract component regions from GLB by color analysis."""
    scene = trimesh.load(glb_path)
    if not isinstance(scene, trimesh.Scene):
        return []

    regions = []
    for name, geom in scene.geometry.items():
        if not isinstance(geom, trimesh.Trimesh):
            continue
        bounds = geom.bounds
        dims = bounds[1] - bounds[0]
        center = (bounds[0] + bounds[1]) / 2
        color = None
        if hasattr(geom.visual, 'main_color'):
            color = tuple(geom.visual.main_color[:3].tolist())
        if color is None:
            continue

        r, g, b = color

        # Gold tact switches
        if (r, g, b) == (255, 215, 0):
            if center[2] > 0:
                key = "dpad_gold" if (center[0] < -25 and center[1] > 0) else "button_gold"
            else:
                key = "shoulder_btn"
            regions.append({"bmin": bounds[0], "bmax": bounds[1], "color_key": key, "priority": 10, "expand": 0.5})

        # Dark large = screen
        elif all(c < 60 for c in (r, g, b)) and dims[0] > 30 and dims[1] > 30:
            regions.append({"bmin": bounds[0], "bmax": bounds[1], "color_key": "screen", "priority": 20, "expand": 0})
            regions.append({
                "bmin": bounds[0] - np.array([2, 2, 0]),
                "bmax": bounds[1] + np.array([2, 2, 0.5]),
                "color_key": "screen_bezel", "priority": 15, "expand": 0
            })

        # Dark small near edge = ports
        elif all(c < 60 for c in (r, g, b)) and not (dims[0] > 20 and dims[1] > 20):
            if max(dims[0], dims[1]) >= 3 and center[1] < -18:
                key = "usbc_metal" if max(dims[0], dims[1]) > 7 else "audio_metal"
                regions.append({"bmin": bounds[0], "bmax": bounds[1], "color_key": key, "priority": 15, "expand": 0.5})
            elif dims[0] > 2 and dims[1] > 2 and dims[0] < 20:
                regions.append({"bmin": bounds[0], "bmax": bounds[1], "color_key": "ic_black", "priority": 5, "expand": 0})

        # Copper mounting pads
        elif (r, g, b) == (200, 170, 80):
            regions.append({"bmin": bounds[0], "bmax": bounds[1], "color_key": "hole_ring", "priority": 12, "expand": 1.0})

        # Gray metal parts
        elif all(40 < c < 120 for c in (r, g, b)) and (dims[0] > 5 or dims[1] > 5):
            regions.append({"bmin": bounds[0], "bmax": bounds[1], "color_key": "sd_slot", "priority": 3, "expand": 0})

    return regions


def colorize_board(mesh, regions):
    """Color board faces based on GLB component regions. Board is in GLB-centered coords."""
    n_faces = len(mesh.faces)
    face_verts = mesh.vertices[mesh.faces]
    centroids = face_verts.mean(axis=1)
    normals = mesh.face_normals

    face_colors = np.zeros((n_faces, 4), dtype=np.uint8)

    # Base: green PCB, top vs bottom
    top_mask = normals[:, 2] > 0.3
    bot_mask = normals[:, 2] < -0.3

    for i in range(n_faces):
        if top_mask[i]:
            face_colors[i] = COLORS["pcb_top"]
        elif bot_mask[i]:
            face_colors[i] = COLORS["pcb_bottom"]
        else:
            face_colors[i] = COLORS["pcb_edge"]

    # Apply component regions (already in GLB/centered coords)
    regions_sorted = sorted(regions, key=lambda r: r["priority"])
    for reg in regions_sorted:
        expand = reg.get("expand", 0.0)
        rmin = np.minimum(reg["bmin"], reg["bmax"]) - expand
        rmax = np.maximum(reg["bmin"], reg["bmax"]) + expand

        mask = (
            (centroids[:, 0] >= rmin[0]) & (centroids[:, 0] <= rmax[0]) &
            (centroids[:, 1] >= rmin[1]) & (centroids[:, 1] <= rmax[1]) &
            (centroids[:, 2] >= rmin[2]) & (centroids[:, 2] <= rmax[2])
        )
        face_colors[mask] = COLORS[reg["color_key"]]

    # Mounting holes
    hole_positions = [[-47.0, -22.0], [44.9, -23.0], [-46.0, 21.8], [46.0, 21.8]]
    for hx, hy in hole_positions:
        dist_xy = np.sqrt((centroids[:, 0] - hx)**2 + (centroids[:, 1] - hy)**2)
        inner_mask = (dist_xy < 2.0) & (~top_mask & ~bot_mask)
        ring_mask = (dist_xy >= 2.0) & (dist_xy < 4.0) & (np.abs(normals[:, 2]) > 0.3)
        face_colors[inner_mask] = COLORS["hole_inner"]
        face_colors[ring_mask] = COLORS["hole_ring"]

    mesh.visual.face_colors = face_colors
    return mesh


def colorize_case_part(mesh, color_outer, color_inner):
    """Color case part: outer faces one color, inner faces another."""
    n_faces = len(mesh.faces)
    normals = mesh.face_normals
    face_verts = mesh.vertices[mesh.faces]
    centroids = face_verts.mean(axis=1)

    face_colors = np.zeros((n_faces, 4), dtype=np.uint8)

    bounds = mesh.bounds
    center = (bounds[0] + bounds[1]) / 2

    for i in range(n_faces):
        # Simple heuristic: faces pointing outward = outer, inward = inner
        cx, cy, cz = centroids[i]
        nx, ny, nz = normals[i]

        # Determine if face is "outer" based on normal direction relative to center
        to_center = center - centroids[i]
        dot = np.dot(normals[i], to_center)

        if dot < 0:
            # Normal points away from center = outer
            face_colors[i] = color_outer
        else:
            face_colors[i] = color_inner

    mesh.visual.face_colors = face_colors
    return mesh


def colorize_buttons(mesh, color):
    """Color button assembly uniformly."""
    face_colors = np.full((len(mesh.faces), 4), color, dtype=np.uint8)
    mesh.visual.face_colors = face_colors
    return mesh


def create_battery_mesh(position):
    """Create battery box at given position (center)."""
    bx, by, bz = BATTERY_SIZE
    battery = trimesh.creation.box([bx, by, bz])
    battery.apply_translation(position)

    face_colors = np.full((len(battery.faces), 4), COLORS["battery"], dtype=np.uint8)

    # Top face = label
    normals = battery.face_normals
    top_faces = normals[:, 2] > 0.9
    face_colors[top_faces] = COLORS["battery_label"]

    battery.visual.face_colors = face_colors
    return battery


def main():
    original_dir = Path("/workspace/original")
    ref_dir = Path("/workspace/ref")
    output_dir = Path("/workspace/output")

    print("=" * 70)
    print("BUILD ASSEMBLY - Colored GLB from STL parts")
    print("=" * 70)

    # ── 1. Load all meshes ──
    print("\n--- Loading meshes ---")
    board_stl = load_mesh(original_dir / "board.stl")
    top_body = load_mesh(original_dir / "top_body.stl")
    bottom_body = load_mesh(original_dir / "bottom_body.stl")
    btn_assy_1 = load_mesh(original_dir / "btn_assy_1.stl")
    btn_assy_2 = load_mesh(original_dir / "btn_assy_2.stl")

    # Board is in corner-origin coords, case is centered at origin
    # Need to translate board to match case coordinate system
    board_bounds = board_stl.bounds
    board_center = (board_bounds[0] + board_bounds[1]) / 2
    print(f"  Board STL center: ({board_center[0]:.2f}, {board_center[1]:.2f}, {board_center[2]:.2f})")

    # Case center (average of top and bottom)
    top_center = (top_body.bounds[0] + top_body.bounds[1]) / 2
    bot_center = (bottom_body.bounds[0] + bottom_body.bounds[1]) / 2
    case_center_xy = [(top_center[0] + bot_center[0]) / 2,
                      (top_center[1] + bot_center[1]) / 2]
    print(f"  Case center XY: ({case_center_xy[0]:.2f}, {case_center_xy[1]:.2f})")

    # Translation to align board to case coords
    board_offset = np.array([
        board_center[0] - case_center_xy[0],
        board_center[1] - case_center_xy[1],
        0.0
    ])
    print(f"  Board offset to apply: ({-board_offset[0]:.2f}, {-board_offset[1]:.2f}, {-board_offset[2]:.2f})")

    # Translate board to centered coords
    board_centered = board_stl.copy()
    board_centered.apply_translation(-board_offset)

    new_board_center = (board_centered.bounds[0] + board_centered.bounds[1]) / 2
    print(f"  Board centered: ({new_board_center[0]:.2f}, {new_board_center[1]:.2f}, {new_board_center[2]:.2f})")

    # ── 2. Get GLB component regions for board colorization ──
    print("\n--- Loading GLB reference for colors ---")
    glb_path = ref_dir / "esplay_micro_pcb.glb"
    regions = get_glb_components(glb_path)
    print(f"  Found {len(regions)} color regions from GLB")

    # ── 3. Colorize all parts ──
    print("\n--- Colorizing parts ---")

    # Board (now in centered coords matching GLB)
    print("  Board...")
    board_colored = colorize_board(board_centered.copy(), regions)
    board_colored.export(output_dir / "board_colored.glb")
    print(f"    -> board_colored.glb")

    # Top body
    print("  Top body...")
    top_colored = colorize_case_part(
        top_body.copy(),
        COLORS["case_top"],
        COLORS["case_top_inner"]
    )
    top_colored.export(output_dir / "top_body_colored.glb")
    print(f"    -> top_body_colored.glb")

    # Bottom body
    print("  Bottom body...")
    bot_colored = colorize_case_part(
        bottom_body.copy(),
        COLORS["case_bottom"],
        COLORS["case_bot_inner"]
    )
    bot_colored.export(output_dir / "bottom_body_colored.glb")
    print(f"    -> bottom_body_colored.glb")

    # Button assemblies
    print("  Buttons...")
    btn1_colored = colorize_buttons(btn_assy_1.copy(), COLORS["btn_dpad"])
    btn1_colored.export(output_dir / "btn_assy_1_colored.glb")

    btn2_colored = colorize_buttons(btn_assy_2.copy(), COLORS["btn_action"])
    btn2_colored.export(output_dir / "btn_assy_2_colored.glb")
    print(f"    -> btn_assy_1_colored.glb, btn_assy_2_colored.glb")

    # ── 4. Battery placement ──
    print("\n--- Battery placement ---")
    board_z_min = board_centered.bounds[0][2]  # Bottom of board
    # Battery sits below the board with some clearance
    battery_clearance = 1.0  # mm between board bottom and battery top
    battery_z_center = board_z_min - battery_clearance - BATTERY_SIZE[2] / 2

    battery_pos = [case_center_xy[0], case_center_xy[1], battery_z_center]
    print(f"  Battery center: ({battery_pos[0]:.2f}, {battery_pos[1]:.2f}, {battery_pos[2]:.2f})")
    print(f"  Battery Z range: [{battery_z_center - BATTERY_SIZE[2]/2:.2f}, {battery_z_center + BATTERY_SIZE[2]/2:.2f}]")

    battery_mesh = create_battery_mesh(battery_pos)
    battery_mesh.export(output_dir / "battery.glb")
    print(f"    -> battery.glb")

    # ── 5. CLOSED ASSEMBLY ──
    print("\n--- Building CLOSED assembly ---")
    closed_scene = trimesh.Scene()
    closed_scene.add_geometry(board_colored, node_name="Board")
    closed_scene.add_geometry(top_colored, node_name="Top_Shell")
    closed_scene.add_geometry(bot_colored, node_name="Bottom_Shell")
    closed_scene.add_geometry(btn1_colored, node_name="Buttons_Left")
    closed_scene.add_geometry(btn2_colored, node_name="Buttons_Right")
    closed_scene.add_geometry(battery_mesh, node_name="Battery")

    closed_scene.export(output_dir / "assembly_closed.glb")
    print(f"    -> assembly_closed.glb")

    # ── 6. OPEN / EXPLODED ASSEMBLY ──
    print("\n--- Building OPEN (exploded) assembly ---")
    explode_z = 20.0  # mm separation

    open_scene = trimesh.Scene()

    # Board stays in place
    open_scene.add_geometry(board_colored, node_name="Board")

    # Top shell moves up
    top_exploded = top_colored.copy()
    top_exploded.apply_translation([0, 0, explode_z])
    open_scene.add_geometry(top_exploded, node_name="Top_Shell")

    # Buttons move up with top shell + extra
    btn1_exploded = btn1_colored.copy()
    btn1_exploded.apply_translation([0, 0, explode_z + 8])
    open_scene.add_geometry(btn1_exploded, node_name="Buttons_Left")

    btn2_exploded = btn2_colored.copy()
    btn2_exploded.apply_translation([0, 0, explode_z + 8])
    open_scene.add_geometry(btn2_exploded, node_name="Buttons_Right")

    # Bottom shell moves down
    bot_exploded = bot_colored.copy()
    bot_exploded.apply_translation([0, 0, -explode_z])
    open_scene.add_geometry(bot_exploded, node_name="Bottom_Shell")

    # Battery between bottom shell and board
    battery_exploded = battery_mesh.copy()
    battery_exploded.apply_translation([0, 0, -explode_z / 2])
    open_scene.add_geometry(battery_exploded, node_name="Battery")

    open_scene.export(output_dir / "assembly_open.glb")
    print(f"    -> assembly_open.glb")

    # ── 7. VERIFICATION ──
    print("\n" + "=" * 70)
    print("ASSEMBLY VERIFICATION")
    print("=" * 70)

    # All Z ranges (closed assembly)
    parts_info = {
        "Bottom Shell": bot_colored,
        "Battery":      battery_mesh,
        "Board":        board_colored,
        "Top Shell":    top_colored,
        "Buttons L":    btn1_colored,
        "Buttons R":    btn2_colored,
    }

    print(f"\n  Z-Stack (closed assembly):")
    print(f"  {'Part':<18} {'Z min':>8} {'Z max':>8} {'Height':>8}")
    print(f"  {'-'*46}")
    for name, mesh in parts_info.items():
        b = mesh.bounds
        print(f"  {name:<18} {b[0][2]:8.2f} {b[1][2]:8.2f} {b[1][2]-b[0][2]:8.2f}")

    # XY alignment
    print(f"\n  XY Alignment (all parts should be centered near 0,0):")
    for name, mesh in parts_info.items():
        c = (mesh.bounds[0] + mesh.bounds[1]) / 2
        print(f"  {name:<18} center=({c[0]:7.2f}, {c[1]:7.2f})")

    # Clearance checks
    print(f"\n  Clearances:")

    board_b = board_colored.bounds
    top_b = top_colored.bounds
    bot_b = bot_colored.bounds
    bat_b = battery_mesh.bounds

    # Board to top shell
    clearance_top = top_b[1][2] - board_b[1][2]
    print(f"    Board top ({board_b[1][2]:.2f}) to Top shell top ({top_b[1][2]:.2f}): {clearance_top:.2f} mm")

    # Board to bottom shell
    clearance_bot = board_b[0][2] - bot_b[0][2]
    print(f"    Board bottom ({board_b[0][2]:.2f}) to Bottom shell bottom ({bot_b[0][2]:.2f}): {clearance_bot:.2f} mm")

    # Battery to board
    gap_bat_board = board_b[0][2] - bat_b[1][2]
    print(f"    Battery top ({bat_b[1][2]:.2f}) to Board bottom ({board_b[0][2]:.2f}): gap={gap_bat_board:.2f} mm")

    # Battery to bottom shell
    gap_bat_shell = bat_b[0][2] - bot_b[0][2]
    print(f"    Battery bottom ({bat_b[0][2]:.2f}) to Bottom shell floor ({bot_b[0][2]:.2f}): gap={gap_bat_shell:.2f} mm")

    # Battery XY fit inside bottom shell
    print(f"\n  Battery fit in bottom shell:")
    bat_dims = bat_b[1] - bat_b[0]
    bot_dims = bot_b[1] - bot_b[0]
    wall_est = 2.0
    inner_x = bot_dims[0] - 2 * wall_est
    inner_y = bot_dims[1] - 2 * wall_est

    print(f"    Battery X={bat_dims[0]:.1f} in inner X={inner_x:.1f}: {'OK' if bat_dims[0] <= inner_x else 'NO FIT'} (gap={inner_x - bat_dims[0]:+.1f})")
    print(f"    Battery Y={bat_dims[1]:.1f} in inner Y={inner_y:.1f}: {'OK' if bat_dims[1] <= inner_y else 'NO FIT'} (gap={inner_y - bat_dims[1]:+.1f})")
    print(f"    Battery Z={bat_dims[2]:.1f} in available Z={clearance_bot - wall_est:.1f}: {'OK' if bat_dims[2] <= (clearance_bot - wall_est) else 'NO FIT'} (gap={clearance_bot - wall_est - bat_dims[2]:+.1f})")

    # Buttons inside top shell XY
    print(f"\n  Buttons inside top shell:")
    for bname, bmesh in [("Buttons L", btn1_colored), ("Buttons R", btn2_colored)]:
        bb = bmesh.bounds
        inside_x = bb[0][0] >= top_b[0][0] and bb[1][0] <= top_b[1][0]
        inside_y = bb[0][1] >= top_b[0][1] and bb[1][1] <= top_b[1][1]
        print(f"    {bname}: X={'OK' if inside_x else 'OUTSIDE'}, Y={'OK' if inside_y else 'OUTSIDE'}")

    # Board inside case
    print(f"\n  Board inside case envelope:")
    case_min_x = min(top_b[0][0], bot_b[0][0])
    case_max_x = max(top_b[1][0], bot_b[1][0])
    case_min_y = min(top_b[0][1], bot_b[0][1])
    case_max_y = max(top_b[1][1], bot_b[1][1])

    margin_x_min = board_b[0][0] - case_min_x
    margin_x_max = case_max_x - board_b[1][0]
    margin_y_min = board_b[0][1] - case_min_y
    margin_y_max = case_max_y - board_b[1][1]

    print(f"    X: board [{board_b[0][0]:.2f}..{board_b[1][0]:.2f}] in case [{case_min_x:.2f}..{case_max_x:.2f}]")
    print(f"       margins: left={margin_x_min:+.2f}, right={margin_x_max:+.2f} -> {'OK' if margin_x_min >= -0.1 and margin_x_max >= -0.1 else 'PROBLEM'}")
    print(f"    Y: board [{board_b[0][1]:.2f}..{board_b[1][1]:.2f}] in case [{case_min_y:.2f}..{case_max_y:.2f}]")
    print(f"       margins: front={margin_y_min:+.2f}, back={margin_y_max:+.2f} -> {'OK' if margin_y_min >= -0.1 and margin_y_max >= -0.1 else 'PROBLEM'}")

    # Overall assembly dimensions
    all_meshes = [board_colored, top_colored, bot_colored, btn1_colored, btn2_colored, battery_mesh]
    all_bounds_min = np.min([m.bounds[0] for m in all_meshes], axis=0)
    all_bounds_max = np.max([m.bounds[1] for m in all_meshes], axis=0)
    total_dims = all_bounds_max - all_bounds_min

    print(f"\n  Overall assembly dimensions:")
    print(f"    X: {total_dims[0]:.2f} mm")
    print(f"    Y: {total_dims[1]:.2f} mm")
    print(f"    Z: {total_dims[2]:.2f} mm (total height when closed)")

    # ── 8. Save verification report ──
    report = {
        "parts": {},
        "battery": {
            "size": BATTERY_SIZE,
            "position": battery_pos,
            "z_range": [battery_pos[2] - BATTERY_SIZE[2]/2, battery_pos[2] + BATTERY_SIZE[2]/2],
        },
        "clearances": {
            "board_top_to_shell_top": clearance_top,
            "battery_to_board_gap": gap_bat_board,
            "battery_to_shell_floor_gap": gap_bat_shell,
        },
        "overall_dimensions": total_dims.tolist(),
        "issues": [],
    }

    for name, mesh in parts_info.items():
        b = mesh.bounds
        c = (b[0] + b[1]) / 2
        report["parts"][name] = {
            "bounds_min": b[0].tolist(),
            "bounds_max": b[1].tolist(),
            "center": c.tolist(),
            "dimensions": (b[1] - b[0]).tolist(),
        }

    # Log issues
    if bat_dims[1] > inner_y:
        report["issues"].append(f"Battery Y ({bat_dims[1]:.1f}mm) doesn't fit in bottom shell inner Y ({inner_y:.1f}mm)")
    if bat_dims[2] > (clearance_bot - wall_est):
        report["issues"].append(f"Battery Z ({bat_dims[2]:.1f}mm) doesn't fit in available Z ({clearance_bot - wall_est:.1f}mm)")
    if margin_x_min < -0.1 or margin_x_max < -0.1:
        report["issues"].append(f"Board doesn't fit in case X (margins: {margin_x_min:+.2f}/{margin_x_max:+.2f})")
    if margin_y_min < -0.1 or margin_y_max < -0.1:
        report["issues"].append(f"Board doesn't fit in case Y (margins: {margin_y_min:+.2f}/{margin_y_max:+.2f})")

    if report["issues"]:
        print(f"\n  *** ISSUES FOUND ***")
        for issue in report["issues"]:
            print(f"    - {issue}")
    else:
        print(f"\n  All checks PASSED!")

    with open(output_dir / "assembly_report.json", "w") as f:
        json.dump(report, f, indent=2, cls=NumpyEncoder)
    print(f"\n  Saved: assembly_report.json")

    # List outputs
    print(f"\n--- Output files ---")
    for f in sorted(output_dir.glob("*.glb")):
        print(f"  {f.name} ({f.stat().st_size / 1024:.0f} KB)")

    print(f"\n{'='*70}")
    print("BUILD COMPLETE")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
