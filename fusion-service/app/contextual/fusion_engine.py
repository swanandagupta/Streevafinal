"""
STREEVA — Phase 3 Contextual Safety Intelligence
app/contextual/fusion_engine.py

Risk Fusion 2.0 Engine:
- Ingests GuardianSnapshot, Area Risk, and edge telemetry.
- Normalizes all signals to [0.0, 1.0] with confidence weighting.
- Implements dynamic weight re-normalization for missing/unavailable signals.
- Evaluates temporal recency decay and persistence counts.
- Applies bounded, transparent contextual interaction boosts.
- Generates unified [0.0, 100.0] risk score, risk level, and explainable RiskFactors.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from .schemas import (
    RiskLevel,
    RiskFactor,
    JourneyRiskAssessment,
)
from .config import ContextualSafetyConfig
from .temporal import TemporalSignalTracker
from ..guardian.journey_state import (
    GuardianSnapshot,
    TelemetryQuality,
    ProgressStatus
)


class ContextualRiskFusionEngine:
    """
    Risk Fusion 2.0 Engine.
    Converts multi-modal signals into a unified, explainable 0-100 risk score.
    """

    def __init__(
        self,
        config: Optional[ContextualSafetyConfig] = None,
        temporal_tracker: Optional[TemporalSignalTracker] = None
    ):
        self.config = config or ContextualSafetyConfig()
        self.temporal_tracker = temporal_tracker or TemporalSignalTracker(self.config)

    def evaluate_risk(
        self,
        snapshot: GuardianSnapshot,
        area_risk_score: Optional[float] = None,
        area_risk_confidence: float = 1.0,
        motion_anomaly_score: Optional[float] = None,
        motion_confidence: float = 1.0,
    ) -> JourneyRiskAssessment:
        """
        Executes unified contextual risk fusion.
        """
        journey_id = snapshot.journey_id
        timestamp = snapshot.timestamp or datetime.now(timezone.utc)
        
        # 1. Data Quality Audit & Signal Availability Tracking
        data_quality: Dict[str, Any] = {
            "telemetry_quality": snapshot.telemetry_quality.value,
            "signals": {}
        }
        
        available_signals: Dict[str, Tuple[float, float, float, str, str]] = {}
        # Format: signal_name -> (normalized_value [0-1], confidence [0-1], base_weight, state_str, reason_str)
        
        # --- A. Area Risk Signal ---
        if area_risk_score is not None:
            norm_area = max(0.0, min(1.0, area_risk_score / 100.0))
            available_signals["area_risk"] = (
                norm_area,
                max(0.0, min(1.0, area_risk_confidence)),
                self.config.weight_area_risk,
                f"SCORE_{round(area_risk_score, 1)}",
                f"Area risk score {round(area_risk_score, 1)}/100 from geospatial crime/isolation priors."
            )
            data_quality["signals"]["area_risk"] = "AVAILABLE"
        else:
            data_quality["signals"]["area_risk"] = "UNAVAILABLE"

        # --- B. Motion Anomaly Signal ---
        if motion_anomaly_score is not None:
            norm_motion = max(0.0, min(1.0, motion_anomaly_score / 100.0))
            available_signals["motion_anomaly"] = (
                norm_motion,
                max(0.0, min(1.0, motion_confidence)),
                self.config.weight_motion_anomaly,
                f"SCORE_{round(motion_anomaly_score, 1)}",
                f"1D-CNN motion anomaly classifier score {round(motion_anomaly_score, 1)}/100."
            )
            data_quality["signals"]["motion_anomaly"] = "AVAILABLE"
        else:
            # If motion score not explicitly passed, mark not provided
            data_quality["signals"]["motion_anomaly"] = "UNAVAILABLE"

        # --- C. Route Deviation Signal ---
        if snapshot.route_deviation is not None:
            rd_state = snapshot.route_deviation.state.value if hasattr(snapshot.route_deviation.state, "value") else str(snapshot.route_deviation.state)
            rd_conf = snapshot.route_deviation.confidence
            
            # Reduce confidence if GPS accuracy is degraded
            if snapshot.telemetry_quality in [TelemetryQuality.POOR_ACCURACY, TelemetryQuality.STALE]:
                rd_conf = min(rd_conf, 0.3)
                
            norm_rd = 0.0
            if rd_state == "DEVIATED":
                norm_rd = 1.0
            elif rd_state == "POSSIBLE_DEVIATION":
                norm_rd = 0.4
            elif rd_state in ["NORMAL", "RECOVERED"]:
                norm_rd = 0.0
                
            # Update temporal persistence
            is_active = rd_state in ["DEVIATED", "POSSIBLE_DEVIATION"]
            t_rd = self.temporal_tracker.update_signal(journey_id, "route_deviation", is_active, timestamp)
            
            # Persistence scaling: single possible spike is slightly damped
            if is_active and t_rd["consecutive_count"] == 1 and rd_state == "POSSIBLE_DEVIATION":
                norm_rd *= 0.75
                
            dev_dist = getattr(snapshot.route_deviation, "deviation_distance_m", getattr(snapshot.route_deviation, "cross_track_distance", 0.0))
            available_signals["route_deviation"] = (
                norm_rd,
                rd_conf,
                self.config.weight_route_deviation,
                rd_state,
                f"Route deviation status {rd_state} (cross-track: {round(dev_dist, 1)}m)."
            )
            data_quality["signals"]["route_deviation"] = "AVAILABLE"
        else:
            data_quality["signals"]["route_deviation"] = "UNAVAILABLE"

        # --- D. Unexpected Stop Signal ---
        if snapshot.unexpected_stop is not None:
            us_state = snapshot.unexpected_stop.state.value if hasattr(snapshot.unexpected_stop.state, "value") else str(snapshot.unexpected_stop.state)
            us_conf = snapshot.unexpected_stop.confidence
            
            if snapshot.telemetry_quality in [TelemetryQuality.POOR_ACCURACY, TelemetryQuality.STALE]:
                us_conf = min(us_conf, 0.3)
                
            norm_us = 0.0
            if us_state == "STOPPED":
                norm_us = 1.0
            elif us_state == "POSSIBLE_STOP":
                norm_us = 0.5
            elif us_state in ["MOVING", "RECOVERED"]:
                norm_us = 0.0
                
            is_active = us_state in ["STOPPED", "POSSIBLE_STOP"]
            t_us = self.temporal_tracker.update_signal(journey_id, "unexpected_stop", is_active, timestamp)
            
            available_signals["unexpected_stop"] = (
                norm_us,
                us_conf,
                self.config.weight_unexpected_stop,
                us_state,
                f"Unexpected stop status {us_state} (stationary duration: {round(snapshot.unexpected_stop.stationary_duration_s, 1)}s)."
            )
            data_quality["signals"]["unexpected_stop"] = "AVAILABLE"
        else:
            data_quality["signals"]["unexpected_stop"] = "UNAVAILABLE"

        # --- E. Fall Detection Signal ---
        if snapshot.fall_event is not None:
            fall_state = snapshot.fall_event.state.value if hasattr(snapshot.fall_event.state, "value") else str(snapshot.fall_event.state)
            fall_conf = snapshot.fall_event.confidence
            
            norm_fall = 0.0
            if fall_state in ["FALL_DETECTED", "CONFIRMED"]:
                norm_fall = 1.0
            elif fall_state in ["POSSIBLE_FALL", "POSSIBLE_IMPACT", "SUSPECTED"]:
                norm_fall = 0.5
            elif fall_state in ["NORMAL", "RECOVERED"]:
                norm_fall = 0.0
                
            event_ts = snapshot.fall_event.timestamp or timestamp
            is_active = fall_state in ["FALL_DETECTED", "CONFIRMED", "POSSIBLE_FALL", "POSSIBLE_IMPACT", "SUSPECTED"]
            t_fall = self.temporal_tracker.update_signal(journey_id, "fall", is_active, event_ts)
            
            # Apply exponential decay based on event timestamp relative to current snapshot timestamp
            decay = self.temporal_tracker.compute_recency_decay("fall", event_ts, timestamp)
            norm_fall *= decay
            
            available_signals["fall_detection"] = (
                norm_fall,
                fall_conf,
                self.config.weight_fall_detection,
                fall_state,
                f"Fall detection status {fall_state} (decay factor: {round(decay, 2)})."
            )
            data_quality["signals"]["fall_detection"] = "AVAILABLE"
        else:
            data_quality["signals"]["fall_detection"] = "UNAVAILABLE"

        # --- F. Audio Distress Signal ---
        if snapshot.audio_distress is not None:
            audio_state = snapshot.audio_distress.state.value if hasattr(snapshot.audio_distress.state, "value") else str(snapshot.audio_distress.state)
            audio_prob = getattr(
                snapshot.audio_distress,
                "raw_distress_probability",
                getattr(
                    snapshot.audio_distress,
                    "raw_probability",
                    getattr(
                        snapshot.audio_distress,
                        "distress_probability",
                        snapshot.audio_distress.distress_score / 100.0
                    )
                )
            )
            audio_conf = snapshot.audio_distress.confidence
            
            norm_audio = 0.0
            if audio_state in ["DISTRESS_DETECTED", "CONFIRMED"]:
                norm_audio = audio_prob
            elif audio_state in ["POSSIBLE_DISTRESS", "POSSIBLE"]:
                norm_audio = audio_prob * 0.5
            elif audio_state in ["NORMAL", "RECOVERED"]:
                norm_audio = 0.0
                
            event_ts = snapshot.audio_distress.timestamp or timestamp
            is_active = audio_state in ["DISTRESS_DETECTED", "CONFIRMED", "POSSIBLE_DISTRESS", "POSSIBLE"]
            t_audio = self.temporal_tracker.update_signal(journey_id, "audio_distress", is_active, event_ts)
            
            decay = self.temporal_tracker.compute_recency_decay("audio_distress", event_ts, timestamp)
            norm_audio *= decay
            
            available_signals["audio_distress"] = (
                norm_audio,
                audio_conf,
                self.config.weight_audio_distress,
                audio_state,
                f"Audio distress probability {round(audio_prob, 2)} in state {audio_state} (decay factor: {round(decay, 2)})."
            )
            data_quality["signals"]["audio_distress"] = "AVAILABLE"
        else:
            data_quality["signals"]["audio_distress"] = "UNAVAILABLE"


        # 2. Dynamic Weight Re-normalization for Missing Signals
        total_available_weight = sum(w for (_, _, w, _, _) in available_signals.values())
        
        if total_available_weight <= 0.0:
            # All signals missing / unavailable -> UNKNOWN risk, not LOW safe!
            return JourneyRiskAssessment(
                journey_id=journey_id,
                timestamp=timestamp,
                risk_score=0.0,
                risk_level=RiskLevel.UNKNOWN,
                area_risk=0.0,
                motion_risk=0.0,
                route_deviation_risk=0.0,
                unexpected_stop_risk=0.0,
                fall_risk=0.0,
                audio_distress_risk=0.0,
                overall_confidence=0.0,
                telemetry_quality=snapshot.telemetry_quality.value,
                active_factors=[],
                dominant_factor=None,
                temporal_context=self.temporal_tracker.get_summary(journey_id),
                data_quality=data_quality
            )

        point_contributions: Dict[str, float] = {}
        risk_factors: List[RiskFactor] = []
        conf_sum = 0.0

        for sig_name, (norm_val, conf, base_w, state_str, reason_str) in available_signals.items():
            # Normalized effective weight
            eff_w = base_w / total_available_weight
            # Point contribution is modulated by detector confidence to prevent low-confidence spikes
            pts = norm_val * 100.0 * eff_w * conf
            point_contributions[sig_name] = pts
            conf_sum += conf * eff_w
            
            if pts > 0.1 or (norm_val > 0.0 and conf > 0.0):
                risk_factors.append(RiskFactor(
                    name=sig_name.upper(),
                    contribution=round(pts, 2),
                    confidence=round(conf, 2),
                    state=state_str,
                    reason=reason_str
                ))

        base_score = sum(point_contributions.values())
        overall_conf = max(0.0, min(1.0, conf_sum))

        # 3. Contextual Interaction Boosts (Transparent & Bounded)
        interaction_boost = 0.0

        # Interaction 1: High Area Risk + Confirmed Route Deviation
        has_high_area = area_risk_score is not None and area_risk_score >= self.config.high_area_threshold
        has_route_deviation = available_signals.get("route_deviation", (0, 0, 0, ""))[3] == "DEVIATED"
        if has_high_area and has_route_deviation:
            boost = self.config.area_deviation_boost
            interaction_boost += boost
            risk_factors.append(RiskFactor(
                name="INTERACTION_HIGH_AREA_AND_DEVIATION",
                contribution=round(boost, 2),
                confidence=round(overall_conf, 2),
                state="ACTIVE",
                reason=f"Compounded risk: Confirmed route deviation occurred within high-risk area (score: {area_risk_score})."
            ))

        # Interaction 2: Unexpected Stop + High Area Risk + Delay
        has_stop = available_signals.get("unexpected_stop", (0, 0, 0, ""))[3] == "STOPPED"
        is_delayed = snapshot.progress_status in [ProgressStatus.DELAYED, ProgressStatus.STALLED]
        if has_stop and has_high_area and is_delayed:
            boost = self.config.stop_area_delay_boost
            interaction_boost += boost
            risk_factors.append(RiskFactor(
                name="INTERACTION_STOP_AREA_DELAY",
                contribution=round(boost, 2),
                confidence=round(overall_conf, 2),
                state="ACTIVE",
                reason=f"Compounded risk: Prolonged unexpected stop in high-risk area during delayed journey."
            ))

        # Interaction 3: High Audio Distress + Confirmed Fall
        # Must be strictly semantically and temporally correlated
        has_audio_distress = False
        has_fall = False
        temporal_correlation_valid = False
        interaction_conf = 0.0

        if snapshot.fall_event is not None and snapshot.audio_distress is not None:
            fall_st = snapshot.fall_event.state.value if hasattr(snapshot.fall_event.state, "value") else str(snapshot.fall_event.state)
            audio_st = snapshot.audio_distress.state.value if hasattr(snapshot.audio_distress.state, "value") else str(snapshot.audio_distress.state)

            fall_confirmed = fall_st in ["FALL_DETECTED", "CONFIRMED"]
            audio_confirmed = audio_st in ["DISTRESS_DETECTED", "CONFIRMED"]

            if fall_confirmed and audio_confirmed:
                fall_ts = snapshot.fall_event.timestamp or timestamp
                audio_ts = snapshot.audio_distress.timestamp or timestamp

                # Temporal correlation window check
                dt_events = abs((audio_ts - fall_ts).total_seconds())

                # Freshness checks: both events must have happened recently relative to current time
                decay_f = self.temporal_tracker.compute_recency_decay("fall", fall_ts, timestamp)
                decay_a = self.temporal_tracker.compute_recency_decay("audio_distress", audio_ts, timestamp)

                if (dt_events <= self.config.audio_fall_correlation_window_s and
                    decay_f >= 0.75 and decay_a >= 0.75):
                    temporal_correlation_valid = True
                    has_audio_distress = True
                    has_fall = True
                    interaction_conf = min(snapshot.fall_event.confidence, snapshot.audio_distress.confidence)

        if has_audio_distress and has_fall and temporal_correlation_valid:
            boost = self.config.audio_fall_boost
            interaction_boost += boost
            risk_factors.append(RiskFactor(
                name="INTERACTION_AUDIO_DISTRESS_AND_FALL",
                contribution=round(boost, 2),
                confidence=round(interaction_conf, 2),
                state="ACTIVE",
                reason="Compounded physical distress: Confirmed audio distress concurrent with physical fall impact within correlation window."
            ))

        final_score = max(0.0, min(100.0, base_score + interaction_boost))

        # 4. Classification
        if final_score >= 75.0:
            risk_level = RiskLevel.CRITICAL
        elif final_score >= 50.0:
            risk_level = RiskLevel.HIGH
        elif final_score >= 25.0:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        # 5. Dominant Factor Identification
        dominant_factor = None
        if risk_factors:
            dominant_factor = max(risk_factors, key=lambda f: f.contribution).name

        return JourneyRiskAssessment(
            journey_id=journey_id,
            timestamp=timestamp,
            risk_score=round(final_score, 2),
            risk_level=risk_level,
            area_risk=round(point_contributions.get("area_risk", 0.0), 2),
            motion_risk=round(point_contributions.get("motion_anomaly", 0.0), 2),
            route_deviation_risk=round(point_contributions.get("route_deviation", 0.0), 2),
            unexpected_stop_risk=round(point_contributions.get("unexpected_stop", 0.0), 2),
            fall_risk=round(point_contributions.get("fall_detection", 0.0), 2),
            audio_distress_risk=round(point_contributions.get("audio_distress", 0.0), 2),
            overall_confidence=round(overall_conf, 2),
            telemetry_quality=snapshot.telemetry_quality.value,
            active_factors=risk_factors,
            dominant_factor=dominant_factor,
            temporal_context=self.temporal_tracker.get_summary(journey_id),
            data_quality=data_quality
        )
