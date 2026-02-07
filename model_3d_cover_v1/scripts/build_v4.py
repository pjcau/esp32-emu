#!/usr/bin/env python3
"""
V4 Assembly: Optimized case with rounded corners, reduced dimensions,
matching top+bottom shells, and L/R shoulder buttons.

Changes from V3:
  - Rounded vertical edges (3mm radius) on both shells
  - Thinner walls (1.5mm), floor (1.5mm), reduced clearance (0.15mm)
  - Top shell recreated to match bottom shell XY dimensions
  - Shells meet flush at Z=0 (no visible gap)
  - L/R shoulder buttons with retention mechanism
  - Overall smaller: ~103x58x26mm (vs V3: 105x60x29mm)
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


# ─── V4 PARAMETERS ──────────────────────────────────────────────────
BATTERY = {"thickness": 9.5, "width": 55.0, "length": 65.0}

WALL = 1.5              # Reduced from 2.0
FLOOR = 1.5             # Reduced from 2.0
CLEARANCE = 0.15        # Reduced from 0.3
BATTERY_GAP = 1.0       # Reduced from 1.5
TOP_PLATE = 1.5         # Top shell plate thickness
CORNER_R = 3.0          # Corner radius
LIP_HEIGHT = 1.0        # Interlocking lip
LIP_WIDTH = 0.8         # Lip wall width
SCREW_R = 1.6
POST_R = 3.5
BAT_HOLDER_W = 1.5

# Component positions (GLB/centered coords)
MOUNT_HOLES = [(-47.0, -22.0), (44.9, -23.0), (-46.0, 21.8), (46.0, 21.8)]

# Top shell opening: one big cutout (from inspection: ~98x47.5mm)
# We add a 2.5mm frame all around for structural rigidity
FRAME_WIDTH = 2.5

# Front wall cutouts (Y-min)
FRONT_CUTS = {
    "usbc":    {"x": -1.5,  "z": -3.2, "w": 10.0, "h": 5.0},
    "audio":   {"x": -16.3, "z": -2.2, "w": 7.0,  "h": 5.0},
    "sd_card": {"x": 35.2,  "z": -2.3, "w": 14.0, "h": 7.0},
}

# Back wall cutouts (Y-max)
BACK_CUTS = {
    "shoulder_l": {"x": -38.6, "z": -3.6, "w": 12.0, "h": 6.0},
    "shoulder_r": {"x":  38.9, "z": -3.6, "w": 12.0, "h": 6.0},
}

# Shoulder button tact switches (GLB coords)
SHOULDER_SWITCHES = {
    "L": {"x": -38.6, "y": 20.7, "z": -3.6},
    "R": {"x":  38.9, "y": 20.7, "z": -3.6},
}


# ─── COLORS ──────────────────────────────────────────────────────────
C = {
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
    "case_top":      [240, 240, 245, 255],
    "case_top_in":   [220, 220, 225, 255],
    "case_bot":      [ 40,  40,  45, 255],
    "case_bot_in":   [ 55,  55,  60, 255],
    "btn_dark":      [ 50,  50,  55, 255],
    "battery":       [ 60, 120, 200, 200],
    "bat_label":     [255, 200,  50, 255],
    "shoulder_cap":  [ 60,  60,  65, 255],
    "shoulder_body": [ 50,  50,  55, 255],
}


class NpEnc(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (np.bool_, np.integer, np.floating)): return o.item()
        if isinstance(o, np.ndarray): return o.tolist()
        return super().default(o)


def load_mesh(fp):
    m = trimesh.load(fp, force='mesh')
    if isinstance(m, trimesh.Scene):
        ms = [g for g in m.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if ms: return trimesh.util.concatenate(ms)
    return m


def bool_diff(a, b):
    if HAS_MANIFOLD:
        try:
            r = trimesh.boolean.difference([a, b], engine='manifold')
            if r is not None and len(r.faces) > 0: return r
        except: pass
    return a


def bool_union(meshes):
    if HAS_MANIFOLD and len(meshes) > 1:
        try:
            r = trimesh.boolean.union(meshes, engine='manifold')
            if r is not None and len(r.faces) > 0: return r
        except: pass
    return trimesh.util.concatenate(meshes)


def rounded_box(sx, sy, sz, radius, sections=32):
    """Box with rounded vertical edges."""
    hx = sx / 2 - radius
    hy = sy / 2 - radius
    parts = []
    for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
        cyl = cylinder(radius=radius, height=sz, sections=sections)
        cyl.apply_translation([dx * hx, dy * hy, 0])
        parts.append(cyl)
    parts.append(box([sx - 2 * radius, sy, sz]))
    parts.append(box([sx, sy - 2 * radius, sz]))
    return bool_union(parts)


def compute_shell_dims(board_bounds):
    """Compute shell dimensions from board and battery requirements."""
    bd = board_bounds[1] - board_bounds[0]

    inner_x = max(bd[0] + 2 * CLEARANCE, BATTERY["length"] + 2 * CLEARANCE)
    inner_y = max(bd[1] + 2 * CLEARANCE, BATTERY["width"] + 2 * CLEARANCE)

    outer_x = inner_x + 2 * WALL
    outer_y = inner_y + 2 * WALL

    pcb_z_bot = board_bounds[0][2]

    bat_top_z = pcb_z_bot - BATTERY_GAP
    bat_bot_z = bat_top_z - BATTERY["thickness"]
    bot_z_min = bat_bot_z - FLOOR

    return {
        "outer_x": outer_x, "outer_y": outer_y,
        "inner_x": inner_x, "inner_y": inner_y,
        "bot_z_min": bot_z_min, "bot_z_max": 0.0,
        "top_z_min": 0.0, "top_z_max": 7.0,
        "bat_top_z": bat_top_z, "bat_bot_z": bat_bot_z,
        "bat_center_z": (bat_top_z + bat_bot_z) / 2,
    }


def generate_bottom_v4(dims):
    """Bottom shell with rounded corners and all cutouts."""
    ox, oy = dims["outer_x"], dims["outer_y"]
    ix, iy = dims["inner_x"], dims["inner_y"]
    z_min, z_max = dims["bot_z_min"], dims["bot_z_max"]
    h = z_max - z_min
    cz = (z_min + z_max) / 2

    print(f"\n  Bottom Shell V4: {ox:.1f} x {oy:.1f} x {h:.1f}mm, Z=[{z_min:.1f},{z_max:.1f}]")

    # Outer rounded box
    outer = rounded_box(ox, oy, h, CORNER_R)
    outer.apply_translation([0, 0, cz])

    # Inner cavity (open top)
    cavity_h = h - FLOOR + 2
    cavity_r = max(CORNER_R - WALL, 0.5)
    cavity = rounded_box(ix, iy, cavity_h, cavity_r)
    cavity.apply_translation([0, 0, z_min + FLOOR + cavity_h / 2])

    shell = bool_diff(outer, cavity)

    # Lip
    lip_outer = rounded_box(ix, iy, LIP_HEIGHT, cavity_r)
    lip_inner_x = ix - 2 * LIP_WIDTH
    lip_inner_y = iy - 2 * LIP_WIDTH
    lip_inner = rounded_box(lip_inner_x, lip_inner_y, LIP_HEIGHT + 2, max(cavity_r - LIP_WIDTH, 0.3))
    lip = bool_diff(lip_outer, lip_inner)
    lip.apply_translation([0, 0, z_max + LIP_HEIGHT / 2])

    # Screw posts
    posts = []
    post_h = h - FLOOR
    for hx, hy in MOUNT_HOLES:
        post = cylinder(radius=POST_R, height=post_h, sections=32)
        post.apply_translation([hx, hy, z_min + FLOOR + post_h / 2])
        hole = cylinder(radius=SCREW_R, height=post_h + 2, sections=32)
        hole.apply_translation([hx, hy, z_min + FLOOR + post_h / 2])
        posts.append(bool_diff(post, hole))

    # Battery retainers
    bat_cz = dims["bat_center_z"]
    bat_h = BATTERY["thickness"] + 1
    bat_hold = []
    for sign in [-1, 1]:
        r = box([BAT_HOLDER_W, BATTERY["width"] + 2, bat_h])
        r.apply_translation([sign * (BATTERY["length"] / 2 + BAT_HOLDER_W / 2), 0, bat_cz])
        bat_hold.append(r)
    for sx in [-1, 1]:
        for sy in [-1, 1]:
            clip = box([10, BAT_HOLDER_W, bat_h])
            clip.apply_translation([sx * (BATTERY["length"] / 2 - 5),
                                    sy * (BATTERY["width"] / 2 + BAT_HOLDER_W / 2), bat_cz])
            bat_hold.append(clip)

    # Union all solid parts
    result = bool_union([shell, lip] + posts + bat_hold)

    # Front cutouts (Y-min)
    y_min_w = -oy / 2
    for name, cd in FRONT_CUTS.items():
        cut = box([cd["w"] + 1, WALL + 4, cd["h"] + 1])
        cut.apply_translation([cd["x"], y_min_w, cd["z"]])
        result = bool_diff(result, cut)

    # Back cutouts (Y-max)
    y_max_w = oy / 2
    for name, cd in BACK_CUTS.items():
        cut = box([cd["w"] + 1, WALL + 4, cd["h"] + 1])
        cut.apply_translation([cd["x"], y_max_w, cd["z"]])
        result = bool_diff(result, cut)

    print(f"    Faces: {len(result.faces)}")
    return result


def generate_top_v4(dims):
    """New top shell matching bottom V4 dimensions, with rounded corners."""
    ox, oy = dims["outer_x"], dims["outer_y"]
    z_min, z_max = dims["top_z_min"], dims["top_z_max"]
    h = z_max - z_min  # 7mm
    cz = (z_min + z_max) / 2

    print(f"\n  Top Shell V4: {ox:.1f} x {oy:.1f} x {h:.1f}mm, Z=[{z_min:.1f},{z_max:.1f}]")

    # Outer rounded box
    outer = rounded_box(ox, oy, h, CORNER_R)
    outer.apply_translation([0, 0, cz])

    # Inner cavity (open bottom - the shell is open where it sits on PCB)
    inner_x = ox - 2 * WALL
    inner_y = oy - 2 * WALL
    cavity_h = h - TOP_PLATE + 2  # extend below bottom
    cavity_r = max(CORNER_R - WALL, 0.5)
    cavity = rounded_box(inner_x, inner_y, cavity_h, cavity_r)
    cavity.apply_translation([0, 0, z_max - TOP_PLATE - cavity_h / 2])

    shell = bool_diff(outer, cavity)

    # Lip recess (accepts bottom shell's lip)
    # Cut a thin slot at the bottom inner edge to accept the lip
    recess_x = inner_x + 0.3  # slightly wider than lip for clearance
    recess_y = inner_y + 0.3
    recess_inner_x = inner_x - 2 * LIP_WIDTH - 0.3
    recess_inner_y = inner_y - 2 * LIP_WIDTH - 0.3
    recess_outer = rounded_box(recess_x, recess_y, LIP_HEIGHT + 0.3, cavity_r)
    recess_inner = rounded_box(recess_inner_x, recess_inner_y, LIP_HEIGHT + 2, max(cavity_r - LIP_WIDTH, 0.3))
    recess = bool_diff(recess_outer, recess_inner)
    recess.apply_translation([0, 0, z_min + (LIP_HEIGHT + 0.3) / 2])

    # Cut recess from shell
    shell = bool_diff(shell, recess)

    # Central opening in top plate (one big opening like original)
    open_x = inner_x - 2 * FRAME_WIDTH
    open_y = inner_y - 2 * FRAME_WIDTH
    open_r = max(CORNER_R - WALL - FRAME_WIDTH, 1.0)
    opening = rounded_box(open_x, open_y, TOP_PLATE + 2, open_r)
    opening.apply_translation([0, 0, z_max])

    shell = bool_diff(shell, opening)

    print(f"    Opening: {open_x:.1f} x {open_y:.1f}mm, frame={FRAME_WIDTH:.1f}mm")
    print(f"    Faces: {len(shell.faces)}")
    return shell


def generate_shoulder_button(side, dims):
    """
    Generate a shoulder button (L or R).
    Design: cap (outside) → guide (in wall) → arm → retention flange → nub
    """
    sw = SHOULDER_SWITCHES[side]
    oy = dims["outer_y"]
    wall_y = oy / 2  # Y position of back wall outer surface
    inner_wall_y = wall_y - WALL

    # Cutout dimensions (from BACK_CUTS)
    cut_w = 12.0  # cutout width (X)
    cut_h = 6.0   # cutout height (Z)

    # Button dimensions
    cap_depth = 2.0       # protrusion outside wall
    guide_clearance = 0.3 # clearance in cutout
    guide_w = cut_w - 2 * guide_clearance
    guide_h = cut_h - 2 * guide_clearance

    # Arm from inner wall to switch + margin
    arm_length = inner_wall_y - sw["y"] + 1.0  # extra 1mm to reach switch
    arm_w = 4.0
    arm_h = 4.0

    # Retention flange (wider than cutout, sits inside)
    flange_w = cut_w + 3.0
    flange_h = cut_h + 2.0
    flange_t = 1.0

    # Nub
    nub_r = 1.5
    nub_h = 1.0

    parts = []

    # Cap (protrudes outside back wall)
    cap = box([guide_w, cap_depth, guide_h])
    cap_y = wall_y + cap_depth / 2
    cap.apply_translation([sw["x"], cap_y, sw["z"]])
    parts.append(cap)

    # Guide (fits in cutout)
    guide = box([guide_w, WALL, guide_h])
    guide.apply_translation([sw["x"], wall_y - WALL / 2, sw["z"]])
    parts.append(guide)

    # Arm (extends inward to switch)
    arm = box([arm_w, arm_length, arm_h])
    arm_y = inner_wall_y - arm_length / 2
    arm.apply_translation([sw["x"], arm_y, sw["z"]])
    parts.append(arm)

    # Retention flange (prevents button from being pushed out)
    flange = box([flange_w, flange_t, flange_h])
    flange_y = inner_wall_y - flange_t / 2
    flange.apply_translation([sw["x"], flange_y, sw["z"]])
    parts.append(flange)

    # Nub (contacts tact switch)
    nub = cylinder(radius=nub_r, height=nub_h, sections=16)
    # Rotate to point along -Y (inward)
    nub.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    nub_y = inner_wall_y - arm_length - nub_h / 2
    nub.apply_translation([sw["x"], nub_y, sw["z"]])
    parts.append(nub)

    button = bool_union(parts)

    print(f"    {side} button: cap_Y={cap_y:.1f}, nub_Y={nub_y:.1f}, "
          f"arm_len={arm_length:.1f}mm, travel=~1mm")

    return button


def get_glb_regions(glb_path):
    scene = trimesh.load(glb_path)
    if not isinstance(scene, trimesh.Scene): return []
    regions = []
    for name, geom in scene.geometry.items():
        if not isinstance(geom, trimesh.Trimesh): continue
        bounds = geom.bounds; dims = bounds[1] - bounds[0]
        center = (bounds[0] + bounds[1]) / 2
        color = None
        if hasattr(geom.visual, 'main_color'):
            color = tuple(geom.visual.main_color[:3].tolist())
        if color is None: continue
        r, g, b = color
        if (r, g, b) == (255, 215, 0):
            key = "dpad_gold" if (center[0]<-25 and center[1]>0 and center[2]>0) else \
                  ("shoulder_btn" if center[2]<0 else "button_gold")
            regions.append({"bmin": bounds[0], "bmax": bounds[1], "color_key": key, "priority": 10, "expand": 0.5})
        elif all(c<60 for c in (r,g,b)) and dims[0]>30 and dims[1]>30:
            regions.append({"bmin": bounds[0], "bmax": bounds[1], "color_key": "screen", "priority": 20, "expand": 0})
            regions.append({"bmin": bounds[0]-[2,2,0], "bmax": bounds[1]+[2,2,0.5], "color_key": "screen_bezel", "priority": 15, "expand": 0})
        elif all(c<60 for c in (r,g,b)):
            if max(dims[0],dims[1])>=3 and center[1]<-18:
                key = "usbc_metal" if max(dims[0],dims[1])>7 else "audio_metal"
                regions.append({"bmin": bounds[0], "bmax": bounds[1], "color_key": key, "priority": 15, "expand": 0.5})
            elif 2<dims[0]<20 and dims[1]>2:
                regions.append({"bmin": bounds[0], "bmax": bounds[1], "color_key": "ic_black", "priority": 5, "expand": 0})
        elif (r,g,b) == (200,170,80):
            regions.append({"bmin": bounds[0], "bmax": bounds[1], "color_key": "hole_ring", "priority": 12, "expand": 1.0})
        elif all(40<c<120 for c in (r,g,b)) and (dims[0]>5 or dims[1]>5):
            regions.append({"bmin": bounds[0], "bmax": bounds[1], "color_key": "sd_slot", "priority": 3, "expand": 0})
    return regions


def colorize_board(mesh, regions):
    n = len(mesh.faces)
    centroids = mesh.vertices[mesh.faces].mean(axis=1)
    normals = mesh.face_normals
    fc = np.zeros((n, 4), dtype=np.uint8)
    top = normals[:,2]>0.3; bot = normals[:,2]<-0.3
    for i in range(n):
        fc[i] = C["pcb_top"] if top[i] else (C["pcb_bottom"] if bot[i] else C["pcb_edge"])
    for reg in sorted(regions, key=lambda r: r["priority"]):
        exp = reg.get("expand", 0)
        rmin = np.minimum(reg["bmin"], reg["bmax"]) - exp
        rmax = np.maximum(reg["bmin"], reg["bmax"]) + exp
        mask = ((centroids >= rmin) & (centroids <= rmax)).all(axis=1)
        fc[mask] = C[reg["color_key"]]
    for hx, hy in [[-47,-22],[44.9,-23],[-46,21.8],[46,21.8]]:
        d = np.sqrt((centroids[:,0]-hx)**2+(centroids[:,1]-hy)**2)
        fc[(d<2)&~top&~bot] = C["hole_inner"]
        fc[(d>=2)&(d<4)&(np.abs(normals[:,2])>0.3)] = C["hole_ring"]
    mesh.visual.face_colors = fc
    return mesh


def colorize_case(mesh, c_out, c_in):
    center = (mesh.bounds[0]+mesh.bounds[1])/2
    centroids = mesh.vertices[mesh.faces].mean(axis=1)
    normals = mesh.face_normals
    fc = np.zeros((len(mesh.faces),4), dtype=np.uint8)
    for i in range(len(mesh.faces)):
        dot = np.dot(normals[i], center - centroids[i])
        fc[i] = c_out if dot<0 else c_in
    mesh.visual.face_colors = fc
    return mesh


def colorize_uniform(mesh, color):
    fc = np.full((len(mesh.faces),4), color, dtype=np.uint8)
    mesh.visual.face_colors = fc
    return mesh


def create_battery(cz):
    bat = box([BATTERY["length"], BATTERY["width"], BATTERY["thickness"]])
    bat.apply_translation([0, 0, cz])
    fc = np.full((len(bat.faces),4), C["battery"], dtype=np.uint8)
    fc[bat.face_normals[:,2]>0.9] = C["bat_label"]
    bat.visual.face_colors = fc
    return bat


def main():
    original_dir = Path("/workspace/original")
    ref_dir = Path("/workspace/ref")
    output_dir = Path("/workspace/output/v4")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("V4 BUILD - Rounded corners, reduced dimensions, shoulder buttons")
    print("=" * 70)

    # ── Load ──
    print("\n--- Loading ---")
    board_stl = load_mesh(original_dir / "board.stl")
    btn1 = load_mesh(original_dir / "btn_assy_1.stl")
    btn2 = load_mesh(original_dir / "btn_assy_2.stl")

    # Center board (original top_body center as reference)
    top_orig = load_mesh(original_dir / "top_body.stl")
    board_c = (board_stl.bounds[0] + board_stl.bounds[1]) / 2
    top_c = (top_orig.bounds[0] + top_orig.bounds[1]) / 2
    offset = np.array([board_c[0] - top_c[0], board_c[1] - top_c[1], 0])

    board = board_stl.copy()
    board.apply_translation(-offset)

    print(f"  Board: [{board.bounds[0][0]:.1f},{board.bounds[0][1]:.1f},{board.bounds[0][2]:.1f}] "
          f"to [{board.bounds[1][0]:.1f},{board.bounds[1][1]:.1f},{board.bounds[1][2]:.1f}]")

    # ── Compute dimensions ──
    dims = compute_shell_dims(board.bounds)
    print(f"\n  Shell outer: {dims['outer_x']:.1f} x {dims['outer_y']:.1f}mm")
    print(f"  Bottom Z: [{dims['bot_z_min']:.1f}, {dims['bot_z_max']:.1f}] = {dims['bot_z_max']-dims['bot_z_min']:.1f}mm")
    print(f"  Top Z:    [{dims['top_z_min']:.1f}, {dims['top_z_max']:.1f}] = {dims['top_z_max']-dims['top_z_min']:.1f}mm")
    print(f"  Total height: {dims['top_z_max']-dims['bot_z_min']:.1f}mm")

    # ── Generate shells ──
    print("\n--- Generating bottom shell V4 ---")
    bottom = generate_bottom_v4(dims)

    print("\n--- Generating top shell V4 ---")
    top = generate_top_v4(dims)

    # ── Shoulder buttons ──
    print("\n--- Generating shoulder buttons ---")
    shoulder_l = generate_shoulder_button("L", dims)
    shoulder_r = generate_shoulder_button("R", dims)

    # ── Colorize ──
    print("\n--- Colorizing ---")
    regions = get_glb_regions(ref_dir / "esplay_micro_pcb.glb")

    board_col = colorize_board(board.copy(), regions)
    top_col = colorize_case(top.copy(), C["case_top"], C["case_top_in"])
    bot_col = colorize_case(bottom.copy(), C["case_bot"], C["case_bot_in"])
    btn1_col = colorize_uniform(btn1.copy(), C["btn_dark"])
    btn2_col = colorize_uniform(btn2.copy(), C["btn_dark"])
    shoulder_l_col = colorize_uniform(shoulder_l.copy(), C["shoulder_cap"])
    shoulder_r_col = colorize_uniform(shoulder_r.copy(), C["shoulder_cap"])
    battery = create_battery(dims["bat_center_z"])

    # ── Save individual ──
    print("\n--- Saving ---")
    for name, mesh in [
        ("board_colored.glb", board_col),
        ("top_body_v4.glb", top_col),
        ("bottom_body_v4.glb", bot_col),
        ("btn_assy_1_colored.glb", btn1_col),
        ("btn_assy_2_colored.glb", btn2_col),
        ("shoulder_l.glb", shoulder_l_col),
        ("shoulder_r.glb", shoulder_r_col),
        ("battery.glb", battery),
    ]:
        mesh.export(output_dir / name)
        print(f"  {name}")

    # ── CLOSED assembly ──
    print("\n--- Closed assembly ---")
    closed = trimesh.Scene()
    closed.add_geometry(board_col, node_name="Board")
    closed.add_geometry(top_col, node_name="Top_Shell_V4")
    closed.add_geometry(bot_col, node_name="Bottom_Shell_V4")
    closed.add_geometry(btn1_col, node_name="Buttons_Left")
    closed.add_geometry(btn2_col, node_name="Buttons_Right")
    closed.add_geometry(shoulder_l_col, node_name="Shoulder_L")
    closed.add_geometry(shoulder_r_col, node_name="Shoulder_R")
    closed.add_geometry(battery, node_name="Battery")
    closed.export(output_dir / "assembly_closed.glb")

    # ── OPEN assembly ──
    print("--- Open assembly ---")
    explode = 25.0
    opened = trimesh.Scene()
    opened.add_geometry(board_col, node_name="Board")

    te = top_col.copy(); te.apply_translation([0, 0, explode])
    opened.add_geometry(te, node_name="Top_Shell_V4")

    b1e = btn1_col.copy(); b1e.apply_translation([0, 0, explode + 10])
    b2e = btn2_col.copy(); b2e.apply_translation([0, 0, explode + 10])
    opened.add_geometry(b1e, node_name="Buttons_Left")
    opened.add_geometry(b2e, node_name="Buttons_Right")

    be = bot_col.copy(); be.apply_translation([0, 0, -explode])
    opened.add_geometry(be, node_name="Bottom_Shell_V4")

    sle = shoulder_l_col.copy(); sle.apply_translation([0, 0, -explode * 0.3])
    sre = shoulder_r_col.copy(); sre.apply_translation([0, 0, -explode * 0.3])
    opened.add_geometry(sle, node_name="Shoulder_L")
    opened.add_geometry(sre, node_name="Shoulder_R")

    bate = battery.copy(); bate.apply_translation([0, 0, -explode * 0.6])
    opened.add_geometry(bate, node_name="Battery")

    opened.export(output_dir / "assembly_open.glb")

    # ══════════════════════════════════════════════════════════════
    # VERIFICATION
    # ══════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("V4 ASSEMBLY VERIFICATION")
    print("=" * 70)

    parts = {
        "Bottom Shell V4": bot_col,
        "Battery": battery,
        "Board": board_col,
        "Top Shell V4": top_col,
        "Buttons L": btn1_col,
        "Buttons R": btn2_col,
        "Shoulder L": shoulder_l_col,
        "Shoulder R": shoulder_r_col,
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
        c = (m.bounds[0]+m.bounds[1])/2
        print(f"  {name:<20} ({c[0]:7.2f}, {c[1]:7.2f})")

    # Key clearances
    print(f"\n  Clearances:")
    bb = board_col.bounds
    tb = top_col.bounds
    btb = bot_col.bounds
    batb = battery.bounds

    issues = []

    c1 = tb[1][2] - bb[1][2]
    print(f"    Board top → Top shell top:   {c1:+.2f} mm  {'OK' if c1>=-0.1 else 'PROBLEM'}")
    if c1<-0.1: issues.append(f"Board protrudes above top shell by {-c1:.2f}mm")

    c2 = bb[0][2] - batb[1][2]
    print(f"    Battery top → Board bottom:  {c2:+.2f} mm  {'OK' if c2>=0 else 'COLLISION'}")
    if c2<0: issues.append(f"Battery collides with board")

    c3 = batb[0][2] - btb[0][2]
    print(f"    Battery bot → Shell floor:   {c3:+.2f} mm  {'OK' if c3>=0.5 else 'TIGHT'}")
    if c3<0: issues.append(f"Battery below shell floor")

    # Top↔Bottom match
    gap = tb[0][2] - btb[1][2]
    print(f"    Top↔Bottom join:             {gap:+.2f} mm (should be ~0)")

    # XY match between top and bottom
    print(f"\n  Top↔Bottom XY match:")
    for ax, i in [("X", 0), ("Y", 1)]:
        diff = abs((tb[1][i]-tb[0][i]) - (btb[1][i]-btb[0][i]))
        print(f"    {ax}: top={tb[1][i]-tb[0][i]:.1f}mm, bottom={btb[1][i]-btb[0][i]:.1f}mm, diff={diff:.1f}mm "
              f"{'MATCH' if diff<0.5 else 'MISMATCH'}")
        if diff > 1.0: issues.append(f"Top/bottom {ax} mismatch: {diff:.1f}mm")

    # Board in case
    print(f"\n  Board fit:")
    for ax, i in [("X", 0), ("Y", 1)]:
        case_min = min(tb[0][i], btb[0][i])
        case_max = max(tb[1][i], btb[1][i])
        m1 = bb[0][i] - case_min; m2 = case_max - bb[1][i]
        ok = m1>=-0.1 and m2>=-0.1
        print(f"    {ax}: margins {m1:+.2f}/{m2:+.2f} {'OK' if ok else 'OUT'}")
        if not ok: issues.append(f"Board outside case {ax}")

    # Battery in bottom
    print(f"\n  Battery fit:")
    bi_x = btb[1][0]-btb[0][0]-2*WALL; bi_y = btb[1][1]-btb[0][1]-2*WALL
    for ax, bd, inner in [("X", BATTERY["length"], bi_x), ("Y", BATTERY["width"], bi_y)]:
        ok = bd <= inner + 0.1
        print(f"    {ax}: {bd:.1f} in {inner:.1f} gap={inner-bd:+.1f} {'OK' if ok else 'NO FIT'}")
        if not ok: issues.append(f"Battery {ax} doesn't fit")

    # Buttons in top
    print(f"\n  Buttons:")
    for bname, bm in [("Left", btn1_col), ("Right", btn2_col)]:
        bbb = bm.bounds
        ok_x = bbb[0][0]>=tb[0][0]-0.1 and bbb[1][0]<=tb[1][0]+0.1
        ok_y = bbb[0][1]>=tb[0][1]-0.1 and bbb[1][1]<=tb[1][1]+0.1
        print(f"    {bname}: X={'OK' if ok_x else 'OUT'}, Y={'OK' if ok_y else 'OUT'}")

    # Shoulder buttons alignment
    print(f"\n  Shoulder buttons:")
    for side, sm in [("L", shoulder_l_col), ("R", shoulder_r_col)]:
        sb = sm.bounds
        sw = SHOULDER_SWITCHES[side]
        nub_y = sb[0][1]  # nub is at min Y (pointing inward)
        dist_to_switch = sw["y"] - nub_y
        print(f"    {side}: nub_Y={nub_y:.1f}, switch_Y={sw['y']:.1f}, reach={dist_to_switch:+.1f}mm "
              f"{'OK' if abs(dist_to_switch)<2 else 'CHECK'}")

    # V3 vs V4 comparison
    print(f"\n  V3 → V4 size reduction:")
    v3_outer = [104.6, 59.6, 29.0]
    v4_outer = [dims["outer_x"], dims["outer_y"], dims["top_z_max"]-dims["bot_z_min"]]
    for ax, v3, v4 in zip(["X", "Y", "Z"], v3_outer, v4_outer):
        print(f"    {ax}: {v3:.1f} → {v4:.1f} mm (saved {v3-v4:.1f}mm)")

    # Overall
    all_b = np.array([(m.bounds[0], m.bounds[1]) for m in parts.values()])
    total_min = all_b[:,0].min(axis=0)
    total_max = all_b[:,1].max(axis=0)
    total_dims = total_max - total_min
    print(f"\n  Overall: {total_dims[0]:.1f} x {total_dims[1]:.1f} x {total_dims[2]:.1f} mm")

    if issues:
        print(f"\n  *** {len(issues)} ISSUES ***")
        for iss in issues: print(f"    - {iss}")
    else:
        print(f"\n  ALL CHECKS PASSED!")

    # Report
    report = {
        "version": "v4",
        "changes": [
            "Rounded vertical edges (3mm radius)",
            "Thinner walls (1.5mm from 2.0mm)",
            "Reduced clearance (0.15mm from 0.3mm)",
            "Thinner floor (1.5mm from 2.0mm)",
            "New parametric top shell matching bottom dimensions",
            "Shells meet flush at Z=0 (no gap)",
            "L/R shoulder buttons with retention mechanism",
        ],
        "parameters": {
            "wall": WALL, "floor": FLOOR, "clearance": CLEARANCE,
            "corner_radius": CORNER_R, "battery_gap": BATTERY_GAP,
        },
        "dimensions": {
            "outer": [dims["outer_x"], dims["outer_y"]],
            "total_height": dims["top_z_max"] - dims["bot_z_min"],
            "bottom_height": dims["bot_z_max"] - dims["bot_z_min"],
            "top_height": dims["top_z_max"] - dims["top_z_min"],
        },
        "issues": issues,
    }
    with open(output_dir / "v4_report.json", "w") as f:
        json.dump(report, f, indent=2, cls=NpEnc)

    print(f"\n--- Output files ---")
    for f in sorted(output_dir.glob("*")):
        print(f"  {f.name} ({f.stat().st_size/1024:.0f} KB)")

    print(f"\n{'='*70}")
    print("V4 BUILD COMPLETE")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
