"""
Maritime Delimitation Engine (TALOS & UNCLOS Compliant)
Calculates strict equidistance median lines (1:1) and weighted maritime boundaries (e.g. 1:2, 2:3).
Implements technical specifications from TALOS (IHO/IAG/IOC S-51) and UNCLOS (Articles 15, 74, 83).
"""

import math
import numpy as np

from .marching_squares import marching_squares_zero_cross, chain_segments_to_polylines, chaikin_smooth
from .geodetic_utils import (
    HAS_QGIS,
    get_recommended_metric_crs,
    transform_geometry,
    meters_to_nautical_miles
)

if HAS_QGIS:
    from qgis.core import (
        QgsGeometry,
        QgsPointXY,
        QgsRectangle,
        QgsWkbTypes,
        QgsFeature,
        QgsField,
        QgsFields,
        QgsVectorLayer,
        QgsCoordinateReferenceSystem,
        QgsCoordinateTransform,
        QgsProject
    )
    from qgis.PyQt.QtCore import QVariant


def extract_segments_from_geometry(geom):
    """
    Extracts 2D line segments [ [[x1, y1], [x2, y2]], ... ] from any QgsGeometry,
    duck-typed geometry, numpy array, or list of coordinates.
    Supports Point, MultiPoint, LineString, MultiLineString, Polygon, MultiPolygon.
    """
    if geom is None:
        return np.empty((0, 2, 2), dtype=np.float64)

    # 1. Direct numpy array support
    if isinstance(geom, np.ndarray):
        if geom.ndim == 3 and geom.shape[1:] == (2, 2):
            return geom
        elif geom.ndim == 2 and geom.shape[1] == 2:
            if len(geom) < 2:
                return np.empty((0, 2, 2), dtype=np.float64)
            segs = []
            for i in range(len(geom) - 1):
                segs.append([geom[i], geom[i + 1]])
            return np.array(segs, dtype=np.float64)

    # 2. List or tuple of coordinates
    if isinstance(geom, (list, tuple)):
        try:
            arr = np.array(geom, dtype=np.float64)
            if arr.ndim == 3 and arr.shape[1:] == (2, 2):
                return arr
            elif arr.ndim == 2 and arr.shape[1] == 2:
                if len(arr) < 2:
                    return np.empty((0, 2, 2), dtype=np.float64)
                segs = []
                for i in range(len(arr) - 1):
                    segs.append([arr[i], arr[i + 1]])
                return np.array(segs, dtype=np.float64)
        except Exception:
            pass

    # 3. Duck-typed object with coords or asPolyline
    if hasattr(geom, "asPolyline") and not HAS_QGIS:
        try:
            pts = geom.asPolyline()
            segs = []
            for i in range(len(pts) - 1):
                p1, p2 = pts[i], pts[i + 1]
                x1 = p1.x() if hasattr(p1, 'x') else p1[0]
                y1 = p1.y() if hasattr(p1, 'y') else p1[1]
                x2 = p2.x() if hasattr(p2, 'x') else p2[0]
                y2 = p2.y() if hasattr(p2, 'y') else p2[1]
                segs.append([[x1, y1], [x2, y2]])
            return np.array(segs, dtype=np.float64) if segs else np.empty((0, 2, 2), dtype=np.float64)
        except Exception:
            pass

    # 4. Standard QgsGeometry handling
    if not HAS_QGIS:
        return np.empty((0, 2, 2), dtype=np.float64)

    if hasattr(geom, "isEmpty") and geom.isEmpty():
        return np.empty((0, 2, 2), dtype=np.float64)

    segments = []
    geom_type = geom.type()

    if geom_type == QgsWkbTypes.PointGeometry:
        if geom.isMultipart():
            pts = geom.asMultiPoint()
            for p in pts:
                segments.append([[p.x(), p.y()], [p.x(), p.y()]])
        else:
            p = geom.asPoint()
            segments.append([[p.x(), p.y()], [p.x(), p.y()]])

    elif geom_type == QgsWkbTypes.LineGeometry:
        if geom.isMultipart():
            lines = geom.asMultiPolyline()
            for line in lines:
                for i in range(len(line) - 1):
                    p1, p2 = line[i], line[i + 1]
                    segments.append([[p1.x(), p1.y()], [p2.x(), p2.y()]])
        else:
            line = geom.asPolyline()
            for i in range(len(line) - 1):
                p1, p2 = line[i], line[i + 1]
                segments.append([[p1.x(), p1.y()], [p2.x(), p2.y()]])

    elif geom_type == QgsWkbTypes.PolygonGeometry:
        if geom.isMultipart():
            polygons = geom.asMultiPolygon()
            for poly in polygons:
                for ring in poly:
                    for i in range(len(ring) - 1):
                        p1, p2 = ring[i], ring[i + 1]
                        segments.append([[p1.x(), p1.y()], [p2.x(), p2.y()]])
        else:
            poly = geom.asPolygon()
            for ring in poly:
                for i in range(len(ring) - 1):
                    p1, p2 = ring[i], ring[i + 1]
                    segments.append([[p1.x(), p1.y()], [p2.x(), p2.y()]])

    if not segments:
        return np.empty((0, 2, 2), dtype=np.float64)
    return np.array(segments, dtype=np.float64)


def extract_segments_from_geometries(geometries):
    """
    Extracts all segments from an iterable of QgsGeometry objects, numpy arrays, or coordinate lists.
    """
    if isinstance(geometries, np.ndarray) and geometries.ndim == 3 and geometries.shape[1:] == (2, 2):
        return geometries

    seg_list = []
    for g in geometries:
        segs = extract_segments_from_geometry(g)
        if len(segs) > 0:
            seg_list.append(segs)
    if not seg_list:
        return np.empty((0, 2, 2), dtype=np.float64)
    return np.vstack(seg_list)


def compute_min_distance_to_segments(pts, segments, chunk_size=1000):
    """
    Vectorized computation of minimum Euclidean distance from query points (pts)
    to a collection of line segments.
    
    Parameters:
        pts : np.ndarray (N, 2)
        segments : np.ndarray (S, 2, 2)
    Returns:
        min_dists : np.ndarray (N,)
        closest_pts : np.ndarray (N, 2)
    """
    if len(segments) == 0:
        return np.full(len(pts), np.inf, dtype=np.float64), np.zeros((len(pts), 2), dtype=np.float64)

    A = segments[:, 0, :]  # (S, 2)
    B = segments[:, 1, :]  # (S, 2)
    AB = B - A            # (S, 2)
    AB_len2 = np.sum(AB**2, axis=1)  # (S,)
    zero_mask = AB_len2 < 1e-12
    AB_len2_safe = np.copy(AB_len2)
    AB_len2_safe[zero_mask] = 1.0

    num_pts = len(pts)
    min_dists = np.empty(num_pts, dtype=np.float64)
    closest_pts = np.empty((num_pts, 2), dtype=np.float64)

    for i in range(0, num_pts, chunk_size):
        chunk = pts[i:i + chunk_size]  # (C, 2)
        AP = chunk[:, None, :] - A[None, :, :]  # (C, S, 2)
        dot = np.sum(AP * AB[None, :, :], axis=2)  # (C, S)
        t = np.clip(dot / AB_len2_safe[None, :], 0.0, 1.0)
        t[:, zero_mask] = 0.0

        Q = A[None, :, :] + t[:, :, None] * AB[None, :, :]  # (C, S, 2)
        diff = chunk[:, None, :] - Q
        dists = np.sqrt(np.sum(diff**2, axis=2))  # (C, S)

        best_seg_indices = np.argmin(dists, axis=1)
        row_indices = np.arange(len(chunk))

        min_dists[i:i + chunk_size] = dists[row_indices, best_seg_indices]
        closest_pts[i:i + chunk_size] = Q[row_indices, best_seg_indices, :]

    return min_dists, closest_pts


class DelimitationEngine:
    """
    TALOS / UNCLOS Maritime Delimitation Engine.
    Handles calculation of Median Line and Weighted Maritime Boundaries.
    """

    # Delimitation mode constants
    MODE_OPPOSITE = "opposite"   # Opposite coasts
    MODE_ADJACENT = "adjacent"   # Adjacent coasts

    def __init__(self,
                 geometries_a,
                 geometries_b,
                 weight_a=1.0,
                 weight_b=1.0,
                 name_a="Baseline A",
                 name_b="Baseline B",
                 source_crs=None,
                 calc_crs=None,
                 resolution=None,
                 smooth_line=True,
                 mode="opposite",
                 seaward_distance=None,
                 lbt_point=None,
                 seaward_point=None,
                 feedback=None):
        """
        Parameters:
            geometries_a : list of QgsGeometry, numpy arrays, or coordinate lists
            geometries_b : list of QgsGeometry, numpy arrays, or coordinate lists
            weight_a : float (weight for state A, > 0)
            weight_b : float (weight for state B, > 0)
            name_a : str (label for state A)
            name_b : str (label for state B)
            source_crs : QgsCoordinateReferenceSystem
            calc_crs : QgsCoordinateReferenceSystem (metric projected CRS)
            resolution : float (grid resolution in meters, or None for auto)
            smooth_line : bool (apply Chaikin smoothing)
            mode : str ('opposite' or 'adjacent')
            seaward_distance : float or None (max lateral boundary reach in meters, e.g. 22224 for 12 NM)
            lbt_point : tuple/list [x, y] or None (Land Boundary Terminus coordinate)
            seaward_point : tuple/list [x, y] or None (point indicating seaward direction)
            feedback : QgsProcessingFeedback or similar
        """
        self.raw_geoms_a = geometries_a
        self.raw_geoms_b = geometries_b
        self.weight_a = float(weight_a)
        self.weight_b = float(weight_b)
        self.name_a = name_a
        self.name_b = name_b
        self.source_crs = source_crs
        self.calc_crs = calc_crs
        self.user_resolution = resolution
        self.smooth_line = smooth_line
        self.mode = mode if mode in (self.MODE_OPPOSITE, self.MODE_ADJACENT) else self.MODE_OPPOSITE
        self.seaward_distance = float(seaward_distance) if seaward_distance is not None and seaward_distance > 0 else None
        self.lbt_point = lbt_point
        self.seaward_point = seaward_point
        self.feedback = feedback

        # Validate weights
        if self.weight_a <= 0.0 or self.weight_b <= 0.0:
            raise ValueError("Baseline weights must be greater than zero (Weight > 0).")

    def _log_info(self, msg):
        if self.feedback is not None:
            if hasattr(self.feedback, "pushInfo"):
                self.feedback.pushInfo(msg)
            elif callable(self.feedback):
                self.feedback(msg)

    def _set_progress(self, pct):
        if self.feedback is not None and hasattr(self.feedback, "setProgress"):
            self.feedback.setProgress(pct)

    def _is_canceled(self):
        if self.feedback is not None and hasattr(self.feedback, "isCanceled"):
            return self.feedback.isCanceled()
        return False

    def _compute_corridor_bbox(self, pts_a, pts_b):
        """
        Compute a bounding box for the corridor between baselines A and B.
        
        For OPPOSITE mode: tight bbox focused on the area between baselines.
        For ADJACENT mode: extended bbox that allows the median line to extend
        outward (seaward) from the Land Boundary Terminus (LBT), accommodating
        the specified seaward distance (e.g. 12 NM = 22.2 km, 24 NM, 200 NM).
        """
        min_a = np.min(pts_a, axis=0)
        max_a = np.max(pts_a, axis=0)
        min_b = np.min(pts_b, axis=0)
        max_b = np.max(pts_b, axis=0)

        # Combined bounding box of both baselines
        combined_min = np.minimum(min_a, min_b)
        combined_max = np.maximum(max_a, max_b)

        # Separation distance between centroids (rough measure of gap)
        centroid_a = (min_a + max_a) / 2.0
        centroid_b = (min_b + max_b) / 2.0
        separation = np.linalg.norm(centroid_a - centroid_b)

        # Span of combined box
        combined_span = combined_max - combined_min

        if self.mode == self.MODE_ADJACENT:
            # Adjacent mode: baselines are side-by-side, median line extends
            # outward (seaward) from the Land Boundary Terminus (LBT).
            max_baseline_span = max(
                np.linalg.norm(max_a - min_a),
                np.linalg.norm(max_b - min_b)
            )
            seaward_buf = self.seaward_distance if self.seaward_distance is not None else 22224.0
            buf = max(max_baseline_span * 0.8, seaward_buf * 1.15, 25000.0)
        else:
            # Opposite mode: tight buffer focused between the baselines.
            buf = min(separation * 0.15, max(combined_span[0], combined_span[1]) * 0.30)

        grid_min = combined_min - buf
        grid_max = combined_max + buf

        return grid_min, grid_max, separation

    def compute(self):
        """
        Executes the maritime boundary delimitation workflow.
        Returns a dictionary containing:
            - 'median_lines': list of continuous polylines in source_crs
            - 'tie_lines': list of construction lines (connecting median line to nearest basepoints)
            - 'critical_points_a': list of controlling basepoints on A
            - 'critical_points_b': list of controlling basepoints on B
            - 'summary': delimitation summary dictionary
        """
        self._log_info("--- Starting Maritime Delimitation (TALOS & UNCLOS) ---")
        self._log_info(f"Feature A: {self.name_a} (Weight: {self.weight_a})")
        self._log_info(f"Feature B: {self.name_b} (Weight: {self.weight_b})")
        mode_desc = "Opposite Coasts" if self.mode == self.MODE_OPPOSITE else "Adjacent Coasts"
        self._log_info(f"Delimitation Mode: {mode_desc}")

        # Ratio explanation: dA / dB = wA / wB
        ratio = self.weight_a / self.weight_b
        if abs(ratio - 1.0) < 1e-4:
            ratio_desc = "1 : 1 (Strict Equidistance / Full Effect)"
        else:
            ratio_desc = f"{self.weight_a:g} : {self.weight_b:g} (dA = {ratio:.3f} × dB)"
        self._log_info(f"Delimitation formula: {ratio_desc}")

        self._set_progress(10)

        # 1. Transform geometries to calculation CRS (metric projected CRS)
        calc_crs = self.calc_crs
        if calc_crs is None and HAS_QGIS and self.source_crs is not None:
            # Combine bounding boxes
            bbox = None
            for g in self.raw_geoms_a + self.raw_geoms_b:
                if g and not g.isEmpty():
                    if bbox is None:
                        bbox = QgsRectangle(g.boundingBox())
                    else:
                        bbox.combineExtentWith(g.boundingBox())
            calc_crs = get_recommended_metric_crs(self.source_crs, bbox)

        self._log_info(f"Calculation Coordinate System: {calc_crs.authid() if hasattr(calc_crs, 'authid') else 'Metric Cartesian'}")

        geoms_a_proj = []
        geoms_b_proj = []

        if HAS_QGIS and self.source_crs and calc_crs and self.source_crs != calc_crs:
            for g in self.raw_geoms_a:
                geoms_a_proj.append(transform_geometry(g, self.source_crs, calc_crs))
            for g in self.raw_geoms_b:
                geoms_b_proj.append(transform_geometry(g, self.source_crs, calc_crs))
        else:
            geoms_a_proj = self.raw_geoms_a
            geoms_b_proj = self.raw_geoms_b

        # 2. Extract segments
        segs_a = extract_segments_from_geometries(geoms_a_proj)
        segs_b = extract_segments_from_geometries(geoms_b_proj)

        if len(segs_a) == 0 or len(segs_b) == 0:
            raise ValueError("No valid geometry found for one or both baselines/basepoints.")

        self._set_progress(20)

        # 3. Determine bounding envelope for grid — corridor-based
        all_pts_a = segs_a.reshape(-1, 2)
        all_pts_b = segs_b.reshape(-1, 2)

        grid_min, grid_max, separation = self._compute_corridor_bbox(all_pts_a, all_pts_b)
        grid_min_x, grid_min_y = grid_min
        grid_max_x, grid_max_y = grid_max

        span_x = max(grid_max_x - grid_min_x, 100.0)
        span_y = max(grid_max_y - grid_min_y, 100.0)

        # 4. Determine resolution
        if self.user_resolution is not None and self.user_resolution > 0:
            res = float(self.user_resolution)
        else:
            # Adaptive resolution: ~300 to 400 cells along largest axis
            res = max(span_x, span_y) / 320.0
            # Clamp reasonable minimum step
            res = max(res, 1.0)

        nx = int(math.ceil(span_x / res)) + 1
        ny = int(math.ceil(span_y / res)) + 1

        # Safety clamp to prevent memory overflow
        max_cells = 800 * 800
        if nx * ny > max_cells:
            scale = math.sqrt((nx * ny) / max_cells)
            res *= scale
            nx = int(math.ceil(span_x / res)) + 1
            ny = int(math.ceil(span_y / res)) + 1

        self._log_info(f"Calculation grid: {nx} × {ny} cells (Resolution: {res:.1f} meters)")
        self._set_progress(30)

        # 5. Build coordinates meshgrid
        xs = np.linspace(grid_min_x, grid_max_x, nx)
        ys = np.linspace(grid_min_y, grid_max_y, ny)
        X, Y = np.meshgrid(xs, ys)
        grid_points = np.column_stack([X.ravel(), Y.ravel()])

        # 6. Compute distance fields
        self._log_info("Computing distance field to Baseline A...")
        dist_a, _ = compute_min_distance_to_segments(grid_points, segs_a)
        dist_a_2d = dist_a.reshape((ny, nx))

        if self._is_canceled():
            return None
        self._set_progress(50)

        self._log_info("Computing distance field to Baseline B...")
        dist_b, _ = compute_min_distance_to_segments(grid_points, segs_b)
        dist_b_2d = dist_b.reshape((ny, nx))

        if self._is_canceled():
            return None
        self._set_progress(70)

        # 7. Compute weighted delimitation field:
        # Zero-contour condition: dA / wA = dB / wB <=> dA - (wA / wB) * dB = 0
        Z = dist_a_2d - ratio * dist_b_2d

        # 8. Extract zero-contour using Marching Squares
        self._log_info("Extracting median line using Marching Squares...")
        contour_segments = marching_squares_zero_cross(X, Y, Z, isovalue=0.0)

        if not contour_segments:
            self._log_info("Warning: No median line contour intersection found within grid domain.")
            return {
                'median_lines': [],
                'tie_lines': [],
                'critical_points_a': [],
                'critical_points_b': [],
                'summary': {'status': 'empty'}
            }

        # 9. Chain segments into polylines
        chain_tol = max(1e-6, res * 1e-4)
        raw_polylines = chain_segments_to_polylines(contour_segments, tol=chain_tol)

        # 10. Delimitation Line Selection & Trimming according to Mode
        if self.mode == self.MODE_ADJACENT:
            self._log_info("Processing adjacent coasts lateral boundary line...")
            # 1. Determine LBT (Land Boundary Terminus)
            dists_a_to_b, closest_b_pts = compute_min_distance_to_segments(all_pts_a, segs_b)
            lbt_idx = np.argmin(dists_a_to_b)
            auto_lbt = (all_pts_a[lbt_idx] + closest_b_pts[lbt_idx]) / 2.0
            lbt = np.array(self.lbt_point, dtype=np.float64) if self.lbt_point is not None else auto_lbt
            self._log_info(f"Land Boundary Terminus (LBT): X={lbt[0]:.2f}, Y={lbt[1]:.2f}")

            # 2. Find the polyline closest to LBT
            best_pl = None
            min_pl_dist = float('inf')
            for pl in raw_polylines:
                arr = np.array(pl)
                dists = np.linalg.norm(arr - lbt, axis=1)
                md = float(np.min(dists))
                if md < min_pl_dist:
                    min_pl_dist = md
                    best_pl = pl

            if best_pl is None:
                clipped_polylines = raw_polylines
            else:
                arr = np.array(best_pl)
                dists_lbt = np.linalg.norm(arr - lbt, axis=1)
                closest_idx = int(np.argmin(dists_lbt))

                # Split into two branches from the vertex closest to LBT
                branch_fwd = arr[closest_idx:]
                branch_bwd = arr[:closest_idx + 1][::-1]

                # 3. Determine seaward direction
                if self.seaward_point is not None:
                    sea_target = np.array(self.seaward_point, dtype=np.float64)
                    sea_vec = sea_target - lbt
                else:
                    # Auto-detect seaward direction:
                    # Find outer endpoints of baselines (furthest from LBT)
                    dist_a_from_lbt = np.linalg.norm(all_pts_a - lbt, axis=1)
                    dist_b_from_lbt = np.linalg.norm(all_pts_b - lbt, axis=1)
                    ea = all_pts_a[np.argmax(dist_a_from_lbt)]
                    eb = all_pts_b[np.argmax(dist_b_from_lbt)]

                    # Vector along coast from ea to eb
                    coast_vec = eb - ea
                    # Normals perpendicular to coast
                    n1 = np.array([-coast_vec[1], coast_vec[0]])
                    n2 = np.array([coast_vec[1], -coast_vec[0]])

                    mid_base = (ea + eb) / 2.0
                    sea_vec = n1 if np.dot(n1, lbt - mid_base) >= 0 else n2
                    if np.linalg.norm(sea_vec) < 1e-6:
                        sea_vec = n1 if (branch_fwd[-1, 1] > lbt[1]) else n2

                # Pick branch aligned with seaward direction
                vec_fwd = branch_fwd[-1] - branch_fwd[0] if len(branch_fwd) > 1 else np.zeros(2)
                vec_bwd = branch_bwd[-1] - branch_bwd[0] if len(branch_bwd) > 1 else np.zeros(2)

                dot_f = float(np.dot(vec_fwd, sea_vec))
                dot_b = float(np.dot(vec_bwd, sea_vec))
                seaward_branch = branch_fwd if dot_f >= dot_b else branch_bwd

                # Ensure line starts exactly at LBT
                pts_list = [lbt.tolist()]
                for p in seaward_branch:
                    if np.linalg.norm(p - lbt) > 1e-4:
                        pts_list.append(p.tolist())

                # 4. Trim at seaward limit if specified
                if self.seaward_distance is not None and self.seaward_distance > 0:
                    seaward_limit = float(self.seaward_distance)
                    arr_sea = np.array(pts_list)
                    d_sea_a, _ = compute_min_distance_to_segments(arr_sea, segs_a)
                    d_sea_b, _ = compute_min_distance_to_segments(arr_sea, segs_b)
                    d_sea = np.minimum(d_sea_a, d_sea_b)

                    trimmed_list = [pts_list[0]]
                    for i in range(1, len(arr_sea)):
                        if d_sea[i] <= seaward_limit:
                            trimmed_list.append(arr_sea[i].tolist())
                        else:
                            # Interpolate exact cutoff point
                            p_prev = arr_sea[i - 1]
                            p_curr = arr_sea[i]
                            d_prev = d_sea[i - 1]
                            d_curr = d_sea[i]
                            if abs(d_curr - d_prev) > 1e-6:
                                t = float((seaward_limit - d_prev) / (d_curr - d_prev))
                                t = max(0.0, min(1.0, t))
                                p_final = p_prev + t * (p_curr - p_prev)
                                trimmed_list.append(p_final.tolist())
                            break
                    pts_list = trimmed_list

                clipped_polylines = [pts_list]
            filtered_polylines = clipped_polylines

        else:
            # OPPOSITE MODE: Corridor clipping between opposite baselines
            self._log_info("Clipping median line to inter-baseline corridor (Opposite Coasts)...")

            # Sample representative points from each baseline
            n_sample_a = min(len(all_pts_a), 200)
            n_sample_b = min(len(all_pts_b), 200)
            sample_a = all_pts_a[np.linspace(0, len(all_pts_a) - 1, n_sample_a, dtype=int)]
            sample_b = all_pts_b[np.linspace(0, len(all_pts_b) - 1, n_sample_b, dtype=int)]

            # Distance from each sample point on A to nearest point on B
            d_a_to_b, _ = compute_min_distance_to_segments(sample_a, segs_b)
            d_b_to_a, _ = compute_min_distance_to_segments(sample_b, segs_a)

            max_sep = max(float(np.max(d_a_to_b)), float(np.max(d_b_to_a)))
            corridor_threshold = max_sep * 1.2

            clipped_polylines = []
            for pl in raw_polylines:
                pl_arr = np.array(pl)
                if len(pl_arr) < 2:
                    continue

                d_to_a, _ = compute_min_distance_to_segments(pl_arr, segs_a)
                d_to_b, _ = compute_min_distance_to_segments(pl_arr, segs_b)

                in_corridor = (d_to_a <= corridor_threshold) & (d_to_b <= corridor_threshold)

                current_segment = []
                for idx in range(len(pl_arr)):
                    if in_corridor[idx]:
                        current_segment.append(pl_arr[idx].tolist())
                    else:
                        if len(current_segment) >= 2:
                            clipped_polylines.append(current_segment)
                        current_segment = []
                if len(current_segment) >= 2:
                    clipped_polylines.append(current_segment)

            if not clipped_polylines and raw_polylines:
                self._log_info("Warning: Corridor clipping was too restrictive, retaining raw contour lines.")
                clipped_polylines = raw_polylines

            # Filter out tiny noise artifacts
            min_length = res * 2.0
            filtered_polylines = []
            for pl in clipped_polylines:
                pl_arr = np.array(pl)
                if len(pl_arr) < 2:
                    continue
                diffs = pl_arr[1:] - pl_arr[:-1]
                seg_lens = np.sqrt(np.sum(diffs**2, axis=1))
                total_len = np.sum(seg_lens)
                if total_len >= min_length or len(clipped_polylines) <= 2:
                    filtered_polylines.append(pl)

            if not filtered_polylines and clipped_polylines:
                filtered_polylines = clipped_polylines

            # Sort polylines by length descending (longest line is the primary median line)
            def poly_length(pl):
                arr = np.array(pl)
                return np.sum(np.sqrt(np.sum((arr[1:] - arr[:-1])**2, axis=1)))

            filtered_polylines.sort(key=poly_length, reverse=True)

        self._set_progress(80)

        # 11. Optional Chaikin smoothing
        if self.smooth_line:
            self._log_info("Applying line smoothing (Chaikin smoothing)...")
            final_polylines_proj = [chaikin_smooth(pl, iterations=2) for pl in filtered_polylines]
        else:
            final_polylines_proj = filtered_polylines

        # 12. Compute Construction / Tie Lines and Critical Turning Points
        # Sample points along the median lines to construct tie lines
        tie_lines_proj = []
        crit_a_pts = []
        crit_b_pts = []

        total_length_m = 0.0
        for pl in final_polylines_proj:
            pl_arr = np.array(pl)
            if len(pl_arr) < 2:
                continue
            seg_diffs = pl_arr[1:] - pl_arr[:-1]
            total_length_m += float(np.sum(np.sqrt(np.sum(seg_diffs**2, axis=1))))

            # Sample tie lines at regular intervals (e.g. every ~15 vertices)
            sample_step = max(1, len(pl_arr) // 25)
            sample_pts = pl_arr[::sample_step]

            _, q_a = compute_min_distance_to_segments(sample_pts, segs_a)
            _, q_b = compute_min_distance_to_segments(sample_pts, segs_b)

            for p, qa, qb in zip(sample_pts, q_a, q_b):
                d_a_val = float(np.linalg.norm(p - qa))
                d_b_val = float(np.linalg.norm(p - qb))
                tie_lines_proj.append({
                    'line_to_a': [p.tolist(), qa.tolist()],
                    'line_to_b': [p.tolist(), qb.tolist()],
                    'tie_full': [qa.tolist(), p.tolist(), qb.tolist()],
                    'p': p.tolist(),
                    'qa': qa.tolist(),
                    'qb': qb.tolist(),
                    'dist_a_m': d_a_val,
                    'dist_b_m': d_b_val,
                    'dist_a_nm': meters_to_nautical_miles(d_a_val),
                    'dist_b_nm': meters_to_nautical_miles(d_b_val),
                    'ratio_obs': (d_a_val / d_b_val) if d_b_val > 1e-6 else 0.0
                })
                crit_a_pts.append(qa.tolist())
                crit_b_pts.append(qb.tolist())

        self._set_progress(90)

        # 13. Transform geometries back to source_crs (or keep in calc_crs)
        output_polylines = []
        output_tie_lines = []

        if HAS_QGIS and self.source_crs and calc_crs and self.source_crs != calc_crs:
            transform_back = QgsCoordinateTransform(calc_crs, self.source_crs, QgsProject.instance())
            for pl in final_polylines_proj:
                pts_src = []
                for x, y in pl:
                    pt_proj = QgsPointXY(x, y)
                    pt_src = transform_back.transform(pt_proj)
                    pts_src.append([pt_src.x(), pt_src.y()])
                output_polylines.append(pts_src)

            for t in tie_lines_proj:
                # Transform tie line points
                tf_p = transform_back.transform(QgsPointXY(t['p'][0], t['p'][1]))
                tf_qa = transform_back.transform(QgsPointXY(t['qa'][0], t['qa'][1]))
                tf_qb = transform_back.transform(QgsPointXY(t['qb'][0], t['qb'][1]))
                output_tie_lines.append({
                    'p': [tf_p.x(), tf_p.y()],
                    'qa': [tf_qa.x(), tf_qa.y()],
                    'qb': [tf_qb.x(), tf_qb.y()],
                    'dist_a_m': t['dist_a_m'],
                    'dist_b_m': t['dist_b_m'],
                    'dist_a_nm': t['dist_a_nm'],
                    'dist_b_nm': t['dist_b_nm'],
                    'ratio_obs': t['ratio_obs']
                })
        else:
            output_polylines = final_polylines_proj
            output_tie_lines = tie_lines_proj

        total_length_nm = meters_to_nautical_miles(total_length_m)
        self._log_info(f"Delimitation complete! Generated {len(output_polylines)} median line(s).")
        self._log_info(f"Total boundary length: {total_length_m:.1f} m ({total_length_nm:.2f} Nautical Miles / NM)")

        summary = {
            'weight_a': self.weight_a,
            'weight_b': self.weight_b,
            'ratio_target': ratio,
            'ratio_desc': ratio_desc,
            'name_a': self.name_a,
            'name_b': self.name_b,
            'mode': self.mode,
            'mode_desc': "Adjacent Coasts" if self.mode == self.MODE_ADJACENT else "Opposite Coasts",
            'seaward_distance_m': self.seaward_distance,
            'seaward_distance_nm': meters_to_nautical_miles(self.seaward_distance) if self.seaward_distance else None,
            'num_lines': len(output_polylines),
            'total_length_m': total_length_m,
            'total_length_km': total_length_m / 1000.0,
            'total_length_nm': total_length_nm,
            'grid_resolution_m': res,
            'calc_crs': calc_crs.authid() if hasattr(calc_crs, 'authid') else 'Metric'
        }

        self._set_progress(100)

        return {
            'median_lines': output_polylines,
            'tie_lines': output_tie_lines,
            'summary': summary
        }

