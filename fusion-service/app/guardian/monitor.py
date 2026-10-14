"""
STREEVA Guardian Monitoring Loop & Orchestrator (Phase 2D).

Orchestrates:
- Journey lifecycle state machine (IDLE, STARTING, ACTIVE, DEGRADED, ARRIVING, ARRIVED, CANCELLED)
- Telemetry quality & freshness monitoring (VALID, STALE, POOR_ACCURACY, MISSING, RECOVERED)
- Delegation to existing Phase 1 detectors (Route Deviation, Unexpected Stop, Fall, Audio Distress)
- Route progress and stabilized ETA tracking
- Arrival confirmation with hysteresis and GPS accuracy protection
- Emits consolidated GuardianSnapshot for future Risk Fusion (no emergency actions)
"""

from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from .journey_state import (
    JourneyState,
    TelemetryQuality,
    ArrivalStatus,
    ProgressStatus,
    ETASource,
    GuardianConfig,
    JourneyContext,
    GuardianSnapshot,
    JourneyStartRequest,
    JourneyUpdateRequest,
    JourneyEndRequest
)
from .route_progress import RouteProgressEngine
from .eta_engine import ETAEngine
from ..edge.route_deviation import (
    RouteDeviationDetector,
    RouteDeviationEvent,
    haversine_distance_m,
    compute_cross_track_distance_m,
    _extract_lat_lng
)
from ..edge.unexpected_stop import UnexpectedStopDetector, UnexpectedStopEvent
from ..edge.fall_detection import FallDetector, FallDetectedEvent
from ..edge.audio_distress import AudioDistressDetector, AudioDistressEvent


class GuardianMonitor:
    """
    Stateful Guardian Journey Orchestrator.
    """

    def __init__(self, config: Optional[GuardianConfig] = None):
        self.config = config or GuardianConfig()
        
        # Sub-engines
        self.route_progress_engine = RouteProgressEngine(monotonic_tolerance_m=self.config.progress_monotonic_tolerance_m)
        self.eta_engine = ETAEngine(config=self.config)
        
        # Phase 1 Edge Detectors (instantiated once, reused deterministically)
        self.route_deviation_detector = RouteDeviationDetector()
        self.unexpected_stop_detector = UnexpectedStopDetector()
        self.fall_detector = FallDetector()
        self.audio_distress_detector = AudioDistressDetector()
        
        # Active journey state
        self.context: Optional[JourneyContext] = None
        self.consecutive_arrival_count: int = 0
        self.last_snapshot: Optional[GuardianSnapshot] = None

    def reset(self) -> None:
        """Completely resets all journey and detector states. Guarantees zero leakage."""
        self.context = None
        self.consecutive_arrival_count = 0
        self.last_snapshot = None
        
        self.route_progress_engine.reset()
        self.eta_engine.reset()
        self.route_deviation_detector.reset()
        self.unexpected_stop_detector.reset()
        self.fall_detector.reset()
        self.audio_distress_detector.reset()

    def start_journey(self, request: JourneyStartRequest) -> GuardianSnapshot:
        """
        Initializes a new traveler journey. Cleans previous state.
        """
        self.reset()
        start_time = request.timestamp or datetime.now(timezone.utc)

        expected_pts = []
        if request.expected_route:
            for p in request.expected_route:
                try:
                    lat, lng = _extract_lat_lng(p)
                    expected_pts.append({"lat": lat, "lng": lng})
                except Exception:
                    continue

        self.context = JourneyContext(
            journey_id=request.journey_id,
            source_lat=request.source_lat,
            source_lng=request.source_lng,
            destination_lat=request.destination_lat,
            destination_lng=request.destination_lng,
            expected_route=expected_pts,
            expected_duration_s=request.expected_duration_s,
            journey_state=JourneyState.STARTING,
            journey_start_time=start_time,
            current_timestamp=start_time,
            current_lat=request.source_lat,
            current_lng=request.source_lng,
            telemetry_quality=TelemetryQuality.VALID,
            arrival_status=ArrivalStatus.NOT_ARRIVED,
            progress_status=ProgressStatus.MOVING_ON_SCHEDULE,
            last_valid_telemetry_time=start_time,
            last_movement_time=start_time
        )

        # Initialize route progress polyline
        self.route_progress_engine.set_route(
            expected_route=expected_pts,
            source={"lat": request.source_lat, "lng": request.source_lng},
            destination={"lat": request.destination_lat, "lng": request.destination_lng}
        )
        self.context.total_route_distance_m = self.route_progress_engine.total_route_distance_m
        self.context.remaining_distance_m = self.route_progress_engine.total_route_distance_m

        # Initial ETA
        eta_res = self.eta_engine.calculate_eta(
            remaining_distance_m=self.context.total_route_distance_m,
            current_speed_mps=None,
            current_time=start_time,
            journey_start_time=start_time,
            expected_duration_s=request.expected_duration_s,
            external_eta=request.external_eta
        )
        self.context.eta = eta_res.eta
        self.context.eta_source = eta_res.eta_source

        snapshot = GuardianSnapshot(
            journey_id=request.journey_id,
            timestamp=start_time,
            journey_state=JourneyState.STARTING,
            current_lat=request.source_lat,
            current_lng=request.source_lng,
            gps_accuracy=None,
            telemetry_quality=TelemetryQuality.VALID,
            route_progress_percent=0.0,
            distance_along_route_m=0.0,
            total_route_distance_m=self.context.total_route_distance_m,
            remaining_distance_m=self.context.remaining_distance_m,
            eta=self.context.eta,
            eta_source=self.context.eta_source,
            smoothed_speed_mps=0.0,
            arrival_status=ArrivalStatus.NOT_ARRIVED,
            progress_status=ProgressStatus.MOVING_ON_SCHEDULE,
            route_adherence_percent=None,
            distance_travelled_m=0.0,
            actual_duration_s=0.0,
            valid_observations_count=0,
            active_anomalies=[],
            details="Journey initiated in STARTING state."
        )
        self.last_snapshot = snapshot
        return snapshot

    def update_telemetry(self, request: JourneyUpdateRequest) -> GuardianSnapshot:
        """
        Ingests a telemetry update, updates JourneyContext, and produces a GuardianSnapshot.
        """
        if not self.context or self.context.journey_id != request.journey_id:
            raise ValueError(f"No active journey found with id '{request.journey_id}'. Call start_journey first.")

        # Ignore telemetry updates if journey has completed or cancelled
        if self.context.journey_state in (JourneyState.ARRIVED, JourneyState.CANCELLED):
            return self.last_snapshot

        obs_time = request.timestamp or datetime.now(timezone.utc)
        lat = request.latitude
        lng = request.longitude
        accuracy = request.gps_accuracy

        # 1. Telemetry Quality Evaluation
        quality = TelemetryQuality.VALID
        degraded_reason = None

        prev_time = self.context.current_timestamp or self.context.last_valid_telemetry_time
        if prev_time is not None:
            time_gap_s = (obs_time - prev_time).total_seconds()
            if time_gap_s > self.config.telemetry_stale_timeout_s:
                quality = TelemetryQuality.STALE
                degraded_reason = f"Telemetry time gap of {time_gap_s:.1f}s exceeded timeout of {self.config.telemetry_stale_timeout_s}s."

        if accuracy is not None and accuracy > self.config.gps_accuracy_ceiling_m:
            quality = TelemetryQuality.POOR_ACCURACY
            degraded_reason = f"GPS accuracy uncertainty ({accuracy:.1f}m) exceeds ceiling ({self.config.gps_accuracy_ceiling_m}m)."

        # Check recovery from degraded
        was_degraded = (self.context.journey_state == JourneyState.DEGRADED)
        if was_degraded and quality == TelemetryQuality.VALID:
            quality = TelemetryQuality.RECOVERED

        self.context.current_timestamp = obs_time
        self.context.current_lat = lat
        self.context.current_lng = lng
        self.context.gps_accuracy = accuracy
        self.context.telemetry_quality = quality
        self.context.degraded_reason = degraded_reason

        # Telemetry observation accounting
        self.context.total_gps_observations += 1
        is_valid_obs = (accuracy is None or accuracy <= self.config.gps_accuracy_ceiling_m)

        if is_valid_obs:
            self.context.valid_gps_observations += 1
            if self.context.last_obs_lat is not None and self.context.last_obs_lng is not None:
                step_m = haversine_distance_m(
                    self.context.last_obs_lat, self.context.last_obs_lng,
                    lat, lng
                )
                self.context.cumulative_distance_travelled_m += step_m

            self.context.last_obs_lat = lat
            self.context.last_obs_lng = lng
            self.context.last_valid_telemetry_time = obs_time

        # 2. Consume Phase 1A Route Deviation Detector
        route_dev_event: Optional[RouteDeviationEvent] = None
        if self.context.expected_route and len(self.context.expected_route) > 0:
            route_dev_event = self.route_deviation_detector.detect(
                current_position={"lat": lat, "lng": lng},
                route_polyline=self.context.expected_route,
                gps_accuracy=accuracy,
                timestamp=obs_time
            )
            # Only valid GPS observations count towards corridor adherence
            if is_valid_obs:
                dev_dist = route_dev_event.deviation_distance_m
                if dev_dist <= self.config.corridor_radius_m:
                    self.context.corridor_conforming_observations += 1
                else:
                    self.context.deviated_observations += 1

        # 3. Consume Phase 1B Unexpected Stop Detector
        journey_is_active = self.context.journey_state in (
            JourneyState.STARTING, JourneyState.ACTIVE,
            JourneyState.ARRIVING, JourneyState.DEGRADED
        )
        unexpected_stop_event = self.unexpected_stop_detector.detect(
            current_position={"lat": lat, "lng": lng},
            timestamp=obs_time,
            gps_accuracy=accuracy,
            journey_active=journey_is_active
        )
        speed_mps = unexpected_stop_event.speed_mps
        if speed_mps >= self.config.min_movement_speed_mps:
            self.context.last_movement_time = obs_time

        # 4. Consume Phase 1C Fall Detector (if accelerometer/gyroscope provided)
        fall_event: Optional[FallDetectedEvent] = None
        if request.accel_x is not None and request.accel_y is not None and request.accel_z is not None:
            fall_event = self.fall_detector.detect(
                accel_x=request.accel_x,
                accel_y=request.accel_y,
                accel_z=request.accel_z,
                gyro_x=request.gyro_x,
                gyro_y=request.gyro_y,
                gyro_z=request.gyro_z,
                timestamp=obs_time,
                latitude=lat,
                longitude=lng
            )

        # 5. Consume Phase 1D Audio Distress Detector (if audio provided)
        audio_distress_event: Optional[AudioDistressEvent] = None
        if request.audio_samples is not None or request.base64_audio is not None:
            audio_distress_event = self.audio_distress_detector.process_audio_window(
                audio_data=request.audio_samples,
                base64_audio=request.base64_audio,
                timestamp=obs_time
            )

        # 6. Route Progress Calculation
        progress_res = self.route_progress_engine.calculate_progress(lat, lng)
        self.context.distance_along_route_m = progress_res.distance_along_route_m
        self.context.total_route_distance_m = progress_res.total_route_distance_m
        self.context.remaining_distance_m = progress_res.remaining_distance_m
        self.context.route_progress_percent = progress_res.progress_percent

        # 7. Destination Arrival Detection
        dist_to_destination = haversine_distance_m(
            lat, lng,
            self.context.destination_lat,
            self.context.destination_lng
        )

        if dist_to_destination <= self.config.arrival_radius_m:
            if accuracy is None or accuracy <= self.config.arrival_gps_accuracy_ceiling_m:
                self.consecutive_arrival_count += 1
                if self.consecutive_arrival_count >= self.config.arrival_consecutive_observations_required:
                    self.context.arrival_status = ArrivalStatus.ARRIVED
                else:
                    self.context.arrival_status = ArrivalStatus.ARRIVAL_POSSIBLE
            else:
                # Poor GPS accuracy suppresses false arrival confirmation
                self.context.arrival_status = ArrivalStatus.NOT_ARRIVED
        else:
            self.consecutive_arrival_count = 0
            self.context.arrival_status = ArrivalStatus.NOT_ARRIVED

        # 8. Journey State Machine Progression
        if self.context.arrival_status == ArrivalStatus.ARRIVED:
            self.context.journey_state = JourneyState.ARRIVED
        elif quality in (TelemetryQuality.STALE, TelemetryQuality.POOR_ACCURACY):
            self.context.journey_state = JourneyState.DEGRADED
        elif quality == TelemetryQuality.RECOVERED:
            self.context.journey_state = (
                JourneyState.ARRIVING if self.context.arrival_status == ArrivalStatus.ARRIVAL_POSSIBLE
                else JourneyState.ACTIVE
            )
        elif self.context.arrival_status == ArrivalStatus.ARRIVAL_POSSIBLE:
            self.context.journey_state = JourneyState.ARRIVING
        elif self.context.journey_state == JourneyState.STARTING:
            # Transition to ACTIVE once movement begins or distance from source exceeds 20m
            dist_from_source = haversine_distance_m(
                lat, lng,
                self.context.source_lat,
                self.context.source_lng
            )
            if dist_from_source > 20.0 or speed_mps >= self.config.min_movement_speed_mps:
                self.context.journey_state = JourneyState.ACTIVE
        elif self.context.journey_state == JourneyState.ARRIVING:
            if self.context.arrival_status == ArrivalStatus.NOT_ARRIVED:
                self.context.journey_state = JourneyState.ACTIVE

        # 9. Stabilized ETA & Progress Status Calculation
        is_stopped = unexpected_stop_event.is_stopped if unexpected_stop_event else False
        eta_res = self.eta_engine.calculate_eta(
            remaining_distance_m=self.context.remaining_distance_m,
            current_speed_mps=speed_mps,
            current_time=obs_time,
            journey_start_time=self.context.journey_start_time,
            expected_duration_s=self.context.expected_duration_s,
            external_eta=request.external_eta,
            is_stopped=is_stopped
        )
        self.context.eta = eta_res.eta
        self.context.eta_source = eta_res.eta_source
        self.context.smoothed_speed_mps = eta_res.smoothed_speed_mps
        self.context.progress_status = eta_res.progress_status

        # 10. Active Anomalies Aggregation (For upstream Risk Fusion)
        anomalies: List[str] = []
        if route_dev_event and route_dev_event.is_deviated:
            anomalies.append("ROUTE_DEVIATION")
        if unexpected_stop_event and unexpected_stop_event.is_stopped:
            anomalies.append("UNEXPECTED_STOP")
        if fall_event and fall_event.is_fall:
            anomalies.append("FALL_DETECTED")
        if audio_distress_event and audio_distress_event.is_distress:
            anomalies.append("AUDIO_DISTRESS")
        if quality in (TelemetryQuality.STALE, TelemetryQuality.POOR_ACCURACY):
            anomalies.append("TELEMETRY_DEGRADED")
        if eta_res.progress_status == ProgressStatus.DELAYED:
            anomalies.append("JOURNEY_DELAYED")

        # 11. Consolidated Guardian Snapshot
        details = (
            f"State: {self.context.journey_state.value} | "
            f"Progress: {self.context.route_progress_percent:.1f}% | "
            f"Speed: {self.context.smoothed_speed_mps:.1f} m/s | "
            f"Remaining: {self.context.remaining_distance_m:.0f}m"
        )
        if degraded_reason:
            details += f" | Degraded: {degraded_reason}"

        snapshot = GuardianSnapshot(
            journey_id=self.context.journey_id,
            timestamp=obs_time,
            journey_state=self.context.journey_state,
            current_lat=lat,
            current_lng=lng,
            gps_accuracy=accuracy,
            telemetry_quality=quality,
            degraded_reason=degraded_reason,
            route_progress_percent=self.context.route_progress_percent,
            distance_along_route_m=self.context.distance_along_route_m,
            total_route_distance_m=self.context.total_route_distance_m,
            remaining_distance_m=self.context.remaining_distance_m,
            eta=self.context.eta,
            eta_source=self.context.eta_source,
            smoothed_speed_mps=self.context.smoothed_speed_mps,
            arrival_status=self.context.arrival_status,
            progress_status=self.context.progress_status,
            route_adherence_percent=self.calculate_route_adherence(),
            distance_travelled_m=round(self.context.cumulative_distance_travelled_m, 1),
            actual_duration_s=round((obs_time - self.context.journey_start_time).total_seconds(), 1) if self.context.journey_start_time else 0.0,
            valid_observations_count=self.context.valid_gps_observations,
            route_deviation=route_dev_event,
            unexpected_stop=unexpected_stop_event,
            fall_event=fall_event,
            audio_distress=audio_distress_event,
            active_anomalies=anomalies,
            details=details
        )
        self.last_snapshot = snapshot
        return snapshot

    def calculate_route_adherence(self) -> Optional[float]:
        """
        Calculates the canonical route adherence percentage based on valid telemetry observations.
        
        Adherence is mathematically defined as the ratio of corridor-conforming observations 
        to total valid GPS observations:
            Adherence % = (corridor_conforming_observations / valid_gps_observations) * 100.0
            
        Strict Data Sufficiency Guards:
        - If valid_gps_observations < 3: Insufficient telemetry; returns None.
          (A single initial fix or two jittery points cannot establish route adherence.)
        - If cumulative_distance_travelled_m < 50.0: Stationary / near-zero movement; returns None.
          (Prevents zero-displacement start->immediate end journeys from claiming adherence.)
        - Readings with gps_accuracy > gps_accuracy_ceiling_m (60.0m) are excluded as degraded noise.
        - If no expected route was provided: returns None.
        
        Returns:
            Float [0.0, 100.0] rounded to 1 decimal place, or None if insufficient valid data.
        """
        if not self.context:
            return None
        if not self.context.expected_route or len(self.context.expected_route) == 0:
            return None
        if self.context.valid_gps_observations < 3:
            return None
        if self.context.cumulative_distance_travelled_m < 50.0:
            return None
        
        adherence = (self.context.corridor_conforming_observations / self.context.valid_gps_observations) * 100.0
        return round(min(100.0, max(0.0, adherence)), 1)

    def end_journey(self, request: JourneyEndRequest) -> GuardianSnapshot:
        """
        Explicitly terminates or cancels the active journey.
        """
        if not self.context or self.context.journey_id != request.journey_id:
            raise ValueError(f"No active journey found with id '{request.journey_id}'.")

        obs_time = request.timestamp or datetime.now(timezone.utc)
        self.context.journey_state = JourneyState.CANCELLED
        self.context.current_timestamp = obs_time

        actual_duration_s = (obs_time - self.context.journey_start_time).total_seconds() if self.context.journey_start_time else 0.0
        adherence_percent = self.calculate_route_adherence()

        snapshot = GuardianSnapshot(
            journey_id=self.context.journey_id,
            timestamp=obs_time,
            journey_state=JourneyState.CANCELLED,
            current_lat=self.context.current_lat,
            current_lng=self.context.current_lng,
            gps_accuracy=self.context.gps_accuracy,
            telemetry_quality=self.context.telemetry_quality,
            route_progress_percent=self.context.route_progress_percent,
            distance_along_route_m=self.context.distance_along_route_m,
            total_route_distance_m=self.context.total_route_distance_m,
            remaining_distance_m=self.context.remaining_distance_m,
            eta=self.context.eta,
            eta_source=self.context.eta_source,
            smoothed_speed_mps=self.context.smoothed_speed_mps,
            arrival_status=self.context.arrival_status,
            progress_status=self.context.progress_status,
            route_adherence_percent=adherence_percent,
            distance_travelled_m=round(self.context.cumulative_distance_travelled_m, 1),
            actual_duration_s=round(actual_duration_s, 1),
            valid_observations_count=self.context.valid_gps_observations,
            route_deviation=self.last_snapshot.route_deviation if self.last_snapshot else None,
            unexpected_stop=self.last_snapshot.unexpected_stop if self.last_snapshot else None,
            fall_event=self.last_snapshot.fall_event if self.last_snapshot else None,
            audio_distress=self.last_snapshot.audio_distress if self.last_snapshot else None,
            active_anomalies=[],
            details=f"Journey ended: {request.reason or 'User requested cancel'}"
        )
        self.last_snapshot = snapshot
        return snapshot

    def get_snapshot(self, journey_id: str) -> GuardianSnapshot:
        """Retrieves the latest snapshot for the requested journey."""
        if not self.context or self.context.journey_id != journey_id:
            raise ValueError(f"No active journey found with id '{journey_id}'.")
        return self.last_snapshot
