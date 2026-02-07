#!/usr/bin/env python3
"""
Render assembly GLB files to PNG images for README documentation.
Uses trimesh's offscreen rendering with pyrender/pyglet.
Falls back to orthographic projection screenshots if GPU not available.
"""
import numpy as np
import trimesh
from pathlib import Path
import json


def render_scene_to_png(glb_path, output_path, resolution=(1920, 1080),
                        camera_angles=None, bg_color=(240, 240, 240, 255)):
    """
    Render a GLB scene to PNG from multiple angles.
    Uses trimesh's built-in scene rendering.
    """
    print(f"  Loading {glb_path.name}...")
    scene = trimesh.load(str(glb_path))

    if not isinstance(scene, trimesh.Scene):
        s = trimesh.Scene()
        s.add_geometry(scene)
        scene = s

    # Get scene bounds for camera positioning
    bounds = scene.bounds
    center = (bounds[0] + bounds[1]) / 2
    extent = (bounds[1] - bounds[0]).max()

    if camera_angles is None:
        camera_angles = {
            "top_front": {"angles": (np.radians(35), 0, np.radians(25)),
                          "label": "Vista frontale"},
            "top": {"angles": (np.radians(5), 0, 0),
                    "label": "Vista dall'alto"},
            "side": {"angles": (np.radians(30), 0, np.radians(90)),
                     "label": "Vista laterale"},
        }

    rendered = []
    for view_name, view_cfg in camera_angles.items():
        out_file = output_path / f"{glb_path.stem}_{view_name}.png"

        try:
            # Try pyrender-based rendering
            png_data = render_with_pyrender(scene, resolution, view_cfg["angles"],
                                           center, extent, bg_color)
            if png_data is not None:
                with open(out_file, 'wb') as f:
                    f.write(png_data)
                print(f"    {out_file.name} (pyrender)")
                rendered.append(out_file)
                continue
        except Exception as e:
            print(f"    pyrender failed: {e}")

        try:
            # Fallback: trimesh scene.save_image
            png_data = scene.save_image(resolution=resolution, visible=False)
            if png_data is not None and len(png_data) > 0:
                with open(out_file, 'wb') as f:
                    f.write(png_data)
                print(f"    {out_file.name} (trimesh)")
                rendered.append(out_file)
                continue
        except Exception as e:
            print(f"    trimesh save_image failed: {e}")

        try:
            # Final fallback: matplotlib 2D projection
            render_matplotlib(scene, out_file, view_cfg["angles"],
                              center, extent, resolution)
            print(f"    {out_file.name} (matplotlib)")
            rendered.append(out_file)
        except Exception as e:
            print(f"    matplotlib failed: {e}")

    return rendered


def render_with_pyrender(scene, resolution, angles, center, extent, bg_color):
    """Try rendering with pyrender (needs OpenGL)."""
    try:
        import pyrender
        import os
        os.environ['PYOPENGL_PLATFORM'] = 'egl'
    except ImportError:
        return None

    pr_scene = pyrender.Scene(bg_color=np.array(bg_color[:3]) / 255.0,
                              ambient_light=[0.3, 0.3, 0.3])

    for name, geom in scene.geometry.items():
        if isinstance(geom, trimesh.Trimesh):
            mesh = pyrender.Mesh.from_trimesh(geom, smooth=True)
            node_tf = scene.graph.get(name)[0] if name in scene.graph else np.eye(4)
            pr_scene.add(mesh, pose=node_tf)

    camera = pyrender.PerspectiveCamera(yfov=np.radians(45))
    dist = extent * 2.0
    cam_pos = center + np.array([
        dist * np.sin(angles[2]) * np.cos(angles[0]),
        dist * np.cos(angles[2]) * np.cos(angles[0]),
        dist * np.sin(angles[0])
    ])
    cam_tf = np.eye(4)
    cam_tf[:3, 3] = cam_pos
    look_dir = center - cam_pos
    look_dir /= np.linalg.norm(look_dir)
    up = np.array([0, 0, 1])
    right = np.cross(look_dir, up)
    right /= np.linalg.norm(right)
    up = np.cross(right, look_dir)
    cam_tf[:3, 0] = right
    cam_tf[:3, 1] = up
    cam_tf[:3, 2] = -look_dir
    pr_scene.add(camera, pose=cam_tf)

    light = pyrender.DirectionalLight(color=[1, 1, 1], intensity=3.0)
    pr_scene.add(light, pose=cam_tf)

    renderer = pyrender.OffscreenRenderer(*resolution)
    color, _ = renderer.render(pr_scene)
    renderer.delete()

    from PIL import Image
    import io
    img = Image.fromarray(color)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def render_matplotlib(scene, output_path, angles, center, extent, resolution):
    """Render using matplotlib 3D projection (always works, no GPU needed)."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    fig = plt.figure(figsize=(resolution[0]/100, resolution[1]/100), dpi=100)
    ax = fig.add_subplot(111, projection='3d')

    # Collect all geometry
    for name, geom in scene.geometry.items():
        if not isinstance(geom, trimesh.Trimesh):
            continue

        # Get transform
        try:
            tf = scene.graph.get(name)
            if tf is not None:
                tf = tf[0]
            else:
                tf = np.eye(4)
        except:
            tf = np.eye(4)

        verts = geom.vertices.copy()
        if not np.allclose(tf, np.eye(4)):
            verts = trimesh.transformations.transform_points(verts, tf)

        faces = geom.faces

        # Get face colors
        if hasattr(geom.visual, 'face_colors') and len(geom.visual.face_colors) == len(faces):
            fc = geom.visual.face_colors[:, :3] / 255.0
        elif hasattr(geom.visual, 'main_color'):
            c = geom.visual.main_color[:3] / 255.0
            fc = np.tile(c, (len(faces), 1))
        else:
            fc = np.tile([0.7, 0.7, 0.7], (len(faces), 1))

        # Subsample faces for performance (max 2000 per geometry)
        if len(faces) > 2000:
            idx = np.random.choice(len(faces), 2000, replace=False)
            faces = faces[idx]
            fc = fc[idx]

        polys = verts[faces]
        poly3d = Poly3DCollection(polys, alpha=0.95)
        poly3d.set_facecolor(fc)
        poly3d.set_edgecolor('none')
        ax.add_collection3d(poly3d)

    # Set view
    elev = np.degrees(angles[0])
    azim = np.degrees(angles[2])
    ax.view_init(elev=elev, azim=azim)

    margin = extent * 0.1
    ax.set_xlim(center[0] - extent/2 - margin, center[0] + extent/2 + margin)
    ax.set_ylim(center[1] - extent/2 - margin, center[1] + extent/2 + margin)
    ax.set_zlim(center[2] - extent/2 - margin, center[2] + extent/2 + margin)

    ax.set_box_aspect([1, 1, 1])
    ax.axis('off')
    ax.set_facecolor((0.94, 0.94, 0.94))
    fig.patch.set_facecolor((0.94, 0.94, 0.94))

    plt.tight_layout(pad=0)
    plt.savefig(str(output_path), dpi=100, bbox_inches='tight',
                facecolor=fig.get_facecolor(), pad_inches=0.1)
    plt.close(fig)


def main():
    output_dir = Path("/workspace/output/v7")
    img_dir = output_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("RENDERING V7 ASSEMBLY IMAGES")
    print("=" * 60)

    views = {
        "front_iso": {"angles": (np.radians(30), 0, np.radians(30)),
                      "label": "Front isometric"},
        "top": {"angles": (np.radians(85), 0, np.radians(0)),
                "label": "Top view"},
        "front": {"angles": (np.radians(15), 0, np.radians(0)),
                  "label": "Front view"},
    }

    all_rendered = []

    # Closed assembly
    print("\n--- Closed Assembly ---")
    closed_path = output_dir / "assembly_closed.glb"
    if closed_path.exists():
        rendered = render_scene_to_png(closed_path, img_dir,
                                       resolution=(1600, 900),
                                       camera_angles=views)
        all_rendered.extend(rendered)

    # Open/exploded assembly
    print("\n--- Open/Exploded Assembly ---")
    open_path = output_dir / "assembly_open.glb"
    if open_path.exists():
        rendered = render_scene_to_png(open_path, img_dir,
                                       resolution=(1600, 900),
                                       camera_angles=views)
        all_rendered.extend(rendered)

    # Top body solo
    print("\n--- Top Body Detail ---")
    top_path = output_dir / "top_body_v7.glb"
    if top_path.exists():
        rendered = render_scene_to_png(top_path, img_dir,
                                       resolution=(1200, 900),
                                       camera_angles={
                                           "detail": {"angles": (np.radians(60), 0, np.radians(20)),
                                                      "label": "Top body detail"},
                                       })
        all_rendered.extend(rendered)

    print(f"\n--- Summary ---")
    print(f"  Total images: {len(all_rendered)}")
    for f in all_rendered:
        sz = f.stat().st_size / 1024
        print(f"  {f.name} ({sz:.0f} KB)")

    print(f"\n{'='*60}")
    print("RENDERING COMPLETE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
