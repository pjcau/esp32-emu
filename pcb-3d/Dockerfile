# Dockerfile for PCB 3D Model Generation
# Includes KiCad, FreeCAD, and Python tools

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Rome

# Install system dependencies
RUN apt-get update && apt-get install -y \
    software-properties-common \
    wget \
    curl \
    git \
    python3 \
    python3-pip \
    python3-venv \
    xvfb \
    libgl1-mesa-glx \
    libglu1-mesa \
    && rm -rf /var/lib/apt/lists/*

# Add KiCad PPA and install KiCad
RUN add-apt-repository --yes ppa:kicad/kicad-7.0-releases && \
    apt-get update && \
    apt-get install -y kicad kicad-libraries && \
    rm -rf /var/lib/apt/lists/*

# Install FreeCAD
RUN add-apt-repository --yes ppa:freecad-maintainers/freecad-stable && \
    apt-get update && \
    apt-get install -y freecad && \
    rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip3 install --no-cache-dir \
    numpy \
    trimesh \
    scipy \
    pillow \
    matplotlib \
    cadquery-ocp \
    OCP \
    build123d \
    pyvista \
    meshio

# Create working directory
WORKDIR /workspace

# Copy scripts
COPY scripts/ /workspace/scripts/

# Set display for headless rendering
ENV DISPLAY=:99

# Entry point
ENTRYPOINT ["python3"]
CMD ["/workspace/scripts/generate_3d_model.py"]
