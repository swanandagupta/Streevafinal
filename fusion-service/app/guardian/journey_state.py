"""
STREEVA Guardian Journey Intelligence Data Models & State Machine Definitions.

Defines:
- JourneyState: Lifecycle states (IDLE, STARTING, ACTIVE, DEGRADED, ARRIVING, ARRIVED, CANCELLED)
- TelemetryQuality: Telemetry health (VALID, STALE, POOR_ACCURACY, MISSING, RECOVERED)
- ArrivalStatus: Destination arrival progress (NOT_ARRIVED, ARRIVAL_POSSIBLE, ARRIVED)
- ProgressStatus: Schedule and velocity indicators (MOVING_ON_SCHEDULE, SLOW_PROGRESS, STALLED, DELAYED, UNKNOWN)
- ETASource: Provenance of ETA (EXTERNAL, ESTIMATED, UNAVAILABLE)
- GuardianConfig: Tunable journey thresholds
- JourneyContext: Rich active journey state representation
- GuardianSnapshot: Consolidated telemetry frame for future Risk Fusion
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from ..edge.route_deviation import RouteDeviationEvent, DeviationState
from ..edge.unexpected_stop import UnexpectedStopEvent, StopState
from ..edge.fall_detection import FallDetectedEvent, FallState
from ..edge.audio_distress import AudioDistressEvent, DistressAudioState


class JourneyState(str, Enum):
    """Lifecycle states of a monitored traveler journey."""
    IDLE = "IDLE"
    STARTING = "STARTING"
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    ARRIVING = "ARRIVING"
    ARRIVED = "ARRIVED"
    CANCELLED = "CANCELLED"


class TelemetryQuality(str, Enum):
    """Health classification of incoming GPS / sensor telemetry."""
    VALID = "VALID"
    STALE = "STALE"
    POOR_ACCURACY = "POOR_ACCURACY"
    MISSING = "MISSING"
    RECOVERED = "RECOVERED"


class ArrivalStatus(str, Enum):
    """Destination proximity and confirmation status."""
    NOT_ARRIVED = "NOT_ARRIVED"
    ARRIVAL_POSSIBLE = "ARRIVAL_POSSIBLE"
    ARRIVED = "ARRIVED"


class ProgressStatus(str, Enum):
    """Journey progress and delay tracking."""
    MOVING_ON_SCHEDULE = "MOVING_ON_SCHEDULE"
    SLOW_PROGRESS = "SLOW_PROGRESS"
    STALLED = "STALLED"
    DELAYED = "DELAYED"
    UNKNOWN = "UNKNOWN"


class ETASource(str, Enum):
    """Provenance of the current Estimated Time of Arrival."""
    EXTERNAL = "EXTERNAL"
    ESTIMATED = "ESTIMATED"
    UNAVAILABLE = "UNAVAILABLE"


class GuardianConfig(BaseModel):
    """
    Tunable configuration parameters for Guardian Journey Intelligence.
    """
    arrival_radius_m: float = Field(
        default=50.0,
        description="Distance to destination in meters within which arrival checks engage."
    )
    arrival_gps_accuracy_ceiling_m: float = Field(
        default=40.0,
        description="Maximum GPS uncertainty permitted when confirming destination arrival."
    )
    arrival_consecutive_observations_required: int = Field(
        default=2,
        description="Number of consecutive valid observations required to transition from ARRIVAL_POSSIBLE to ARRIVED."
    )
    telemetry_stale_timeout_s: float = Field(
        default=30.0,
        description="Seconds without fresh telemetry before the journey state transitions to DEGRADED (STALE)."
    )
    gps_accuracy_ceiling_m: float = Field(
        default=60.0,
        description="Maximum acceptable GPS horizontal accuracy uncertainty in meters."
    )
    corridor_radius_m: float = Field(
        default=50.0,
        description="Authoritative corridor margin around the expected polyline."
    )
    min_movement_speed_mps: float = Field(
        default=0.5,
        description="Speed in m/s below which traveler is considered stationary."
    )
    default_travel_speed_mps: float = Field(
        default=1.3,
        description="Default baseline speed in m/s (~4.7 km/h urban walking) for fallback ETA calculations."
    )
    eta_smoothing_alpha: float = Field(
        default=0.4,
        description="Exponential smoothing factor for speed/ETA calculations (0.0 = fixed, 1.0 = raw)."
    )
    delay_threshold_s: float = Field(
        default=180.0,
        description="Seconds past expected schedule or prolonged delay before flagging DELAYED."
    )
    progress_monotonic_tolerance_m: float = Field(
        default=50.0,
        description="Tolerance in meters for GPS noise before allowing route progress percentage to decrease."
    )


class JourneyContext(BaseModel):
    """
    Comprehensive state representation of an active journey.
    """
    journey_id: str
    source_lat: float
    source_lng: float
    destination_lat: float
    destination_lng: float
    expected_route: List[Dict[str, float]] = Field(default_factory=list)
    expected_duration_s: Optional[float] = None
    
    journey_state: JourneyState = JourneyState.IDLE
    journey_start_time: Optional[datetime] = None
    current_timestamp: Optional[datetime] = None
    
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None
    gps_accuracy: Optional[float] = None
    
    telemetry_quality: TelemetryQuality = TelemetryQuality.MISSING
    degraded_reason: Optional[str] = None
    
    route_progress_percent: float = 0.0
    distance_along_route_m: float = 0.0
    total_route_distance_m: float = 0.0
    remaining_distance_m: float = 0.0
    
    eta: Optional[datetime] = None
    eta_source: ETASource = ETASource.UNAVAILABLE
    smoothed_speed_mps: float = 0.0
    
    arrival_status: ArrivalStatus = ArrivalStatus.NOT_ARRIVED
    progress_status: ProgressStatus = ProgressStatus.UNKNOWN
    
    last_valid_telemetry_time: Optional[datetime] = None
    last_movement_time: Optional[datetime] = None

    # Telemetry and route adherence tracking
    total_gps_observations: int = 0
    valid_gps_observations: int = 0
    corridor_conforming_observations: int = 0
    deviated_observations: int = 0
    cumulative_distance_travelled_m: float = 0.0
    last_obs_lat: Optional[float] = None
    last_obs_lng: Optional[float] = None


class GuardianSnapshot(BaseModel):
    """
    Consolidated telemetry and Edge AI snapshot emitted by Guardian Journey Intelligence.
    Designed for consumption by future Risk Fusion and Decision layers.
    
    NOTE: Does NOT compute 0-100 risk score or trigger emergency dispatch.
    """
    journey_id: str
    timestamp: datetime
    journey_state: JourneyState
    
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None
    gps_accuracy: Optional[float] = None
    telemetry_quality: TelemetryQuality
    degraded_reason: Optional[str] = None
    
    route_progress_percent: float
    distance_along_route_m: float
    total_route_distance_m: float
    remaining_distance_m: float
    
    eta: Optional[datetime] = None
    eta_source: ETASource
    smoothed_speed_mps: float
    
    arrival_status: ArrivalStatus
    progress_status: ProgressStatus
    
    # Journey adherence & summary telemetry
    route_adherence_percent: Optional[float] = None
    distance_travelled_m: float = 0.0
    actual_duration_s: float = 0.0
    valid_observations_count: int = 0

    # Edge detector events (consumed directly, never duplicated)
    route_deviation: Optional[RouteDeviationEvent] = None
    unexpected_stop: Optional[UnexpectedStopEvent] = None
    fall_event: Optional[FallDetectedEvent] = None
    audio_distress: Optional[AudioDistressEvent] = None
    
    active_anomalies: List[str] = Field(default_factory=list)
    details: Optional[str] = None


# --- API Request Models ---

class JourneyStartRequest(BaseModel):
    journey_id: str
    source_lat: float
    source_lng: float
    destination_lat: float
    destination_lng: float
    expected_route: Optional[List[Dict[str, float]]] = Field(
        default=None,
        description="Optional ordered sequence of {'lat': float, 'lng': float} waypoints."
    )
    expected_duration_s: Optional[float] = Field(
        default=None,
        description="Optional expected journey duration in seconds."
    )
    external_eta: Optional[datetime] = Field(
        default=None,
        description="Optional external routing provider ETA."
    )
    timestamp: Optional[datetime] = None


class JourneyUpdateRequest(BaseModel):
    journey_id: str
    latitude: float
    longitude: float
    gps_accuracy: Optional[float] = Field(default=None, description="GPS horizontal accuracy in meters")
    timestamp: Optional[datetime] = None
    
    # Optional Inertial sensor telemetry for Fall Detection
    accel_x: Optional[float] = None
    accel_y: Optional[float] = None
    accel_z: Optional[float] = None
    gyro_x: Optional[float] = None
    gyro_y: Optional[float] = None
    gyro_z: Optional[float] = None
    
    # Optional Audio telemetry for Distress Audio Detection
    audio_samples: Optional[List[float]] = None
    base64_audio: Optional[str] = None
    
    # Optional dynamic external ETA update
    external_eta: Optional[datetime] = None


class JourneyEndRequest(BaseModel):
    journey_id: str
    reason: Optional[str] = Field(default="USER_CANCELLED", description="Reason for ending journey")
    timestamp: Optional[datetime] = None
