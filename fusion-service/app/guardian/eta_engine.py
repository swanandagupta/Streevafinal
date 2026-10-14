"""
STREEVA Estimated Time of Arrival (ETA) & Progress Intelligence Engine (Phase 2C).

Implements:
- Multiple ETA sources (External, Deterministic Fallback, Unavailable)
- Speed smoothing with exponential moving average
- Protection against zero-speed division and absurd estimates
- Delay & schedule tracking (MOVING_ON_SCHEDULE, SLOW_PROGRESS, STALLED, DELAYED)
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional
from pydantic import BaseModel

from .journey_state import ETASource, ProgressStatus, GuardianConfig


class ETAResult(BaseModel):
    """Output contract for ETA calculation."""
    eta: Optional[datetime] = None
    eta_source: ETASource = ETASource.UNAVAILABLE
    smoothed_speed_mps: float = 0.0
    estimated_remaining_seconds: Optional[float] = None
    progress_status: ProgressStatus = ProgressStatus.UNKNOWN


class ETAEngine:
    """
    Stateful ETA & Progress Calculation Engine.
    """

    def __init__(self, config: Optional[GuardianConfig] = None):
        self.config = config or GuardianConfig()
        self.smoothed_speed_mps: float = 0.0
        self.last_estimated_eta: Optional[datetime] = None

    def reset(self) -> None:
        """Resets smoothed speed and previous ETA."""
        self.smoothed_speed_mps = 0.0
        self.last_estimated_eta = None

    def calculate_eta(
        self,
        remaining_distance_m: float,
        current_speed_mps: Optional[float],
        current_time: datetime,
        journey_start_time: Optional[datetime] = None,
        expected_duration_s: Optional[float] = None,
        external_eta: Optional[datetime] = None,
        is_stopped: bool = False
    ) -> ETAResult:
        """
        Calculates stabilized ETA and determines journey progress status.
        """
        # 1. External ETA Provenance
        if external_eta is not None:
            # Check delay vs expected duration if provided
            status = ProgressStatus.MOVING_ON_SCHEDULE
            if is_stopped:
                status = ProgressStatus.STALLED
            elif expected_duration_s and journey_start_time:
                expected_end = journey_start_time + timedelta(seconds=expected_duration_s)
                if external_eta > (expected_end + timedelta(seconds=self.config.delay_threshold_s)):
                    status = ProgressStatus.DELAYED

            return ETAResult(
                eta=external_eta,
                eta_source=ETASource.EXTERNAL,
                smoothed_speed_mps=round(current_speed_mps or 0.0, 2),
                estimated_remaining_seconds=(external_eta - current_time).total_seconds(),
                progress_status=status
            )

        # 2. Destination already reached / trivial remaining distance
        if remaining_distance_m <= 10.0:
            return ETAResult(
                eta=current_time,
                eta_source=ETASource.ESTIMATED,
                smoothed_speed_mps=round(current_speed_mps or 0.0, 2),
                estimated_remaining_seconds=0.0,
                progress_status=ProgressStatus.MOVING_ON_SCHEDULE
            )

        # 3. Update Smoothed Speed
        alpha = self.config.eta_smoothing_alpha
        if current_speed_mps is not None and current_speed_mps > 0.0:
            if self.smoothed_speed_mps <= 0.0:
                self.smoothed_speed_mps = current_speed_mps
            else:
                self.smoothed_speed_mps = (alpha * current_speed_mps) + ((1.0 - alpha) * self.smoothed_speed_mps)

        # 4. Safe Effective Speed (Prevent zero division)
        # If traveler is moving, use smoothed speed. If stationary or unknown, use default walking speed
        if self.smoothed_speed_mps >= self.config.min_movement_speed_mps:
            effective_speed = self.smoothed_speed_mps
        else:
            effective_speed = self.config.default_travel_speed_mps

        # 5. Deterministic Fallback ETA
        remaining_seconds = remaining_distance_m / max(0.2, effective_speed)
        # Cap max ETA to 48 hours to prevent absurd values
        remaining_seconds = min(remaining_seconds, 172800.0)

        calculated_eta = current_time + timedelta(seconds=remaining_seconds)

        # 6. Evaluate Progress Status
        if is_stopped:
            status = ProgressStatus.STALLED
        elif expected_duration_s and journey_start_time:
            expected_end = journey_start_time + timedelta(seconds=expected_duration_s)
            if calculated_eta > (expected_end + timedelta(seconds=self.config.delay_threshold_s)):
                status = ProgressStatus.DELAYED
            elif current_speed_mps is not None and current_speed_mps < 0.8:
                status = ProgressStatus.SLOW_PROGRESS
            else:
                status = ProgressStatus.MOVING_ON_SCHEDULE
        elif current_speed_mps is not None:
            if current_speed_mps < 0.8 and current_speed_mps >= 0.2:
                status = ProgressStatus.SLOW_PROGRESS
            else:
                status = ProgressStatus.MOVING_ON_SCHEDULE
        else:
            status = ProgressStatus.UNKNOWN

        self.last_estimated_eta = calculated_eta

        return ETAResult(
            eta=calculated_eta,
            eta_source=ETASource.ESTIMATED,
            smoothed_speed_mps=round(self.smoothed_speed_mps, 2),
            estimated_remaining_seconds=round(remaining_seconds, 1),
            progress_status=status
        )
