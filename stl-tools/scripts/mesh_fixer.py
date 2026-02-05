"""
Mesh Fixer Module
Fixes STL files to ensure minimum wall thickness while preserving centers.
Uses voxelization and morphological operations for accurate wall thickening.
"""

import numpy as np
import trimesh
from typing import Dict, Tuple
import logging
from scipy import ndimage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MeshFixer:
    """Fixes mesh wall thickness while preserving geometric centers."""

    def __init__(self, mesh: trimesh.Trimesh):
        self.original_mesh = mesh.copy()
        self.mesh = mesh
        self.mesh.fix_normals()
        self.original_centroid = mesh.centroid.copy()
        self.original_bounds = mesh.bounds.copy()

    @classmethod
    def from_file(cls, filepath: str) -> 'MeshFixer':
        """Load mesh from STL file."""
        mesh = trimesh.load(filepath)
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate(
                list(mesh.geometry.values())
            )
        return cls(mesh)

    def measure_thickness_at_points(self, num_samples: int = 5000) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Measure wall thickness at sample points using bidirectional ray casting.
        Returns: (points, thicknesses, normals)
        """
        points, face_indices = trimesh.sample.sample_surface(self.mesh, num_samples)
        normals = self.mesh.face_normals[face_indices]

        offset = 0.01
        thicknesses = np.full(len(points), np.inf)

        # Cast rays in both directions
        for direction in [-1, 1]:
            ray_origins = points + normals * offset * direction
            ray_directions = normals * (-direction)

            locations, index_ray, _ = self.mesh.ray.intersects_location(
                ray_origins=ray_origins,
                ray_directions=ray_directions
            )

            for i in range(len(points)):
                hits = locations[index_ray == i]
                if len(hits) > 0:
                    distances = np.linalg.norm(hits - points[i], axis=1)
                    distances = distances[distances > offset]
                    if len(distances) > 0:
                        thicknesses[i] = min(thicknesses[i], np.min(distances))

        # Replace inf with a large value for solid objects
        thicknesses[thicknesses == np.inf] = np.max(self.mesh.extents)

        return points, thicknesses, normals

    def fix_thickness_voxel_dilation(self, min_thickness: float = 1.0,
                                      max_thickness: float = 1.25,
                                      preserve_center: bool = True) -> trimesh.Trimesh:
        """
        Fix wall thickness using voxelization and controlled morphological dilation.

        Uses iterative single-voxel dilation with thickness checking after each step
        to achieve precise control over final wall thickness.
        """
        logger.info(f"Starting controlled voxel dilation (target: {min_thickness}-{max_thickness}mm)")

        original_centroid = self.mesh.centroid.copy()
        original_bounds = self.mesh.bounds.copy()

        # Measure current minimum thickness
        _, thicknesses, _ = self.measure_thickness_at_points(3000)
        current_p5 = np.percentile(thicknesses, 5)
        logger.info(f"Current 5th percentile thickness: {current_p5:.3f}mm")

        if current_p5 >= min_thickness:
            logger.info("Mesh already meets minimum thickness requirement")
            return self.mesh

        # Use fixed voxel size for predictable behavior
        voxel_size = 0.15  # 0.15mm voxels for good balance of speed and precision
        logger.info(f"Voxel size: {voxel_size:.3f}mm")

        # Voxelize the mesh
        try:
            voxels = self.mesh.voxelized(pitch=voxel_size)
            voxel_matrix = voxels.matrix.copy()
            voxel_transform = voxels.transform.copy()
            logger.info(f"Voxel grid shape: {voxel_matrix.shape}")
        except Exception as e:
            logger.error(f"Voxelization failed: {e}")
            return self._fallback_scale_fix(min_thickness, max_thickness, preserve_center)

        # Use 6-connectivity (axis-aligned only) for more predictable expansion
        # Each iteration adds exactly voxel_size to the surface in cardinal directions
        struct = ndimage.generate_binary_structure(3, 1)  # 6-connectivity

        # Calculate maximum iterations allowed based on max_thickness constraint
        # Each iteration adds ~2*voxel_size to wall thickness (both sides)
        thickness_increase_per_iter = voxel_size * 2
        max_additional_thickness = max_thickness - current_p5
        max_iterations = max(1, int(np.ceil(max_additional_thickness / thickness_increase_per_iter)))
        max_iterations = min(max_iterations, 10)  # Safety cap at 10 iterations

        logger.info(f"Max iterations: {max_iterations} (max additional thickness: {max_additional_thickness:.3f}mm)")

        dilated_matrix = voxel_matrix.copy()
        final_mesh = None

        for i in range(max_iterations):
            # Apply one step of dilation
            dilated_matrix = ndimage.binary_dilation(dilated_matrix, structure=struct)
            logger.info(f"Dilation step {i+1}/{max_iterations}: {np.sum(dilated_matrix)} voxels")

            # Reconstruct mesh to check thickness
            try:
                temp_voxels = trimesh.voxel.VoxelGrid(
                    trimesh.voxel.encoding.DenseEncoding(dilated_matrix),
                    transform=voxel_transform
                )
                temp_mesh = temp_voxels.marching_cubes

                if temp_mesh is None or len(temp_mesh.vertices) == 0:
                    logger.warning(f"Iteration {i+1}: marching cubes failed")
                    continue

                # Clean and position the mesh
                temp_mesh.fix_normals()

                # Translate back to original position
                temp_centroid = temp_mesh.centroid
                translation = original_centroid - temp_centroid
                temp_mesh.apply_translation(translation)

                # Measure new thickness
                temp_fixer = MeshFixer(temp_mesh)
                _, new_thicknesses, _ = temp_fixer.measure_thickness_at_points(2000)
                new_p5 = np.percentile(new_thicknesses, 5)

                logger.info(f"After step {i+1}: 5th percentile = {new_p5:.3f}mm")

                final_mesh = temp_mesh

                # Check if we've reached target
                if new_p5 >= min_thickness:
                    logger.info(f"Target thickness achieved at iteration {i+1}")
                    break

                # Check if we're at max thickness already
                if new_p5 >= max_thickness:
                    logger.info(f"Max thickness reached at iteration {i+1}")
                    break

            except Exception as e:
                logger.warning(f"Iteration {i+1} reconstruction failed: {e}")
                continue

        if final_mesh is None:
            logger.error("All dilation iterations failed, using fallback")
            return self._fallback_scale_fix(min_thickness, max_thickness, preserve_center)

        # Final cleanup
        try:
            if hasattr(final_mesh, 'split'):
                components = final_mesh.split(only_watertight=False)
                if len(components) > 1:
                    final_mesh = max(components, key=lambda m: len(m.vertices))
                    logger.info(f"Kept largest component: {len(final_mesh.vertices)} vertices")
        except Exception:
            pass

        # Light smoothing to reduce voxel artifacts
        try:
            trimesh.smoothing.filter_laplacian(final_mesh, iterations=1)
        except Exception:
            pass

        # Final centroid correction
        if preserve_center:
            final_centroid = final_mesh.centroid
            translation = original_centroid - final_centroid
            final_mesh.apply_translation(translation)
            logger.info(f"Final centroid drift corrected: {np.linalg.norm(translation):.4f}mm")

        self.mesh = final_mesh
        return final_mesh

    def _fallback_scale_fix(self, min_thickness: float, max_thickness: float,
                            preserve_center: bool) -> trimesh.Trimesh:
        """
        Fallback method using uniform scaling when voxelization fails.
        """
        logger.info("Using fallback scale method")

        original_centroid = self.mesh.centroid.copy()

        # Measure current thickness
        _, thicknesses, _ = self.measure_thickness_at_points(5000)
        current_min = np.percentile(thicknesses, 5)

        if current_min >= min_thickness:
            return self.mesh

        # Calculate uniform scale factor
        scale_factor = min_thickness / max(current_min, 0.01)
        # Cap to avoid over-scaling
        max_scale = max_thickness / max(current_min, 0.01)
        scale_factor = min(scale_factor, max_scale, 2.0)  # Max 2x scale

        logger.info(f"Applying scale factor: {scale_factor:.4f}")

        # Scale from centroid
        vertices = self.mesh.vertices.copy()
        vertices = (vertices - original_centroid) * scale_factor + original_centroid

        fixed_mesh = trimesh.Trimesh(
            vertices=vertices,
            faces=self.mesh.faces.copy()
        )
        fixed_mesh.fix_normals()

        # Ensure center is preserved
        if preserve_center:
            translation = original_centroid - fixed_mesh.centroid
            fixed_mesh.apply_translation(translation)

        self.mesh = fixed_mesh
        return fixed_mesh

    def fix_thickness_iterative(self, min_thickness: float = 1.0,
                                 max_thickness: float = 1.25,
                                 preserve_center: bool = True,
                                 max_iterations: int = 1) -> trimesh.Trimesh:
        """
        Fix thickness using the voxel dilation method.
        The voxel dilation now handles iterations internally with thickness checking.
        """
        logger.info(f"Starting thickness fix (target: {min_thickness}-{max_thickness}mm)")

        # Measure initial thickness
        _, thicknesses, _ = self.measure_thickness_at_points(3000)
        current_p5 = np.percentile(thicknesses, 5)
        current_min = np.min(thicknesses)

        logger.info(f"Initial min: {current_min:.3f}mm, 5th percentile: {current_p5:.3f}mm")

        if current_p5 >= min_thickness * 0.95:  # 95% of target
            logger.info("Already meets thickness requirements")
            return self.mesh

        # Apply voxel dilation (it handles iterations internally now)
        self.fix_thickness_voxel_dilation(
            min_thickness=min_thickness,
            max_thickness=max_thickness,
            preserve_center=preserve_center
        )

        # Final verification
        _, thicknesses, _ = self.measure_thickness_at_points(3000)
        final_p5 = np.percentile(thicknesses, 5)
        logger.info(f"Final 5th percentile: {final_p5:.3f}mm")

        return self.mesh

    def verify_thickness(self, min_thickness: float = 1.0,
                         num_samples: int = 10000) -> Dict:
        """Verify that the mesh meets minimum thickness requirements."""
        _, thicknesses, _ = self.measure_thickness_at_points(num_samples)

        violations = np.sum(thicknesses < min_thickness)

        return {
            'passes': np.percentile(thicknesses, 5) >= min_thickness * 0.9,
            'min_thickness': float(np.min(thicknesses)),
            'max_thickness': float(np.max(thicknesses)),
            'mean_thickness': float(np.mean(thicknesses)),
            'percentile_5': float(np.percentile(thicknesses, 5)),
            'percentile_10': float(np.percentile(thicknesses, 10)),
            'violations': int(violations),
            'violation_percentage': float(violations / len(thicknesses) * 100),
            'samples_checked': len(thicknesses)
        }

    def save(self, filepath: str):
        """Save the fixed mesh to file."""
        self.mesh.export(filepath)
        logger.info(f"Saved fixed mesh to: {filepath}")

    def get_center_comparison(self) -> Dict:
        """Compare original and current centroids."""
        current_centroid = self.mesh.centroid
        drift = np.linalg.norm(current_centroid - self.original_centroid)
        return {
            'original_centroid': self.original_centroid.tolist(),
            'current_centroid': current_centroid.tolist(),
            'drift_mm': float(drift),
            'center_preserved': drift < 0.05  # Less than 0.05mm drift
        }


def fix_stl_file(input_path: str, output_path: str,
                 min_thickness: float = 1.0,
                 max_thickness: float = 1.25,
                 method: str = 'iterative') -> Dict:
    """
    Fix a single STL file for minimum wall thickness.

    Args:
        input_path: Path to input STL file
        output_path: Path to save fixed STL file
        min_thickness: Minimum wall thickness in mm (default 1.0)
        max_thickness: Maximum wall thickness target in mm (default 1.25)
        method: Fix method ('voxel', 'iterative')

    Returns:
        Dictionary with fix results
    """
    logger.info(f"Fixing: {input_path}")
    logger.info(f"Target thickness: {min_thickness}-{max_thickness}mm, Method: {method}")

    fixer = MeshFixer.from_file(input_path)

    # Check if fix is needed
    initial_verification = fixer.verify_thickness(min_thickness, num_samples=5000)
    logger.info(f"Initial 5th percentile: {initial_verification['percentile_5']:.3f}mm")

    if initial_verification['passes']:
        logger.info("Mesh already meets requirements, copying without modification")
        fixer.save(output_path)
        return {
            'input_file': input_path,
            'output_file': output_path,
            'needed_fix': False,
            'verification': initial_verification,
            'center_check': fixer.get_center_comparison(),
            'success': True
        }

    # Apply fix
    if method == 'voxel':
        fixer.fix_thickness_voxel_dilation(min_thickness, max_thickness, preserve_center=True)
    else:  # 'iterative' or default
        fixer.fix_thickness_iterative(min_thickness, max_thickness, preserve_center=True)

    # Verify result
    verification = fixer.verify_thickness(min_thickness)
    center_check = fixer.get_center_comparison()

    logger.info(f"Final 5th percentile: {verification['percentile_5']:.3f}mm")
    logger.info(f"Center drift: {center_check['drift_mm']:.4f}mm")

    # Save
    fixer.save(output_path)

    # Success if 5th percentile is at least 90% of min_thickness
    success = verification['percentile_5'] >= min_thickness * 0.9

    return {
        'input_file': input_path,
        'output_file': output_path,
        'needed_fix': True,
        'method_used': method,
        'initial_p5_thickness': initial_verification['percentile_5'],
        'final_p5_thickness': verification['percentile_5'],
        'verification': verification,
        'center_check': center_check,
        'success': success
    }
