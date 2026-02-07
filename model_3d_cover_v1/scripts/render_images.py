#!/usr/bin/env python3
"""
Render assembly GLB files to high-quality PNG images.
Uses pyrender with EGL offscreen rendering when available,
falls back to a high-quality matplotlib renderer with proper
face sorting and simulated lighting.
"""
import os
import sys
import numpy as np
import trimesh
from pathlib import Path
from PIL import Image
import io


def look_at(eye, target, up=np.array([0, 0, 1.0])):
    """Build a 4x4 camera-to-world matrix (OpenGL convention: -Z forward)."""
    fwd = np.array(target - eye, dtype=float)
    fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, up)
    if np.linalg.norm(right) < 1e-6:
        up = np.array([0, 1, 0.0])
        right = np.cross(fwd, up)
    right /= np.linalg.norm(right)
    true_up = np.cross(right, fwd)
    mat = np.eye(4)
    mat[:3, 0] = right
    mat[:3, 1] = true_up
    mat[:3, 2] = -fwd
    mat[:3, 3] = eye
    return mat


def try_pyrender_render(scene_tm, output_path, resolution, elevation_deg,
                        azimuth_deg, dist_factor, bg_color):
    """Try rendering with pyrender + EGL. Returns True on success."""
    try:
        os.environ['PYOPENGL_PLATFORM'] = 'egl'
        import pyrender
    except Exception:
        return False

    bounds = scene_tm.bounds
    center = (bounds[0] + bounds[1]) / 2
    extent = np.linalg.norm(bounds[1] - bounds[0])

    pr_scene = pyrender.Scene(
        bg_color=bg_color,
        ambient_light=[0.25, 0.25, 0.25],
    )

    for name, geom in scene_tm.geometry.items():
        if not isinstance(geom, trimesh.Trimesh):
            continue
        try:
            tf_tuple = scene_tm.graph.get(name)
            node_tf = tf_tuple[0] if tf_tuple is not None else np.eye(4)
        except Exception:
            node_tf = np.eye(4)
        try:
            pr_mesh = pyrender.Mesh.from_trimesh(geom, smooth=True)
        except Exception:
            pr_mesh = pyrender.Mesh.from_trimesh(geom, smooth=False)
        pr_scene.add(pr_mesh, pose=node_tf)

    elev = np.radians(elevation_deg)
    azim = np.radians(azimuth_deg)
    dist = extent * dist_factor

    eye = center + dist * np.array([
        np.cos(elev) * np.sin(azim),
        -np.cos(elev) * np.cos(azim),
        np.sin(elev),
    ])

    cam_tf = look_at(eye, center)
    aspect = resolution[0] / resolution[1]
    camera = pyrender.PerspectiveCamera(yfov=np.radians(35), aspectRatio=aspect)
    pr_scene.add(camera, pose=cam_tf)

    # 3-point lighting
    for angle_off, intensity in [(0.5, 4.0), (-1.2, 2.0), (3.14, 1.5)]:
        ld = center + dist * 1.2 * np.array([
            np.cos(elev + 0.3) * np.sin(azim + angle_off),
            -np.cos(elev + 0.3) * np.cos(azim + angle_off),
            np.sin(elev + 0.3),
        ])
        lt = look_at(ld, center)
        pr_scene.add(pyrender.DirectionalLight(color=[1, 1, 1], intensity=intensity),
                      pose=lt)

    try:
        # Render at 2x resolution for antialiasing, then downsample
        ss_factor = 2
        ss_res = (resolution[0] * ss_factor, resolution[1] * ss_factor)
        renderer = pyrender.OffscreenRenderer(*ss_res)
        color, _ = renderer.render(pr_scene,
                                    flags=pyrender.RenderFlags.SHADOWS_DIRECTIONAL)
        renderer.delete()
        img = Image.fromarray(color)
        # Downsample with high-quality Lanczos filter (antialiasing)
        img = img.resize(resolution, Image.LANCZOS)
        img.save(str(output_path), format='PNG', optimize=True)
        return True
    except Exception as e:
        print(f"      pyrender render failed: {e}")
        return False


def render_matplotlib_hq(scene_tm, output_path, resolution, elevation_deg,
                         azimuth_deg, dist_factor, bg_color_rgb):
    """
    High-quality matplotlib renderer with:
    - ALL faces rendered (no subsampling)
    - Painter's algorithm (z-sorting)
    - Phong-like diffuse lighting simulation
    - Edge hints for light-colored surfaces
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    bg = tuple(c / 255.0 for c in bg_color_rgb[:3])
    dpi = 150
    fig = plt.figure(figsize=(resolution[0] / dpi, resolution[1] / dpi), dpi=dpi)
    ax = fig.add_subplot(111, projection='3d')

    bounds = scene_tm.bounds
    center = (bounds[0] + bounds[1]) / 2
    extent = np.linalg.norm(bounds[1] - bounds[0])

    # Light direction (from camera-ish position)
    elev = np.radians(elevation_deg)
    azim = np.radians(azimuth_deg)
    light_dir = np.array([
        np.cos(elev + 0.2) * np.sin(azim + 0.3),
        -np.cos(elev + 0.2) * np.cos(azim + 0.3),
        np.sin(elev + 0.2),
    ])
    light_dir /= np.linalg.norm(light_dir)

    all_polys = []
    all_colors = []
    all_edge_colors = []
    all_z_order = []

    for name, geom in scene_tm.geometry.items():
        if not isinstance(geom, trimesh.Trimesh):
            continue

        try:
            tf_tuple = scene_tm.graph.get(name)
            tf = tf_tuple[0] if tf_tuple is not None else np.eye(4)
        except Exception:
            tf = np.eye(4)

        verts = geom.vertices.copy()
        if not np.allclose(tf, np.eye(4)):
            verts = trimesh.transformations.transform_points(verts, tf)

        faces = geom.faces

        # Get base colors
        if hasattr(geom.visual, 'face_colors') and len(geom.visual.face_colors) == len(faces):
            base_colors = geom.visual.face_colors[:, :3] / 255.0
        elif hasattr(geom.visual, 'main_color'):
            c = geom.visual.main_color[:3] / 255.0
            base_colors = np.tile(c, (len(faces), 1))
        else:
            base_colors = np.tile([0.7, 0.7, 0.7], (len(faces), 1))

        # Compute face normals for lighting
        v0 = verts[faces[:, 0]]
        v1 = verts[faces[:, 1]]
        v2 = verts[faces[:, 2]]
        normals = np.cross(v1 - v0, v2 - v0)
        norms = np.linalg.norm(normals, axis=1, keepdims=True)
        norms[norms < 1e-10] = 1
        normals = normals / norms

        # Phong-like diffuse lighting
        diffuse = np.abs(np.dot(normals, light_dir))
        # Ambient + diffuse
        shade = 0.35 + 0.65 * diffuse
        shaded_colors = base_colors * shade[:, np.newaxis]
        shaded_colors = np.clip(shaded_colors, 0, 1)

        polys = verts[faces]
        face_centers = polys.mean(axis=1)

        # Edge color: slightly darker for depth cues
        brightness = base_colors.mean(axis=1)
        edge_colors = np.where(
            brightness[:, np.newaxis] > 0.85,
            np.clip(base_colors * 0.7, 0, 1),  # darker edges for light surfaces
            np.full_like(base_colors, 0.0)  # no visible edges for dark surfaces (set to 'none' below)
        )

        for i in range(len(faces)):
            all_polys.append(polys[i])
            all_colors.append(shaded_colors[i])
            all_z_order.append(face_centers[i, 2])
            if brightness[i] > 0.85:
                all_edge_colors.append((*edge_colors[i], 0.15))
            else:
                all_edge_colors.append((0, 0, 0, 0))

    # Sort by Z (painter's algorithm) - draw farthest first
    if not all_polys:
        print("      No geometry to render!")
        return

    order = np.argsort(all_z_order)
    all_polys = [all_polys[i] for i in order]
    all_colors = [all_colors[i] for i in order]
    all_edge_colors = [all_edge_colors[i] for i in order]

    # Batch draw in chunks for performance
    chunk_size = 5000
    for start in range(0, len(all_polys), chunk_size):
        end = min(start + chunk_size, len(all_polys))
        poly3d = Poly3DCollection(all_polys[start:end], alpha=1.0)
        poly3d.set_facecolor(all_colors[start:end])
        poly3d.set_edgecolor(all_edge_colors[start:end])
        poly3d.set_linewidth(0.1)
        ax.add_collection3d(poly3d)

    ax.view_init(elev=elevation_deg, azim=azimuth_deg)

    margin = extent * 0.05
    half = extent / 2
    ax.set_xlim(center[0] - half - margin, center[0] + half + margin)
    ax.set_ylim(center[1] - half - margin, center[1] + half + margin)
    ax.set_zlim(center[2] - half - margin, center[2] + half + margin)

    ax.set_box_aspect([1, 1, 1])
    ax.axis('off')
    ax.set_facecolor(bg)
    fig.patch.set_facecolor(bg)

    plt.tight_layout(pad=0)
    plt.savefig(str(output_path), dpi=dpi, bbox_inches='tight',
                facecolor=fig.get_facecolor(), pad_inches=0.05)
    plt.close(fig)


def render_glb(glb_path, output_path, resolution=(1920, 1080),
               elevation_deg=30, azimuth_deg=30, dist_factor=2.2,
               bg_color=None):
    """Render a GLB file to PNG."""
    if bg_color is None:
        bg_color = [235, 235, 235, 255]

    scene_tm = trimesh.load(str(glb_path))
    if not isinstance(scene_tm, trimesh.Scene):
        s = trimesh.Scene()
        s.add_geometry(scene_tm)
        scene_tm = s

    bg_float = [c / 255.0 for c in bg_color]

    # Try pyrender first
    ok = try_pyrender_render(scene_tm, output_path, resolution,
                             elevation_deg, azimuth_deg, dist_factor, bg_float)
    if ok:
        print(f"      rendered with pyrender/EGL")
        return

    # Fallback: high-quality matplotlib
    render_matplotlib_hq(scene_tm, output_path, resolution,
                         elevation_deg, azimuth_deg, dist_factor, bg_color)
    print(f"      rendered with matplotlib (HQ)")


def main():
    output_dir = Path("/workspace/output/v7")
    img_dir = output_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("RENDERING V7 ASSEMBLY IMAGES")
    print("=" * 60)

    all_rendered = []

    # ── Closed assembly ──
    closed_path = output_dir / "assembly_closed.glb"
    if closed_path.exists():
        print("\n--- Closed Assembly ---")
        views = {
            "front_iso": {"elev": 30, "azim": 35, "dist": 2.0},
            "top":       {"elev": 80, "azim": 5,  "dist": 2.2},
        }
        for vname, cfg in views.items():
            out = img_dir / f"assembly_closed_{vname}.png"
            print(f"  {out.name}...")
            render_glb(closed_path, out, resolution=(2560, 1440),
                       elevation_deg=cfg["elev"],
                       azimuth_deg=cfg["azim"],
                       dist_factor=cfg["dist"])
            all_rendered.append(out)
            print(f"    OK ({out.stat().st_size/1024:.0f} KB)")

    # ── Open/exploded assembly ──
    open_path = output_dir / "assembly_open.glb"
    if open_path.exists():
        print("\n--- Open/Exploded Assembly ---")
        views = {
            "front_iso": {"elev": 25, "azim": 30, "dist": 2.2},
            "front":     {"elev": 12, "azim": 0,  "dist": 2.5},
        }
        for vname, cfg in views.items():
            out = img_dir / f"assembly_open_{vname}.png"
            print(f"  {out.name}...")
            render_glb(open_path, out, resolution=(2560, 1440),
                       elevation_deg=cfg["elev"],
                       azimuth_deg=cfg["azim"],
                       dist_factor=cfg["dist"])
            all_rendered.append(out)
            print(f"    OK ({out.stat().st_size/1024:.0f} KB)")

    # ── Top body detail ──
    top_path = output_dir / "top_body_v7.glb"
    if top_path.exists():
        print("\n--- Top Body Detail ---")
        out = img_dir / "top_body_v7_detail.png"
        print(f"  {out.name}...")
        render_glb(top_path, out, resolution=(2560, 1920),
                   elevation_deg=55, azimuth_deg=25, dist_factor=2.0)
        all_rendered.append(out)
        print(f"    OK ({out.stat().st_size/1024:.0f} KB)")

    # ── Summary ──
    print(f"\n{'='*60}")
    print(f"RENDERING COMPLETE - {len(all_rendered)} images")
    for f in all_rendered:
        print(f"  {f.name} ({f.stat().st_size/1024:.0f} KB)")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
