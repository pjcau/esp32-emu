FROM python:3.11-slim-bookworm

# Install system dependencies for mesh processing and headless rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libopengl0 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libegl1 \
    libgles2 \
    libharfbuzz0b \
    libfontconfig1 \
    libxcb1 \
    libx11-6 \
    libocct-data-exchange-7.6 \
    libocct-foundation-7.6 \
    libocct-modeling-data-7.6 \
    xvfb \
    xauth \
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages for 3D mesh processing and rendering
RUN pip install --no-cache-dir \
    numpy \
    scipy \
    scikit-image \
    trimesh[easy] \
    numpy-stl \
    pymeshlab \
    networkx \
    shapely \
    Pillow \
    pyglet

# Create working directories
WORKDIR /app
RUN mkdir -p /app/input /app/output /app/logs /app/scripts

# Copy scripts
COPY scripts/ /app/scripts/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYOPENGL_PLATFORM=osmesa
ENV DISPLAY=:99

# Default command
CMD ["python", "/app/scripts/main.py"]
