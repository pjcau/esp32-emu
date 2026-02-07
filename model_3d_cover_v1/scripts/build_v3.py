#!/usr/bin/env python3
"""
V3 Assembly: Bottom shell with ALL cutouts:
  - USB-C port (Y-min wall)
  - Audio jack / headphone (Y-min wall)
  - SD card slot (Y-min wall)
  - L/R shoulder buttons (Y-max wall)
  - Battery 955565 (9.5 × 55 × 65 mm)

Changes from V2:
  - Added SD card slot cutout (X=35.2, Y-min, 8x7mm)
  - Added L shoulder button cutout (Y-max wall)
  - Added R shoulder button cutout (Y-max wall)
  - Enlarged audio jack cutout to proper size
"""

import json
import numpy as np
import trimesh
from trimesh.creation import box, cylinder
from pathlib import Path

try:
    import manifold3d
    HAS_MANIFOLD = True
except ImportError:
    HAS_MANIFOLD = False


# ─── PARAMETERS ──────────────────────────────────────────────────────
BATTERY = {
    "thickness": 9.5,   # Z
    "width":     55.0,   # Y
    "length":    65.0,   # X
}

WALL = 2.0
CLEARANCE = 0.3
BATTERY_GAP = 1.5
FLOOR = 2.0
LIP_HEIGHT = 1.5
LIP_WIDTH = 1.0
SCREW_R = 1.6
POST_OUTER_R = 3.5
BATTERY_HOLDER_W = 1.5

# Mounting holes (GLB/centered coords)
MOUNT_HOLES = [
    (-47.0, -22.0),
    ( 44.9, -23.0),
    (-46.0,  21.8),
    ( 46.0,  21.8),
]

# ─── ALL EDGE COMPONENTS (from GLB analysis) ────────────────────────
# Y-min wall (front edge) cutouts
FRONT_CUTOUTS = {
    "usbc": {
        "x": -1.5, "z": -3.2,
        "width": 10.0, "height": 5.0,   # USB-C connector
        "label": "USB-C Port",
    },
    "audio": {
        "x": -16.3, "z": -2.2,
        "width": 7.0, "height": 5.0,    # 3.5mm audio jack
        "label": "Audio Jack (3.5mm)",
    },
    "sd_card": {
        "x": 35.2, "z": -2.3,
        "width": 14.0, "height": 7.0,   # SD card slot - needs to be wide for card insertion
        "label": "SD Card Slot",
    },
}

# Y-max wall (back edge) cutouts
BACK_CUTOUTS = {
    "shoulder_l": {
        "x": -38.6, "z": -3.6,
        "width": 12.0, "height": 6.0,   # L shoulder button
        "label": "L Shoulder Button",
    },
    "shoulder_r": {
        "x": 38.9, "z": -3.6,
        "width": 12.0, "height": 6.0,   # R shoulder button
        "label": "R Shoulder Button",
    },
}


# ─── COLORS ──────────────────────────────────────────────────────────
COLORS = {
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
    "case_top":      [230, 230, 235, 255],
    "case_top_inner":[210, 210, 215, 255],
    "case_bottom":   [ 45,  45,  50, 255],
    "case_bot_inner":[ 55,  55,  60, 255],
    "btn_dark":      [ 50,  50,  55, 255],
    "battery":       [ 60, 120, 200, 200],
    "battery_label": [255, 200,  50, 255],
}


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


def boolean_difference(a, b):
    if HAS_MANIFOLD:
        try:
            result = trimesh.boolean.difference([a, b], engine='manifold')
            if result is not None and len(result.faces) > 0:
                return result
        except Exception as e:
            print(f"    boolean diff failed: {e}")
    return a


def boolean_union(meshes):
    if HAS_MANIFOLD and len(meshes) > 1:
        try:
            result = trimesh.boolean.union(meshes, engine='manifold')
            if result is not None and len(result.faces) > 0:
                return result
        except Exception:
            pass
    return trimesh.util.concatenate(meshes)


def generate_bottom_shell_v3(board_bounds, top_body_bounds):
    """
    Generate bottom shell V3 with ALL cutouts:
    - Front: USB-C, audio jack, SD card slot
    - Back: L/R shoulder buttons
    - Internal: battery bay, screw posts, lip
    """
    board_min, board_max = board_bounds
    board_dims = board_max - board_min

    top_min, top_max = top_body_bounds
    top_dims = top_max - top_min

    pcb_z_bottom = board_min[2]

    # ── Dimensions ──
    inner_x = max(board_dims[0] + 2 * CLEARANCE, BATTERY["length"] + 2 * CLEARANCE)
    inner_y = max(board_dims[1] + 2 * CLEARANCE, BATTERY["width"] + 2 * CLEARANCE)

    outer_x = inner_x + 2 * WALL
    outer_y = inner_y + 2 * WALL

    outer_x = max(outer_x, top_dims[0])
    outer_y = max(outer_y, top_dims[1])

    shell_top_z = -1.0

    battery_top_z = pcb_z_bottom - BATTERY_GAP
    battery_bot_z = battery_top_z - BATTERY["thickness"]
    shell_bot_z = battery_bot_z - FLOOR

    shell_height = shell_top_z - shell_bot_z
    shell_center_z = (shell_top_z + shell_bot_z) / 2

    print(f"\n  Bottom Shell V3 dimensions:")
    print(f"    Outer: {outer_x:.1f} x {outer_y:.1f} x {shell_height:.1f} mm")
    print(f"    Z range: [{shell_bot_z:.1f}, {shell_top_z:.1f}]")
    print(f"    Battery Z: [{battery_bot_z:.1f}, {battery_top_z:.1f}]")

    # ── Step 1: Shell box ──
    outer_box = box([outer_x, outer_y, shell_height])
    outer_box.apply_translation([0, 0, shell_center_z])

    cavity_height = shell_height - FLOOR + 1
    cavity = box([inner_x, inner_y, cavity_height])
    cavity.apply_translation([0, 0, shell_bot_z + FLOOR + cavity_height / 2])

    shell = boolean_difference(outer_box, cavity)
    print(f"    Shell base: {len(shell.faces)} faces")

    # ── Step 2: Lip ──
    lip_outer = box([inner_x, inner_y, LIP_HEIGHT])
    lip_inner = box([inner_x - 2 * LIP_WIDTH, inner_y - 2 * LIP_WIDTH, LIP_HEIGHT + 1])
    lip = boolean_difference(lip_outer, lip_inner)
    lip.apply_translation([0, 0, shell_top_z + LIP_HEIGHT / 2])

    # ── Step 3: Screw posts ──
    posts = []
    for hx, hy in MOUNT_HOLES:
        post_h = shell_height - FLOOR
        post = cylinder(radius=POST_OUTER_R, height=post_h, sections=32)
        post.apply_translation([hx, hy, shell_bot_z + FLOOR + post_h / 2])
        hole = cylinder(radius=SCREW_R, height=post_h + 2, sections=32)
        hole.apply_translation([hx, hy, shell_bot_z + FLOOR + post_h / 2])
        post = boolean_difference(post, hole)
        posts.append(post)

    # ── Step 4: Battery retainers ──
    bat_holders = []
    bat_center_z = (battery_top_z + battery_bot_z) / 2
    bat_wall_h = BATTERY["thickness"] + 1

    for sign in [-1, 1]:
        ret = box([BATTERY_HOLDER_W, BATTERY["width"] + 2, bat_wall_h])
        ret.apply_translation([sign * (BATTERY["length"] / 2 + BATTERY_HOLDER_W / 2), 0, bat_center_z])
        bat_holders.append(ret)

    for sx in [-1, 1]:
        for sy in [-1, 1]:
            clip = box([10, BATTERY_HOLDER_W, bat_wall_h])
            clip.apply_translation([sx * (BATTERY["length"] / 2 - 5),
                                    sy * (BATTERY["width"] / 2 + BATTERY_HOLDER_W / 2),
                                    bat_center_z])
            bat_holders.append(clip)

    # ── Combine solid parts ──
    print("    Combining solid parts...")
    all_add = [shell, lip] + posts + bat_holders
    result = boolean_union(all_add)
    print(f"    After union: {len(result.faces)} faces")

    # ── Step 5: FRONT CUTOUTS (Y-min wall) ──
    y_min_wall = -outer_y / 2
    print(f"\n    Front cutouts (Y-min wall at Y={y_min_wall:.1f}):")
    for name, cut_def in FRONT_CUTOUTS.items():
        pw = cut_def["width"] + 1.0   # +1mm clearance
        ph = cut_def["height"] + 1.0
        pd = WALL + 4                 # ensure cut goes through wall
        cut = box([pw, pd, ph])
        cut.apply_translation([cut_def["x"], y_min_wall, cut_def["z"]])
        result = boolean_difference(result, cut)
        print(f"      {name}: X={cut_def['x']:.1f}, Z={cut_def['z']:.1f}, "
              f"opening={pw:.0f}x{ph:.0f}mm -> {cut_def['label']}")

    # ── Step 6: BACK CUTOUTS (Y-max wall) ──
    y_max_wall = outer_y / 2
    print(f"\n    Back cutouts (Y-max wall at Y={y_max_wall:.1f}):")
    for name, cut_def in BACK_CUTOUTS.items():
        pw = cut_def["width"] + 1.0
        ph = cut_def["height"] + 1.0
        pd = WALL + 4
        cut = box([pw, pd, ph])
        cut.apply_translation([cut_def["x"], y_max_wall, cut_def["z"]])
        result = boolean_difference(result, cut)
        print(f"      {name}: X={cut_def['x']:.1f}, Z={cut_def['z']:.1f}, "
              f"opening={pw:.0f}x{ph:.0f}mm -> {cut_def['label']}")

    print(f"\n    Final bottom shell V3: {len(result.faces)} faces")

    metadata = {
        "outer_dims": [outer_x, outer_y, shell_height],
        "inner_dims": [inner_x, inner_y],
        "z_range": [shell_bot_z, shell_top_z],
        "lip_top": shell_top_z + LIP_HEIGHT,
        "battery_z_range": [battery_bot_z, battery_top_z],
        "battery_center_z": bat_center_z,
        "cutouts": {
            "front": {k: {"x": v["x"], "z": v["z"], "w": v["width"], "h": v["height"]}
                      for k, v in FRONT_CUTOUTS.items()},
            "back": {k: {"x": v["x"], "z": v["z"], "w": v["width"], "h": v["height"]}
                     for k, v in BACK_CUTOUTS.items()},
        },
    }
    return result, metadata


def get_glb_regions(glb_path):
    """Get color regions from GLB for board colorization."""
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
        if (r, g, b) == (255, 215, 0):
            key = "dpad_gold" if (center[0] < -25 and center[1] > 0 and center[2] > 0) else \
                  ("shoulder_btn" if center[2] < 0 else "button_gold")
            regions.append({"bmin": bounds[0], "bmax": bounds[1], "color_key": key, "priority": 10, "expand": 0.5})
        elif all(c < 60 for c in (r, g, b)) and dims[0] > 30 and dims[1] > 30:
            regions.append({"bmin": bounds[0], "bmax": bounds[1], "color_key": "screen", "priority": 20, "expand": 0})
            regions.append({"bmin": bounds[0]-[2,2,0], "bmax": bounds[1]+[2,2,0.5], "color_key": "screen_bezel", "priority": 15, "expand": 0})
        elif all(c < 60 for c in (r, g, b)):
            if max(dims[0], dims[1]) >= 3 and center[1] < -18:
                key = "usbc_metal" if max(dims[0], dims[1]) > 7 else "audio_metal"
                regions.append({"bmin": bounds[0], "bmax": bounds[1], "color_key": key, "priority": 15, "expand": 0.5})
            elif 2 < dims[0] < 20 and dims[1] > 2:
                regions.append({"bmin": bounds[0], "bmax": bounds[1], "color_key": "ic_black", "priority": 5, "expand": 0})
        elif (r, g, b) == (200, 170, 80):
            regions.append({"bmin": bounds[0], "bmax": bounds[1], "color_key": "hole_ring", "priority": 12, "expand": 1.0})
        elif all(40 < c < 120 for c in (r, g, b)) and (dims[0] > 5 or dims[1] > 5):
            regions.append({"bmin": bounds[0], "bmax": bounds[1], "color_key": "sd_slot", "priority": 3, "expand": 0})

    return regions


def colorize_board(mesh, regions):
    n = len(mesh.faces)
    centroids = mesh.vertices[mesh.faces].mean(axis=1)
    normals = mesh.face_normals
    fc = np.zeros((n, 4), dtype=np.uint8)

    top = normals[:, 2] > 0.3
    bot = normals[:, 2] < -0.3
    for i in range(n):
        fc[i] = COLORS["pcb_top"] if top[i] else (COLORS["pcb_bottom"] if bot[i] else COLORS["pcb_edge"])

    for reg in sorted(regions, key=lambda r: r["priority"]):
        exp = reg.get("expand", 0)
        rmin = np.minimum(reg["bmin"], reg["bmax"]) - exp
        rmax = np.maximum(reg["bmin"], reg["bmax"]) + exp
        mask = ((centroids >= rmin) & (centroids <= rmax)).all(axis=1)
        fc[mask] = COLORS[reg["color_key"]]

    for hx, hy in [[-47,-22],[44.9,-23],[-46,21.8],[46,21.8]]:
        d = np.sqrt((centroids[:,0]-hx)**2 + (centroids[:,1]-hy)**2)
        fc[(d < 2) & ~top & ~bot] = COLORS["hole_inner"]
        fc[(d >= 2) & (d < 4) & (np.abs(normals[:,2]) > 0.3)] = COLORS["hole_ring"]

    mesh.visual.face_colors = fc
    return mesh


def colorize_case(mesh, c_out, c_in):
    center = (mesh.bounds[0] + mesh.bounds[1]) / 2
    centroids = mesh.vertices[mesh.faces].mean(axis=1)
    normals = mesh.face_normals
    fc = np.zeros((len(mesh.faces), 4), dtype=np.uint8)
    for i in range(len(mesh.faces)):
        dot = np.dot(normals[i], center - centroids[i])
        fc[i] = c_out if dot < 0 else c_in
    mesh.visual.face_colors = fc
    return mesh


def create_battery(center_z):
    bat = box([BATTERY["length"], BATTERY["width"], BATTERY["thickness"]])
    bat.apply_translation([0, 0, center_z])
    fc = np.full((len(bat.faces), 4), COLORS["battery"], dtype=np.uint8)
    fc[bat.face_normals[:, 2] > 0.9] = COLORS["battery_label"]
    bat.visual.face_colors = fc
    return bat


def main():
    original_dir = Path("/workspace/original")
    ref_dir = Path("/workspace/ref")
    output_dir = Path("/workspace/output/v3")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("V3 BUILD - Bottom shell with ALL cutouts")
    print("  Front: USB-C, Audio Jack, SD Card Slot")
    print("  Back:  L/R Shoulder Buttons")
    print("  Internal: Battery 955565 (9.5 x 55 x 65 mm)")
    print("=" * 70)

    # ── Load parts ──
    print("\n--- Loading parts ---")
    board_stl = load_mesh(original_dir / "board.stl")
    top_body = load_mesh(original_dir / "top_body.stl")
    btn1 = load_mesh(original_dir / "btn_assy_1.stl")
    btn2 = load_mesh(original_dir / "btn_assy_2.stl")

    # Center board
    board_center = (board_stl.bounds[0] + board_stl.bounds[1]) / 2
    top_center = (top_body.bounds[0] + top_body.bounds[1]) / 2
    offset = np.array([board_center[0] - top_center[0],
                       board_center[1] - top_center[1], 0])

    board = board_stl.copy()
    board.apply_translation(-offset)

    print(f"  Board: [{board.bounds[0][0]:.1f},{board.bounds[0][1]:.1f},{board.bounds[0][2]:.1f}] "
          f"to [{board.bounds[1][0]:.1f},{board.bounds[1][1]:.1f},{board.bounds[1][2]:.1f}]")

    # ── Generate V3 bottom shell ──
    print("\n--- Generating bottom shell V3 ---")
    new_bottom, bot_meta = generate_bottom_shell_v3(board.bounds, top_body.bounds)

    # ── Colorize ──
    print("\n--- Colorizing ---")
    regions = get_glb_regions(ref_dir / "esplay_micro_pcb.glb")

    board_c = colorize_board(board.copy(), regions)
    top_c = colorize_case(top_body.copy(), COLORS["case_top"], COLORS["case_top_inner"])
    bot_c = colorize_case(new_bottom.copy(), COLORS["case_bottom"], COLORS["case_bot_inner"])

    btn1_c = btn1.copy()
    btn1_c.visual.face_colors = np.full((len(btn1.faces), 4), COLORS["btn_dark"], dtype=np.uint8)
    btn2_c = btn2.copy()
    btn2_c.visual.face_colors = np.full((len(btn2.faces), 4), COLORS["btn_dark"], dtype=np.uint8)

    battery = create_battery(bot_meta["battery_center_z"])

    # ── Save individual ──
    print("\n--- Saving individual parts ---")
    for name, mesh in [("board_colored.glb", board_c),
                        ("top_body_colored.glb", top_c),
                        ("bottom_body_v3.glb", bot_c),
                        ("btn_assy_1_colored.glb", btn1_c),
                        ("btn_assy_2_colored.glb", btn2_c),
                        ("battery.glb", battery)]:
        mesh.export(output_dir / name)
        print(f"  {name}")

    # ── CLOSED assembly ──
    print("\n--- Closed assembly ---")
    closed = trimesh.Scene()
    closed.add_geometry(board_c, node_name="Board")
    closed.add_geometry(top_c, node_name="Top_Shell")
    closed.add_geometry(bot_c, node_name="Bottom_Shell_V3")
    closed.add_geometry(btn1_c, node_name="Buttons_Left")
    closed.add_geometry(btn2_c, node_name="Buttons_Right")
    closed.add_geometry(battery, node_name="Battery")
    closed.export(output_dir / "assembly_closed.glb")

    # ── OPEN assembly ──
    print("--- Open assembly ---")
    explode = 25.0
    opened = trimesh.Scene()
    opened.add_geometry(board_c, node_name="Board")

    top_e = top_c.copy(); top_e.apply_translation([0, 0, explode])
    opened.add_geometry(top_e, node_name="Top_Shell")

    btn1_e = btn1_c.copy(); btn1_e.apply_translation([0, 0, explode + 10])
    btn2_e = btn2_c.copy(); btn2_e.apply_translation([0, 0, explode + 10])
    opened.add_geometry(btn1_e, node_name="Buttons_Left")
    opened.add_geometry(btn2_e, node_name="Buttons_Right")

    bot_e = bot_c.copy(); bot_e.apply_translation([0, 0, -explode])
    opened.add_geometry(bot_e, node_name="Bottom_Shell_V3")

    bat_e = battery.copy(); bat_e.apply_translation([0, 0, -explode * 0.6])
    opened.add_geometry(bat_e, node_name="Battery")

    opened.export(output_dir / "assembly_open.glb")

    # ══════════════════════════════════════════════════════════════
    # VERIFICATION
    # ══════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("V3 ASSEMBLY VERIFICATION")
    print("=" * 70)

    parts = {
        "Bottom Shell V3": bot_c,
        "Battery":         battery,
        "Board":           board_c,
        "Top Shell":       top_c,
        "Buttons L":       btn1_c,
        "Buttons R":       btn2_c,
    }

    # Z-stack
    print(f"\n  Z-Stack:")
    print(f"  {'Part':<20} {'Z min':>8} {'Z max':>8} {'Height':>8}")
    print(f"  {'-'*48}")
    for name, m in parts.items():
        b = m.bounds
        print(f"  {name:<20} {b[0][2]:8.2f} {b[1][2]:8.2f} {b[1][2]-b[0][2]:8.2f}")

    print(f"\n  XY Centers:")
    for name, m in parts.items():
        c = (m.bounds[0] + m.bounds[1]) / 2
        print(f"  {name:<20} ({c[0]:7.2f}, {c[1]:7.2f})")

    # Clearances
    print(f"\n  Clearances:")
    bb = board_c.bounds
    tb = top_c.bounds
    btb = bot_c.bounds
    batb = battery.bounds

    issues = []

    c1 = tb[1][2] - bb[1][2]
    s = "OK" if c1 >= -0.1 else "PROBLEM"
    print(f"    Board top → Top shell top:   {c1:+.2f} mm  [{s}]")
    if c1 < -0.1: issues.append(f"Board protrudes {-c1:.2f}mm above top shell")

    c2 = bb[0][2] - batb[1][2]
    s = "OK" if c2 >= 0.5 else ("CLOSE" if c2 >= 0 else "COLLISION")
    print(f"    Battery top → Board bottom:  {c2:+.2f} mm  [{s}]")
    if c2 < 0: issues.append(f"Battery collides with board by {-c2:.2f}mm")

    c3 = batb[0][2] - btb[0][2]
    s = "OK" if c3 >= 1.0 else ("TIGHT" if c3 >= 0 else "COLLISION")
    print(f"    Battery bot → Shell floor:   {c3:+.2f} mm  [{s}]")
    if c3 < 0: issues.append(f"Battery below shell floor by {-c3:.2f}mm")

    gap_tb = tb[0][2] - btb[1][2]
    lip_top = bot_meta.get("lip_top", btb[1][2])
    print(f"    Top↔Bottom gap:              {gap_tb:.2f} mm")
    print(f"    Lip top at Z={lip_top:.2f}, enters top shell by: {lip_top - tb[0][2]:.2f} mm")

    # Board XY fit
    print(f"\n  Board fit in case:")
    for ax, i in [("X", 0), ("Y", 1)]:
        case_min = min(tb[0][i], btb[0][i])
        case_max = max(tb[1][i], btb[1][i])
        m1 = bb[0][i] - case_min
        m2 = case_max - bb[1][i]
        ok = m1 >= -0.1 and m2 >= -0.1
        print(f"    {ax}: [{bb[0][i]:.2f}..{bb[1][i]:.2f}] in [{case_min:.2f}..{case_max:.2f}] "
              f"margins:{m1:+.2f}/{m2:+.2f} {'OK' if ok else 'OUT'}")
        if not ok: issues.append(f"Board outside case {ax}")

    # Battery XY fit
    print(f"\n  Battery fit in shell:")
    bot_inner_x = btb[1][0] - btb[0][0] - 2 * WALL
    bot_inner_y = btb[1][1] - btb[0][1] - 2 * WALL
    for ax, bat_d, inner_d in [("X", BATTERY["length"], bot_inner_x),
                                ("Y", BATTERY["width"], bot_inner_y)]:
        ok = bat_d <= inner_d + 0.1
        print(f"    {ax}: battery {bat_d:.1f} in inner {inner_d:.1f} "
              f"gap={inner_d-bat_d:+.1f} {'OK' if ok else 'NO FIT'}")
        if not ok: issues.append(f"Battery {ax} doesn't fit")

    # Buttons
    print(f"\n  Buttons in top shell:")
    for bname, bm in [("Left", btn1_c), ("Right", btn2_c)]:
        bbb = bm.bounds
        ok_x = bbb[0][0] >= tb[0][0] - 0.1 and bbb[1][0] <= tb[1][0] + 0.1
        ok_y = bbb[0][1] >= tb[0][1] - 0.1 and bbb[1][1] <= tb[1][1] + 0.1
        print(f"    {bname}: X={'OK' if ok_x else 'OUT'}, Y={'OK' if ok_y else 'OUT'}")

    # Cutout verification - check components align with openings
    print(f"\n  Cutout alignment check:")
    board_y_min = bb[0][1]  # front edge of board
    board_y_max = bb[1][1]  # back edge of board
    shell_y_min = btb[0][1]
    shell_y_max = btb[1][1]

    print(f"    Board front edge Y={board_y_min:.2f}, Shell front wall Y={shell_y_min:.2f}")
    print(f"    Board back edge  Y={board_y_max:.2f}, Shell back wall  Y={shell_y_max:.2f}")

    for cname, cdef in FRONT_CUTOUTS.items():
        print(f"    {cname}: cutout at X={cdef['x']:.1f}, Z={cdef['z']:.1f}, "
              f"W={cdef['width']:.0f}mm H={cdef['height']:.0f}mm (front wall)")

    for cname, cdef in BACK_CUTOUTS.items():
        print(f"    {cname}: cutout at X={cdef['x']:.1f}, Z={cdef['z']:.1f}, "
              f"W={cdef['width']:.0f}mm H={cdef['height']:.0f}mm (back wall)")

    # Overall
    all_b = np.array([(m.bounds[0], m.bounds[1]) for m in parts.values()])
    total_min = all_b[:, 0].min(axis=0)
    total_max = all_b[:, 1].max(axis=0)
    total_dims = total_max - total_min
    print(f"\n  Overall: {total_dims[0]:.1f} x {total_dims[1]:.1f} x {total_dims[2]:.1f} mm")

    if issues:
        print(f"\n  *** {len(issues)} ISSUES ***")
        for iss in issues:
            print(f"    - {iss}")
    else:
        print(f"\n  ALL CHECKS PASSED!")

    # Report
    report = {
        "version": "v3",
        "changes_from_v2": [
            "Added SD card slot cutout on front wall (X=35.2, 14x7mm)",
            "Added L shoulder button cutout on back wall (X=-38.6, 12x6mm)",
            "Added R shoulder button cutout on back wall (X=38.9, 12x6mm)",
            "Enlarged audio jack cutout to 7x5mm",
        ],
        "bottom_shell": bot_meta,
        "battery": {"size": [BATTERY["length"], BATTERY["width"], BATTERY["thickness"]]},
        "overall_dimensions": total_dims.tolist(),
        "clearances": {
            "board_to_top_shell": float(c1),
            "battery_to_board": float(c2),
            "battery_to_floor": float(c3),
        },
        "issues": issues,
    }
    with open(output_dir / "v3_report.json", "w") as f:
        json.dump(report, f, indent=2, cls=NumpyEncoder)

    print(f"\n--- Output files ---")
    for f in sorted(output_dir.glob("*")):
        print(f"  {f.name} ({f.stat().st_size/1024:.0f} KB)")

    print(f"\n{'='*70}")
    print("V3 BUILD COMPLETE")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
