"""
STREEVA Route Progress Calculation Engine (Phase 2B).

Calculates deterministic distance along an expected route polyline,
remaining distance to destination, progress percentage, and enforces
monotonicity safeguards against GPS jitter.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel

from ..edge.route_deviation import (
    haversine_distance_m,
    compute_cross_track_distance_m,
    _extract_lat_lng,
    EARTH_RADIUS_M
)


def _to_lat_lng(point: Union[Dict[str, Any], Tuple[float, float], Any]) -> Tuple[float, float]:
    """Converts tuple, dict, or object into (lat, lng) float tuple."""
    if isinstance(point, (tuple, list)) and len(point) >= 2:
        lat, lng = float(point[0]), float(point[1])
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
            raise ValueError(f"Invalid coordinate bounds: lat={lat}, lng={lng}")
        return lat, lng
    return _extract_lat_lng(point)


class RouteProgressResult(BaseModel):
    """Output contract for a route progress observation."""
    distance_along_route_m: float
    total_route_distance_m: float
    remaining_distance_m: float
    progress_percent: float
    nearest_segment_index: Optional[int] = None
    is_off_route: bool = False
    cross_track_distance_m: float = 0.0


class RouteProgressEngine:
    """
    Stateful Route Progress Engine for active journeys.
    """

    def __init__(
        self,
        expected_route: Optional[List[Union[Dict[str, float], Any]]] = None,
        source: Optional[Union[Tuple[float, float], Dict[str, float], Any]] = None,
        destination: Optional[Union[Tuple[float, float], Dict[str, float], Any]] = None,
        monotonic_tolerance_m: float = 50.0
    ):
        self.monotonic_tolerance_m = monotonic_tolerance_m
        self.points: List[Tuple[float, float]] = []
        self.segment_lengths: List[float] = []
        self.cumulative_lengths: List[float] = []
        self.total_route_distance_m: float = 0.0
        
        self.last_distance_along_m: float = 0.0
        self.last_progress_percent: float = 0.0
        
        self.set_route(expected_route, source, destination)

    def set_route(
        self,
        expected_route: Optional[List[Union[Dict[str, float], Any]]] = None,
        source: Optional[Union[Tuple[float, float], Dict[str, float], Any]] = None,
        destination: Optional[Union[Tuple[float, float], Dict[str, float], Any]] = None
    ) -> None:
        """Initializes or updates the expected polyline and precomputes segment lengths."""
        self.points = []
        self.segment_lengths = []
        self.cumulative_lengths = [0.0]
        self.total_route_distance_m = 0.0
        self.last_distance_along_m = 0.0
        self.last_progress_percent = 0.0

        if expected_route and len(expected_route) > 0:
            for p in expected_route:
                try:
                    self.points.append(_to_lat_lng(p))
                except Exception:
                    continue

        if len(self.points) < 2 and source is not None and destination is not None:
            # Fallback: straight-line segment from source to destination
            src_pt = _to_lat_lng(source)
            dst_pt = _to_lat_lng(destination)
            self.points = [src_pt, dst_pt]

        # Precompute segment distances
        cum = 0.0
        for i in range(len(self.points) - 1):
            seg_len = haversine_distance_m(
                self.points[i][0], self.points[i][1],
                self.points[i + 1][0], self.points[i + 1][1]
            )
            self.segment_lengths.append(seg_len)
            cum += seg_len
            self.cumulative_lengths.append(cum)

        self.total_route_distance_m = cum

    def reset(self) -> None:
        """Resets tracking progress to 0."""
        self.last_distance_along_m = 0.0
        self.last_progress_percent = 0.0

    def calculate_progress(
        self,
        lat: float,
        lng: float
    ) -> RouteProgressResult:
        """
        Calculates distance along route, remaining distance, and progress percent.
        """
        if not self.points or self.total_route_distance_m <= 0.0:
            return RouteProgressResult(
                distance_along_route_m=0.0,
                total_route_distance_m=0.0,
                remaining_distance_m=0.0,
                progress_percent=0.0,
                nearest_segment_index=None
            )

        # Single point edge case
        if len(self.points) == 1:
            d = haversine_distance_m(lat, lng, self.points[0][0], self.points[0][1])
            return RouteProgressResult(
                distance_along_route_m=0.0,
                total_route_distance_m=0.0,
                remaining_distance_m=d,
                progress_percent=100.0 if d < 20.0 else 0.0,
                nearest_segment_index=0
            )

        # Projection using metric local ENU coordinates centered at query point
        phi0 = math.radians(lat)
        cos_phi0 = math.cos(phi0)

        def to_xy(p_lat: float, p_lng: float) -> Tuple[float, float]:
            x = EARTH_RADIUS_M * math.radians(p_lng - lng) * cos_phi0
            y = EARTH_RADIUS_M * math.radians(p_lat - lat)
            return x, y

        px, py = 0.0, 0.0
        min_cross_track = float("inf")
        best_segment_idx = 0
        best_distance_along = 0.0

        for i in range(len(self.points) - 1):
            ax, ay = to_xy(self.points[i][0], self.points[i][1])
            bx, by = to_xy(self.points[i + 1][0], self.points[i + 1][1])

            vx = bx - ax
            vy = by - ay
            v_len_sq = vx * vx + vy * vy

            if v_len_sq < 1e-9:
                u = 0.0
                dx = px - ax
                dy = py - ay
                dist = math.sqrt(dx * dx + dy * dy)
            else:
                u = ((px - ax) * vx + (py - ay) * vy) / v_len_sq
                u_clamped = max(0.0, min(1.0, u))
                proj_x = ax + u_clamped * vx
                proj_y = ay + u_clamped * vy
                dx = px - proj_x
                dy = py - proj_y
                dist = math.sqrt(dx * dx + dy * dy)

            if dist < min_cross_track:
                min_cross_track = dist
                best_segment_idx = i
                seg_len = self.segment_lengths[i]
                u_along = max(0.0, min(1.0, u)) if v_len_sq >= 1e-9 else 0.0
                best_distance_along = self.cumulative_lengths[i] + (u_along * seg_len)

        # Handle point strictly before route start
        dist_to_start = haversine_distance_m(lat, lng, self.points[0][0], self.points[0][1])
        dist_to_end = haversine_distance_m(lat, lng, self.points[-1][0], self.points[-1][1])

        # If closest to the very end of the route
        if best_segment_idx == len(self.points) - 2 and dist_to_end < 25.0:
            best_distance_along = self.total_route_distance_m

        # Monotonic Progress Safeguard:
        # Small backward jitter due to GPS noise does not jump backward
        d_along = best_distance_along
        if d_along < self.last_distance_along_m:
            drop = self.last_distance_along_m - d_along
            if drop <= self.monotonic_tolerance_m:
                d_along = self.last_distance_along_m
                progress_pct = self.last_progress_percent
            else:
                # Intentional major reversal > tolerance
                raw_pct = (d_along / self.total_route_distance_m) * 100.0
                progress_pct = max(0.0, min(100.0, raw_pct))
        else:
            raw_pct = (d_along / self.total_route_distance_m) * 100.0
            progress_pct = max(0.0, min(100.0, raw_pct))

        self.last_distance_along_m = d_along
        self.last_progress_percent = progress_pct

        remaining_m = max(0.0, self.total_route_distance_m - d_along)

        return RouteProgressResult(
            distance_along_route_m=round(d_along, 1),
            total_route_distance_m=round(self.total_route_distance_m, 1),
            remaining_distance_m=round(remaining_m, 1),
            progress_percent=round(self.last_progress_percent, 1),
            nearest_segment_index=best_segment_idx,
            cross_track_distance_m=round(min_cross_track, 1)
        )
