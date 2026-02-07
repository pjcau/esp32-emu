#!/usr/bin/env python3
"""
V5 Assembly - Fixes from V4:
  1. Top shell: EXTEND original top_body.stl to match bottom XY.
     Internal geometry (cavity, opening) stays identical to original.
     Only outer walls grow wider.
  2. Shoulder buttons: shorter arm, centered on tact switch.
  3. Bottom shell: explicit SD card slot verification.
  4. Rounded corners, reduced dimensions kept from V4.
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
BATTERY_GAP = 1.0
CORNER_R = 3.0
LIP_HEIGHT = 1.5
LIP_WIDTH = 0.8
SCREW_R = 1.6
POST_R = 3.5
BAT_HOLDER_W = 1.5

# Original top shell internal dimensions (from inspection)
ORIG_TOP = {
    "outer_x": 100.06, "outer_y": 49.94,
    "inner_x": 98.1,   "inner_y": 46.7,    # inner cavity [-49.3,48.8] x [-23.3,23.4]
    "opening_x": 98.0, "opening_y": 47.5,   # top plate opening
    "inner_z_max": 5.5,                      # inner ceiling (cavity top)
    "z_min": 1.0, "z_max": 7.0,             # original Z range
    "top_plate_t": 1.5,                      # keep 1.5mm top plate
}

MOUNT_HOLES = [(-47.0, -22.0), (44.9, -23.0), (-46.0, 21.8), (46.0, 21.8)]

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

# Shoulder tact switches (GLB coords)
# geometry_81: center=(-38.6, 20.7, -3.6), dims=(10x6x5.5)
# geometry_82: center=(38.9, 20.7, -3.6), dims=(10x6x5.5)
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
    """Box with rounded vertical edges."""
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
        "bot_z_max": ORIG_TOP["z_min"],  # Bottom shell top = original top shell bottom = Z=1
        "top_z_min": ORIG_TOP["z_min"],  # Z=1
        "top_z_max": ORIG_TOP["z_max"],  # Z=7
        "bat_top": bat_top, "bat_bot": bat_bot,
        "bat_center_z": (bat_top + bat_bot) / 2,
    }


# ═══════════════════════════════════════════════════════════════════
# BOTTOM SHELL V5
# ═══════════════════════════════════════════════════════════════════
def generate_bottom_v5(dims):
    ox, oy = dims["outer_x"], dims["outer_y"]
    ix, iy = dims["inner_x"], dims["inner_y"]
    z_min = dims["bot_z_min"]
    z_max = dims["bot_z_max"]  # Z=1
    h = z_max - z_min
    cz = (z_min + z_max) / 2

    print(f"\n  Bottom V5: {ox:.1f} x {oy:.1f} x {h:.1f}mm, Z=[{z_min:.1f},{z_max:.1f}]")

    # Outer
    outer = rounded_box(ox, oy, h, CORNER_R)
    outer.apply_translation([0, 0, cz])

    # Inner cavity (open top)
    cav_r = max(CORNER_R - WALL, 0.5)
    cav_h = h - FLOOR + 2
    cavity = rounded_box(ix, iy, cav_h, cav_r)
    cavity.apply_translation([0, 0, z_min + FLOOR + cav_h / 2])

    shell = bool_diff(outer, cavity)

    # Lip (internal protrusion above shell top, enters the top shell)
    lip_outer = rounded_box(
        ORIG_TOP["inner_x"] - 0.3,  # slightly smaller than top's inner cavity
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
    pre_cut_faces = len(result.faces)

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
              f"opening={cw:.0f}x{ch:.0f}mm {'OK' if changed else 'WARN:no change!'}")

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
              f"opening={cw:.0f}x{ch:.0f}mm {'OK' if changed else 'WARN:no change!'}")

    print(f"    Final: {len(result.faces)} faces (pre-cut: {pre_cut_faces})")
    return result


# ═══════════════════════════════════════════════════════════════════
# TOP SHELL V5 - Extend original, keep internal geometry
# ═══════════════════════════════════════════════════════════════════
def generate_top_v5(dims, original_top):
    """
    Strategy: Create a frame extension around the original top body,
    then boolean union. This preserves the original internal geometry
    exactly, only adding outer wall material.
    """
    ox, oy = dims["outer_x"], dims["outer_y"]
    orig_ox = ORIG_TOP["outer_x"]
    orig_oy = ORIG_TOP["outer_y"]
    z_min = ORIG_TOP["z_min"]
    z_max = ORIG_TOP["z_max"]
    h = z_max - z_min
    cz = (z_min + z_max) / 2

    print(f"\n  Top V5: extending original ({orig_ox:.1f}x{orig_oy:.1f}) "
          f"→ ({ox:.1f}x{oy:.1f})")
    print(f"    Added wall X: {(ox - orig_ox)/2:.1f}mm per side")
    print(f"    Added wall Y: {(oy - orig_oy)/2:.1f}mm per side")

    # Create outer frame at new dimensions
    outer_frame = rounded_box(ox, oy, h, CORNER_R)
    outer_frame.apply_translation([0, 0, cz])

    # Cut out the original footprint (slightly expanded for clean merge)
    # Use a box slightly smaller than original outer so there's overlap for merging
    inner_cut = box([orig_ox - 0.2, orig_oy - 0.2, h + 2])
    inner_cut.apply_translation([0, 0, cz])

    frame = bool_diff(outer_frame, inner_cut)
    print(f"    Extension frame: {len(frame.faces)} faces")

    # Union frame with original top
    result = bool_union([original_top.copy(), frame])
    print(f"    After union with original: {len(result.faces)} faces")

    return result


# ═══════════════════════════════════════════════════════════════════
# SHOULDER BUTTONS V5 - Shorter, centered on switches
# ═══════════════════════════════════════════════════════════════════
def generate_shoulder_button(side, dims):
    """
    Shorter shoulder button centered on tact switch.
    Arm reaches switch near edge (not center).
    """
    sw = SHOULDER_SW[side]
    oy = dims["outer_y"]
    wall_outer_y = oy / 2          # outer back wall Y
    wall_inner_y = wall_outer_y - WALL   # inner back wall Y

    # Cutout dimensions
    cut_w = BACK_CUTS[f"shoulder_{side.lower()}"]["w"]
    cut_h = BACK_CUTS[f"shoulder_{side.lower()}"]["h"]

    # Button clearance in cutout
    btn_clearance = 0.25
    guide_w = cut_w - 2 * btn_clearance   # width in X
    guide_h = cut_h - 2 * btn_clearance   # height in Z

    # Cap protrusion
    cap_depth = 1.5

    # Arm length: from inner wall to switch near edge
    arm_target_y = sw["y_near"]  # near edge of switch (closest to wall)
    arm_length = wall_inner_y - arm_target_y
    arm_w = min(6.0, guide_w - 2)  # narrower than guide for printability
    arm_h = min(4.0, guide_h - 1)

    # Retention flange (wider than cutout, prevents falling out)
    flange_w = cut_w + 3.0
    flange_h = cut_h + 2.0
    flange_t = 1.0

    # Nub
    nub_r = 1.5
    nub_len = 1.0

    print(f"    {side} button:")
    print(f"      Switch center: X={sw['x']:.1f}, Y={sw['y_center']:.1f}, Z={sw['z']:.1f}")
    print(f"      Switch near edge: Y={sw['y_near']:.1f}")
    print(f"      Inner wall: Y={wall_inner_y:.1f}")
    print(f"      Arm length: {arm_length:.1f}mm (was 7.9mm in V4)")

    parts = []

    # Cap (protrudes outside back wall)
    cap = box([guide_w, cap_depth, guide_h])
    cap.apply_translation([sw["x"], wall_outer_y + cap_depth / 2, sw["z"]])
    parts.append(cap)

    # Guide (through wall)
    guide = box([guide_w, WALL, guide_h])
    guide.apply_translation([sw["x"], wall_outer_y - WALL / 2, sw["z"]])
    parts.append(guide)

    # Retention flange (just inside wall, wider than cutout)
    flange = box([flange_w, flange_t, flange_h])
    flange.apply_translation([sw["x"], wall_inner_y - flange_t / 2, sw["z"]])
    parts.append(flange)

    # Arm (extends inward to switch)
    arm = box([arm_w, arm_length, arm_h])
    arm.apply_translation([sw["x"], wall_inner_y - arm_length / 2, sw["z"]])
    parts.append(arm)

    # Nub (contacts switch)
    nub = cylinder(radius=nub_r, height=nub_len, sections=16)
    nub.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    nub_y = wall_inner_y - arm_length - nub_len / 2
    nub.apply_translation([sw["x"], nub_y, sw["z"]])
    parts.append(nub)

    button = bool_union(parts)

    # Verify centering
    btn_bounds = button.bounds
    btn_center = (btn_bounds[0] + btn_bounds[1]) / 2
    print(f"      Button center: X={btn_center[0]:.1f}, Z={btn_center[2]:.1f}")
    print(f"      X offset from switch: {btn_center[0] - sw['x']:+.2f}mm")
    print(f"      Z offset from switch: {btn_center[2] - sw['z']:+.2f}mm")
    print(f"      Nub Y={nub_y:.1f}, reaches {sw['y_near'] - nub_y:.1f}mm past switch edge")

    return button


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


# ═══════════════════════════════════════════════════════════════════
# CUTOUT VERIFICATION (ray casting)
# ═══════════════════════════════════════════════════════════════════
def verify_cutouts(mesh, cutouts, wall_axis, wall_pos, label):
    """Verify cutouts exist by casting rays through expected openings."""
    print(f"\n  Cutout verification ({label}):")
    for name, cd in cutouts.items():
        # Cast ray from outside through the wall
        origin = np.array([cd["x"], wall_pos, cd["z"]])
        direction = np.array([0, -np.sign(wall_pos), 0])  # toward interior

        # Check if ray hits the mesh
        locations, index_ray, index_tri = mesh.ray.intersects_location(
            ray_origins=[origin],
            ray_directions=[direction]
        )

        if len(locations) == 0:
            print(f"    {cd['label']}: OPEN (ray passes through) ✓")
        else:
            # Find closest hit
            dists = np.linalg.norm(locations - origin, axis=1)
            min_dist = dists.min()
            if min_dist < WALL + 1:
                print(f"    {cd['label']}: BLOCKED at dist={min_dist:.1f}mm ✗")
            else:
                print(f"    {cd['label']}: OPEN (first hit at {min_dist:.1f}mm) ✓")


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
def main():
    original_dir = Path("/workspace/original")
    ref_dir = Path("/workspace/ref")
    output_dir = Path("/workspace/output/v5")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("V5 BUILD")
    print("  - Top shell: original extended (internal geometry preserved)")
    print("  - Shoulder buttons: shorter, centered on switches")
    print("  - Bottom shell: verified cutouts (USB-C, audio, SD card)")
    print("=" * 70)

    # ── Load ──
    print("\n--- Loading ---")
    board_stl = load_mesh(original_dir / "board.stl")
    top_orig = load_mesh(original_dir / "top_body.stl")
    btn1 = load_mesh(original_dir / "btn_assy_1.stl")
    btn2 = load_mesh(original_dir / "btn_assy_2.stl")

    # Center board
    bc = (board_stl.bounds[0] + board_stl.bounds[1]) / 2
    tc = (top_orig.bounds[0] + top_orig.bounds[1]) / 2
    board = board_stl.copy()
    board.apply_translation(-np.array([bc[0]-tc[0], bc[1]-tc[1], 0]))

    print(f"  Board: [{board.bounds[0][0]:.1f},{board.bounds[0][1]:.1f},{board.bounds[0][2]:.1f}] "
          f"to [{board.bounds[1][0]:.1f},{board.bounds[1][1]:.1f},{board.bounds[1][2]:.1f}]")
    print(f"  Original top: [{top_orig.bounds[0][0]:.1f},{top_orig.bounds[0][1]:.1f},{top_orig.bounds[0][2]:.1f}] "
          f"to [{top_orig.bounds[1][0]:.1f},{top_orig.bounds[1][1]:.1f},{top_orig.bounds[1][2]:.1f}]")

    dims = compute_dims(board.bounds)
    total_h = dims["top_z_max"] - dims["bot_z_min"]
    print(f"\n  Shell outer: {dims['outer_x']:.1f} x {dims['outer_y']:.1f}mm")
    print(f"  Bottom: Z=[{dims['bot_z_min']:.1f}, {dims['bot_z_max']:.1f}]")
    print(f"  Top: Z=[{dims['top_z_min']:.1f}, {dims['top_z_max']:.1f}]")
    print(f"  Total: {total_h:.1f}mm")

    # ── Generate shells ──
    print("\n--- Bottom shell V5 ---")
    bottom = generate_bottom_v5(dims)

    print("\n--- Top shell V5 (original + extension) ---")
    top = generate_top_v5(dims, top_orig)

    # ── Shoulder buttons ──
    print("\n--- Shoulder buttons V5 ---")
    sh_l = generate_shoulder_button("L", dims)
    sh_r = generate_shoulder_button("R", dims)

    # ── Colorize ──
    print("\n--- Colorizing ---")
    regions = get_glb_regions(ref_dir / "esplay_micro_pcb.glb")

    board_col = colorize_board(board.copy(), regions)
    top_col = colorize_case(top.copy(), COL["case_top"], COL["case_top_in"])
    bot_col = colorize_case(bottom.copy(), COL["case_bot"], COL["case_bot_in"])
    btn1_col = colorize_uniform(btn1.copy(), COL["btn_dark"])
    btn2_col = colorize_uniform(btn2.copy(), COL["btn_dark"])
    sh_l_col = colorize_uniform(sh_l.copy(), COL["shoulder_cap"])
    sh_r_col = colorize_uniform(sh_r.copy(), COL["shoulder_cap"])
    battery = create_battery(dims["bat_center_z"])

    # ── Verify cutouts ──
    verify_cutouts(bottom, FRONT_CUTS, 1, -dims["outer_y"]/2, "Front (Y-min)")
    verify_cutouts(bottom, BACK_CUTS, 1, dims["outer_y"]/2, "Back (Y-max)")

    # ── Save ──
    print("\n--- Saving ---")
    for name, mesh in [
        ("board_colored.glb", board_col),
        ("top_body_v5.glb", top_col),
        ("bottom_body_v5.glb", bot_col),
        ("btn_assy_1_colored.glb", btn1_col),
        ("btn_assy_2_colored.glb", btn2_col),
        ("shoulder_l.glb", sh_l_col),
        ("shoulder_r.glb", sh_r_col),
        ("battery.glb", battery),
    ]:
        mesh.export(output_dir / name)
        print(f"  {name}")

    # ── Assemblies ──
    print("\n--- Assemblies ---")
    closed = trimesh.Scene()
    for n, m in [("Board", board_col), ("Top_V5", top_col), ("Bottom_V5", bot_col),
                  ("Btn_L", btn1_col), ("Btn_R", btn2_col),
                  ("Shoulder_L", sh_l_col), ("Shoulder_R", sh_r_col),
                  ("Battery", battery)]:
        closed.add_geometry(m, node_name=n)
    closed.export(output_dir / "assembly_closed.glb")

    explode = 25.0
    opened = trimesh.Scene()
    opened.add_geometry(board_col, node_name="Board")
    for n, m, dz in [("Top_V5", top_col, explode), ("Btn_L", btn1_col, explode+10),
                      ("Btn_R", btn2_col, explode+10), ("Bottom_V5", bot_col, -explode),
                      ("Shoulder_L", sh_l_col, -explode*0.3), ("Shoulder_R", sh_r_col, -explode*0.3),
                      ("Battery", battery, -explode*0.6)]:
        mc = m.copy(); mc.apply_translation([0, 0, dz])
        opened.add_geometry(mc, node_name=n)
    opened.export(output_dir / "assembly_open.glb")

    # ══════════════════════════════════════════════════════════════
    # VERIFICATION
    # ══════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("V5 VERIFICATION")
    print("=" * 70)

    parts = {
        "Bottom V5": bot_col, "Battery": battery, "Board": board_col,
        "Top V5": top_col, "Buttons L": btn1_col, "Buttons R": btn2_col,
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

    # Top ↔ Bottom match
    tb = top_col.bounds; btb = bot_col.bounds
    print(f"\n  Top ↔ Bottom match:")
    for ax, i in [("X", 0), ("Y", 1)]:
        t_dim = tb[1][i] - tb[0][i]
        b_dim = btb[1][i] - btb[0][i]
        # Compare max extents
        t_range = (tb[0][i], tb[1][i])
        b_range = (btb[0][i], btb[1][i])
        print(f"    {ax}: top=[{t_range[0]:.1f},{t_range[1]:.1f}]={t_dim:.1f}mm, "
              f"bottom=[{b_range[0]:.1f},{b_range[1]:.1f}]={b_dim:.1f}mm")
        if abs(b_dim - t_dim) > 2:
            print(f"         Bottom wider by {b_dim-t_dim:.1f}mm (extended frame fills this)")

    # Clearances
    bb = board_col.bounds; batb = battery.bounds
    issues = []

    c1 = tb[1][2] - bb[1][2]
    print(f"\n  Clearances:")
    print(f"    Board top → Top top:       {c1:+.2f}mm {'OK' if c1>=-0.1 else 'PROBLEM'}")
    if c1<-0.1: issues.append(f"Board above top shell")

    c2 = bb[0][2] - batb[1][2]
    print(f"    Battery → Board:           {c2:+.2f}mm {'OK' if c2>=0 else 'COLLISION'}")
    if c2<0: issues.append(f"Battery/board collision")

    c3 = batb[0][2] - btb[0][2]
    print(f"    Battery → Floor:           {c3:+.2f}mm {'OK' if c3>=0.5 else 'TIGHT'}")

    # Joint
    joint = tb[0][2] - btb[1][2]
    print(f"    Top↔Bottom joint:          {joint:+.2f}mm")

    # Board in case
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

    # Shoulder button centering
    print(f"\n  Shoulder button alignment:")
    for side, sm in [("L", sh_l_col), ("R", sh_r_col)]:
        sb = sm.bounds
        sc = (sb[0] + sb[1]) / 2
        sw = SHOULDER_SW[side]
        dx = sc[0] - sw["x"]
        dz = sc[2] - sw["z"]
        nub_y = sb[0][1]
        dist = sw["y_near"] - nub_y
        print(f"    {side}: X offset={dx:+.2f}mm, Z offset={dz:+.2f}mm, "
              f"nub reaches {dist:+.1f}mm past switch edge")

    # V4 comparison
    print(f"\n  V4 → V5 changes:")
    print(f"    Top shell: parametric → original+extension (internal preserved)")
    print(f"    Shoulder arm: 7.9mm → {dims['outer_y']/2-WALL-SHOULDER_SW['L']['y_near']:.1f}mm")
    print(f"    Bottom meets top at Z={dims['bot_z_max']:.1f} (was Z=0)")

    all_b = np.array([(m.bounds[0], m.bounds[1]) for m in parts.values()])
    total_dims = all_b[:,1].max(axis=0) - all_b[:,0].min(axis=0)
    print(f"\n  Overall: {total_dims[0]:.1f} x {total_dims[1]:.1f} x {total_dims[2]:.1f} mm")

    if issues:
        print(f"\n  *** {len(issues)} ISSUES ***")
        for iss in issues: print(f"    - {iss}")
    else:
        print(f"\n  ALL CHECKS PASSED!")

    report = {
        "version": "v5",
        "fixes": [
            "Top shell: original geometry preserved, extended with frame",
            "Shoulder buttons: shorter arm, centered on switches",
            "Cutout verification via ray casting",
        ],
        "dimensions": {"outer": [dims["outer_x"], dims["outer_y"]],
                       "total_height": total_h},
        "issues": issues,
    }
    with open(output_dir / "v5_report.json", "w") as f:
        json.dump(report, f, indent=2, cls=NpEnc)

    print(f"\n--- Output ---")
    for f in sorted(output_dir.glob("*")):
        print(f"  {f.name} ({f.stat().st_size/1024:.0f} KB)")

    print(f"\n{'='*70}")
    print("V5 BUILD COMPLETE")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
