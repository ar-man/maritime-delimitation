"""
Maritime Median Line Delimitation - Marching Squares & Contour Tracer
Implements 2D Marching Squares isovalue contour extraction and topological segment chaining.
"""

import math
from collections import defaultdict
import numpy as np


def marching_squares_zero_cross(X, Y, Z, isovalue=0.0):
    """
    Extracts isovalue line segments from a 2D scalar field Z(X, Y) using Marching Squares.
    
    Parameters:
        X : 2D numpy array of X coordinates (shape: ny, nx)
        Y : 2D numpy array of Y coordinates (shape: ny, nx)
        Z : 2D numpy array of scalar values (shape: ny, nx)
        isovalue : float, contour target value (typically 0.0 for dA - (wA/wB)*dB = 0)
        
    Returns:
        List of segments: [((x1, y1), (x2, y2)), ...]
    """
    ny, nx = Z.shape
    segments = []

    # Corner values:
    # BL: (j, i), BR: (j, i+1), TR: (j+1, i+1), TL: (j+1, i)
    v_bl = Z[:-1, :-1]
    v_br = Z[:-1, 1:]
    v_tr = Z[1:, 1:]
    v_tl = Z[1:, :-1]

    # Binary bits: 1 if >= isovalue else 0
    b_bl = (v_bl >= isovalue).astype(np.int32)
    b_br = (v_br >= isovalue).astype(np.int32)
    b_tr = (v_tr >= isovalue).astype(np.int32)
    b_tl = (v_tl >= isovalue).astype(np.int32)

    case = b_bl | (b_br << 1) | (b_tr << 2) | (b_tl << 3)

    # Active cells have sign change (not 0 and not 15)
    active_j, active_i = np.where((case > 0) & (case < 15))

    def interpolate(p1, p2, val1, val2):
        denom = val2 - val1
        if abs(denom) < 1e-12:
            return (p1 + p2) * 0.5
        t = (isovalue - val1) / denom
        t = max(0.0, min(1.0, float(t)))
        return p1 + t * (p2 - p1)

    for j, i in zip(active_j, active_i):
        c = int(case[j, i])

        p_bl = np.array([X[j, i], Y[j, i]], dtype=np.float64)
        p_br = np.array([X[j, i + 1], Y[j, i + 1]], dtype=np.float64)
        p_tr = np.array([X[j + 1, i + 1], Y[j + 1, i + 1]], dtype=np.float64)
        p_tl = np.array([X[j + 1, i], Y[j + 1, i]], dtype=np.float64)

        val_bl = float(v_bl[j, i])
        val_br = float(v_br[j, i])
        val_tr = float(v_tr[j, i])
        val_tl = float(v_tl[j, i])

        # Edge intersection points
        # Bottom edge: BL -> BR
        e_bottom = interpolate(p_bl, p_br, val_bl, val_br)
        # Right edge: BR -> TR
        e_right = interpolate(p_br, p_tr, val_br, val_tr)
        # Top edge: TL -> TR
        e_top = interpolate(p_tl, p_tr, val_tl, val_tr)
        # Left edge: BL -> TL
        e_left = interpolate(p_bl, p_tl, val_bl, val_tl)

        # Cases according to standard Marching Squares lookup table
        if c in (1, 14):
            segments.append((e_left, e_bottom))
        elif c in (2, 13):
            segments.append((e_bottom, e_right))
        elif c in (3, 12):
            segments.append((e_left, e_right))
        elif c in (4, 11):
            segments.append((e_right, e_top))
        elif c == 5:
            # Ambiguity: saddle point
            center_val = (val_bl + val_br + val_tr + val_tl) * 0.25
            if center_val >= isovalue:
                segments.append((e_left, e_top))
                segments.append((e_bottom, e_right))
            else:
                segments.append((e_left, e_bottom))
                segments.append((e_right, e_top))
        elif c in (6, 9):
            segments.append((e_bottom, e_top))
        elif c in (7, 8):
            segments.append((e_left, e_top))
        elif c == 10:
            center_val = (val_bl + val_br + val_tr + val_tl) * 0.25
            if center_val >= isovalue:
                segments.append((e_left, e_bottom))
                segments.append((e_top, e_right))
            else:
                segments.append((e_left, e_top))
                segments.append((e_bottom, e_right))

    return segments


def chain_segments_to_polylines(segments, tol=1e-5):
    """
    Chains unstructured segments into continuous polylines.
    Handles open lines and closed loops.
    
    Parameters:
        segments : list of ((x1, y1), (x2, y2))
        tol : spatial quantization tolerance for snapping endpoints
        
    Returns:
        List of polylines: [ [(x1, y1), (x2, y2), ...], ... ]
    """
    if not segments:
        return []

    def quantize(p):
        return (int(round(p[0] / tol)), int(round(p[1] / tol)))

    adj = defaultdict(list)
    node_coords = {}

    for s_idx, (p1, p2) in enumerate(segments):
        k1 = quantize(p1)
        k2 = quantize(p2)
        if k1 == k2:
            continue
        if k1 not in node_coords:
            node_coords[k1] = p1
        if k2 not in node_coords:
            node_coords[k2] = p2
        adj[k1].append((k2, s_idx))
        adj[k2].append((k1, s_idx))

    visited_edges = set()
    polylines = []

    # 1. Start from open ends (degree == 1)
    open_keys = [k for k, edges in adj.items() if len(edges) == 1]
    for start_k in open_keys:
        # Check if start node has an unvisited edge
        unvisited = [edge for edge in adj[start_k] if edge[1] not in visited_edges]
        if not unvisited:
            continue

        path = [node_coords[start_k]]
        curr_k = start_k
        while True:
            nxt_edge = None
            for nxt_k, e_idx in adj[curr_k]:
                if e_idx not in visited_edges:
                    visited_edges.add(e_idx)
                    nxt_edge = nxt_k
                    break
            if nxt_edge is None:
                break
            path.append(node_coords[nxt_edge])
            curr_k = nxt_edge

        if len(path) > 1:
            polylines.append(path)

    # 2. Trace remaining edges (closed loops or cycles)
    for k in list(adj.keys()):
        while True:
            unvisited = [edge for edge in adj[k] if edge[1] not in visited_edges]
            if not unvisited:
                break

            path = [node_coords[k]]
            curr_k = k
            while True:
                nxt_edge = None
                for nxt_k, e_idx in adj[curr_k]:
                    if e_idx not in visited_edges:
                        visited_edges.add(e_idx)
                        nxt_edge = nxt_k
                        break
                if nxt_edge is None:
                    break
                path.append(node_coords[nxt_edge])
                curr_k = nxt_edge
                if curr_k == k:
                    break

            if len(path) > 1:
                polylines.append(path)

    return polylines


def chaikin_smooth(polyline, iterations=1):
    """
    Smooths a polyline using Chaikin's corner-cutting algorithm.
    Preserves endpoints of open polylines.
    """
    if len(polyline) < 3 or iterations < 1:
        return polyline

    pts = [np.array(p, dtype=np.float64) for p in polyline]
    is_closed = np.allclose(pts[0], pts[-1], atol=1e-6)

    for _ in range(iterations):
        new_pts = []
        if is_closed:
            n = len(pts) - 1
            for i in range(n):
                p0 = pts[i]
                p1 = pts[(i + 1) % n]
                q = 0.75 * p0 + 0.25 * p1
                r = 0.25 * p0 + 0.75 * p1
                new_pts.extend([q, r])
            new_pts.append(new_pts[0])  # close loop
        else:
            new_pts.append(pts[0])
            for i in range(len(pts) - 1):
                p0 = pts[i]
                p1 = pts[i + 1]
                q = 0.75 * p0 + 0.25 * p1
                r = 0.25 * p0 + 0.75 * p1
                new_pts.extend([q, r])
            new_pts.append(pts[-1])
        pts = new_pts

    return [p.tolist() if isinstance(p, np.ndarray) else p for p in pts]
