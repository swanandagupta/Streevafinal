"""
STREEVA Gyroscope & Accelerometer Fall Detection Engine (Phase 1C).

Detects accidental falls using multi-stage kinematic verification:
1. High-g impact spike (|a| >= 2.5g)
2. Significant orientation change (>= 45 deg via gyroscope or gravitational tilt)
3. Post-impact stillness / inactivity confirmation (>= 2.0s of low acceleration variance)
4. Graceful sensor degradation (supports Accel + Gyro, or Accel-only without fabricating gyro values)

NOTE: This is a deterministic kinematic/sensor edge detector, NOT an ML model.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field

GRAVITY_MPS2 = 9.80665


class FallState(str, Enum):
    """Lifecycle states for fall detection."""
    NORMAL = "NORMAL"
    POSSIBLE_IMPACT = "POSSIBLE_IMPACT"
    POSSIBLE_FALL = "POSSIBLE_FALL"
    FALL_DETECTED = "FALL_DETECTED"
    RECOVERED = "RECOVERED"


class SensorMode(str, Enum):
    """Sensor availability mode."""
    ACCEL_AND_GYRO = "accel_and_gyro"
    ACCEL_ONLY = "accel_only"
    INSUFFICIENT_DATA = "insufficient_data"


class FallDetectionConfig(BaseModel):
    """
    Tunable configuration parameters for the multi-stage fall detector.

    Defaults:
    - impact_threshold_g: 2.5g (~24.5 m/s2; human falls typically peak at 2.5g - 6.0g).
    - orientation_change_threshold_deg: 45.0 deg (tilt change from upright to recumbent).
    - gyro_angular_velocity_threshold_dps: 120.0 deg/s (rotational velocity during fall impact).
    - post_impact_inactivity_duration_s: 2.0 s (period of low motion confirming victim is down).
    - inactivity_accel_variance_max: 0.5 (maximum variance in magnitude during stillness).
    - recovery_motion_threshold_g: 0.6 (magnitude deviation indicating standing up or recovery).
    - consecutive_recovery_observations: 2 (readings required to establish recovery).
    """
    impact_threshold_g: float = Field(
        default=2.5,
        description="Acceleration magnitude in units of g (9.81 m/s2) required to register an impact spike."
    )
    orientation_change_threshold_deg: float = Field(
        default=45.0,
        description="Minimum angular posture change in degrees required to confirm fall orientation."
    )
    gyro_angular_velocity_threshold_dps: float = Field(
        default=120.0,
        description="Minimum rotational rate in deg/s during impact to confirm angular rotation."
    )
    post_impact_inactivity_duration_s: float = Field(
        default=2.0,
        description="Duration in seconds of post-impact stillness required to confirm a fall."
    )
    inactivity_accel_variance_max: float = Field(
        default=0.5,
        description="Maximum acceleration variance allowed during the post-impact inactivity window."
    )
    recovery_motion_threshold_g: float = Field(
        default=0.6,
        description="Deviation from 1.0g required to indicate active movement after a fall."
    )
    consecutive_recovery_observations: int = Field(
        default=2,
        description="Consecutive motion observations needed to transition from FALL_DETECTED to RECOVERED."
    )


class FallDetectedEvent(BaseModel):
    """
    Structured telemetry event emitted for each evaluated inertial observation.
    """
    event_type: str = "FALL_DETECTED"
    is_fall: bool = Field(
        ...,
        description="True only if the current state is FALL_DETECTED."
    )
    state: FallState = Field(
        ...,
        description="Current state in the fall detection state machine."
    )
    impact_magnitude_g: float = Field(
        ...,
        description="Measured peak acceleration magnitude in units of g."
    )
    orientation_change_deg: Optional[float] = Field(
        default=None,
        description="Estimated angular orientation change in degrees, if computable."
    )
    confidence: float = Field(
        ...,
        description="Heuristic kinematic confidence score (0.0 to 1.0). NOT an ML probability."
    )
    sensor_mode: SensorMode = Field(
        ...,
        description="Mode indicating whether both accelerometer and gyroscope were available."
    )
    timestamp: Optional[datetime] = Field(
        default=None,
        description="Timestamp of the evaluated observation."
    )
    latitude: Optional[float] = Field(
        default=None,
        description="Latitude where the inertial event occurred, if available."
    )
    longitude: Optional[float] = Field(
        default=None,
        description="Longitude where the inertial event occurred, if available."
    )
    details: Optional[str] = Field(
        default=None,
        description="Human-readable context or explanation of the detection state."
    )


class FallDetector:
    """
    Stateful Multi-Stage Gyroscope & Accelerometer Fall Detector.

    Verifies the sequential kinematic phases of a genuine fall:
    Impact Spike -> Orientation Change -> Post-Impact Inactivity.
    """

    def __init__(self, config: Optional[FallDetectionConfig] = None):
        self.config = config or FallDetectionConfig()
        self.current_state: FallState = FallState.NORMAL
        self.pre_impact_vectors: List[Tuple[float, float, float]] = []
        self.post_impact_samples: List[float] = []
        self.impact_time: Optional[datetime] = None
        self.peak_impact_g: float = 1.0
        self.observed_orientation_change: Optional[float] = None
        self.consecutive_recoveries: int = 0

    def reset(self) -> None:
        """Resets the state machine to initial NORMAL state."""
        self.current_state = FallState.NORMAL
        self.pre_impact_vectors = []
        self.post_impact_samples = []
        self.impact_time = None
        self.peak_impact_g = 1.0
        self.observed_orientation_change = None
        self.consecutive_recoveries = 0

    def detect(
        self,
        accel_x: float,
        accel_y: float,
        accel_z: float,
        gyro_x: Optional[float] = None,
        gyro_y: Optional[float] = None,
        gyro_z: Optional[float] = None,
        timestamp: Optional[datetime] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None
    ) -> FallDetectedEvent:
        """
        Evaluates a single inertial sensor frame for fall signatures.

        Args:
            accel_x, accel_y, accel_z: Acceleration in m/s2 or units of g.
                If values exceed 4.0, treated as m/s2 and converted to g.
            gyro_x, gyro_y, gyro_z: Optional rotational velocity in deg/s.
            timestamp: Observation datetime.
            latitude, longitude: Optional geographic coordinates.

        Returns:
            FallDetectedEvent.
        """
        obs_time = timestamp or datetime.now(timezone.utc)

        # 1. Standardize Accelerometer into units of g
        # If absolute components exceed 4.0, values are in SI m/s2 (where 1g = 9.81 m/s2)
        raw_mag = math.sqrt(accel_x * accel_x + accel_y * accel_y + accel_z * accel_z)
        if raw_mag > 4.0:
            ax = accel_x / GRAVITY_MPS2
            ay = accel_y / GRAVITY_MPS2
            az = accel_z / GRAVITY_MPS2
            mag_g = raw_mag / GRAVITY_MPS2
        else:
            ax, ay, az = accel_x, accel_y, accel_z
            mag_g = raw_mag

        # 2. Check Gyroscope Availability
        has_gyro = (gyro_x is not None and gyro_y is not None and gyro_z is not None)
        sensor_mode = SensorMode.ACCEL_AND_GYRO if has_gyro else SensorMode.ACCEL_ONLY

        gyro_rate_dps = 0.0
        if has_gyro:
            gyro_rate_dps = math.sqrt(gyro_x * gyro_x + gyro_y * gyro_y + gyro_z * gyro_z)

        # Maintain running pre-impact posture baseline (only normal non-impact samples)
        if self.current_state == FallState.NORMAL and mag_g < self.config.impact_threshold_g:
            self.pre_impact_vectors.append((ax, ay, az))
            if len(self.pre_impact_vectors) > 10:
                self.pre_impact_vectors.pop(0)

        details = ""

        # 3. State Machine Progression
        if self.current_state == FallState.NORMAL:
            self.consecutive_recoveries = 0
            if mag_g >= self.config.impact_threshold_g:
                # Stage 1 Triggered: Impact Spike detected
                self.current_state = FallState.POSSIBLE_IMPACT
                self.impact_time = obs_time
                self.peak_impact_g = mag_g
                self.post_impact_samples = []

                # Check Orientation Change immediately or begin tracking
                orientation_change = self._evaluate_orientation_change(
                    ax, ay, az, gyro_rate_dps, has_gyro
                )
                self.observed_orientation_change = orientation_change

                if orientation_change is not None and orientation_change >= self.config.orientation_change_threshold_deg:
                    self.current_state = FallState.POSSIBLE_FALL
                    self.post_impact_samples = []
                    details = (
                        f"Impact spike ({mag_g:.2f}g) and orientation change ({orientation_change:.1f} deg) "
                        f"detected. Monitoring post-impact stillness."
                    )
                else:
                    details = f"Impact spike ({mag_g:.2f}g) detected. Verifying orientation change."
            else:
                self.peak_impact_g = mag_g
                self.observed_orientation_change = None
                details = f"Normal motion ({mag_g:.2f}g)."

        elif self.current_state == FallState.POSSIBLE_IMPACT:
            # Stage 2: Verify orientation change
            if mag_g > self.peak_impact_g:
                self.peak_impact_g = mag_g

            orientation_change = self._evaluate_orientation_change(
                ax, ay, az, gyro_rate_dps, has_gyro
            )
            self.observed_orientation_change = orientation_change

            if orientation_change is not None and orientation_change >= self.config.orientation_change_threshold_deg:
                self.current_state = FallState.POSSIBLE_FALL
                self.post_impact_samples = []
                details = (
                    f"Orientation change confirmed ({orientation_change:.1f} deg). "
                    f"Awaiting {self.config.post_impact_inactivity_duration_s:.1f}s post-impact stillness."
                )

            else:
                # Impact without orientation change (e.g. jumping or running) -> false alarm
                self.current_state = FallState.NORMAL
                self.observed_orientation_change = orientation_change
                details = (
                    f"Impact spike without significant orientation change "
                    f"({orientation_change if orientation_change is not None else 0.0:.1f} deg < "
                    f"{self.config.orientation_change_threshold_deg} deg). Cleared to NORMAL."
                )

        elif self.current_state == FallState.POSSIBLE_FALL:
            # Stage 3: Verify post-impact stillness / inactivity
            self.post_impact_samples.append(mag_g)
            elapsed_s = (obs_time - self.impact_time).total_seconds() if self.impact_time else 0.0

            # Check if active movement resumed prematurely (e.g. dropped phone picked up, or walking)
            if abs(mag_g - 1.0) > 0.8 or mag_g > 1.8:
                self.current_state = FallState.NORMAL
                details = (
                    f"Active motion resumed ({mag_g:.2f}g) during post-impact window. "
                    f"Cleared false fall to NORMAL."
                )
            elif elapsed_s >= self.config.post_impact_inactivity_duration_s:
                # Stillness confirmed for required duration
                variance = self._calculate_variance(self.post_impact_samples)
                if variance <= self.config.inactivity_accel_variance_max:
                    self.current_state = FallState.FALL_DETECTED
                    details = (
                        f"Fall confirmed: Impact {self.peak_impact_g:.2f}g, "
                        f"orientation change {self.observed_orientation_change or 0.0:.1f} deg, "
                        f"post-impact stillness verified ({elapsed_s:.1f}s, var={variance:.2f})."
                    )
                else:
                    self.current_state = FallState.NORMAL
                    details = f"Motion variance too high ({variance:.2f} > {self.config.inactivity_accel_variance_max}). Cleared."
            else:
                details = f"Stillness monitoring in progress ({elapsed_s:.1f}s / {self.config.post_impact_inactivity_duration_s:.1f}s)."

        elif self.current_state == FallState.FALL_DETECTED:
            # Check for recovery: traveler stands up or moves away
            if abs(mag_g - 1.0) >= self.config.recovery_motion_threshold_g:
                self.consecutive_recoveries += 1
                if self.consecutive_recoveries >= self.config.consecutive_recovery_observations:
                    self.current_state = FallState.RECOVERED
                    details = f"Post-fall movement detected ({mag_g:.2f}g). State changed to RECOVERED."
                else:
                    details = f"Recovery movement detected ({self.consecutive_recoveries}/{self.config.consecutive_recovery_observations})."
            else:
                self.consecutive_recoveries = 0
                details = "Victim remains stationary following confirmed fall."

        elif self.current_state == FallState.RECOVERED:
            # Moving again normally
            if abs(mag_g - 1.0) < self.config.recovery_motion_threshold_g:
                # Settled back to normal walking/resting
                self.current_state = FallState.NORMAL
                details = "Motion stabilized. State returned to NORMAL."
            else:
                details = f"Traveler in recovery motion ({mag_g:.2f}g)."

        # 4. Compute Heuristic Confidence (NOT an ML probability)
        confidence = self._compute_heuristic_confidence(
            impact_g=self.peak_impact_g,
            orientation_deg=self.observed_orientation_change,
            sensor_mode=sensor_mode,
            state=self.current_state
        )

        return FallDetectedEvent(
            event_type="FALL_DETECTED",
            is_fall=(self.current_state == FallState.FALL_DETECTED),
            state=self.current_state,
            impact_magnitude_g=round(self.peak_impact_g, 2),
            orientation_change_deg=round(self.observed_orientation_change, 1) if self.observed_orientation_change is not None else None,
            confidence=round(confidence, 2),
            sensor_mode=sensor_mode,
            timestamp=obs_time,
            latitude=latitude,
            longitude=longitude,
            details=details
        )

    def _evaluate_orientation_change(
        self,
        ax: float,
        ay: float,
        az: float,
        gyro_rate_dps: float,
        has_gyro: bool
    ) -> Optional[float]:
        """
        Evaluates orientation/posture change.
        - With Gyro: Combines rotational rate and tilt.
        - Without Gyro: Calculates gravitational tilt angle between pre-impact and post-impact vectors.
        """
        if has_gyro and gyro_rate_dps >= self.config.gyro_angular_velocity_threshold_dps:
            # Gyro confirms intense rotation during impact
            # Estimate orientation change angle (deg)
            return max(50.0, min(90.0, gyro_rate_dps * 0.4))

        # Fallback to Accelerometer Gravity Vector Tilt
        if not self.pre_impact_vectors:
            return 0.0

        # Average pre-impact static vector
        pre_x = sum(v[0] for v in self.pre_impact_vectors) / len(self.pre_impact_vectors)
        pre_y = sum(v[1] for v in self.pre_impact_vectors) / len(self.pre_impact_vectors)
        pre_z = sum(v[2] for v in self.pre_impact_vectors) / len(self.pre_impact_vectors)

        pre_norm = math.sqrt(pre_x * pre_x + pre_y * pre_y + pre_z * pre_z)
        cur_norm = math.sqrt(ax * ax + ay * ay + az * az)

        if pre_norm < 1e-6 or cur_norm < 1e-6:
            return 0.0

        dot_product = (pre_x * ax + pre_y * ay + pre_z * az) / (pre_norm * cur_norm)
        clamped_dot = max(-1.0, min(1.0, dot_product))
        angle_rad = math.acos(clamped_dot)
        return math.degrees(angle_rad)

    def _calculate_variance(self, samples: List[float]) -> float:
        """Calculates sample variance for stillness verification."""
        if len(samples) < 2:
            return 0.0
        mean = sum(samples) / len(samples)
        return sum((s - mean) ** 2 for s in samples) / (len(samples) - 1)

    def _compute_heuristic_confidence(
        self,
        impact_g: float,
        orientation_deg: Optional[float],
        sensor_mode: SensorMode,
        state: FallState
    ) -> float:
        """
        Calculates a deterministic geometric/kinematic confidence score in [0.0, 1.0].
        
        Factors:
        - Sensor mode: Accel + Gyro receives bonus over Accel-only.
        - Impact margin: clarity beyond impact threshold.
        - Orientation margin: clarity beyond orientation threshold.
        - State confirmation: FALL_DETECTED vs intermediate states.
        """
        sensor_factor = 0.95 if sensor_mode == SensorMode.ACCEL_AND_GYRO else 0.80

        # Impact clarity
        impact_factor = min(1.0, impact_g / (self.config.impact_threshold_g * 1.5))

        # Orientation clarity
        deg = orientation_deg if orientation_deg is not None else 0.0
        orient_factor = min(1.0, deg / (self.config.orientation_change_threshold_deg * 1.5))

        if state == FallState.FALL_DETECTED:
            raw_conf = (0.35 * sensor_factor) + (0.35 * impact_factor) + (0.30 * orient_factor)
            return max(0.65, min(1.0, raw_conf))
        elif state in (FallState.POSSIBLE_IMPACT, FallState.POSSIBLE_FALL):
            raw_conf = (0.3 * sensor_factor) + (0.4 * impact_factor) + (0.3 * orient_factor)
            return max(0.3, min(0.75, raw_conf))
        elif state == FallState.RECOVERED:
            return 0.85
        else:  # NORMAL
            return 0.95
