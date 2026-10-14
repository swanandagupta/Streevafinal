"""
STREEVA — Phase 3 Contextual Safety Intelligence Replay Demonstration
scripts/demo_risk_fusion.py

Executes all 10 deterministic replay scenarios demonstrating:
- Scenario 1: Safe Journey (Low Risk & Policy)
- Scenario 2: Elevated Environmental Risk (Medium/High)
- Scenario 3: Route Deviation Contextual Risk
- Scenario 4: Unexpected Stop & Journey Delay
- Scenario 5: Kinematic Fall Impact
- Scenario 6: Sustained Distress Audio
- Scenario 7: Multi-Signal Compound Threat (Critical)
- Scenario 8: False Positive Resistance (Transitory Spike Debouncing)
- Scenario 9: Recovery with Schmitt-Trigger Hysteresis
- Scenario 10: Telemetry Degradation (Data Quality Visibility)
"""

import sys
import os
from datetime import datetime, timezone, timedelta

# Ensure fusion-service directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.contextual import (
    RiskLevel,
    DecisionTier,
    SensorProfile,
    ContextualRiskFusionEngine,
    DecisionEngine,
    AdaptiveSensorManager,
    BatteryContext,
    NetworkContext,
    NetworkState
)
from app.guardian.journey_state import (
    GuardianSnapshot,
    JourneyState,
    TelemetryQuality,
    ArrivalStatus,
    ProgressStatus,
    ETASource
)
from app.edge.route_deviation import RouteDeviationEvent, DeviationState
from app.edge.unexpected_stop import UnexpectedStopEvent, StopState
from app.edge.fall_detection import FallDetectedEvent, FallState, SensorMode
from app.edge.audio_distress import AudioDistressEvent, DistressAudioState


def make_snapshot(
    journey_id: str,
    telemetry_quality: TelemetryQuality = TelemetryQuality.VALID,
    route_deviation: RouteDeviationEvent = None,
    unexpected_stop: UnexpectedStopEvent = None,
    fall_event: FallDetectedEvent = None,
    audio_distress: AudioDistressEvent = None,
    progress_status: ProgressStatus = ProgressStatus.MOVING_ON_SCHEDULE,
    timestamp: datetime = None
) -> GuardianSnapshot:
    ts = timestamp or datetime.now(timezone.utc)
    return GuardianSnapshot(
        journey_id=journey_id,
        timestamp=ts,
        journey_state=JourneyState.ACTIVE,
        current_lat=12.95,
        current_lng=80.15,
        gps_accuracy=12.0,
        telemetry_quality=telemetry_quality,
        route_progress_percent=45.0,
        distance_along_route_m=4500.0,
        total_route_distance_m=10000.0,
        remaining_distance_m=5500.0,
        eta=ts + timedelta(minutes=25),
        eta_source=ETASource.ESTIMATED,
        smoothed_speed_mps=1.35,
        arrival_status=ArrivalStatus.NOT_ARRIVED,
        progress_status=progress_status,
        route_deviation=route_deviation,
        unexpected_stop=unexpected_stop,
        fall_event=fall_event,
        audio_distress=audio_distress,
        active_anomalies=[]
    )


def run_all_scenarios():
    print("=" * 80)
    print("STREEVA — PHASE 3 CONTEXTUAL SAFETY INTELLIGENCE: 10 REPLAY SCENARIOS")
    print("=" * 80)

    engine = ContextualRiskFusionEngine()
    decision_engine = DecisionEngine()
    sensor_mgr = AdaptiveSensorManager()

    # -------------------------------------------------------------
    # Scenario 1 — Safe Journey
    # -------------------------------------------------------------
    print("\n[SCENARIO 1] Safe Journey (Normal movement, Low Area Risk)")
    s1 = make_snapshot("journey_s1")
    a1 = engine.evaluate_risk(s1, area_risk_score=15.0, motion_anomaly_score=5.0)
    d1 = decision_engine.evaluate(a1)
    p1 = sensor_mgr.generate_policy(d1)

    print(f"  Risk Score: {a1.risk_score} | Level: {a1.risk_level.value}")
    print(f"  Decision Tier: {d1.decision_tier.value}")
    print(f"  Sensor Profile: {p1.profile.value} (GPS: {p1.gps_interval_s}s, Accel: {p1.accel_sampling_rate_hz}Hz)")
    assert a1.risk_level == RiskLevel.LOW
    assert d1.decision_tier == DecisionTier.MONITOR
    assert p1.profile == SensorProfile.LOW
    print("  -> PASS: Low risk maintained, power-saving sensing policy assigned.")

    # -------------------------------------------------------------
    # Scenario 2 — Elevated Environment
    # -------------------------------------------------------------
    print("\n[SCENARIO 2] Elevated Environment (High Area Risk 78/100, Normal Movement)")
    s2 = make_snapshot("journey_s2")
    a2 = engine.evaluate_risk(s2, area_risk_score=78.0, motion_anomaly_score=10.0)
    d2 = decision_engine.evaluate(a2)
    p2 = sensor_mgr.generate_policy(d2)

    print(f"  Risk Score: {a2.risk_score} | Level: {a2.risk_level.value} | Dominant: {a2.dominant_factor}")
    print(f"  Decision Tier: {d2.decision_tier.value}")
    print(f"  Sensor Profile: {p2.profile.value}")
    assert a2.risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH]
    assert a2.dominant_factor == "AREA_RISK"
    print("  -> PASS: Environmental risk elevates score proportionally without false alarm.")

    # -------------------------------------------------------------
    # Scenario 3 — Route Deviation
    # -------------------------------------------------------------
    print("\n[SCENARIO 3] Route Deviation (Confirmed 85m Deviation in Moderate Area)")
    rd3 = RouteDeviationEvent(
        is_deviated=True,
        state=DeviationState.DEVIATED,
        deviation_distance_m=85.0,
        threshold_m=50.0,
        recovery_threshold_m=35.0,
        confidence=0.92,
        latitude=12.95,
        longitude=80.15,
        timestamp=datetime.now(timezone.utc)
    )
    s3 = make_snapshot("journey_s3", route_deviation=rd3)
    a3 = engine.evaluate_risk(s3, area_risk_score=35.0)
    d3 = decision_engine.evaluate(a3)
    p3 = sensor_mgr.generate_policy(d3)

    print(f"  Risk Score: {a3.risk_score} | Route Dev Risk: {a3.route_deviation_risk} | Level: {a3.risk_level.value}")
    print(f"  Decision Tier: {d3.decision_tier.value} | Sensor Profile: {p3.profile.value}")
    assert a3.route_deviation_risk > 20.0
    print("  -> PASS: Confirmed route corridor departure recorded in risk factors.")

    # -------------------------------------------------------------
    # Scenario 4 — Unexpected Stop & Delayed Journey
    # -------------------------------------------------------------
    print("\n[SCENARIO 4] Unexpected Stop (Stationary for 180s in High-Risk Area)")
    us4 = UnexpectedStopEvent(
        is_stopped=True,
        state=StopState.STOPPED,
        stationary_duration_s=180.0,
        speed_mps=0.0,
        confidence=0.90,
        latitude=12.95,
        longitude=80.15,
        timestamp=datetime.now(timezone.utc)
    )

    s4 = make_snapshot("journey_s4", unexpected_stop=us4, progress_status=ProgressStatus.DELAYED)
    a4 = engine.evaluate_risk(s4, area_risk_score=68.0)
    d4 = decision_engine.evaluate(a4)

    print(f"  Risk Score: {a4.risk_score} | Stop Risk: {a4.unexpected_stop_risk} | Active Factors: {len(a4.active_factors)}")
    print(f"  Decision Tier: {d4.decision_tier.value} (Check-in Required: {d4.requires_user_check_in})")
    assert any("INTERACTION_STOP_AREA_DELAY" in f.name for f in a4.active_factors)
    print("  -> PASS: Compounded stop + area + delay interaction boost applied.")

    # -------------------------------------------------------------
    # Scenario 5 — Fall Event
    # -------------------------------------------------------------
    print("\n[SCENARIO 5] Kinematic Fall Impact (3.8g Peak + Orientation Change)")
    fall5 = FallDetectedEvent(
        is_fall=True,
        state=FallState.FALL_DETECTED,
        impact_magnitude_g=3.8,
        confidence=0.95,
        sensor_mode=SensorMode.ACCEL_AND_GYRO,
        timestamp=datetime.now(timezone.utc)
    )
    s5 = make_snapshot("journey_s5", fall_event=fall5)
    a5 = engine.evaluate_risk(s5, area_risk_score=25.0)
    d5 = decision_engine.evaluate(a5)

    print(f"  Risk Score: {a5.risk_score} | Fall Risk: {a5.fall_risk} | Level: {a5.risk_level.value}")
    print(f"  Decision Tier: {d5.decision_tier.value}")
    assert a5.fall_risk > 0.0
    assert a5.dominant_factor == "FALL_DETECTION"
    print("  -> PASS: Kinematic fall impact contributes heavily to movement risk.")

    # -------------------------------------------------------------
    # Scenario 6 — Sustained Audio Distress
    # -------------------------------------------------------------
    print("\n[SCENARIO 6] Sustained Audio Distress (CNN Probability 0.94)")
    audio6 = AudioDistressEvent(
        is_distress=True,
        state=DistressAudioState.DISTRESS_DETECTED,
        distress_score=94.0,
        raw_probability=0.94,
        confidence=0.92,
        consecutive_distress_count=3,
        timestamp=datetime.now(timezone.utc)
    )
    s6 = make_snapshot("journey_s6", audio_distress=audio6)
    a6 = engine.evaluate_risk(s6, area_risk_score=20.0)
    d6 = decision_engine.evaluate(a6)

    print(f"  Risk Score: {a6.risk_score} | Audio Risk: {a6.audio_distress_risk} | Dominant: {a6.dominant_factor}")
    assert a6.audio_distress_risk > 0.0
    print("  -> PASS: Audio distress probability properly scaled and isolated.")

    # -------------------------------------------------------------
    # Scenario 7 — Multi-Signal Compound Threat
    # -------------------------------------------------------------
    print("\n[SCENARIO 7] Multi-Signal Compound Threat (Area + Deviation + Stop + Audio)")
    s7 = make_snapshot("journey_s7", route_deviation=rd3, unexpected_stop=us4, audio_distress=audio6)
    a7 = engine.evaluate_risk(s7, area_risk_score=85.0)
    # 1st observation: raises to ELEVATED_MONITORING
    d7_obs1 = decision_engine.evaluate(a7)
    # 2nd observation: confirms AUTONOMOUS_RESPONSE_REQUIRED
    d7_obs2 = decision_engine.evaluate(a7)
    p7 = sensor_mgr.generate_policy(d7_obs2)

    print(f"  Risk Score: {a7.risk_score} | Level: {a7.risk_level.value}")
    print(f"  Active Factors: {[f.name for f in a7.active_factors]}")
    print(f"  Decision Tier: {d7_obs2.decision_tier.value}")
    print(f"  Sensor Policy: {p7.profile.value} (GPS: {p7.gps_interval_s}s, Accel: {p7.accel_sampling_rate_hz}Hz, Mic: {p7.mic_duty_cycle_percent}%)")
    assert a7.risk_level == RiskLevel.CRITICAL
    assert d7_obs2.decision_tier == DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED
    assert p7.profile == SensorProfile.CRITICAL
    print("  -> PASS: Compound anomalies escalate to CRITICAL tier deterministically.")

    # -------------------------------------------------------------
    # Scenario 8 — False Positive Resistance (Transitory Spike)
    # -------------------------------------------------------------
    print("\n[SCENARIO 8] False Positive Resistance (Single Noisy Spike)")
    rd_spike = RouteDeviationEvent(
        is_deviated=False,
        state=DeviationState.POSSIBLE_DEVIATION,
        deviation_distance_m=42.0,
        threshold_m=50.0,
        recovery_threshold_m=35.0,
        confidence=0.45,
        latitude=12.95,
        longitude=80.15,
        timestamp=datetime.now(timezone.utc)
    )
    s8 = make_snapshot("journey_s8", route_deviation=rd_spike)
    a8 = engine.evaluate_risk(s8, area_risk_score=20.0)
    d8 = decision_engine.evaluate(a8)

    print(f"  Risk Score: {a8.risk_score} | Level: {a8.risk_level.value} | Decision Tier: {d8.decision_tier.value}")
    assert a8.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]
    assert d8.decision_tier != DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED
    print("  -> PASS: Weak low-confidence transitory noise suppressed by temporal damping.")


    # -------------------------------------------------------------
    # Scenario 9 — Recovery with Hysteresis
    # -------------------------------------------------------------
    print("\n[SCENARIO 9] Recovery with Debounced Hysteresis")
    # In journey_s7, we are currently at CRITICAL
    # Suddenly situation clears to safe
    s9_safe = make_snapshot("journey_s7")
    a9_safe = engine.evaluate_risk(s9_safe, area_risk_score=15.0)

    d9_1 = decision_engine.evaluate(a9_safe)
    print(f"  Safe Obs 1 -> Decision: {d9_1.decision_tier.value} (Held at CRITICAL for debounce)")
    assert d9_1.decision_tier == DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED

    d9_2 = decision_engine.evaluate(a9_safe)
    print(f"  Safe Obs 2 -> Decision: {d9_2.decision_tier.value} (Still held)")
    assert d9_2.decision_tier == DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED

    d9_3 = decision_engine.evaluate(a9_safe)
    print(f"  Safe Obs 3 -> Decision: {d9_3.decision_tier.value} (De-escalation confirmed!)")
    assert d9_3.decision_tier != DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED
    print("  -> PASS: Rapid flapping prevented by 3-observation de-escalation requirement.")

    # -------------------------------------------------------------
    # Scenario 10 — Missing Telemetry & Quality Degradation
    # -------------------------------------------------------------
    print("\n[SCENARIO 10] Missing Telemetry & Data Quality Audit")
    s10 = make_snapshot("journey_s10", telemetry_quality=TelemetryQuality.STALE)
    a10 = engine.evaluate_risk(s10, area_risk_score=None, motion_anomaly_score=None)
    d10 = decision_engine.evaluate(a10)

    print(f"  Telemetry Quality: {a10.telemetry_quality}")
    print(f"  Risk Level: {a10.risk_level.value}")
    print(f"  Decision Tier: {d10.decision_tier.value}")
    print(f"  Data Quality Audit: {a10.data_quality['signals']}")
    print(f"  Overall Confidence: {a10.overall_confidence}")
    assert a10.data_quality["telemetry_quality"] == "STALE"
    assert a10.data_quality["signals"]["area_risk"] == "UNAVAILABLE"
    assert a10.overall_confidence == 0.0
    assert a10.risk_level == RiskLevel.UNKNOWN
    assert d10.decision_tier == DecisionTier.DEGRADED_MONITORING
    print("  -> PASS: Upstream telemetry gaps surfaced explicitly with UNKNOWN / DEGRADED_MONITORING (no evidence of danger != evidence of safety).")

    print("\n" + "=" * 80)
    print("ALL 10 REPLAY SCENARIOS EXECUTED & VERIFIED (100% SUCCESS)!")
    print("=" * 80)


if __name__ == "__main__":
    run_all_scenarios()
