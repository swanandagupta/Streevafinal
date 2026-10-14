"""
STREEVA Unexpected Stop Detection Engine (Phase 1B).

Detects whether a traveler has unexpectedly halted during an active journey
using velocity, geographic displacement analysis, stationary duration tracking,
hysteresis, and GPS accuracy protection.

NOTE: This is a deterministic temporal/telemetry edge detector, NOT an ML model.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional, Tuple, Union
from pydantic import BaseModel, Field

from .route_deviation import haversine_distance_m, _extract_lat_lng


class StopState(str, Enum):
    """Lifecycle states for unexpected stop detection."""
    MOVING = "MOVING"
    POSSIBLE_STOP = "POSSIBLE_STOP"
    STOPPED = "STOPPED"
    RECOVERING = "RECOVERING"


class UnexpectedStopConfig(BaseModel):
    """
    Tunable configuration parameters for unexpected stop detection.
    
    Defaults:
    - stop_speed_threshold_mps: 0.5 m/s (~1.8 km/h; below typical walking speed ~1.2-1.4 m/s).
    - possible_stop_duration_s: 15.0 s (tentative pause; triggers POSSIBLE_STOP).
    - minimum_stop_duration_s: 45.0 s (filters normal urban traffic signals ~30-40s before confirming STOPPED).
    - recovery_speed_threshold_mps: 1.0 m/s (~3.6 km/h; hysteresis speed to clear stop).
    - consecutive_recovery_observations: 2 observations (ensures sustained movement before returning to MOVING).
    - gps_accuracy_limit_m: 50.0 m (degraded GPS uncertainty blocks false STOPPED transitions).
    - max_time_gap_s: 120.0 s (time gaps larger than this reset velocity tracking safely).
    """
    stop_speed_threshold_mps: float = Field(
        default=0.5,
        description="Speed threshold in m/s below which a traveler is considered stationary."
    )
    possible_stop_duration_s: float = Field(
        default=15.0,
        description="Duration in seconds of sub-threshold speed before transitioning to POSSIBLE_STOP."
    )
    minimum_stop_duration_s: float = Field(
        default=45.0,
        description="Duration in seconds of sub-threshold speed before confirming STOPPED state."
    )
    recovery_speed_threshold_mps: float = Field(
        default=1.0,
        description="Speed in m/s required to initiate recovery towards MOVING state (hysteresis threshold)."
    )
    consecutive_recovery_observations: int = Field(
        default=2,
        description="Number of consecutive recovery speed observations needed to restore MOVING state."
    )
    gps_accuracy_limit_m: float = Field(
        default=50.0,
        description="Maximum GPS horizontal accuracy uncertainty in meters. Degraded points cannot trigger STOPPED."
    )
    max_time_gap_s: float = Field(
        default=120.0,
        description="Maximum gap between observations in seconds before resetting temporal baseline."
    )


class UnexpectedStopEvent(BaseModel):
    """
    Structured telemetry event emitted for each evaluated position.
    """
    event_type: str = "UNEXPECTED_STOP"
    is_stopped: bool = Field(
        ...,
        description="True only if the current state is STOPPED."
    )
    state: StopState = Field(
        ...,
        description="Current state in the unexpected stop state machine."
    )
    stationary_duration_s: float = Field(
        ...,
        description="Seconds elapsed since the traveler became stationary (0.0 if moving)."
    )
    speed_mps: float = Field(
        ...,
        description="Calculated ground speed in meters per second."
    )
    confidence: float = Field(
        ...,
        description="Heuristic/telemetry confidence score (0.0 to 1.0). NOT an ML probability."
    )
    gps_accuracy_m: Optional[float] = Field(
        default=None,
        description="Reported GPS accuracy radius in meters, if supplied."
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
    journey_active: bool = Field(
        default=True,
        description="Indicates if an active journey is in progress."
    )
    details: Optional[str] = Field(
        default=None,
        description="Human-readable context or explanation of the detection state."
    )


class UnexpectedStopDetector:
    """
    Stateful Unexpected Stop Detection Engine.
    
    Maintains sequential displacement history, stationary duration timers,
    hysteresis recovery, and GPS accuracy protection.
    """

    def __init__(self, config: Optional[UnexpectedStopConfig] = None):
        self.config = config or UnexpectedStopConfig()
        self.current_state: StopState = StopState.MOVING
        self.stationary_start_time: Optional[datetime] = None
        self.last_position: Optional[Tuple[float, float]] = None
        self.last_timestamp: Optional[datetime] = None
        self.consecutive_recoveries: int = 0

    def reset(self) -> None:
        """Resets the state machine back to initial MOVING state."""
        self.current_state = StopState.MOVING
        self.stationary_start_time = None
        self.last_position = None
        self.last_timestamp = None
        self.consecutive_recoveries = 0

    def detect(
        self,
        current_position: Union[Dict[str, Any], Any],
        timestamp: Optional[datetime] = None,
        gps_accuracy: Optional[float] = None,
        journey_active: bool = True
    ) -> UnexpectedStopEvent:
        """
        Evaluates a single GPS position against movement history to detect unexpected stops.

        Args:
            current_position: Dict or object containing lat/lng.
            timestamp: Observation datetime.
            gps_accuracy: Optional reported horizontal accuracy in meters.
            journey_active: Optional boolean flag indicating whether a journey is ongoing.

        Returns:
            UnexpectedStopEvent with state, stationary duration, speed, and confidence.
        """
        lat, lng = _extract_lat_lng(current_position)
        obs_time = timestamp or datetime.now(timezone.utc)

        # 1. Calculate Velocity from Displacement
        speed_mps = 0.0
        dt = 0.0
        prev_timestamp = self.last_timestamp

        if self.last_position is not None and self.last_timestamp is not None:
            dt = (obs_time - self.last_timestamp).total_seconds()

            if dt > 0 and dt <= self.config.max_time_gap_s:
                dist_m = haversine_distance_m(
                    self.last_position[0], self.last_position[1],
                    lat, lng
                )
                speed_mps = dist_m / dt
            elif dt > self.config.max_time_gap_s:
                # Discontinuity in telemetry stream; reset temporal baseline
                self.stationary_start_time = None
                self.consecutive_recoveries = 0
                self.current_state = StopState.MOVING
                prev_timestamp = None
                speed_mps = 0.0
        else:
            # First observation in session: assume nominal walking speed initially
            speed_mps = 1.2

        self.last_position = (lat, lng)
        self.last_timestamp = obs_time


        # 2. Check GPS Accuracy Degradation
        is_accuracy_degraded = (
            gps_accuracy is not None and
            gps_accuracy > self.config.gps_accuracy_limit_m
        )

        # 3. State Machine & Stationary Duration
        details = ""
        stationary_duration = 0.0

        if not journey_active:
            # Journey is not active; traveler is expected to be stationary
            self.current_state = StopState.MOVING
            self.stationary_start_time = None
            details = "Journey inactive; unexpected stop evaluation bypassed."
            stationary_duration = 0.0

        elif is_accuracy_degraded:
            # High GPS uncertainty; do not allow state transition to STOPPED
            details = (
                f"GPS accuracy uncertainty ({gps_accuracy:.1f}m) exceeds limit "
                f"({self.config.gps_accuracy_limit_m:.1f}m). State transition to STOPPED suppressed."
            )
            if self.stationary_start_time is not None:
                stationary_duration = (obs_time - self.stationary_start_time).total_seconds()

        elif speed_mps < self.config.stop_speed_threshold_mps:
            # Speed is below stationary threshold
            if self.stationary_start_time is None:
                self.stationary_start_time = prev_timestamp or obs_time

            stationary_duration = (obs_time - self.stationary_start_time).total_seconds()
            self.consecutive_recoveries = 0


            if stationary_duration >= self.config.minimum_stop_duration_s:
                self.current_state = StopState.STOPPED
                details = (
                    f"Unexpected stop confirmed: stationary for {stationary_duration:.1f}s "
                    f"(>= {self.config.minimum_stop_duration_s:.1f}s threshold) at {speed_mps:.2f} m/s."
                )
            elif stationary_duration >= self.config.possible_stop_duration_s:
                if self.current_state == StopState.MOVING:
                    self.current_state = StopState.POSSIBLE_STOP
                details = (
                    f"Possible stop: stationary for {stationary_duration:.1f}s "
                    f"(waiting for {self.config.minimum_stop_duration_s:.1f}s)."
                )
            else:
                details = f"Brief pause ({stationary_duration:.1f}s); below alert threshold."

        elif speed_mps >= self.config.recovery_speed_threshold_mps:
            # Speed is safely above recovery threshold
            if self.current_state in (StopState.STOPPED, StopState.RECOVERING):
                self.consecutive_recoveries += 1
                if self.consecutive_recoveries >= self.config.consecutive_recovery_observations:
                    self.current_state = StopState.MOVING
                    self.stationary_start_time = None
                    self.consecutive_recoveries = 0
                    details = (
                        f"Movement resumed ({speed_mps:.2f} m/s >= {self.config.recovery_speed_threshold_mps:.2f} m/s). "
                        f"Returned to MOVING state."
                    )
                else:
                    self.current_state = StopState.RECOVERING
                    details = (
                        f"Movement detected ({speed_mps:.2f} m/s). "
                        f"Recovery observation {self.consecutive_recoveries} of "
                        f"{self.config.consecutive_recovery_observations} required."
                    )
            elif self.current_state == StopState.POSSIBLE_STOP:
                self.current_state = StopState.MOVING
                self.stationary_start_time = None
                details = f"Movement resumed ({speed_mps:.2f} m/s). Cleared POSSIBLE_STOP."
            else:
                self.current_state = StopState.MOVING
                self.stationary_start_time = None
                details = f"Traveler is moving at {speed_mps:.2f} m/s."

        else:
            # Hysteresis corridor: stop_speed_threshold <= speed < recovery_speed_threshold
            # (e.g. 0.5 m/s to 1.0 m/s; slow loitering/creeping)
            if self.stationary_start_time is not None:
                stationary_duration = (obs_time - self.stationary_start_time).total_seconds()
            details = (
                f"Speed ({speed_mps:.2f} m/s) within hysteresis corridor "
                f"({self.config.stop_speed_threshold_mps:.2f} - {self.config.recovery_speed_threshold_mps:.2f} m/s). "
                f"Retaining state {self.current_state.value}."
            )

        # 4. Compute Heuristic Confidence (NOT an ML probability)
        confidence = self._compute_heuristic_confidence(
            speed_mps=speed_mps,
            stationary_duration=stationary_duration,
            gps_accuracy=gps_accuracy,
            state=self.current_state
        )

        return UnexpectedStopEvent(
            is_stopped=(self.current_state == StopState.STOPPED),
            state=self.current_state,
            stationary_duration_s=round(stationary_duration, 1),
            speed_mps=round(speed_mps, 2),
            confidence=round(confidence, 2),
            gps_accuracy_m=round(gps_accuracy, 1) if gps_accuracy is not None else None,
            latitude=lat,
            longitude=lng,
            timestamp=obs_time,
            journey_active=journey_active,
            details=details
        )

    def _compute_heuristic_confidence(
        self,
        speed_mps: float,
        stationary_duration: float,
        gps_accuracy: Optional[float],
        state: StopState
    ) -> float:
        """
        Calculates a deterministic geometric/telemetry confidence score in [0.0, 1.0].
        
        Factors:
        - GPS accuracy multiplier (good accuracy -> high confidence).
        - Duration progress relative to minimum stop threshold.
        - Speed clarity: how definitively below threshold the velocity is.
        """
        if gps_accuracy is None:
            acc_factor = 0.85
        else:
            acc_factor = max(0.15, min(1.0, 1.0 - (gps_accuracy / 100.0)))

        min_dur = max(1.0, self.config.minimum_stop_duration_s)

        if state == StopState.STOPPED:
            dur_factor = min(1.0, stationary_duration / (min_dur * 1.5))
            raw_conf = (0.5 * acc_factor) + (0.3 * dur_factor) + 0.2

        elif state == StopState.POSSIBLE_STOP:
            dur_factor = stationary_duration / min_dur
            raw_conf = (0.4 * acc_factor) + (0.4 * dur_factor) + 0.1

        elif state == StopState.RECOVERING:
            progression = self.consecutive_recoveries / max(1, self.config.consecutive_recovery_observations)
            raw_conf = (0.4 * acc_factor) + (0.4 * progression) + 0.1

        else:  # MOVING
            # Faster moving -> higher confidence that it is moving
            speed_factor = min(1.0, speed_mps / 2.0)
            raw_conf = (0.5 * acc_factor) + (0.3 * speed_factor) + 0.2

        return max(0.1, min(1.0, raw_conf))
