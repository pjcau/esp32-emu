"""
Mesh Analyzer Module
Analyzes STL files for wall thickness and geometric properties.
"""

import numpy as np
import trimesh
from typing import Tuple, List, Dict, Optional
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MeshAnalyzer:
    """Analyzes mesh geometry including wall thickness."""

    def __init__(self, mesh: trimesh.Trimesh):
        self.mesh = mesh
        self.mesh.fix_normals()

    @classmethod
    def from_file(cls, filepath: str) -> 'MeshAnalyzer':
        """Load mesh from STL file."""
        mesh = trimesh.load(filepath)
        if isinstance(mesh, trimesh.Scene):
            # If it's a scene, get the geometry
            mesh = trimesh.util.concatenate(
                [g for g in mesh.geometry.values()]
            )
        return cls(mesh)

    def get_bounding_box(self) -> Dict:
        """Get bounding box information."""
        bounds = self.mesh.bounds
        extents = self.mesh.extents
        center = self.mesh.centroid
        return {
            'min': bounds[0].tolist(),
            'max': bounds[1].tolist(),
            'extents': extents.tolist(),
            'center': center.tolist()
        }

    def calculate_wall_thickness(self, num_samples: int = 10000) -> Dict:
        """
        Calculate wall thickness using ray casting from surface points.

        For each sample point on the surface, cast rays in both directions
        (along and opposite to normal) and measure the distance to the
        nearest surface in each direction. Wall thickness is the minimum
        of these distances.

        Returns dictionary with thickness statistics.
        """
        # Sample points on the surface
        points, face_indices = trimesh.sample.sample_surface(
            self.mesh, num_samples
        )

        # Get normals at sample points
        normals = self.mesh.face_normals[face_indices]

        # We need to cast rays in BOTH directions to properly measure wall thickness
        # Use a larger offset to ensure we're outside the surface
        offset = 0.01  # 0.01mm offset

        thicknesses = []
        thin_points = []

        # Cast rays in negative normal direction (inward if normals point outward)
        ray_origins_neg = points - normals * offset
        ray_directions_neg = -normals

        locations_neg, index_ray_neg, _ = self.mesh.ray.intersects_location(
            ray_origins=ray_origins_neg,
            ray_directions=ray_directions_neg
        )

        # Cast rays in positive normal direction (outward if normals point outward)
        ray_origins_pos = points + normals * offset
        ray_directions_pos = normals

        locations_pos, index_ray_pos, _ = self.mesh.ray.intersects_location(
            ray_origins=ray_origins_pos,
            ray_directions=ray_directions_pos
        )

        # Process each sample point
        for i in range(len(points)):
            min_thickness = float('inf')

            # Check negative direction hits
            neg_hits = locations_neg[index_ray_neg == i]
            if len(neg_hits) > 0:
                distances = np.linalg.norm(neg_hits - points[i], axis=1)
                # Filter out very small distances (self-intersection)
                distances = distances[distances > offset]
                if len(distances) > 0:
                    min_thickness = min(min_thickness, np.min(distances))

            # Check positive direction hits
            pos_hits = locations_pos[index_ray_pos == i]
            if len(pos_hits) > 0:
                distances = np.linalg.norm(pos_hits - points[i], axis=1)
                # Filter out very small distances (self-intersection)
                distances = distances[distances > offset]
                if len(distances) > 0:
                    min_thickness = min(min_thickness, np.min(distances))

            # Only add valid thickness measurements
            if min_thickness < float('inf'):
                thicknesses.append(min_thickness)

                if min_thickness < 1.0:  # Less than 1mm
                    thin_points.append({
                        'point': points[i].tolist(),
                        'thickness': float(min_thickness),
                        'normal': normals[i].tolist()
                    })

        thicknesses = np.array(thicknesses)

        if len(thicknesses) == 0:
            # Fallback: use bounding box diagonal / 2 as estimate
            # This handles solid objects where rays don't find opposite surfaces
            diagonal = np.linalg.norm(self.mesh.extents)
            min_extent = np.min(self.mesh.extents)
            logger.warning(f"No wall thickness measured via ray casting. Using min extent: {min_extent:.3f}mm")
            return {
                'min_thickness': float(min_extent),
                'max_thickness': float(np.max(self.mesh.extents)),
                'mean_thickness': float(min_extent),
                'std_thickness': 0,
                'median_thickness': float(min_extent),
                'percentile_5': float(min_extent),
                'percentile_10': float(min_extent),
                'thin_areas_count': 0 if min_extent >= 1.0 else 1,
                'thin_areas': [],
                'num_samples': num_samples,
                'valid_samples': 0,
                'below_1mm_percentage': 0 if min_extent >= 1.0 else 100,
                'measurement_method': 'extent_fallback'
            }

        return {
            'min_thickness': float(np.min(thicknesses)),
            'max_thickness': float(np.max(thicknesses)),
            'mean_thickness': float(np.mean(thicknesses)),
            'std_thickness': float(np.std(thicknesses)),
            'median_thickness': float(np.median(thicknesses)),
            'percentile_5': float(np.percentile(thicknesses, 5)),
            'percentile_10': float(np.percentile(thicknesses, 10)),
            'thin_areas_count': len(thin_points),
            'thin_areas': thin_points[:100],  # Limit to first 100 for readability
            'num_samples': num_samples,
            'valid_samples': len(thicknesses),
            'below_1mm_percentage': float(np.sum(thicknesses < 1.0) / len(thicknesses) * 100),
            'measurement_method': 'ray_casting'
        }

    def check_mesh_quality(self) -> Dict:
        """Check mesh quality metrics."""
        return {
            'is_watertight': self.mesh.is_watertight,
            'is_winding_consistent': self.mesh.is_winding_consistent,
            'euler_number': self.mesh.euler_number,
            'num_vertices': len(self.mesh.vertices),
            'num_faces': len(self.mesh.faces),
            'volume': float(self.mesh.volume) if self.mesh.is_watertight else None,
            'surface_area': float(self.mesh.area),
            'has_degenerate_faces': bool(self.mesh.degenerate_faces.any()) if hasattr(self.mesh, 'degenerate_faces') else False
        }

    def get_analysis_report(self, num_thickness_samples: int = 10000) -> Dict:
        """Generate complete analysis report."""
        logger.info("Analyzing mesh geometry...")

        bbox = self.get_bounding_box()
        logger.info(f"Bounding box: {bbox['extents']} mm")

        quality = self.check_mesh_quality()
        logger.info(f"Mesh quality: watertight={quality['is_watertight']}, vertices={quality['num_vertices']}")

        logger.info(f"Calculating wall thickness ({num_thickness_samples} samples)...")
        thickness = self.calculate_wall_thickness(num_thickness_samples)
        logger.info(f"Wall thickness: min={thickness['min_thickness']:.3f}mm, mean={thickness['mean_thickness']:.3f}mm")

        return {
            'bounding_box': bbox,
            'quality': quality,
            'wall_thickness': thickness
        }


def analyze_stl_file(filepath: str, num_samples: int = 10000) -> Dict:
    """Analyze a single STL file and return report."""
    logger.info(f"Loading: {filepath}")
    analyzer = MeshAnalyzer.from_file(filepath)
    report = analyzer.get_analysis_report(num_samples)
    report['filepath'] = filepath
    report['filename'] = Path(filepath).name
    return report
