"""
STREEVA Route Deviation Detection Engine.

Detects whether a traveler has deviated significantly from an expected journey route polyline
using local metric cross-track distance calculations, temporal safeguards, hysteresis corridors,
and GPS accuracy filtering.

NOTE: This is a deterministic geometric/heuristic edge detector, NOT an ML model.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field


class DeviationState(str, Enum):
    """Lifecycle states for route deviation."""
    NORMAL = "NORMAL"
    POSSIBLE_DEVIATION = "POSSIBLE_DEVIATION"
    DEVIATED = "DEVIATED"
    RECOVERED = "RECOVERED"


class RouteDeviationConfig(BaseModel):
    """
    Tunable configuration parameters for the route deviation detector.
    
    Defaults are selected for typical urban GPS conditions (Chennai / metropolitan):
    - deviation_threshold_m: 50.0m (accounts for standard road width ~15-20m + typical urban GPS jitter ~15-25m).
    - normal_threshold_m: 35.0m (hysteresis margin of 15m to prevent rapid oscillation).
    - consecutive_deviations_required: 3 observations (temporal noise filter to suppress single-multipath anomalies).
    - consecutive_recoveries_required: 2 observations (ensures sustained return before clearing deviation).
    - max_acceptable_gps_accuracy_m: 60.0m (degraded readings beyond this cannot trigger deviation).
    """
    deviation_threshold_m: float = Field(
        default=50.0,
        description="Cross-track distance in meters beyond which a position is considered off-route."
    )
    normal_threshold_m: float = Field(
        default=35.0,
        description="Cross-track distance in meters below which a position is considered safely on-route (hysteresis recovery threshold)."
    )
    consecutive_deviations_required: int = Field(
        default=3,
        description="Number of consecutive off-route observations required to transition from POSSIBLE_DEVIATION to DEVIATED."
    )
    consecutive_recoveries_required: int = Field(
        default=2,
        description="Number of consecutive on-route observations required to transition from RECOVERED to NORMAL."
    )
    max_acceptable_gps_accuracy_m: float = Field(
        default=60.0,
        description="Maximum horizontal GPS accuracy uncertainty (meters). Readings with worse accuracy are treated as degraded."
    )


class RouteDeviationEvent(BaseModel):
    """
    Structured telemetry event emitted for each evaluated GPS point.
    """
    event_type: str = "ROUTE_DEVIATION"
    is_deviated: bool = Field(
        ...,
        description="True only if the current state is DEVIATED."
    )
    state: DeviationState = Field(
        ...,
        description="Current state in the deviation state machine."
    )
    deviation_distance_m: float = Field(
        ...,
        description="Calculated perpendicular cross-track distance in meters to the nearest route segment."
    )
    threshold_m: float = Field(
        ...,
        description="Configured deviation threshold in meters."
    )
    recovery_threshold_m: float = Field(
        ...,
        description="Configured recovery threshold in meters."
    )
    confidence: float = Field(
        ...,
        description="Geometric/heuristic confidence score (0.0 to 1.0). NOT an ML probability."
    )
    nearest_segment_index: Optional[int] = Field(
        default=None,
        description="0-indexed identifier of the nearest route segment [i -> i+1]."
    )
    gps_accuracy_m: Optional[float] = Field(
        default=None,
        description="Reported GPS accuracy radius in meters, if supplied by telemetry."
    )
    latitude: float = Field(
        ...,
        description="Latitude of the evaluated GPS point."
    )
    longitude: float = Field(
        ...,
        description="Longitude of the evaluated GPS point."
    )
    timestamp: Optional[datetime] = Field(
        default=None,
        description="Timestamp of the evaluated observation."
    )
    details: Optional[str] = Field(
        default=None,
        description="Human-readable context or explanation of the detection state."
    )


# --- Geographic Math Utilities ---

EARTH_RADIUS_M = 6_371_000.0


def _extract_lat_lng(point: Union[Dict[str, Any], Any]) -> Tuple[float, float]:
    """Extracts (latitude, longitude) floats from dicts or objects."""
    if isinstance(point, dict):
        if "lat" in point and "lng" in point:
            lat, lng = point["lat"], point["lng"]
        elif "latitude" in point and "longitude" in point:
            lat, lng = point["latitude"], point["longitude"]
        else:
            raise ValueError(f"Point dict must contain 'lat' and 'lng': {point}")
    else:
        if hasattr(point, "lat") and hasattr(point, "lng"):
            lat, lng = point.lat, point.lng
        elif hasattr(point, "latitude") and hasattr(point, "longitude"):
            lat, lng = point.latitude, point.longitude
        else:
            raise ValueError(f"Point object must have 'lat' and 'lng' attributes: {point}")

    lat, lng = float(lat), float(lng)
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
        raise ValueError(f"Invalid coordinate bounds: lat={lat}, lng={lng}")
    return lat, lng


def haversine_distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two points on Earth using Haversine formula."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return EARTH_RADIUS_M * c


def compute_cross_track_distance_m(
    lat: float,
    lng: float,
    polyline: List[Union[Dict[str, Any], Any]]
) -> Tuple[float, Optional[int]]:
    """
    Calculates the shortest distance from a GPS coordinate to a polyline in meters.
    
    Uses a local Equirectangular / East-North-Up (ENU) metric projection centered
    at the query point. For urban journeys (< 50 km), distortion is < 0.05%,
    providing exact perpendicular projection onto segments.
    
    Returns:
        (min_distance_m, nearest_segment_index)
    """
    if not polyline:
        return 0.0, None

    points = [_extract_lat_lng(p) for p in polyline]
    if len(points) == 1:
        return haversine_distance_m(lat, lng, points[0][0], points[0][1]), 0

    # Local reference origin for ENU projection
    phi0 = math.radians(lat)
    cos_phi0 = math.cos(phi0)

    def to_xy(p_lat: float, p_lng: float) -> Tuple[float, float]:
        x = EARTH_RADIUS_M * math.radians(p_lng - lng) * cos_phi0
        y = EARTH_RADIUS_M * math.radians(p_lat - lat)
        return x, y

    px, py = 0.0, 0.0  # By definition at origin
    min_dist = float("inf")
    nearest_idx = 0

    for i in range(len(points) - 1):
        ax, ay = to_xy(points[i][0], points[i][1])
        bx, by = to_xy(points[i + 1][0], points[i + 1][1])

        vx = bx - ax
        vy = by - ay
        v_len_sq = vx * vx + vy * vy

        if v_len_sq < 1e-9:
            # Degenerate zero-length segment
            dx = px - ax
            dy = py - ay
            dist = math.sqrt(dx * dx + dy * dy)
        else:
            wx = px - ax
            wy = py - ay
            t = (wx * vx + wy * vy) / v_len_sq
            t_clamped = max(0.0, min(1.0, t))
            qx = ax + t_clamped * vx
            qy = ay + t_clamped * vy
            dx = px - qx
            dy = py - qy
            dist = math.sqrt(dx * dx + dy * dy)

        if dist < min_dist:
            min_dist = dist
            nearest_idx = i

    return min_dist, nearest_idx


# --- Route Deviation Detector Engine ---

class RouteDeviationDetector:
    """
    Stateful Route Deviation Detection Engine.
    
    Maintains sequential observation counters and state transitions with hysteresis
    and GPS noise filtering.
    """

    def __init__(self, config: Optional[RouteDeviationConfig] = None):
        self.config = config or RouteDeviationConfig()
        self.current_state: DeviationState = DeviationState.NORMAL
        self.consecutive_deviations: int = 0
        self.consecutive_recoveries: int = 0

    def reset(self) -> None:
        """Resets the state machine back to initial NORMAL state."""
        self.current_state = DeviationState.NORMAL
        self.consecutive_deviations = 0
        self.consecutive_recoveries = 0

    def detect(
        self,
        current_position: Union[Dict[str, Any], Any],
        route_polyline: List[Union[Dict[str, Any], Any]],
        gps_accuracy: Optional[float] = None,
        timestamp: Optional[datetime] = None
    ) -> RouteDeviationEvent:
        """
        Evaluates a single GPS position against an expected route polyline.

        Args:
            current_position: Dict or object containing lat/lng.
            route_polyline: Ordered sequence of route vertices.
            gps_accuracy: Optional reported horizontal accuracy in meters.
            timestamp: Optional observation datetime.

        Returns:
            RouteDeviationEvent with state, cross-track distance, and confidence.
        """
        lat, lng = _extract_lat_lng(current_position)
        obs_time = timestamp or datetime.now(timezone.utc)

        # 1. Polyline Boundary Checks
        if not route_polyline:
            return RouteDeviationEvent(
                is_deviated=False,
                state=DeviationState.NORMAL,
                deviation_distance_m=0.0,
                threshold_m=self.config.deviation_threshold_m,
                recovery_threshold_m=self.config.normal_threshold_m,
                confidence=0.0,
                nearest_segment_index=None,
                gps_accuracy_m=gps_accuracy,
                latitude=lat,
                longitude=lng,
                timestamp=obs_time,
                details="No route polyline provided. Defaulting to NORMAL."
            )

        # 2. Compute Cross-Track Distance to Nearest Route Segment
        dist_m, nearest_idx = compute_cross_track_distance_m(lat, lng, route_polyline)

        # 3. GPS Accuracy Filtering
        is_accuracy_degraded = (
            gps_accuracy is not None and
            gps_accuracy > self.config.max_acceptable_gps_accuracy_m
        )

        # 4. State Machine Transition Logic with Hysteresis
        prev_state = self.current_state
        details = ""

        if is_accuracy_degraded:
            # Degraded GPS reading: do not allow transitioning into DEVIATED
            details = (
                f"GPS accuracy uncertainty ({gps_accuracy:.1f}m) exceeds acceptable "
                f"threshold ({self.config.max_acceptable_gps_accuracy_m:.1f}m). "
                f"State transitions to DEVIATED are suppressed."
            )
            # Retain current state or downgrade tentative states
            if self.current_state == DeviationState.POSSIBLE_DEVIATION:
                # Do not increment deviation counter with bad accuracy
                pass

        elif dist_m > self.config.deviation_threshold_m:
            # Distance is beyond the outer deviation corridor
            self.consecutive_recoveries = 0

            if self.current_state == DeviationState.NORMAL:
                self.consecutive_deviations = 1
                if self.config.consecutive_deviations_required <= 1:
                    self.current_state = DeviationState.DEVIATED
                    details = f"Deviation detected ({dist_m:.1f}m > {self.config.deviation_threshold_m}m)."
                else:
                    self.current_state = DeviationState.POSSIBLE_DEVIATION
                    details = (
                        f"Possible deviation detected ({dist_m:.1f}m). "
                        f"Observation 1 of {self.config.consecutive_deviations_required} required."
                    )

            elif self.current_state == DeviationState.POSSIBLE_DEVIATION:
                self.consecutive_deviations += 1
                if self.consecutive_deviations >= self.config.consecutive_deviations_required:
                    self.current_state = DeviationState.DEVIATED
                    details = (
                        f"Sustained deviation confirmed ({dist_m:.1f}m > {self.config.deviation_threshold_m}m) "
                        f"after {self.consecutive_deviations} consecutive observations."
                    )
                else:
                    details = (
                        f"Possible deviation sustained ({dist_m:.1f}m). "
                        f"Observation {self.consecutive_deviations} of {self.config.consecutive_deviations_required} required."
                    )

            elif self.current_state == DeviationState.RECOVERED:
                # Flapped back to deviated while in recovery
                self.current_state = DeviationState.DEVIATED
                self.consecutive_deviations = self.config.consecutive_deviations_required
                details = f"Traveler moved back off-route ({dist_m:.1f}m) during recovery."

            elif self.current_state == DeviationState.DEVIATED:
                details = f"Traveler remains deviated ({dist_m:.1f}m from route)."

        elif dist_m <= self.config.normal_threshold_m:
            # Distance is safely inside the normal/recovery corridor
            self.consecutive_deviations = 0

            if self.current_state in (DeviationState.DEVIATED, DeviationState.RECOVERED):
                self.consecutive_recoveries += 1
                if self.consecutive_recoveries >= self.config.consecutive_recoveries_required:
                    self.current_state = DeviationState.NORMAL
                    self.consecutive_recoveries = 0
                    details = (
                        f"Route recovered ({dist_m:.1f}m <= {self.config.normal_threshold_m}m). "
                        f"State returned to NORMAL."
                    )
                else:
                    self.current_state = DeviationState.RECOVERED
                    details = (
                        f"Approaching route ({dist_m:.1f}m <= {self.config.normal_threshold_m}m). "
                        f"Recovery observation {self.consecutive_recoveries} of {self.config.consecutive_recoveries_required} required."
                    )

            elif self.current_state == DeviationState.POSSIBLE_DEVIATION:
                # Transitory spike cleared
                self.current_state = DeviationState.NORMAL
                details = f"Spike dissipated ({dist_m:.1f}m <= {self.config.normal_threshold_m}m). Back to NORMAL."

            else:
                self.current_state = DeviationState.NORMAL
                details = f"Position is on-route ({dist_m:.1f}m <= {self.config.normal_threshold_m}m)."

        else:
            # Hysteresis corridor: normal_threshold_m < dist_m <= deviation_threshold_m
            # Maintain current state to prevent flapping
            details = (
                f"Position within hysteresis corridor ({dist_m:.1f}m between "
                f"{self.config.normal_threshold_m}m and {self.config.deviation_threshold_m}m). "
                f"Retaining state {self.current_state.value}."
            )

        # 5. Compute Geometric / Heuristic Confidence (NOT an ML probability)
        confidence = self._compute_heuristic_confidence(
            dist_m=dist_m,
            gps_accuracy=gps_accuracy,
            state=self.current_state
        )

        return RouteDeviationEvent(
            is_deviated=(self.current_state == DeviationState.DEVIATED),
            state=self.current_state,
            deviation_distance_m=round(dist_m, 2),
            threshold_m=self.config.deviation_threshold_m,
            recovery_threshold_m=self.config.normal_threshold_m,
            confidence=round(confidence, 2),
            nearest_segment_index=nearest_idx,
            gps_accuracy_m=round(gps_accuracy, 1) if gps_accuracy is not None else None,
            latitude=lat,
            longitude=lng,
            timestamp=obs_time,
            details=details
        )

    def _compute_heuristic_confidence(
        self,
        dist_m: float,
        gps_accuracy: Optional[float],
        state: DeviationState
    ) -> float:
        """
        Calculates a deterministic geometric/heuristic confidence score in [0.0, 1.0].
        
        Factors:
        - GPS horizontal accuracy penalty (good accuracy -> high confidence).
        - Margin factor: distance clarity relative to thresholds.
        - Temporal persistence: fully confirmed states (DEVIATED, NORMAL) have higher base confidence.
        """
        # Base accuracy multiplier
        if gps_accuracy is None:
            acc_factor = 0.85
        else:
            # Penalty scales from 1.0 at 0m accuracy to 0.2 at 100m+ accuracy
            acc_factor = max(0.15, min(1.0, 1.0 - (gps_accuracy / 120.0)))

        # Distance clarity factor
        dev_thresh = self.config.deviation_threshold_m
        norm_thresh = self.config.normal_threshold_m

        if state == DeviationState.DEVIATED:
            # Farther past the threshold -> higher confidence that it is a true deviation
            margin = min(1.0, dist_m / (dev_thresh * 1.5))
            state_factor = 0.95
            raw_conf = (0.5 * acc_factor) + (0.3 * margin) + (0.2 * state_factor)

        elif state == DeviationState.POSSIBLE_DEVIATION:
            # Tentative state -> inherently lower confidence
            progression = self.consecutive_deviations / max(1, self.config.consecutive_deviations_required)
            raw_conf = (0.4 * acc_factor) + (0.3 * progression) + 0.2

        elif state == DeviationState.RECOVERED:
            progression = self.consecutive_recoveries / max(1, self.config.consecutive_recoveries_required)
            raw_conf = (0.4 * acc_factor) + (0.3 * progression) + 0.2

        else:  # NORMAL
            # Closer to route -> higher confidence that it is normal
            margin = max(0.0, 1.0 - (dist_m / norm_thresh)) if norm_thresh > 0 else 1.0
            raw_conf = (0.5 * acc_factor) + (0.3 * margin) + 0.2

        return max(0.1, min(1.0, raw_conf))
