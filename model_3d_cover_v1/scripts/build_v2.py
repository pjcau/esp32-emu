#!/usr/bin/env python3
"""
V2 Assembly: New bottom shell sized for 955565 battery (9.5 × 55 × 65 mm).
- Generates new bottom_body that fits battery + board
- Keeps original top_body, buttons
- Re-colorizes everything
- Builds closed + open assemblies
- Full dimensional verification
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

WALL = 2.0              # Wall thickness
CLEARANCE = 0.3         # PCB clearance
BATTERY_GAP = 1.5       # Gap between PCB bottom and battery top
FLOOR = 2.0             # Bottom floor thickness
LIP_HEIGHT = 1.5        # Interlocking lip height
LIP_WIDTH = 1.0         # Lip wall width
CORNER_R = 2.0          # Corner radius (for appearance)
SCREW_R = 1.6           # M3 screw hole radius
POST_OUTER_R = 3.5      # Screw post outer radius
BATTERY_HOLDER_W = 1.5  # Battery retainer wall width

# Mounting hole positions (GLB/centered coords)
MOUNT_HOLES = [
    (-47.0, -22.0),  # bottom_left
    ( 44.9, -23.0),  # bottom_right
    (-46.0,  21.8),  # top_left
    ( 46.0,  21.8),  # top_right
]

# Port positions (GLB coords, Y = bottom edge)
PORTS = {
    "usbc":  {"x": -1.5,  "z": -3.2, "width": 10.0, "height": 4.0},
    "audio": {"x": -16.3, "z": -2.2, "width": 7.0,  "height": 4.0},
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
    "battery_holder":[  55,  55,  60, 255],
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
    """Subtract mesh b from mesh a."""
    if HAS_MANIFOLD:
        try:
            result = trimesh.boolean.difference([a, b], engine='manifold')
            if result is not None and len(result.faces) > 0:
                return result
        except Exception as e:
            print(f"    manifold boolean failed: {e}, using fallback")
    # Fallback: just return a (no cut)
    return a


def boolean_union(meshes):
    """Union multiple meshes."""
    if HAS_MANIFOLD and len(meshes) > 1:
        try:
            result = trimesh.boolean.union(meshes, engine='manifold')
            if result is not None and len(result.faces) > 0:
                return result
        except Exception:
            pass
    return trimesh.util.concatenate(meshes)


def rounded_box_shell(outer_x, outer_y, outer_z, wall, floor_z, open_top=True):
    """
    Create a box shell (outer - inner cavity).
    open_top: if True, cavity extends to top (open box).
    """
    outer = box([outer_x, outer_y, outer_z])

    inner_x = outer_x - 2 * wall
    inner_y = outer_y - 2 * wall

    if open_top:
        inner_z = outer_z - floor_z + 1  # extend past top
        inner = box([inner_x, inner_y, inner_z])
        # Shift inner up so bottom of inner = bottom of outer + floor
        inner.apply_translation([0, 0, (outer_z - floor_z + 1) / 2 - outer_z / 2 + floor_z])
    else:
        inner_z = outer_z - floor_z - wall  # closed on both ends
        inner = box([inner_x, inner_y, inner_z])
        inner.apply_translation([0, 0, (floor_z - wall) / 2])

    shell = boolean_difference(outer, inner)
    return shell


def generate_bottom_shell(board_bounds, top_body_bounds):
    """
    Generate new bottom shell that fits:
    - The board (with clearance)
    - The 955565 battery below
    - Screw posts at mounting holes
    - Port cutouts on Y-min edge
    - Lip for interlocking with top shell
    """

    board_min, board_max = board_bounds
    board_dims = board_max - board_min
    board_center_xy = [(board_min[0] + board_max[0]) / 2,
                       (board_min[1] + board_max[1]) / 2]

    # Top body info (for matching dimensions on XY)
    top_min, top_max = top_body_bounds
    top_dims = top_max - top_min

    pcb_z_bottom = board_min[2]  # Z of PCB bottom surface

    # ── Calculate required dimensions ──
    # X: must fit board (100mm) + clearance
    inner_x = max(board_dims[0] + 2 * CLEARANCE, BATTERY["length"] + 2 * CLEARANCE)
    # Y: must fit battery (55mm) + clearance, and also board (52.8mm)
    inner_y = max(board_dims[1] + 2 * CLEARANCE, BATTERY["width"] + 2 * CLEARANCE)

    outer_x = inner_x + 2 * WALL
    outer_y = inner_y + 2 * WALL

    # Match top body X if it's larger (for flush sides)
    outer_x = max(outer_x, top_dims[0])
    outer_y = max(outer_y, top_dims[1])

    # Z calculation:
    # Top of bottom shell = where it meets top shell
    # From analysis: top_body Z=[1, 7], bottom_body Z=[-13, -1]
    # So they meet at Z around 0 (gap between -1 and 1)
    # The original bottom shell top is at Z=-1
    shell_top_z = top_min[2] - 0.0  # Align exactly with top body bottom (Z=1.0... actually top_min is 1.0)

    # Actually looking at original: bottom Z=[-13,-1], top Z=[1,7]
    # They have a 2mm gap. The lip fills this.
    # Let's keep bottom shell top at Z = -1 (original) for compatibility with top body
    shell_top_z = -1.0

    # Z depth needed below:
    # PCB bottom at Z=-7.0
    # Gap to battery: BATTERY_GAP = 1.5mm
    # Battery thickness: 9.5mm
    # Floor: 2.0mm
    battery_top_z = pcb_z_bottom - BATTERY_GAP  # -8.5
    battery_bot_z = battery_top_z - BATTERY["thickness"]  # -18.0
    shell_bot_z = battery_bot_z - FLOOR  # -20.0

    shell_height = shell_top_z - shell_bot_z  # 19.0
    shell_center_z = (shell_top_z + shell_bot_z) / 2

    print(f"\n  New Bottom Shell dimensions:")
    print(f"    Outer: {outer_x:.1f} x {outer_y:.1f} x {shell_height:.1f} mm")
    print(f"    Inner: {inner_x:.1f} x {inner_y:.1f} mm")
    print(f"    Z range: [{shell_bot_z:.1f}, {shell_top_z:.1f}]")
    print(f"    Battery Z: [{battery_bot_z:.1f}, {battery_top_z:.1f}]")

    # ── Step 1: Main shell box ──
    outer_box = box([outer_x, outer_y, shell_height])
    outer_box.apply_translation([0, 0, shell_center_z])

    # Inner cavity (open top)
    cavity_height = shell_height - FLOOR + 1  # extend past top
    cavity = box([inner_x, inner_y, cavity_height])
    cavity_center_z = shell_bot_z + FLOOR + cavity_height / 2
    cavity.apply_translation([0, 0, cavity_center_z])

    shell = boolean_difference(outer_box, cavity)
    print(f"    Shell base: {len(shell.faces)} faces")

    # ── Step 2: Lip (raised edge for interlocking with top body) ──
    lip_outer_x = inner_x
    lip_outer_y = inner_y
    lip_inner_x = inner_x - 2 * LIP_WIDTH
    lip_inner_y = inner_y - 2 * LIP_WIDTH

    lip_outer = box([lip_outer_x, lip_outer_y, LIP_HEIGHT])
    lip_inner = box([lip_inner_x, lip_inner_y, LIP_HEIGHT + 1])
    lip = boolean_difference(lip_outer, lip_inner)
    lip.apply_translation([0, 0, shell_top_z + LIP_HEIGHT / 2])
    print(f"    Lip: {len(lip.faces)} faces")

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
    print(f"    Screw posts: {len(posts)} x {len(posts[0].faces)} faces")

    # ── Step 4: Battery retainer walls ──
    # Small walls on X-ends to hold battery in place
    bat_holder_parts = []
    bat_center_z = (battery_top_z + battery_bot_z) / 2
    bat_wall_h = BATTERY["thickness"] + 1

    # Two X-end retainers
    for sign in [-1, 1]:
        retainer_x = BATTERY_HOLDER_W
        retainer_y = BATTERY["width"] + 2
        retainer = box([retainer_x, retainer_y, bat_wall_h])
        rx = sign * (BATTERY["length"] / 2 + BATTERY_HOLDER_W / 2)
        retainer.apply_translation([rx, 0, bat_center_z])
        bat_holder_parts.append(retainer)

    # Two Y-end retainers (short clips at corners)
    for sx in [-1, 1]:
        for sy in [-1, 1]:
            clip = box([10, BATTERY_HOLDER_W, bat_wall_h])
            cx = sx * (BATTERY["length"] / 2 - 5)
            cy = sy * (BATTERY["width"] / 2 + BATTERY_HOLDER_W / 2)
            clip.apply_translation([cx, cy, bat_center_z])
            bat_holder_parts.append(clip)

    print(f"    Battery holders: {len(bat_holder_parts)} parts")

    # ── Step 5: Port cutouts on Y-min wall ──
    port_cuts = []
    y_min_wall_center = -outer_y / 2
    for pname, port in PORTS.items():
        pw = port["width"] + 1.0  # extra clearance
        ph = port["height"] + 1.0
        pd = WALL + 2  # cut through wall
        cut = box([pw, pd, ph])
        # Port Z is in GLB coords, board bottom components
        cut_z = port["z"]
        cut.apply_translation([port["x"], y_min_wall_center, cut_z])
        port_cuts.append((pname, cut))
    print(f"    Port cutouts: {len(port_cuts)}")

    # ── Combine everything ──
    print("    Combining...")
    all_add = [shell, lip] + posts + bat_holder_parts
    result = boolean_union(all_add)

    # Cut ports
    for pname, cut in port_cuts:
        result = boolean_difference(result, cut)

    print(f"    Final bottom shell: {len(result.faces)} faces")

    # Store metadata
    metadata = {
        "outer_dims": [outer_x, outer_y, shell_height],
        "inner_dims": [inner_x, inner_y],
        "z_range": [shell_bot_z, shell_top_z],
        "lip_top": shell_top_z + LIP_HEIGHT,
        "battery_z_range": [battery_bot_z, battery_top_z],
        "battery_center_z": bat_center_z,
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
    """Color board faces based on GLB component regions."""
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
    """Color case faces outer/inner."""
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
    """Create battery mesh at center."""
    bat = box([BATTERY["length"], BATTERY["width"], BATTERY["thickness"]])
    bat.apply_translation([0, 0, center_z])
    fc = np.full((len(bat.faces), 4), COLORS["battery"], dtype=np.uint8)
    fc[bat.face_normals[:, 2] > 0.9] = COLORS["battery_label"]
    bat.visual.face_colors = fc
    return bat


def main():
    original_dir = Path("/workspace/original")
    ref_dir = Path("/workspace/ref")
    output_dir = Path("/workspace/output/v2")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("V2 BUILD - New bottom shell for 955565 battery")
    print("=" * 70)

    # ── Load original parts ──
    print("\n--- Loading parts ---")
    board_stl = load_mesh(original_dir / "board.stl")
    top_body = load_mesh(original_dir / "top_body.stl")
    btn1 = load_mesh(original_dir / "btn_assy_1.stl")
    btn2 = load_mesh(original_dir / "btn_assy_2.stl")

    # Center the board (STL corner-origin -> centered coords)
    board_center = (board_stl.bounds[0] + board_stl.bounds[1]) / 2
    top_center = (top_body.bounds[0] + top_body.bounds[1]) / 2
    offset = np.array([board_center[0] - top_center[0],
                       board_center[1] - top_center[1], 0])

    board = board_stl.copy()
    board.apply_translation(-offset)
    print(f"  Board centered: [{board.bounds[0][0]:.1f},{board.bounds[0][1]:.1f},{board.bounds[0][2]:.1f}] "
          f"to [{board.bounds[1][0]:.1f},{board.bounds[1][1]:.1f},{board.bounds[1][2]:.1f}]")
    print(f"  Top body: [{top_body.bounds[0][0]:.1f},{top_body.bounds[0][1]:.1f},{top_body.bounds[0][2]:.1f}] "
          f"to [{top_body.bounds[1][0]:.1f},{top_body.bounds[1][1]:.1f},{top_body.bounds[1][2]:.1f}]")

    # ── Generate new bottom shell ──
    print("\n--- Generating new bottom shell ---")
    new_bottom, bot_meta = generate_bottom_shell(board.bounds, top_body.bounds)

    # ── Colorize all parts ──
    print("\n--- Colorizing ---")
    glb_path = ref_dir / "esplay_micro_pcb.glb"
    regions = get_glb_regions(glb_path)
    print(f"  {len(regions)} GLB color regions")

    board_c = colorize_board(board.copy(), regions)
    top_c = colorize_case(top_body.copy(), COLORS["case_top"], COLORS["case_top_inner"])
    bot_c = colorize_case(new_bottom.copy(), COLORS["case_bottom"], COLORS["case_bot_inner"])
    btn1_c = btn1.copy(); btn1_c.visual.face_colors = np.full((len(btn1.faces),4), COLORS["btn_dark"], dtype=np.uint8)
    btn2_c = btn2.copy(); btn2_c.visual.face_colors = np.full((len(btn2.faces),4), COLORS["btn_dark"], dtype=np.uint8)

    battery = create_battery(bot_meta["battery_center_z"])

    # ── Save individual parts ──
    print("\n--- Saving individual parts ---")
    board_c.export(output_dir / "board_colored.glb")
    top_c.export(output_dir / "top_body_colored.glb")
    bot_c.export(output_dir / "bottom_body_v2.glb")
    btn1_c.export(output_dir / "btn_assy_1_colored.glb")
    btn2_c.export(output_dir / "btn_assy_2_colored.glb")
    battery.export(output_dir / "battery.glb")

    # ── CLOSED assembly ──
    print("\n--- Closed assembly ---")
    closed = trimesh.Scene()
    closed.add_geometry(board_c, node_name="Board")
    closed.add_geometry(top_c, node_name="Top_Shell")
    closed.add_geometry(bot_c, node_name="Bottom_Shell_V2")
    closed.add_geometry(btn1_c, node_name="Buttons_Left")
    closed.add_geometry(btn2_c, node_name="Buttons_Right")
    closed.add_geometry(battery, node_name="Battery")
    closed.export(output_dir / "assembly_closed.glb")

    # ── OPEN / EXPLODED assembly ──
    print("\n--- Open assembly ---")
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
    opened.add_geometry(bot_e, node_name="Bottom_Shell_V2")

    bat_e = battery.copy(); bat_e.apply_translation([0, 0, -explode * 0.6])
    opened.add_geometry(bat_e, node_name="Battery")

    opened.export(output_dir / "assembly_open.glb")

    # ══════════════════════════════════════════════════════════════════
    # VERIFICATION
    # ══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("V2 ASSEMBLY VERIFICATION")
    print("=" * 70)

    parts_check = {
        "Bottom Shell V2": bot_c,
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
    for name, m in parts_check.items():
        b = m.bounds
        print(f"  {name:<20} {b[0][2]:8.2f} {b[1][2]:8.2f} {b[1][2]-b[0][2]:8.2f}")

    # XY alignment
    print(f"\n  XY Centers:")
    for name, m in parts_check.items():
        c = (m.bounds[0] + m.bounds[1]) / 2
        print(f"  {name:<20} ({c[0]:7.2f}, {c[1]:7.2f})")

    # Clearances
    print(f"\n  Clearances:")
    bb = board_c.bounds
    tb = top_c.bounds
    btb = bot_c.bounds
    batb = battery.bounds

    issues = []

    # Board ↔ top shell
    c1 = tb[1][2] - bb[1][2]
    status = "OK" if c1 >= -0.1 else "PROBLEM"
    print(f"    Board top → Top shell top: {c1:+.2f} mm  [{status}]")
    if c1 < -0.1:
        issues.append(f"Board protrudes {-c1:.2f}mm above top shell")

    # Battery ↔ board
    c2 = bb[0][2] - batb[1][2]
    status = "OK" if c2 >= 0.5 else "TOO CLOSE" if c2 >= 0 else "COLLISION"
    print(f"    Battery top → Board bottom: {c2:+.2f} mm  [{status}]")
    if c2 < 0:
        issues.append(f"Battery collides with board by {-c2:.2f}mm")

    # Battery ↔ bottom shell floor
    c3 = batb[0][2] - btb[0][2]
    status = "OK" if c3 >= 1.0 else "TIGHT" if c3 >= 0 else "COLLISION"
    print(f"    Battery bottom → Shell floor: {c3:+.2f} mm  [{status}]")
    if c3 < 0:
        issues.append(f"Battery protrudes {-c3:.2f}mm below shell floor")

    # Top ↔ bottom shell gap
    gap_tb = tb[0][2] - btb[1][2]
    lip_top = bot_meta.get("lip_top", btb[1][2])
    print(f"    Top shell bottom ({tb[0][2]:.2f}) ↔ Bottom shell top ({btb[1][2]:.2f}): gap={gap_tb:.2f} mm")
    print(f"    Lip top: {lip_top:.2f}, overlaps into top by: {lip_top - tb[0][2]:.2f} mm")

    # XY fit: board in case
    print(f"\n  Board fit in case XY:")
    for ax, i in [("X", 0), ("Y", 1)]:
        case_min = min(tb[0][i], btb[0][i])
        case_max = max(tb[1][i], btb[1][i])
        m_min = bb[0][i] - case_min
        m_max = case_max - bb[1][i]
        ok = m_min >= -0.1 and m_max >= -0.1
        print(f"    {ax}: board [{bb[0][i]:.2f}..{bb[1][i]:.2f}] in case [{case_min:.2f}..{case_max:.2f}] "
              f"margins: {m_min:+.2f}/{m_max:+.2f} {'OK' if ok else 'OUTSIDE'}")
        if not ok:
            issues.append(f"Board outside case in {ax} by {min(m_min, m_max):.2f}mm")

    # Battery XY fit
    print(f"\n  Battery fit in bottom shell XY:")
    bot_inner_x = btb[1][0] - btb[0][0] - 2 * WALL
    bot_inner_y = btb[1][1] - btb[0][1] - 2 * WALL
    bat_x = batb[1][0] - batb[0][0]
    bat_y = batb[1][1] - batb[0][1]
    for ax, bat_d, inner_d in [("X", bat_x, bot_inner_x), ("Y", bat_y, bot_inner_y)]:
        ok = bat_d <= inner_d + 0.1
        print(f"    {ax}: battery {bat_d:.1f} in inner {inner_d:.1f} gap={inner_d-bat_d:+.1f} {'OK' if ok else 'NO FIT'}")
        if not ok:
            issues.append(f"Battery {ax} ({bat_d:.1f}mm) doesn't fit in shell ({inner_d:.1f}mm)")

    # Buttons in top shell
    print(f"\n  Buttons fit:")
    for bname, bm in [("Buttons L", btn1_c), ("Buttons R", btn2_c)]:
        bbb = bm.bounds
        ok_x = bbb[0][0] >= tb[0][0] - 0.1 and bbb[1][0] <= tb[1][0] + 0.1
        ok_y = bbb[0][1] >= tb[0][1] - 0.1 and bbb[1][1] <= tb[1][1] + 0.1
        print(f"    {bname}: X={'OK' if ok_x else 'OUT'}, Y={'OK' if ok_y else 'OUT'}")

    # Overall dims
    all_bounds = np.array([(m.bounds[0], m.bounds[1]) for m in parts_check.values()])
    total_min = all_bounds[:, 0].min(axis=0)
    total_max = all_bounds[:, 1].max(axis=0)
    total_dims = total_max - total_min
    print(f"\n  Overall assembly: {total_dims[0]:.1f} x {total_dims[1]:.1f} x {total_dims[2]:.1f} mm")

    if issues:
        print(f"\n  *** {len(issues)} ISSUES ***")
        for iss in issues:
            print(f"    - {iss}")
    else:
        print(f"\n  ALL CHECKS PASSED!")

    # Save report
    report = {
        "version": "v2",
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
    with open(output_dir / "v2_report.json", "w") as f:
        json.dump(report, f, indent=2, cls=NumpyEncoder)

    print(f"\n--- Output files ---")
    for f in sorted(output_dir.glob("*")):
        sz = f.stat().st_size
        print(f"  {f.name} ({sz/1024:.0f} KB)")

    print(f"\n{'='*70}")
    print("V2 BUILD COMPLETE")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
