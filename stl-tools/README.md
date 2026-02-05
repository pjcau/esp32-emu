# STL Processing Tools

Tools for analyzing and fixing STL files for 3D printing, ensuring minimum wall thickness requirements are met while preserving part alignment for assembly.

## Requirements

- Docker
- Docker Compose

## Quick Start

```bash
cd stl-tools

# Run complete pipeline (recommended)
./run.sh pipeline

# Or run everything including renders and animations
./run.sh all
```

## Features

1. **Wall Thickness Analysis**: Checks all STL files for wall thickness < 1mm
2. **Automatic Fix**: Thickens thin walls while preserving part centers
3. **Assembly Verification**: Ensures parts still fit together after fixes
4. **Render Comparison**: Before/after visual comparisons
5. **Assembly Simulation**: Animated assembly/disassembly views
6. **Hardware Verification**: Checks alignment with PCB, screw holes, etc.

## Commands

| Command | Description |
|---------|-------------|
| `./run.sh analyze` | Analyze STL files only |
| `./run.sh fix` | Fix wall thickness issues |
| `./run.sh verify` | Verify parts fit together |
| `./run.sh render` | Generate render comparisons |
| `./run.sh simulate` | Generate assembly animations |
| `./run.sh hardware` | Verify hardware alignment |
| `./run.sh pipeline` | Run complete pipeline |
| `./run.sh all` | Run everything |
| `./run.sh clean` | Remove output files |
| `./run.sh shell` | Open container shell |

## Output Files

After running the pipeline, check these output files:

```
output/
├── analysis_report.json       # Initial thickness analysis
├── analysis_summary.txt       # Human-readable analysis summary
├── fixed/                     # Fixed STL files
│   ├── frame.stl
│   ├── top_cover.stl
│   └── ...
├── fix_report.json            # Fix operation results
├── verification_report.json   # Assembly fit verification
├── pipeline_report.html       # Complete HTML report
├── renders/                   # Render images
│   ├── render_report.html
│   └── *.png
├── simulation/                # Animation files
│   ├── simulation_viewer.html
│   ├── assembly.gif
│   ├── disassembly.gif
│   └── rotation_*.gif
└── hardware_verification_report.json
```

## Configuration

Environment variables in `docker-compose.yml`:

| Variable | Default | Description |
|----------|---------|-------------|
| `MIN_WALL_THICKNESS` | `1.0` | Minimum wall thickness in mm |
| `PRESERVE_CENTERS` | `true` | Keep part centers invariant during fix |
| `FIX_METHOD` | `auto` | Fix method: auto, vertex, shell, pymeshlab |
| `NUM_SAMPLES` | `15000` | Samples for thickness analysis |

## How It Works

### Wall Thickness Analysis
Uses ray casting from surface points inward to measure the distance to the opposite surface. This gives an accurate measurement of wall thickness at thousands of sample points.

### Thickness Fix Algorithm
1. Identifies thin regions (< 1mm)
2. Calculates required offset for each vertex
3. Displaces vertices outward along normals
4. Translates mesh to preserve original centroid
5. Verifies fix meets requirements

### Center Preservation
After any mesh modification, the centroid is calculated and the mesh is translated to match the original centroid position. This ensures parts remain properly aligned in the assembly.

### Assembly Verification
Uses collision detection between all part pairs to ensure no unwanted intersections occur after thickness fixes.

## Input Files

The pipeline expects STL files in:
```
model3d/ESPlay micro v2 case - 5592683/files/
```

Expected files:
- `frame.stl` - Main case frame
- `top_cover.stl` - Front cover
- `back_cover.stl` - Back cover
- `d_Pad.stl` - D-pad
- `A_B.stl` - A/B buttons
- `L_R.stl` - Shoulder buttons
- `start_select.stl` - Start/Select buttons
- `menu.stl` - Menu button
- `power.stl` - Power button

## Troubleshooting

### Rendering fails
The container uses OSMesa for headless rendering. If renders are blank, check:
```bash
./run.sh shell
python -c "import trimesh; print(trimesh.viewer)"
```

### Fix doesn't meet thickness requirement
Try different fix methods:
```bash
# Edit docker-compose.yml
environment:
  - FIX_METHOD=shell  # or 'vertex' or 'pymeshlab'
```

### Parts don't fit after fix
If assembly verification fails, the fix may have been too aggressive. Reduce the offset or use a different method.
