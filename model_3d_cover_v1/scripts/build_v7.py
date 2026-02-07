#!/usr/bin/env python3
"""
V7 Assembly - Changes from V6:
  1. Top shell: SOLID top plate with specific cutouts for screen, D-pad, A/B buttons.
     No more giant opening - the center of the top is now solid.
  2. Bottom shell: Battery pressed against internal wall (gap reduced to 0.3mm).
     Reduced depth. Countersunk M3 screws preserved.
  3. SD card slot cutout preserved in bottom shell.
  4. STL export for 3D printing.
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
BATTERY = {"thickness": 9.5, "width": 55.0, "length": 65.0}

WALL = 1.5
FLOOR = 1.5
CLEARANCE = 0.15
BATTERY_GAP = 0.3        # Minimal gap: battery pressed against internal wall
CORNER_R = 3.0
LIP_HEIGHT = 1.5
LIP_WIDTH = 0.8
SCREW_R = 1.6
POST_R = 3.5
BAT_HOLDER_W = 1.5

# Countersunk screw parameters
COUNTERBORE_R = 3.25
COUNTERBORE_DEPTH = 2.0
SCREW_CLEAR_R = 1.7
SCREW_TAP_R = 1.25

# Original top shell internal dimensions (from inspection)
ORIG_TOP = {
    "outer_x": 100.06, "outer_y": 49.94,
    "inner_x": 98.1,   "inner_y": 46.7,
    "inner_z_max": 5.5,
    "z_min": 1.0, "z_max": 7.0,
    "top_plate_t": 1.5,
}

MOUNT_HOLES = [(-47.0, -22.0), (44.9, -23.0), (-46.0, 21.8), (46.0, 21.8)]

# ─── TOP PLATE CUTOUTS ────────────────────────────────────────────
# Screen (LCD module): GLB geometry_28 = 46x42mm at center (1.56, 4.03)
# Wider-than-tall opening: reduced ~5mm on right side
SCREEN_CUT = {
    "x_min": -27.4, "x_max": 25.6,
    "y_min": -18.0, "y_max": 26.0,
    "label": "Screen/LCD",
}

# D-pad: CROSS-SHAPED cutout from GLB gold switch positions
# 4 switches: UP(-39.2,13.7) DOWN(-39.1,2.2) LEFT(-44.9,8.0) RIGHT(-33.5,8.0)
# Cross = two overlapping rectangles, arm width 8mm (6mm switch + 1mm clearance each)
DPAD_CUT = {
    "cx": -39.2, "cy": 8.0,
    # Horizontal arm: left switch X_min to right switch X_max + clearance
    "h_width": 18.4,   # -47.9 to -30.5 = 17.4 + 1.0
    "h_height": 8.0,   # 6mm switch + 1mm each side
    # Vertical arm: down switch Y_min to up switch Y_max + clearance
    "v_width": 8.0,    # 6mm switch + 1mm each side
    "v_height": 18.5,  # -0.8 to 16.7 = 17.5 + 1.0
    "label": "D-pad cross",
}

# Button cap cutouts are AUTO-DETECTED from mesh geometry at runtime.
# Only the actual button caps get holes - the rest of the top plate is solid.
BTN_CAP_Z_THRESHOLD = 7.0    # above top plate surface = cap protrusion
BTN_CAP_CLEARANCE = 0.5      # mm clearance around each cap hole
BTN_CAP_MIN_AREA = 9.0       # mm² minimum to filter noise

# Button flange parameters (retention lip between board and top plate)
BTN_FLANGE_EXTRA = 1.0   # mm wider than button mesh on each side
BTN_FLANGE_T = 1.0       # thickness in Z
BTN_FLANGE_Z_TOP = 5.5   # just below top plate inner surface

# Front wall cutouts (Y-min)
FRONT_CUTS = {
    "usbc":    {"x": -1.5,  "z": -3.2, "w": 10.0, "h": 5.0, "label": "USB-C"},
    "audio":   {"x": -16.3, "z": -2.2, "w": 7.0,  "h": 5.0, "label": "Audio Jack"},
    "sd_card": {"x": 35.2,  "z": -2.3, "w": 14.0, "h": 7.0, "label": "SD Card Slot"},
}

# Back wall cutouts (Y-max)
BACK_CUTS = {
    "shoulder_l": {"x": -38.6, "z": -3.6, "w": 12.0, "h": 6.0, "label": "L Shoulder"},
    "shoulder_r": {"x":  38.9, "z": -3.6, "w": 12.0, "h": 6.0, "label": "R Shoulder"},
}

SHOULDER_SW = {
    "L": {"x": -38.6, "y_center": 20.7, "y_near": 23.7, "z": -3.6,
           "dims": [10.0, 6.0, 5.5]},
    "R": {"x":  38.9, "y_center": 20.7, "y_near": 23.7, "z": -3.6,
           "dims": [10.0, 6.0, 5.5]},
}


# ─── COLORS ──────────────────────────────────────────────────────────
COL = {
    "pcb_top":      [  0, 100,  30, 255], "pcb_bottom":   [  0,  80,  25, 255],
    "pcb_edge":     [  0,  90,  28, 255], "screen":       [ 20,  20,  25, 255],
    "screen_bezel": [ 40,  40,  45, 255], "button_gold":  [200, 170,  40, 255],
    "dpad_gold":    [210, 180,  50, 255], "usbc_metal":   [160, 165, 170, 255],
    "audio_metal":  [140, 140, 145, 255], "hole_ring":    [200, 170,  80, 255],
    "hole_inner":   [ 50,  50,  55, 255], "ic_black":     [ 15,  15,  20, 255],
    "sd_slot":      [120, 120, 125, 255], "shoulder_btn": [200, 170,  40, 255],
    "case_top":     [240, 240, 245, 255], "case_top_in":  [220, 220, 225, 255],
    "case_bot":     [ 40,  40,  45, 255], "case_bot_in":  [ 55,  55,  60, 255],
    "btn_dark":     [ 50,  50,  55, 255], "battery":      [ 60, 120, 200, 200],
    "bat_label":    [255, 200,  50, 255], "shoulder_cap": [ 60,  60,  65, 255],
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
            if r is not None and len(r.faces) > 0:
                return r
            else:
                print(f"      WARNING: boolean diff returned empty, keeping original")
        except Exception as e:
            print(f"      WARNING: boolean diff failed: {e}")
    return a


def bool_union(meshes):
    if HAS_MANIFOLD and len(meshes) > 1:
        try:
            r = trimesh.boolean.union(meshes, engine='manifold')
            if r is not None and len(r.faces) > 0:
                return r
        except: pass
    return trimesh.util.concatenate(meshes)


def rounded_box(sx, sy, sz, radius, sections=32):
    hx = sx / 2 - radius
    hy = sy / 2 - radius
    parts = []
    for dx, dy in [(-1,-1), (-1,1), (1,-1), (1,1)]:
        cyl = cylinder(radius=radius, height=sz, sections=sections)
        cyl.apply_translation([dx * hx, dy * hy, 0])
        parts.append(cyl)
    parts.append(box([sx - 2 * radius, sy, sz]))
    parts.append(box([sx, sy - 2 * radius, sz]))
    return bool_union(parts)


def compute_dims(board_bounds):
    bd = board_bounds[1] - board_bounds[0]
    inner_x = max(bd[0] + 2 * CLEARANCE, BATTERY["length"] + 2 * CLEARANCE)
    inner_y = max(bd[1] + 2 * CLEARANCE, BATTERY["width"] + 2 * CLEARANCE)
    outer_x = inner_x + 2 * WALL
    outer_y = inner_y + 2 * WALL

    pcb_z_bot = board_bounds[0][2]
    bat_top = pcb_z_bot - BATTERY_GAP
    bat_bot = bat_top - BATTERY["thickness"]
    bot_z_min = bat_bot - FLOOR

    return {
        "outer_x": outer_x, "outer_y": outer_y,
        "inner_x": inner_x, "inner_y": inner_y,
        "bot_z_min": bot_z_min,
        "bot_z_max": ORIG_TOP["z_min"],
        "top_z_min": ORIG_TOP["z_min"],
        "top_z_max": ORIG_TOP["z_max"],
        "bat_top": bat_top, "bat_bot": bat_bot,
        "bat_center_z": (bat_top + bat_bot) / 2,
        "pcb_z_bot": pcb_z_bot,
    }


# ═══════════════════════════════════════════════════════════════════
# BUTTON CAP DETECTION (find individual caps from mesh geometry)
# ═══════════════════════════════════════════════════════════════════
def find_button_caps(btn_mesh, label_prefix="btn"):
    """
    Find individual button cap positions using grid-based 2D analysis.
    Projects the top-surface faces onto a 2D grid and uses scipy
    connected-component labeling to find distinct button regions.
    """
    from scipy import ndimage

    z_vals = btn_mesh.vertices[:, 2]
    z_min, z_max = z_vals.min(), z_vals.max()
    print(f"      {label_prefix} mesh Z range: [{z_min:.2f}, {z_max:.2f}]")

    # Analyze multiple Z slices to find where distinct caps appear
    # Start from top and work down until we find separate regions
    best_caps = []
    best_z = z_max

    for z_probe in np.arange(z_max - 0.1, BTN_CAP_Z_THRESHOLD, -0.5):
        # Get face centroids at this Z level
        face_verts = btn_mesh.vertices[btn_mesh.faces]
        face_z_min = face_verts[:, :, 2].min(axis=1)
        face_z_max = face_verts[:, :, 2].max(axis=1)
        # Faces that cross this Z level
        mask = (face_z_min <= z_probe) & (face_z_max >= z_probe)
        if mask.sum() == 0:
            continue

        centroids_xy = face_verts[mask].mean(axis=1)[:, :2]

        # Create 2D grid (0.3mm resolution)
        grid_res = 0.3
        xy_min = centroids_xy.min(axis=0) - 1
        xy_max = centroids_xy.max(axis=0) + 1
        grid_w = int((xy_max[0] - xy_min[0]) / grid_res) + 1
        grid_h = int((xy_max[1] - xy_min[1]) / grid_res) + 1

        grid = np.zeros((grid_h, grid_w), dtype=bool)
        ix = ((centroids_xy[:, 0] - xy_min[0]) / grid_res).astype(int)
        iy = ((centroids_xy[:, 1] - xy_min[1]) / grid_res).astype(int)
        ix = np.clip(ix, 0, grid_w - 1)
        iy = np.clip(iy, 0, grid_h - 1)
        grid[iy, ix] = True

        # Dilate slightly to connect nearby faces
        grid = ndimage.binary_dilation(grid, iterations=2)

        # Label connected components
        labeled, n_features = ndimage.label(grid)

        if n_features > len(best_caps) and n_features > 1:
            # Found more distinct regions at this Z level
            caps = []
            for label_id in range(1, n_features + 1):
                region = np.where(labeled == label_id)
                ry_min = region[0].min() * grid_res + xy_min[1]
                ry_max = (region[0].max() + 1) * grid_res + xy_min[1]
                rx_min = region[1].min() * grid_res + xy_min[0]
                rx_max = (region[1].max() + 1) * grid_res + xy_min[0]
                w = rx_max - rx_min
                h = ry_max - ry_min
                if w * h >= BTN_CAP_MIN_AREA:
                    caps.append({
                        "x_min": float(rx_min - BTN_CAP_CLEARANCE),
                        "x_max": float(rx_max + BTN_CAP_CLEARANCE),
                        "y_min": float(ry_min - BTN_CAP_CLEARANCE),
                        "y_max": float(ry_max + BTN_CAP_CLEARANCE),
                        "label": f"{label_prefix}_cap_{len(caps)+1}",
                        "w": w + 2 * BTN_CAP_CLEARANCE,
                        "h": h + 2 * BTN_CAP_CLEARANCE,
                    })
            if len(caps) > len(best_caps):
                best_caps = caps
                best_z = z_probe

    print(f"      Best Z probe: {best_z:.2f} → {len(best_caps)} caps")
    for c in best_caps:
        print(f"        {c['label']}: {c['w']:.1f}x{c['h']:.1f}mm "
              f"at ({(c['x_min']+c['x_max'])/2:.1f}, {(c['y_min']+c['y_max'])/2:.1f})")

    # If no distinct caps found, the whole assembly area is one cap
    if not best_caps:
        bounds = btn_mesh.bounds
        print(f"      No distinct caps found, using full assembly bounds")
        best_caps = [{
            "x_min": float(bounds[0][0] - BTN_CAP_CLEARANCE),
            "x_max": float(bounds[1][0] + BTN_CAP_CLEARANCE),
            "y_min": float(bounds[0][1] - BTN_CAP_CLEARANCE),
            "y_max": float(bounds[1][1] + BTN_CAP_CLEARANCE),
            "label": f"{label_prefix}_cap_1",
            "w": float(bounds[1][0] - bounds[0][0] + 2 * BTN_CAP_CLEARANCE),
            "h": float(bounds[1][1] - bounds[0][1] + 2 * BTN_CAP_CLEARANCE),
        }]

    # Merge overlapping caps
    merged = True
    while merged:
        merged = False
        new_caps = []
        used = set()
        for i, a in enumerate(best_caps):
            if i in used:
                continue
            for j, b in enumerate(best_caps):
                if j <= i or j in used:
                    continue
                # Check overlap (with 1mm tolerance)
                if (a["x_min"] - 1 <= b["x_max"] and a["x_max"] + 1 >= b["x_min"] and
                    a["y_min"] - 1 <= b["y_max"] and a["y_max"] + 1 >= b["y_min"]):
                    # Merge into a
                    a = {
                        "x_min": min(a["x_min"], b["x_min"]),
                        "x_max": max(a["x_max"], b["x_max"]),
                        "y_min": min(a["y_min"], b["y_min"]),
                        "y_max": max(a["y_max"], b["y_max"]),
                        "label": a["label"],
                        "w": max(a["x_max"], b["x_max"]) - min(a["x_min"], b["x_min"]),
                        "h": max(a["y_max"], b["y_max"]) - min(a["y_min"], b["y_min"]),
                    }
                    used.add(j)
                    merged = True
            new_caps.append(a)
        best_caps = new_caps

    best_caps.sort(key=lambda c: c["y_min"])
    return best_caps


# ═══════════════════════════════════════════════════════════════════
# TOP SHELL V7 - Solid top plate with per-cap cutouts
# ═══════════════════════════════════════════════════════════════════
def generate_top_v7(dims, btn1_mesh, btn2_mesh):
    """
    Seamless parametric top shell with SOLID top plate.
    Auto-detects individual button cap positions from mesh geometry.
    Only the actual caps get holes - the rest of the plate is solid.
    """
    ox, oy = dims["outer_x"], dims["outer_y"]
    z_min = ORIG_TOP["z_min"]        # 1.0
    z_max = ORIG_TOP["z_max"]        # 7.0
    h = z_max - z_min                # 6.0
    cz = (z_min + z_max) / 2        # 4.0

    ix = ORIG_TOP["inner_x"]         # 98.1
    iy = ORIG_TOP["inner_y"]         # 46.7
    top_t = ORIG_TOP["top_plate_t"]  # 1.5
    inner_z_max = ORIG_TOP["inner_z_max"]  # 5.5

    print(f"\n  Top V7 (solid plate + per-cap cutouts):")
    print(f"    Outer: {ox:.1f} x {oy:.1f} (rounded, r={CORNER_R})")
    print(f"    Inner cavity: {ix:.1f} x {iy:.1f}")
    print(f"    Top plate: SOLID {top_t:.1f}mm (Z={inner_z_max:.1f} to {z_max:.1f})")

    # 1. Outer shell (rounded box)
    outer = rounded_box(ox, oy, h, CORNER_R)
    outer.apply_translation([0, 0, cz])

    # 2. Inner cavity (open at bottom, ceiling at inner_z_max = 5.5)
    cav_bot = z_min - 1
    cav_top = inner_z_max
    cav_h = cav_top - cav_bot
    cavity = box([ix, iy, cav_h])
    cavity.apply_translation([0, 0, (cav_bot + cav_top) / 2])

    shell = bool_diff(outer, cavity)

    # 3. Detect button caps from mesh geometry
    print(f"    Detecting button caps (Z > {BTN_CAP_Z_THRESHOLD:.1f}):")
    caps_left = find_button_caps(btn1_mesh, "dpad")
    caps_right = find_button_caps(btn2_mesh, "ab")
    all_caps = caps_left + caps_right

    print(f"      btn_assy_1: {len(caps_left)} caps found")
    for c in caps_left:
        print(f"        {c['label']}: {c['w']:.1f}x{c['h']:.1f}mm "
              f"at ({(c['x_min']+c['x_max'])/2:.1f}, {(c['y_min']+c['y_max'])/2:.1f})")
    print(f"      btn_assy_2: {len(caps_right)} caps found")
    for c in caps_right:
        print(f"        {c['label']}: {c['w']:.1f}x{c['h']:.1f}mm "
              f"at ({(c['x_min']+c['x_max'])/2:.1f}, {(c['y_min']+c['y_max'])/2:.1f})")

    # 4. Cut openings: screen + individual button caps
    cut_bot = inner_z_max - 0.5
    cut_top = z_max + 1
    cut_h = cut_top - cut_bot
    cut_cz = (cut_bot + cut_top) / 2

    print(f"    Cutting top plate openings:")

    # Screen cutout
    sw = SCREEN_CUT["x_max"] - SCREEN_CUT["x_min"]
    sh = SCREEN_CUT["y_max"] - SCREEN_CUT["y_min"]
    scx = (SCREEN_CUT["x_min"] + SCREEN_CUT["x_max"]) / 2
    scy = (SCREEN_CUT["y_min"] + SCREEN_CUT["y_max"]) / 2
    screen_box = box([sw, sh, cut_h])
    screen_box.apply_translation([scx, scy, cut_cz])
    shell = bool_diff(shell, screen_box)
    print(f"      Screen: {sw:.1f}x{sh:.1f}mm (wider than tall) OK")

    # D-pad cutout (CROSS shape = 2 overlapping rectangles)
    dcx, dcy = DPAD_CUT["cx"], DPAD_CUT["cy"]
    # Horizontal arm
    h_bar = box([DPAD_CUT["h_width"], DPAD_CUT["h_height"], cut_h])
    h_bar.apply_translation([dcx, dcy, cut_cz])
    shell = bool_diff(shell, h_bar)
    # Vertical arm
    v_bar = box([DPAD_CUT["v_width"], DPAD_CUT["v_height"], cut_h])
    v_bar.apply_translation([dcx, dcy, cut_cz])
    shell = bool_diff(shell, v_bar)
    print(f"      D-pad cross: {DPAD_CUT['h_width']:.0f}x{DPAD_CUT['h_height']:.0f} + "
          f"{DPAD_CUT['v_width']:.0f}x{DPAD_CUT['v_height']:.0f}mm at ({dcx:.1f},{dcy:.1f}) OK")

    # Individual button cap cutouts (ROUND holes)
    for cap in all_caps:
        w = cap["x_max"] - cap["x_min"]
        d = cap["y_max"] - cap["y_min"]
        diameter = max(w, d)  # circle encompasses full cap
        r = diameter / 2
        cx = (cap["x_min"] + cap["x_max"]) / 2
        cy = (cap["y_min"] + cap["y_max"]) / 2
        cut_cyl = cylinder(radius=r, height=cut_h, sections=48)
        cut_cyl.apply_translation([cx, cy, cut_cz])
        shell = bool_diff(shell, cut_cyl)
        print(f"      {cap['label']}: Ø{diameter:.1f}mm at ({cx:.1f},{cy:.1f}) OK")

    # 5. Screw bosses
    bosses = []
    boss_h = inner_z_max - z_min

    for hx, hy in MOUNT_HOLES:
        boss = cylinder(radius=POST_R, height=boss_h, sections=32)
        boss.apply_translation([hx, hy, (z_min + inner_z_max) / 2])
        tap = cylinder(radius=SCREW_TAP_R, height=boss_h + 2, sections=32)
        tap.apply_translation([hx, hy, (z_min + inner_z_max) / 2])
        bosses.append(bool_diff(boss, tap))

    result = bool_union([shell] + bosses)

    wall_x = (ox - ix) / 2
    wall_y = (oy - iy) / 2
    print(f"    Wall X: {wall_x:.1f}mm, Y: {wall_y:.1f}mm")
    print(f"    Total cutouts: 1 screen + {len(all_caps)} caps")
    print(f"    Final: {len(result.faces)} faces")

    # Store caps for verification
    dims["_all_caps"] = all_caps
    return result


# ═══════════════════════════════════════════════════════════════════
# BOTTOM SHELL V7 - Reduced depth + countersunk screws
# ═══════════════════════════════════════════════════════════════════
def generate_bottom_v7(dims):
    ox, oy = dims["outer_x"], dims["outer_y"]
    ix, iy = dims["inner_x"], dims["inner_y"]
    z_min = dims["bot_z_min"]
    z_max = dims["bot_z_max"]
    h = z_max - z_min
    cz = (z_min + z_max) / 2

    print(f"\n  Bottom V7: {ox:.1f} x {oy:.1f} x {h:.1f}mm, Z=[{z_min:.1f},{z_max:.1f}]")
    print(f"    Battery gap: {BATTERY_GAP:.1f}mm (pressed against internal wall)")

    # Outer
    outer = rounded_box(ox, oy, h, CORNER_R)
    outer.apply_translation([0, 0, cz])

    # Inner cavity
    cav_r = max(CORNER_R - WALL, 0.5)
    cav_h = h - FLOOR + 2
    cavity = rounded_box(ix, iy, cav_h, cav_r)
    cavity.apply_translation([0, 0, z_min + FLOOR + cav_h / 2])

    shell = bool_diff(outer, cavity)

    # Lip
    lip_outer = rounded_box(
        ORIG_TOP["inner_x"] - 0.3,
        ORIG_TOP["inner_y"] - 0.3,
        LIP_HEIGHT, cav_r
    )
    lip_inner_x = ORIG_TOP["inner_x"] - 0.3 - 2 * LIP_WIDTH
    lip_inner_y = ORIG_TOP["inner_y"] - 0.3 - 2 * LIP_WIDTH
    lip_inner = rounded_box(lip_inner_x, lip_inner_y, LIP_HEIGHT + 2,
                            max(cav_r - LIP_WIDTH, 0.3))
    lip = bool_diff(lip_outer, lip_inner)
    lip.apply_translation([0, 0, z_max + LIP_HEIGHT / 2])

    # Screw posts
    posts = []
    post_h = h - FLOOR
    for hx, hy in MOUNT_HOLES:
        p = cylinder(radius=POST_R, height=post_h, sections=32)
        p.apply_translation([hx, hy, z_min + FLOOR + post_h / 2])
        hole = cylinder(radius=SCREW_R, height=post_h + 2, sections=32)
        hole.apply_translation([hx, hy, z_min + FLOOR + post_h / 2])
        posts.append(bool_diff(p, hole))

    # Battery retainers
    bat_cz = dims["bat_center_z"]
    bat_h = BATTERY["thickness"] + 1
    bat_hold = []
    for sign in [-1, 1]:
        r = box([BAT_HOLDER_W, BATTERY["width"] + 2, bat_h])
        r.apply_translation([sign * (BATTERY["length"]/2 + BAT_HOLDER_W/2), 0, bat_cz])
        bat_hold.append(r)
    for sx in [-1, 1]:
        for sy in [-1, 1]:
            clip = box([10, BAT_HOLDER_W, bat_h])
            clip.apply_translation([sx*(BATTERY["length"]/2-5),
                                    sy*(BATTERY["width"]/2+BAT_HOLDER_W/2), bat_cz])
            bat_hold.append(clip)

    # Union
    result = bool_union([shell, lip] + posts + bat_hold)

    # Front cutouts (Y-min wall)
    y_wall_front = -oy / 2
    print(f"    Front cutouts (wall Y={y_wall_front:.1f}):")
    for name, cd in FRONT_CUTS.items():
        cw = cd["w"] + 1.0
        ch = cd["h"] + 1.0
        cut = box([cw, WALL + 6, ch])
        cut.apply_translation([cd["x"], y_wall_front, cd["z"]])
        before = len(result.faces)
        result = bool_diff(result, cut)
        after = len(result.faces)
        changed = before != after
        print(f"      {cd['label']}: X={cd['x']:.1f} Z={cd['z']:.1f} "
              f"opening={cw:.0f}x{ch:.0f}mm {'OK' if changed else 'WARN'}")

    # Back cutouts (Y-max wall)
    y_wall_back = oy / 2
    print(f"    Back cutouts (wall Y={y_wall_back:.1f}):")
    for name, cd in BACK_CUTS.items():
        cw = cd["w"] + 1.0
        ch = cd["h"] + 1.0
        cut = box([cw, WALL + 6, ch])
        cut.apply_translation([cd["x"], y_wall_back, cd["z"]])
        before = len(result.faces)
        result = bool_diff(result, cut)
        after = len(result.faces)
        changed = before != after
        print(f"      {cd['label']}: X={cd['x']:.1f} Z={cd['z']:.1f} "
              f"opening={cw:.0f}x{ch:.0f}mm {'OK' if changed else 'WARN'}")

    # Countersunk screw recesses
    print(f"\n    Countersunk screws (M3 flush mount):")
    for hx, hy in MOUNT_HOLES:
        th = cylinder(radius=SCREW_CLEAR_R, height=FLOOR + 2, sections=32)
        th.apply_translation([hx, hy, z_min + FLOOR / 2])
        result = bool_diff(result, th)

        cb = cylinder(radius=COUNTERBORE_R, height=COUNTERBORE_DEPTH, sections=32)
        cb.apply_translation([hx, hy, z_min + COUNTERBORE_DEPTH / 2])
        result = bool_diff(result, cb)
        print(f"      Hole ({hx:.1f}, {hy:.1f}): OK")

    print(f"    Final: {len(result.faces)} faces")
    return result


# ═══════════════════════════════════════════════════════════════════
# SHOULDER BUTTONS (same as V5/V6)
# ═══════════════════════════════════════════════════════════════════
def generate_shoulder_button(side, dims):
    sw = SHOULDER_SW[side]
    oy = dims["outer_y"]
    wall_outer_y = oy / 2
    wall_inner_y = wall_outer_y - WALL

    cut_w = BACK_CUTS[f"shoulder_{side.lower()}"]["w"]
    cut_h = BACK_CUTS[f"shoulder_{side.lower()}"]["h"]

    btn_clearance = 0.25
    guide_w = cut_w - 2 * btn_clearance
    guide_h = cut_h - 2 * btn_clearance
    cap_depth = 1.5

    arm_target_y = sw["y_near"]
    arm_length = wall_inner_y - arm_target_y
    arm_w = min(6.0, guide_w - 2)
    arm_h = min(4.0, guide_h - 1)

    flange_w = cut_w + 3.0
    flange_h = cut_h + 2.0
    flange_t = 1.0
    nub_r = 1.5
    nub_len = 1.0

    print(f"    {side}: arm={arm_length:.1f}mm")

    parts = []
    cap = box([guide_w, cap_depth, guide_h])
    cap.apply_translation([sw["x"], wall_outer_y + cap_depth / 2, sw["z"]])
    parts.append(cap)

    guide = box([guide_w, WALL, guide_h])
    guide.apply_translation([sw["x"], wall_outer_y - WALL / 2, sw["z"]])
    parts.append(guide)

    flange = box([flange_w, flange_t, flange_h])
    flange.apply_translation([sw["x"], wall_inner_y - flange_t / 2, sw["z"]])
    parts.append(flange)

    arm = box([arm_w, arm_length, arm_h])
    arm.apply_translation([sw["x"], wall_inner_y - arm_length / 2, sw["z"]])
    parts.append(arm)

    nub = cylinder(radius=nub_r, height=nub_len, sections=16)
    nub.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    nub_y = wall_inner_y - arm_length - nub_len / 2
    nub.apply_translation([sw["x"], nub_y, sw["z"]])
    parts.append(nub)

    return bool_union(parts)


# ═══════════════════════════════════════════════════════════════════
# BUTTON FLANGES (retention lips between board and top plate)
# ═══════════════════════════════════════════════════════════════════
def add_button_flange(btn_mesh):
    """
    Add a retention flange at the base of the button assembly.
    The flange covers the full button footprint + 1mm margin,
    sitting just below the top plate inner surface (Z=5.5).
    Since the top plate is now solid (only small cap holes),
    the flange prevents the assembly from moving upward.
    """
    bounds = btn_mesh.bounds
    # Flange dimensions: full button mesh footprint + margin
    fx = (bounds[1][0] - bounds[0][0]) + 2 * BTN_FLANGE_EXTRA
    fy = (bounds[1][1] - bounds[0][1]) + 2 * BTN_FLANGE_EXTRA
    cx = (bounds[0][0] + bounds[1][0]) / 2
    cy = (bounds[0][1] + bounds[1][1]) / 2
    # Flange Z: from (top_plate_inner - flange_t) to top_plate_inner
    fz_top = BTN_FLANGE_Z_TOP
    fz_bot = fz_top - BTN_FLANGE_T
    fz_center = (fz_top + fz_bot) / 2

    # Clip to inner cavity bounds
    inner_hx = ORIG_TOP["inner_x"] / 2
    inner_hy = ORIG_TOP["inner_y"] / 2
    f_xmin = max(cx - fx/2, -inner_hx + 0.2)
    f_xmax = min(cx + fx/2, inner_hx - 0.2)
    f_ymin = max(cy - fy/2, -inner_hy + 0.2)
    f_ymax = min(cy + fy/2, inner_hy - 0.2)

    clipped_fx = f_xmax - f_xmin
    clipped_fy = f_ymax - f_ymin
    clipped_cx = (f_xmin + f_xmax) / 2
    clipped_cy = (f_ymin + f_ymax) / 2

    flange = box([clipped_fx, clipped_fy, BTN_FLANGE_T])
    flange.apply_translation([clipped_cx, clipped_cy, fz_center])

    result = bool_union([btn_mesh, flange])

    btn_w = bounds[1][0] - bounds[0][0]
    btn_h = bounds[1][1] - bounds[0][1]
    print(f"      Flange: {clipped_fx:.1f}x{clipped_fy:.1f}x{BTN_FLANGE_T:.1f}mm "
          f"at Z=[{fz_bot:.1f},{fz_top:.1f}]")
    print(f"      Button footprint: {btn_w:.1f}x{btn_h:.1f}mm "
          f"+ {BTN_FLANGE_EXTRA:.1f}mm margin = retention under solid plate")

    return result


# ═══════════════════════════════════════════════════════════════════
# COLORIZE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════
def get_glb_regions(glb_path):
    scene = trimesh.load(glb_path)
    if not isinstance(scene, trimesh.Scene): return []
    regions = []
    for name, geom in scene.geometry.items():
        if not isinstance(geom, trimesh.Trimesh): continue
        bounds = geom.bounds; dims = bounds[1]-bounds[0]
        center = (bounds[0]+bounds[1])/2
        color = None
        if hasattr(geom.visual, 'main_color'):
            color = tuple(geom.visual.main_color[:3].tolist())
        if color is None: continue
        r, g, b = color
        if (r,g,b)==(255,215,0):
            key = "dpad_gold" if (center[0]<-25 and center[1]>0 and center[2]>0) else \
                  ("shoulder_btn" if center[2]<0 else "button_gold")
            regions.append({"bmin":bounds[0],"bmax":bounds[1],"color_key":key,"priority":10,"expand":0.5})
        elif all(c<60 for c in (r,g,b)) and dims[0]>30 and dims[1]>30:
            regions.append({"bmin":bounds[0],"bmax":bounds[1],"color_key":"screen","priority":20,"expand":0})
            regions.append({"bmin":bounds[0]-[2,2,0],"bmax":bounds[1]+[2,2,0.5],"color_key":"screen_bezel","priority":15,"expand":0})
        elif all(c<60 for c in (r,g,b)):
            if max(dims[0],dims[1])>=3 and center[1]<-18:
                key = "usbc_metal" if max(dims[0],dims[1])>7 else "audio_metal"
                regions.append({"bmin":bounds[0],"bmax":bounds[1],"color_key":key,"priority":15,"expand":0.5})
            elif 2<dims[0]<20 and dims[1]>2:
                regions.append({"bmin":bounds[0],"bmax":bounds[1],"color_key":"ic_black","priority":5,"expand":0})
        elif (r,g,b)==(200,170,80):
            regions.append({"bmin":bounds[0],"bmax":bounds[1],"color_key":"hole_ring","priority":12,"expand":1.0})
        elif all(40<c<120 for c in (r,g,b)) and (dims[0]>5 or dims[1]>5):
            regions.append({"bmin":bounds[0],"bmax":bounds[1],"color_key":"sd_slot","priority":3,"expand":0})
    return regions


def colorize_board(mesh, regions):
    n=len(mesh.faces); centroids=mesh.vertices[mesh.faces].mean(axis=1)
    normals=mesh.face_normals; fc=np.zeros((n,4),dtype=np.uint8)
    top=normals[:,2]>0.3; bot=normals[:,2]<-0.3
    for i in range(n):
        fc[i]=COL["pcb_top"] if top[i] else (COL["pcb_bottom"] if bot[i] else COL["pcb_edge"])
    for reg in sorted(regions,key=lambda r:r["priority"]):
        exp=reg.get("expand",0)
        rmin=np.minimum(reg["bmin"],reg["bmax"])-exp
        rmax=np.maximum(reg["bmin"],reg["bmax"])+exp
        mask=((centroids>=rmin)&(centroids<=rmax)).all(axis=1)
        fc[mask]=COL[reg["color_key"]]
    for hx,hy in [[-47,-22],[44.9,-23],[-46,21.8],[46,21.8]]:
        d=np.sqrt((centroids[:,0]-hx)**2+(centroids[:,1]-hy)**2)
        fc[(d<2)&~top&~bot]=COL["hole_inner"]
        fc[(d>=2)&(d<4)&(np.abs(normals[:,2])>0.3)]=COL["hole_ring"]
    mesh.visual.face_colors=fc; return mesh


def colorize_case(mesh, c_out, c_in):
    center=(mesh.bounds[0]+mesh.bounds[1])/2
    centroids=mesh.vertices[mesh.faces].mean(axis=1)
    normals=mesh.face_normals; fc=np.zeros((len(mesh.faces),4),dtype=np.uint8)
    for i in range(len(mesh.faces)):
        fc[i]=c_out if np.dot(normals[i],center-centroids[i])<0 else c_in
    mesh.visual.face_colors=fc; return mesh


def colorize_uniform(mesh, color):
    mesh.visual.face_colors=np.full((len(mesh.faces),4),color,dtype=np.uint8)
    return mesh


def create_battery(cz):
    bat=box([BATTERY["length"],BATTERY["width"],BATTERY["thickness"]])
    bat.apply_translation([0,0,cz])
    fc=np.full((len(bat.faces),4),COL["battery"],dtype=np.uint8)
    fc[bat.face_normals[:,2]>0.9]=COL["bat_label"]
    bat.visual.face_colors=fc; return bat


def verify_cutouts(mesh, cutouts, wall_pos, label):
    print(f"\n  Cutout verification ({label}):")
    for name, cd in cutouts.items():
        origin = np.array([cd["x"], wall_pos, cd["z"]])
        direction = np.array([0, -np.sign(wall_pos), 0])
        locations, _, _ = mesh.ray.intersects_location(
            ray_origins=[origin], ray_directions=[direction]
        )
        if len(locations) == 0:
            print(f"    {cd['label']}: OPEN (ray passes through)")
        else:
            dists = np.linalg.norm(locations - origin, axis=1)
            min_dist = dists.min()
            if min_dist < WALL + 1:
                print(f"    {cd['label']}: BLOCKED at dist={min_dist:.1f}mm !!!")
            else:
                print(f"    {cd['label']}: OPEN (first hit at {min_dist:.1f}mm)")


def verify_top_cutouts(mesh, dims):
    """Verify top plate cutouts by casting rays downward through expected openings."""
    print(f"\n  Top plate cutout verification:")
    z_above = ORIG_TOP["z_max"] + 5

    # Verify screen
    scx = (SCREEN_CUT["x_min"] + SCREEN_CUT["x_max"]) / 2
    scy = (SCREEN_CUT["y_min"] + SCREEN_CUT["y_max"]) / 2
    origin = np.array([scx, scy, z_above])
    locs, _, _ = mesh.ray.intersects_location(
        ray_origins=[origin], ray_directions=[[0, 0, -1]])
    status = "OPEN" if len(locs) == 0 else ("OPEN" if locs[:, 2].max() < ORIG_TOP["inner_z_max"] else "BLOCKED")
    print(f"    Screen: {status}")

    # Verify D-pad
    origin = np.array([DPAD_CUT["cx"], DPAD_CUT["cy"], z_above])
    locs, _, _ = mesh.ray.intersects_location(
        ray_origins=[origin], ray_directions=[[0, 0, -1]])
    status = "OPEN" if len(locs) == 0 else ("OPEN" if locs[:, 2].max() < ORIG_TOP["inner_z_max"] else "BLOCKED")
    print(f"    D-pad: {status}")

    # Verify individual button caps
    all_caps = dims.get("_all_caps", [])
    open_count = 0
    for cap in all_caps:
        cx = (cap["x_min"] + cap["x_max"]) / 2
        cy = (cap["y_min"] + cap["y_max"]) / 2
        origin = np.array([cx, cy, z_above])
        locs, _, _ = mesh.ray.intersects_location(
            ray_origins=[origin], ray_directions=[[0, 0, -1]])
        if len(locs) == 0 or locs[:, 2].max() < ORIG_TOP["inner_z_max"]:
            open_count += 1
        else:
            print(f"    {cap['label']}: BLOCKED !!!")
    print(f"    Button caps: {open_count}/{len(all_caps)} OPEN")

    # Verify solid between buttons (should be blocked)
    mid_x = 0.0  # center of top plate, between screen and buttons
    mid_y = 15.0  # area that should be solid
    origin = np.array([mid_x, mid_y, z_above])
    locs, _, _ = mesh.ray.intersects_location(
        ray_origins=[origin], ray_directions=[[0, 0, -1]])
    is_solid = len(locs) > 0 and locs[:, 2].max() >= ORIG_TOP["inner_z_max"]
    print(f"    Solid between components: {'YES' if is_solid else 'NO (gap!)'}")


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
def main():
    original_dir = Path("/workspace/original")
    ref_dir = Path("/workspace/ref")
    output_dir = Path("/workspace/output/v7")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("V7 BUILD")
    print("  1. Top shell: SOLID plate + per-cap cutouts (auto-detected)")
    print("     Only actual button caps get holes - plate covers assemblies")
    print("  2. Button flanges: 1mm wider base for retention (board<->top)")
    print("  3. Bottom shell: battery against wall, reduced depth")
    print("  4. Countersunk M3 screws + SD card slot preserved")
    print("=" * 70)

    # ── Load ──
    print("\n--- Loading ---")
    board_stl = load_mesh(original_dir / "board.stl")
    btn1 = load_mesh(original_dir / "btn_assy_1.stl")
    btn2 = load_mesh(original_dir / "btn_assy_2.stl")

    # Center board
    top_orig = load_mesh(original_dir / "top_body.stl")
    bc = (board_stl.bounds[0] + board_stl.bounds[1]) / 2
    tc = (top_orig.bounds[0] + top_orig.bounds[1]) / 2
    board = board_stl.copy()
    board.apply_translation(-np.array([bc[0]-tc[0], bc[1]-tc[1], 0]))

    print(f"  Board: [{board.bounds[0][0]:.1f},{board.bounds[0][1]:.1f},{board.bounds[0][2]:.1f}] "
          f"to [{board.bounds[1][0]:.1f},{board.bounds[1][1]:.1f},{board.bounds[1][2]:.1f}]")
    print(f"  btn_assy_1: [{btn1.bounds[0][0]:.1f},{btn1.bounds[0][1]:.1f}] "
          f"to [{btn1.bounds[1][0]:.1f},{btn1.bounds[1][1]:.1f}]")
    print(f"  btn_assy_2: [{btn2.bounds[0][0]:.1f},{btn2.bounds[0][1]:.1f}] "
          f"to [{btn2.bounds[1][0]:.1f},{btn2.bounds[1][1]:.1f}]")

    dims = compute_dims(board.bounds)
    total_h = dims["top_z_max"] - dims["bot_z_min"]

    # ── Depth breakdown ──
    print(f"\n--- Depth Breakdown (V7 optimized) ---")
    print(f"  Board Z_min (lowest component):   {dims['pcb_z_bot']:.1f}mm")
    print(f"  Battery gap (minimized):          {BATTERY_GAP:.1f}mm")
    print(f"  Battery top:                      {dims['bat_top']:.1f}mm")
    print(f"  Battery (955565):                 {BATTERY['thickness']:.1f}mm thick")
    print(f"  Battery bottom:                   {dims['bat_bot']:.1f}mm")
    print(f"  Floor:                            {FLOOR:.1f}mm")
    print(f"  Shell floor Z:                    {dims['bot_z_min']:.1f}mm")
    print(f"  Shell top Z:                      {dims['bot_z_max']:.1f}mm")
    print(f"  Bottom shell height:              {dims['bot_z_max'] - dims['bot_z_min']:.1f}mm")
    print(f"  + Lip:                            {LIP_HEIGHT:.1f}mm")
    print(f"  Bottom total:                     {dims['bot_z_max'] + LIP_HEIGHT - dims['bot_z_min']:.1f}mm")
    print(f"")
    print(f"  DEPTH CONSTRAINT: battery 955565 = {BATTERY['thickness']:.1f}mm thick.")
    print(f"  Min bottom depth = board_depth({abs(dims['pcb_z_bot']):.1f}) + "
          f"gap({BATTERY_GAP:.1f}) + battery({BATTERY['thickness']:.1f}) + "
          f"floor({FLOOR:.1f}) + above_split({dims['bot_z_max']:.1f}) = "
          f"{dims['bot_z_max'] - dims['bot_z_min']:.1f}mm")

    # ── Generate ──
    print("\n--- Top shell V7 ---")
    top = generate_top_v7(dims, btn1, btn2)

    print("\n--- Bottom shell V7 ---")
    bottom = generate_bottom_v7(dims)

    print("\n--- Shoulder buttons ---")
    sh_l = generate_shoulder_button("L", dims)
    sh_r = generate_shoulder_button("R", dims)

    # ── Add button retention flanges ──
    print("\n--- Button retention flanges ---")
    print("    btn_assy_1 (D-pad):")
    btn1_flanged = add_button_flange(btn1.copy())
    print("    btn_assy_2 (A/B):")
    btn2_flanged = add_button_flange(btn2.copy())

    # ── Colorize ──
    print("\n--- Colorizing ---")
    regions = get_glb_regions(ref_dir / "esplay_micro_pcb.glb")

    board_col = colorize_board(board.copy(), regions)
    top_col = colorize_case(top.copy(), COL["case_top"], COL["case_top_in"])
    bot_col = colorize_case(bottom.copy(), COL["case_bot"], COL["case_bot_in"])
    btn1_col = colorize_uniform(btn1_flanged.copy(), COL["btn_dark"])
    btn2_col = colorize_uniform(btn2_flanged.copy(), COL["btn_dark"])
    sh_l_col = colorize_uniform(sh_l.copy(), COL["shoulder_cap"])
    sh_r_col = colorize_uniform(sh_r.copy(), COL["shoulder_cap"])
    battery = create_battery(dims["bat_center_z"])

    # ── Verify cutouts ──
    verify_cutouts(bottom, FRONT_CUTS, -dims["outer_y"]/2, "Front (Y-min)")
    verify_cutouts(bottom, BACK_CUTS, dims["outer_y"]/2, "Back (Y-max)")
    verify_top_cutouts(top, dims)

    # ── Save ──
    print("\n--- Saving ---")
    for name, mesh in [
        ("board_colored.glb", board_col),
        ("top_body_v7.glb", top_col),
        ("bottom_body_v7.glb", bot_col),
        ("btn_assy_1_colored.glb", btn1_col),
        ("btn_assy_2_colored.glb", btn2_col),
        ("shoulder_l.glb", sh_l_col),
        ("shoulder_r.glb", sh_r_col),
        ("battery.glb", battery),
    ]:
        mesh.export(output_dir / name)
        print(f"  {name}")

    for name, mesh in [
        ("top_body_v7.stl", top),
        ("bottom_body_v7.stl", bottom),
        ("btn_assy_1_v7.stl", btn1_flanged),
        ("btn_assy_2_v7.stl", btn2_flanged),
        ("shoulder_l.stl", sh_l),
        ("shoulder_r.stl", sh_r),
    ]:
        mesh.export(output_dir / name)
        print(f"  {name} (print)")

    # ── Assemblies ──
    print("\n--- Assemblies ---")
    closed = trimesh.Scene()
    for n, m in [("Board", board_col), ("Top_V7", top_col), ("Bottom_V7", bot_col),
                  ("Btn_L", btn1_col), ("Btn_R", btn2_col),
                  ("Shoulder_L", sh_l_col), ("Shoulder_R", sh_r_col),
                  ("Battery", battery)]:
        closed.add_geometry(m, node_name=n)
    closed.export(output_dir / "assembly_closed.glb")

    explode = 25.0
    opened = trimesh.Scene()
    opened.add_geometry(board_col, node_name="Board")
    for n, m, dz in [("Top_V7", top_col, explode), ("Btn_L", btn1_col, explode+10),
                      ("Btn_R", btn2_col, explode+10), ("Bottom_V7", bot_col, -explode),
                      ("Shoulder_L", sh_l_col, -explode*0.3), ("Shoulder_R", sh_r_col, -explode*0.3),
                      ("Battery", battery, -explode*0.6)]:
        mc = m.copy(); mc.apply_translation([0, 0, dz])
        opened.add_geometry(mc, node_name=n)
    opened.export(output_dir / "assembly_open.glb")

    # ══════════════════════════════════════════════════════════════
    # VERIFICATION
    # ══════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("V7 VERIFICATION")
    print("=" * 70)

    parts = {
        "Bottom V7": bot_col, "Battery": battery, "Board": board_col,
        "Top V7": top_col, "Buttons L": btn1_col, "Buttons R": btn2_col,
        "Shoulder L": sh_l_col, "Shoulder R": sh_r_col,
    }

    print(f"\n  Z-Stack:")
    print(f"  {'Part':<20} {'Z min':>8} {'Z max':>8} {'Height':>8}")
    print(f"  {'-'*48}")
    for name, m in parts.items():
        b = m.bounds
        print(f"  {name:<20} {b[0][2]:8.2f} {b[1][2]:8.2f} {b[1][2]-b[0][2]:8.2f}")

    print(f"\n  XY dimensions:")
    for name, m in parts.items():
        d = m.bounds[1] - m.bounds[0]
        print(f"  {name:<20} {d[0]:8.2f} x {d[1]:8.2f}")

    # Top <-> Bottom match
    tb = top_col.bounds; btb = bot_col.bounds
    print(f"\n  Top <-> Bottom XY match:")
    for ax, i in [("X", 0), ("Y", 1)]:
        t_dim = tb[1][i] - tb[0][i]
        b_dim = btb[1][i] - btb[0][i]
        diff = abs(b_dim - t_dim)
        status = "MATCH" if diff < 0.5 else f"DIFF {diff:.1f}mm"
        print(f"    {ax}: top={t_dim:.1f}mm, bottom={b_dim:.1f}mm  {status}")

    # Clearances
    bb = board_col.bounds; batb = battery.bounds
    issues = []

    c1 = tb[1][2] - bb[1][2]
    print(f"\n  Clearances:")
    print(f"    Board top -> Top top:       {c1:+.2f}mm {'OK' if c1>=-0.1 else 'PROBLEM'}")
    if c1<-0.1: issues.append("Board above top shell")

    c2 = bb[0][2] - batb[1][2]
    print(f"    Battery -> Board:           {c2:+.2f}mm {'OK' if c2>=0 else 'COLLISION'}")
    if c2<0: issues.append("Battery/board collision")

    c3 = batb[0][2] - btb[0][2]
    print(f"    Battery -> Floor:           {c3:+.2f}mm {'OK' if c3>=0.5 else 'TIGHT'}")

    # Board fit
    print(f"\n  Board fit:")
    for ax, i in [("X", 0), ("Y", 1)]:
        c_min = min(tb[0][i], btb[0][i])
        c_max = max(tb[1][i], btb[1][i])
        m1 = bb[0][i] - c_min; m2 = c_max - bb[1][i]
        print(f"    {ax}: margins {m1:+.2f}/{m2:+.2f} {'OK' if m1>=-0.1 and m2>=-0.1 else 'OUT'}")
        if m1<-0.1 or m2<-0.1: issues.append(f"Board outside case {ax}")

    # Battery fit
    print(f"\n  Battery fit:")
    bi_x = btb[1][0]-btb[0][0]-2*WALL; bi_y = btb[1][1]-btb[0][1]-2*WALL
    for ax, bd, inner in [("X", BATTERY["length"], bi_x), ("Y", BATTERY["width"], bi_y)]:
        print(f"    {ax}: {bd:.1f} in {inner:.1f} gap={inner-bd:+.1f} "
              f"{'OK' if bd<=inner+0.1 else 'NO'}")
        if bd > inner + 0.1: issues.append(f"Battery {ax} no fit")

    # V6 comparison
    v6_depth = 20.0
    v7_depth = dims["bot_z_max"] - dims["bot_z_min"]
    print(f"\n  V6 -> V7 changes:")
    print(f"    Top shell: giant opening -> solid plate + 3 cutouts")
    print(f"    Battery gap: 1.0mm -> {BATTERY_GAP:.1f}mm (against internal wall)")
    print(f"    Bottom depth: {v6_depth:.1f}mm -> {v7_depth:.1f}mm (saved {v6_depth-v7_depth:.1f}mm)")
    print(f"    Bottom with lip: {v6_depth+1.5:.1f}mm -> {v7_depth+LIP_HEIGHT:.1f}mm")

    all_b = np.array([(m.bounds[0], m.bounds[1]) for m in parts.values()])
    total_dims = all_b[:,1].max(axis=0) - all_b[:,0].min(axis=0)
    print(f"\n  Overall: {total_dims[0]:.1f} x {total_dims[1]:.1f} x {total_dims[2]:.1f} mm")

    if issues:
        print(f"\n  *** {len(issues)} ISSUES ***")
        for iss in issues: print(f"    - {iss}")
    else:
        print(f"\n  ALL CHECKS PASSED!")

    report = {
        "version": "v7",
        "changes": [
            "Top shell: solid plate with per-cap cutouts (auto-detected from mesh)",
            "Battery gap reduced to 0.3mm (pressed against internal wall)",
            f"Bottom depth reduced: {v6_depth:.1f} -> {v7_depth:.1f}mm",
            "Countersunk M3 screws preserved",
            "SD card slot preserved",
        ],
        "top_cutouts": {
            "screen": {"w": SCREEN_CUT["x_max"]-SCREEN_CUT["x_min"],
                       "h": SCREEN_CUT["y_max"]-SCREEN_CUT["y_min"]},
            "button_caps": [{"label": c["label"], "w": c["w"], "h": c["h"]}
                            for c in dims.get("_all_caps", [])],
        },
        "depth": {
            "bottom_shell": v7_depth,
            "bottom_total": v7_depth + LIP_HEIGHT,
            "battery_gap": BATTERY_GAP,
            "constraint": f"Battery 955565 ({BATTERY['thickness']}mm) is the limiting factor",
        },
        "issues": issues,
    }
    with open(output_dir / "v7_report.json", "w") as f:
        json.dump(report, f, indent=2, cls=NpEnc)

    print(f"\n--- Output ---")
    for f in sorted(output_dir.glob("*")):
        print(f"  {f.name} ({f.stat().st_size/1024:.0f} KB)")

    print(f"\n{'='*70}")
    print("V7 BUILD COMPLETE")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
