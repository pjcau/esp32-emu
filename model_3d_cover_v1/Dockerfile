FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libosmesa6-dev libgl1-mesa-dri libglib2.0-0 libglx-mesa0 libgl1 \
    libglu1-mesa libglu1-mesa-dev libegl1-mesa-dev xvfb xauth && \
    rm -rf /var/lib/apt/lists/*
ENV PYOPENGL_PLATFORM=osmesa
RUN pip install --no-cache-dir "numpy<2" trimesh scipy networkx matplotlib jinja2 pillow rtree manifold3d PyOpenGL "pyglet<2" pyrender
