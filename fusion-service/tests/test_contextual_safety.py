"""
STREEVA — Phase 3 Contextual Safety Intelligence Tests
tests/test_contextual_safety.py

Comprehensive test suite for:
- Risk Fusion 2.0 (signal normalization, missing data handling, weight re-normalization)
- Temporal Reasoning & Recency Decay
- Confidence & Data Quality
- Contextual Interactions & Bounded Clamping
- Risk Classification Boundaries (0, 24.99, 25, 49.99, 50, 74.99, 75, 100)
- Explainability & Dominant Factor Selection
- Decision Engine with Stateful Hysteresis & Debounce
- Adaptive Sensor Manager (Battery & Network awareness)
- FastAPI REST Endpoints & Reset Isolation
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.contextual import (
    RiskLevel,
    DecisionTier,
    SensorProfile,
    NetworkState,
    BatteryContext,
    NetworkContext,
    ContextualSafetyConfig,
    TemporalSignalTracker,
    ContextualRiskFusionEngine,
    DecisionEngine,
    AdaptiveSensorManager,
    ContextualSafetyRequest
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

client = TestClient(app)


def make_route_deviation(
    state: DeviationState = DeviationState.DEVIATED,
    distance: float = 80.0,
    confidence: float = 0.90
) -> RouteDeviationEvent:
    return RouteDeviationEvent(
        is_deviated=(state == DeviationState.DEVIATED),
        state=state,
        deviation_distance_m=distance,
        threshold_m=50.0,
        recovery_threshold_m=35.0,
        confidence=confidence,
        latitude=12.95,
        longitude=80.15,
        timestamp=datetime.now(timezone.utc)
    )


def make_fall_event(
    state: FallState = FallState.FALL_DETECTED,
    confidence: float = 0.90,
    timestamp: datetime = None
) -> FallDetectedEvent:
    return FallDetectedEvent(
        is_fall=(state == FallState.FALL_DETECTED),
        state=state,
        impact_magnitude_g=3.2,
        confidence=confidence,
        sensor_mode=SensorMode.ACCEL_AND_GYRO,
        timestamp=timestamp or datetime.now(timezone.utc),
        details="Kinematic fall pattern verified"
    )


def make_audio_event(
    state: DistressAudioState = DistressAudioState.DISTRESS_DETECTED,
    distress_probability: float = 0.88,
    confidence: float = 0.90,
    timestamp: datetime = None
) -> AudioDistressEvent:
    return AudioDistressEvent(
        is_distress=(state == DistressAudioState.DISTRESS_DETECTED),
        state=state,
        distress_score=distress_probability * 100.0,
        raw_probability=distress_probability,
        confidence=confidence,
        consecutive_distress_count=3 if state == DistressAudioState.DISTRESS_DETECTED else 0,
        timestamp=timestamp or datetime.now(timezone.utc)
    )



def make_snapshot(

    journey_id: str = "test_journey_1",
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
        gps_accuracy=10.0,
        telemetry_quality=telemetry_quality,
        route_progress_percent=50.0,
        distance_along_route_m=5000.0,
        total_route_distance_m=10000.0,
        remaining_distance_m=5000.0,
        eta=ts + timedelta(minutes=20),
        eta_source=ETASource.ESTIMATED,
        smoothed_speed_mps=1.4,
        arrival_status=ArrivalStatus.NOT_ARRIVED,
        progress_status=progress_status,
        route_deviation=route_deviation,
        unexpected_stop=unexpected_stop,
        fall_event=fall_event,
        audio_distress=audio_distress,
        active_anomalies=[]
    )



# ==========================================
# 1. Basic Fusion & Normalization Tests
# ==========================================

def test_safe_journey_low_risk():
    """Normal movement + low area risk produces LOW risk."""
    engine = ContextualRiskFusionEngine()
    snapshot = make_snapshot()
    assessment = engine.evaluate_risk(
        snapshot=snapshot,
        area_risk_score=15.0,
        motion_anomaly_score=10.0
    )
    assert assessment.risk_level == RiskLevel.LOW
    assert assessment.risk_score < 25.0
    assert assessment.area_risk > 0.0


def test_elevated_area_risk_only():
    """High area risk without movement anomalies elevates score moderately."""
    engine = ContextualRiskFusionEngine()
    snapshot = make_snapshot()
    assessment = engine.evaluate_risk(
        snapshot=snapshot,
        area_risk_score=80.0,
        motion_anomaly_score=5.0
    )
    # Area risk is weighted, so 80.0 area risk with low motion results in medium risk
    assert assessment.risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH]
    assert assessment.dominant_factor == "AREA_RISK"


def test_route_deviation_risk_contribution():
    """Confirmed route deviation adds significant route_deviation_risk."""
    engine = ContextualRiskFusionEngine()
    rd = make_route_deviation(state=DeviationState.DEVIATED, distance=95.0, confidence=0.90)
    snapshot = make_snapshot(route_deviation=rd)
    assessment = engine.evaluate_risk(
        snapshot=snapshot,
        area_risk_score=20.0,
        motion_anomaly_score=10.0
    )
    assert assessment.route_deviation_risk > 0.0
    assert any(f.name == "ROUTE_DEVIATION" for f in assessment.active_factors)


def test_fall_and_audio_distress_contribution():
    """Fall and audio distress contribute independently and transparently."""
    engine = ContextualRiskFusionEngine()
    fall = make_fall_event(state=FallState.FALL_DETECTED, confidence=0.95)
    audio = make_audio_event(state=DistressAudioState.DISTRESS_DETECTED, distress_probability=0.88, confidence=0.90)
    snapshot = make_snapshot(fall_event=fall, audio_distress=audio)
    assessment = engine.evaluate_risk(
        snapshot=snapshot,
        area_risk_score=30.0
    )
    assert assessment.fall_risk > 0.0
    assert assessment.audio_distress_risk > 0.0
    assert assessment.risk_score > 50.0



# ==========================================
# 2. Missing Signals & Data Quality Tests
# ==========================================

def test_missing_signals_dynamically_renormalize():
    """Missing signals are not treated as zero risk; remaining signals re-normalize weights."""
    engine = ContextualRiskFusionEngine()
    # Provide only area risk (100.0) and motion anomaly (100.0); other signals are None
    snapshot = make_snapshot()
    assessment = engine.evaluate_risk(
        snapshot=snapshot,
        area_risk_score=100.0,
        motion_anomaly_score=100.0
    )
    # Since only area (0.2) and motion (0.15) exist, they re-normalize to 100% of the score
    assert assessment.risk_score == 100.0
    assert assessment.data_quality["signals"]["audio_distress"] == "UNAVAILABLE"
    assert assessment.data_quality["signals"]["fall_detection"] == "UNAVAILABLE"


def test_all_signals_missing_returns_zero_safely():
    """If all signals are unavailable, returns 0.0 with UNKNOWN risk level (not LOW)."""
    engine = ContextualRiskFusionEngine()
    snapshot = make_snapshot()
    assessment = engine.evaluate_risk(
        snapshot=snapshot,
        area_risk_score=None,
        motion_anomaly_score=None
    )
    assert assessment.risk_score == 0.0
    assert assessment.overall_confidence == 0.0
    assert assessment.risk_level == RiskLevel.UNKNOWN
    assert assessment.data_quality["signals"]["area_risk"] == "UNAVAILABLE"


# ==========================================
# 3. Temporal Reasoning & Recency Decay Tests
# ==========================================

def test_temporal_fall_decay():
    """Ancient fall event decays and has reduced risk contribution."""
    tracker = TemporalSignalTracker()
    engine = ContextualRiskFusionEngine(temporal_tracker=tracker)

    t0 = datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc)
    fall = make_fall_event(state=FallState.FALL_DETECTED, confidence=0.95, timestamp=t0)
    snapshot_t0 = make_snapshot(fall_event=fall, timestamp=t0)
    res_t0 = engine.evaluate_risk(snapshot_t0, area_risk_score=20.0)

    # 5 minutes later (300 seconds; half-life is 120s => decayed by > 80%)
    t1 = t0 + timedelta(minutes=5)
    snapshot_t1 = make_snapshot(fall_event=fall, timestamp=t1)
    res_t1 = engine.evaluate_risk(snapshot_t1, area_risk_score=20.0)

    assert res_t0.fall_risk > res_t1.fall_risk
    assert res_t1.fall_risk < res_t0.fall_risk * 0.5


def test_transitory_deviation_vs_sustained():
    """Single possible deviation has slightly lower scaling than sustained deviation."""
    tracker = TemporalSignalTracker()
    engine = ContextualRiskFusionEngine(temporal_tracker=tracker)
    t0 = datetime.now(timezone.utc)

    rd_possible = make_route_deviation(state=DeviationState.POSSIBLE_DEVIATION, confidence=0.7)
    s1 = make_snapshot(route_deviation=rd_possible, timestamp=t0)
    res1 = engine.evaluate_risk(s1, area_risk_score=30.0)

    # Second observation: sustained possible deviation
    s2 = make_snapshot(route_deviation=rd_possible, timestamp=t0 + timedelta(seconds=5))
    res2 = engine.evaluate_risk(s2, area_risk_score=30.0)

    assert res2.route_deviation_risk >= res1.route_deviation_risk


# ==========================================
# 4. Contextual Interactions & Bounded Clamping
# ==========================================

def test_contextual_interaction_area_and_deviation():
    """High area risk (>60) + confirmed deviation triggers compounded interaction boost."""
    engine = ContextualRiskFusionEngine()
    rd = make_route_deviation(state=DeviationState.DEVIATED, distance=80.0, confidence=0.9)
    snapshot = make_snapshot(route_deviation=rd)
    assessment = engine.evaluate_risk(
        snapshot=snapshot,
        area_risk_score=75.0
    )
    factor_names = [f.name for f in assessment.active_factors]
    assert "INTERACTION_HIGH_AREA_AND_DEVIATION" in factor_names


def test_contextual_interaction_audio_and_fall():
    """High audio distress + confirmed fall triggers physical distress interaction boost."""
    engine = ContextualRiskFusionEngine()
    fall = make_fall_event(state=FallState.FALL_DETECTED, confidence=0.9)
    audio = make_audio_event(state=DistressAudioState.DISTRESS_DETECTED, distress_probability=0.85)
    snapshot = make_snapshot(fall_event=fall, audio_distress=audio)
    assessment = engine.evaluate_risk(snapshot=snapshot, area_risk_score=40.0)

    factor_names = [f.name for f in assessment.active_factors]
    assert "INTERACTION_AUDIO_DISTRESS_AND_FALL" in factor_names
    assert assessment.risk_score <= 100.0  # Must be clamped strictly



# ==========================================
# 5. Risk Classification Boundaries
# ==========================================

@pytest.mark.parametrize("score,expected_level", [
    (0.0, RiskLevel.LOW),
    (24.99, RiskLevel.LOW),
    (25.0, RiskLevel.MEDIUM),
    (49.99, RiskLevel.MEDIUM),
    (50.0, RiskLevel.HIGH),
    (74.99, RiskLevel.HIGH),
    (75.0, RiskLevel.CRITICAL),
    (100.0, RiskLevel.CRITICAL)
])
def test_exact_risk_classification_boundaries(score, expected_level):
    """Verifies all boundary edges map deterministically to expected RiskLevels."""
    engine = ContextualRiskFusionEngine()
    # Force mock assessment using single area_risk score
    snapshot = make_snapshot()
    assessment = engine.evaluate_risk(snapshot=snapshot, area_risk_score=score)
    assert assessment.risk_level == expected_level


# ==========================================
# 6. Decision Engine & Hysteresis Tests
# ==========================================

def test_decision_engine_mapping_and_hysteresis_escalation():
    """Requires consecutive observations to escalate to CRITICAL."""
    engine = ContextualRiskFusionEngine()
    decision_engine = DecisionEngine()

    fall = make_fall_event(state=FallState.FALL_DETECTED, confidence=0.85)
    audio = make_audio_event(state=DistressAudioState.DISTRESS_DETECTED, distress_probability=0.85)
    snapshot = make_snapshot(fall_event=fall, audio_distress=audio)

    # First critical observation
    assessment1 = engine.evaluate_risk(snapshot, area_risk_score=85.0)
    assert assessment1.risk_score >= 75.0
    dec1 = decision_engine.evaluate(assessment1)

    # Escalation to CRITICAL is allowed on consecutive count or high-confidence audio+fall
    assert dec1.decision_tier in [DecisionTier.ELEVATED_MONITORING, DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED]

    # Second critical observation
    dec2 = decision_engine.evaluate(assessment1)
    assert dec2.decision_tier == DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED


def test_decision_deescalation_debouncing():
    """De-escalation holds state until multiple lower observations confirm recovery."""
    engine = ContextualRiskFusionEngine()
    decision_engine = DecisionEngine()

    fall = make_fall_event(state=FallState.FALL_DETECTED, confidence=0.95)
    audio = make_audio_event(state=DistressAudioState.DISTRESS_DETECTED, distress_probability=0.95)
    snapshot_high = make_snapshot(fall_event=fall, audio_distress=audio)


    # Escalate to CRITICAL
    a_high = engine.evaluate_risk(snapshot_high, area_risk_score=90.0)
    decision_engine.evaluate(a_high)
    d_crit = decision_engine.evaluate(a_high)
    assert d_crit.decision_tier == DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED

    # Now situation suddenly reports low risk
    snapshot_low = make_snapshot()
    a_low = engine.evaluate_risk(snapshot_low, area_risk_score=10.0)

    # First lower observation: held at CRITICAL due to de-escalation debounce
    d1 = decision_engine.evaluate(a_low)
    assert d1.decision_tier == DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED

    # Second lower observation: still held
    d2 = decision_engine.evaluate(a_low)
    assert d2.decision_tier == DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED

    # Third lower observation: confirmed de-escalation
    d3 = decision_engine.evaluate(a_low)
    assert d3.decision_tier != DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED


# ==========================================
# 7. Adaptive Sensor Manager Tests
# ==========================================

def test_sensor_policy_profiles():
    """Verifies sensor sampling parameters by decision tier."""
    manager = AdaptiveSensorManager()
    from app.contextual.schemas import DecisionOutput

    d_low = DecisionOutput(
        decision_tier=DecisionTier.MONITOR,
        hysteresis_state="STABLE",
        consecutive_observations=1,
        reason="Normal"
    )
    p_low = manager.generate_policy(d_low)
    assert p_low.profile == SensorProfile.LOW
    assert p_low.gps_interval_s == 60.0
    assert p_low.gyro_enabled is False

    d_crit = DecisionOutput(
        decision_tier=DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED,
        hysteresis_state="ESC_2",
        consecutive_observations=2,
        reason="Critical threat"
    )
    p_crit = manager.generate_policy(d_crit)
    assert p_crit.profile == SensorProfile.CRITICAL
    assert p_crit.gps_interval_s == 1.0
    assert p_crit.accel_sampling_rate_hz == 100.0
    assert p_crit.mic_duty_cycle_percent == 100.0


def test_sensor_policy_battery_optimization():
    """Low battery throttles non-critical sensing, but preserves CRITICAL sensing."""
    manager = AdaptiveSensorManager()
    from app.contextual.schemas import DecisionOutput

    low_battery = BatteryContext(battery_level=15.0, is_charging=False)

    # 1. Medium tier with low battery throttles GPS to 30s
    d_med = DecisionOutput(decision_tier=DecisionTier.ADAPT_MONITORING, hysteresis_state="STABLE", consecutive_observations=1, reason="M")
    p_med = manager.generate_policy(d_med, battery=low_battery)
    assert p_med.gps_interval_s == 30.0
    assert "Low battery optimization" in p_med.reason

    # 2. Critical tier with low battery keeps 1s GPS because safety takes precedence
    d_crit = DecisionOutput(decision_tier=DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED, hysteresis_state="STABLE", consecutive_observations=2, reason="C")
    p_crit = manager.generate_policy(d_crit, battery=low_battery)
    assert p_crit.gps_interval_s == 1.0
    assert "safety takes precedence" in p_crit.reason


def test_sensor_policy_network_degraded():
    """Degraded network recommends local buffering on edge client."""
    manager = AdaptiveSensorManager()
    from app.contextual.schemas import DecisionOutput

    net = NetworkContext(network_state=NetworkState.DEGRADED)
    d = DecisionOutput(decision_tier=DecisionTier.ELEVATED_MONITORING, hysteresis_state="STABLE", consecutive_observations=1, reason="High")
    p = manager.generate_policy(d, network=net)
    assert p.local_buffering_recommended is True


# ==========================================
# 8. REST API & Lifecycle Tests
# ==========================================

def test_api_contextual_safety_evaluate_and_reset():
    """Tests POST /contextual-safety/evaluate and POST /contextual-safety/reset."""
    # Reset state first
    r_reset = client.post("/contextual-safety/reset")
    assert r_reset.status_code == 200
    assert r_reset.json()["status"] == "reset"

    snapshot = make_snapshot(
        route_deviation=make_route_deviation(state=DeviationState.DEVIATED, distance=80.0, confidence=0.9)
    )

    payload = {
        "snapshot": snapshot.model_dump(mode="json"),
        "area_risk_score": 70.0,
        "battery": {"battery_level": 80.0, "is_charging": True},
        "network": {"network_state": "ONLINE"}
    }

    resp = client.post("/contextual-safety/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert "assessment" in data
    assert "decision" in data
    assert "sensor_policy" in data

    assessment = data["assessment"]
    assert assessment["risk_score"] > 50.0
    assert assessment["dominant_factor"] is not None

    policy = data["sensor_policy"]
    assert policy["profile"] in ["HIGH", "CRITICAL"]


# ==============================================================================
# 9. Phase 3 Safety Audit Verification Tests
# ==============================================================================

def test_audit_all_telemetry_missing_distinguishes_low_risk_from_no_data():
    """
    CRITICAL AUDIT 1:
    Verifies that 'No evidence of danger' != 'evidence of safety'.
    When all telemetry is missing:
    - risk_score = 0.0
    - overall_confidence = 0.0
    - risk_level = RiskLevel.UNKNOWN (NOT RiskLevel.LOW)
    - decision_tier = DecisionTier.DEGRADED_MONITORING (NOT DecisionTier.MONITOR)
    - sensor_policy = MEDIUM with local_buffering_recommended = True

    Contrasted with MEASURED LOW RISK:
    - signals present and confirming safety -> RiskLevel.LOW + DecisionTier.MONITOR
    """
    engine = ContextualRiskFusionEngine()
    decision_engine = DecisionEngine()
    sensor_mgr = AdaptiveSensorManager()

    # Part A: All signals missing / unavailable
    snapshot_missing = make_snapshot(
        journey_id="audit_missing_1",
        telemetry_quality=TelemetryQuality.MISSING,
        route_deviation=None,
        unexpected_stop=None,
        fall_event=None,
        audio_distress=None
    )
    assessment_missing = engine.evaluate_risk(
        snapshot=snapshot_missing,
        area_risk_score=None,
        motion_anomaly_score=None
    )

    assert assessment_missing.risk_score == 0.0
    assert assessment_missing.overall_confidence == 0.0
    # Must NOT automatically claim LOW / safe!
    assert assessment_missing.risk_level == RiskLevel.UNKNOWN
    assert assessment_missing.data_quality["signals"]["area_risk"] == "UNAVAILABLE"
    assert assessment_missing.data_quality["signals"]["motion_anomaly"] == "UNAVAILABLE"
    assert assessment_missing.data_quality["signals"]["route_deviation"] == "UNAVAILABLE"
    assert assessment_missing.data_quality["signals"]["unexpected_stop"] == "UNAVAILABLE"
    assert assessment_missing.data_quality["signals"]["fall_detection"] == "UNAVAILABLE"
    assert assessment_missing.data_quality["signals"]["audio_distress"] == "UNAVAILABLE"

    dec_missing = decision_engine.evaluate(assessment_missing)
    assert dec_missing.decision_tier == DecisionTier.DEGRADED_MONITORING
    assert "no evidence of danger != evidence of safety" in dec_missing.reason

    policy_missing = sensor_mgr.generate_policy(dec_missing)
    assert policy_missing.profile == SensorProfile.MEDIUM
    assert policy_missing.local_buffering_recommended is True

    # Part B: Measured Low Risk (Signals available and verifying safety)
    decision_engine.reset_all()
    snapshot_safe = make_snapshot(
        journey_id="audit_safe_1",
        telemetry_quality=TelemetryQuality.VALID
    )
    assessment_safe = engine.evaluate_risk(
        snapshot=snapshot_safe,
        area_risk_score=5.0,
        area_risk_confidence=1.0,
        motion_anomaly_score=2.0,
        motion_confidence=1.0
    )

    assert assessment_safe.risk_score < 10.0
    assert assessment_safe.overall_confidence > 0.80
    assert assessment_safe.risk_level == RiskLevel.LOW

    dec_safe = decision_engine.evaluate(assessment_safe)
    assert dec_safe.decision_tier == DecisionTier.MONITOR
    policy_safe = sensor_mgr.generate_policy(dec_safe)
    assert policy_safe.profile == SensorProfile.LOW
    assert policy_safe.local_buffering_recommended is False


def test_audit_fall_alone_does_not_immediately_escalate_to_critical():
    """
    CRITICAL AUDIT 2A:
    Fall alone (even confirmed and high-risk) does NOT immediately escalate to CRITICAL.
    Must require 2 consecutive observations.
    """
    engine = ContextualRiskFusionEngine()
    decision_engine = DecisionEngine()

    fall = make_fall_event(state=FallState.FALL_DETECTED, confidence=0.95)
    snapshot = make_snapshot(journey_id="audit_fall_alone", fall_event=fall)

    assessment = engine.evaluate_risk(snapshot, area_risk_score=90.0)
    assert assessment.risk_score >= 75.0

    # Observation 1: held at ELEVATED_MONITORING while autonomous response confirmation is pending
    d1 = decision_engine.evaluate(assessment)
    assert d1.decision_tier == DecisionTier.ELEVATED_MONITORING
    assert d1.decision_tier != DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED

    # Observation 2: confirms escalation to CRITICAL
    d2 = decision_engine.evaluate(assessment)
    assert d2.decision_tier == DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED


def test_audit_audio_alone_does_not_immediately_escalate_to_critical():
    """
    CRITICAL AUDIT 2B:
    Audio distress alone (even high probability) does NOT immediately escalate to CRITICAL.
    Must require 2 consecutive observations.
    """
    engine = ContextualRiskFusionEngine()
    decision_engine = DecisionEngine()

    audio = make_audio_event(state=DistressAudioState.DISTRESS_DETECTED, distress_probability=0.98, confidence=0.95)
    snapshot = make_snapshot(journey_id="audit_audio_alone", audio_distress=audio)

    assessment = engine.evaluate_risk(snapshot, area_risk_score=90.0)
    assert assessment.risk_score >= 75.0

    # Observation 1: held at ELEVATED_MONITORING
    d1 = decision_engine.evaluate(assessment)
    assert d1.decision_tier == DecisionTier.ELEVATED_MONITORING

    # Observation 2: confirmed
    d2 = decision_engine.evaluate(assessment)
    assert d2.decision_tier == DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED


def test_audit_possible_fall_and_possible_audio_does_not_bypass():
    """
    CRITICAL AUDIT 2C:
    Possible fall + possible audio does NOT trigger the critical bypass.
    """
    engine = ContextualRiskFusionEngine()
    decision_engine = DecisionEngine()

    fall_pos = make_fall_event(state=FallState.POSSIBLE_FALL, confidence=0.60)
    audio_pos = make_audio_event(state=DistressAudioState.POSSIBLE_DISTRESS, distress_probability=0.65, confidence=0.60)
    snapshot = make_snapshot(journey_id="audit_possible_bypass", fall_event=fall_pos, audio_distress=audio_pos)

    assessment = engine.evaluate_risk(snapshot, area_risk_score=90.0)
    # Interaction must not be active
    assert not any(f.name == "INTERACTION_AUDIO_DISTRESS_AND_FALL" for f in assessment.active_factors)

    d1 = decision_engine.evaluate(assessment)
    # Cannot immediately bypass to CRITICAL
    assert d1.decision_tier != DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED


def test_audit_confirmed_fall_and_audio_within_window_bypasses():
    """
    CRITICAL AUDIT 2D & 2G:
    Confirmed fall + confirmed distress audio within configurable correlation window (<= 15s)
    immediately escalates to CRITICAL on 1st observation.
    """
    engine = ContextualRiskFusionEngine()
    decision_engine = DecisionEngine()
    t0 = datetime.now(timezone.utc)

    # Both confirmed, separated by 3.0s (within default 15.0s window)
    fall = make_fall_event(state=FallState.FALL_DETECTED, confidence=0.95, timestamp=t0 - timedelta(seconds=3))
    audio = make_audio_event(state=DistressAudioState.DISTRESS_DETECTED, distress_probability=0.95, confidence=0.95, timestamp=t0)
    snapshot = make_snapshot(journey_id="audit_confirmed_bypass", fall_event=fall, audio_distress=audio, timestamp=t0)

    assessment = engine.evaluate_risk(snapshot, area_risk_score=50.0)
    assert any(f.name == "INTERACTION_AUDIO_DISTRESS_AND_FALL" for f in assessment.active_factors)
    assert assessment.risk_score >= 75.0

    # Observation 1: immediately bypasses hysteresis to AUTONOMOUS_RESPONSE_REQUIRED
    d1 = decision_engine.evaluate(assessment)
    assert d1.decision_tier == DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED


def test_audit_old_fall_new_audio_does_not_bypass():
    """
    CRITICAL AUDIT 2E:
    OLD fall + NEW audio outside temporal window (> 15s) must NOT automatically qualify for bypass.
    """
    engine = ContextualRiskFusionEngine()
    decision_engine = DecisionEngine()
    t0 = datetime.now(timezone.utc)

    # Fall happened 60s ago, audio happened now (difference 60s > 15s window)
    fall_old = make_fall_event(state=FallState.FALL_DETECTED, confidence=0.95, timestamp=t0 - timedelta(seconds=60))
    audio_new = make_audio_event(state=DistressAudioState.DISTRESS_DETECTED, distress_probability=0.95, confidence=0.95, timestamp=t0)
    snapshot = make_snapshot(journey_id="audit_old_fall", fall_event=fall_old, audio_distress=audio_new, timestamp=t0)

    assessment = engine.evaluate_risk(snapshot, area_risk_score=90.0)
    assert not any(f.name == "INTERACTION_AUDIO_DISTRESS_AND_FALL" for f in assessment.active_factors)

    d1 = decision_engine.evaluate(assessment)
    assert d1.decision_tier != DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED


def test_audit_new_fall_old_audio_does_not_bypass():
    """
    CRITICAL AUDIT 2F:
    NEW fall + OLD audio outside temporal window (> 15s) must NOT automatically qualify for bypass.
    """
    engine = ContextualRiskFusionEngine()
    decision_engine = DecisionEngine()
    t0 = datetime.now(timezone.utc)

    # Audio happened 50s ago, fall happened now (difference 50s > 15s window)
    audio_old = make_audio_event(state=DistressAudioState.DISTRESS_DETECTED, distress_probability=0.95, confidence=0.95, timestamp=t0 - timedelta(seconds=50))
    fall_new = make_fall_event(state=FallState.FALL_DETECTED, confidence=0.95, timestamp=t0)
    snapshot = make_snapshot(journey_id="audit_old_audio", fall_event=fall_new, audio_distress=audio_old, timestamp=t0)

    assessment = engine.evaluate_risk(snapshot, area_risk_score=90.0)
    assert not any(f.name == "INTERACTION_AUDIO_DISTRESS_AND_FALL" for f in assessment.active_factors)

    d1 = decision_engine.evaluate(assessment)
    assert d1.decision_tier != DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED


def test_audit_recovered_events_do_not_trigger_bypass():
    """
    CRITICAL AUDIT 2H:
    Stale / recovered events must NOT count as simultaneous evidence.
    """
    engine = ContextualRiskFusionEngine()
    decision_engine = DecisionEngine()
    t0 = datetime.now(timezone.utc)

    # Fall recovered + fresh audio
    fall_rec = make_fall_event(state=FallState.RECOVERED, confidence=0.95, timestamp=t0)
    audio_fresh = make_audio_event(state=DistressAudioState.DISTRESS_DETECTED, distress_probability=0.95, confidence=0.95, timestamp=t0)
    s1 = make_snapshot(journey_id="audit_rec_1", fall_event=fall_rec, audio_distress=audio_fresh, timestamp=t0)

    a1 = engine.evaluate_risk(s1, area_risk_score=90.0)
    assert not any(f.name == "INTERACTION_AUDIO_DISTRESS_AND_FALL" for f in a1.active_factors)
    d1 = decision_engine.evaluate(a1)
    assert d1.decision_tier != DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED


def test_audit_confidence_modulates_dynamic_weight_renormalization():
    """
    CRITICAL AUDIT 3:
    Confidence actually affects contribution when weights are dynamically renormalized.
    If only one signal is available:
    - High confidence (0.95) contributes up to 95 points.
    - Low confidence (0.20) contributes only 20 points, NOT 100 points!
    """
    engine = ContextualRiskFusionEngine()

    # Case A: Only fall_event available, HIGH confidence (0.95)
    fall_high_conf = make_fall_event(state=FallState.FALL_DETECTED, confidence=0.95)
    s_high = make_snapshot(fall_event=fall_high_conf)
    a_high = engine.evaluate_risk(s_high, area_risk_score=None, motion_anomaly_score=None)

    # Case B: Only fall_event available, LOW confidence (0.20)
    fall_low_conf = make_fall_event(state=FallState.FALL_DETECTED, confidence=0.20)
    s_low = make_snapshot(fall_event=fall_low_conf)
    a_low = engine.evaluate_risk(s_low, area_risk_score=None, motion_anomaly_score=None)

    print(f"High-conf fall risk: {a_high.risk_score} | Low-conf fall risk: {a_low.risk_score}")
    assert a_high.risk_score == 95.0
    assert a_low.risk_score == 20.0
    assert a_low.risk_score < 25.0
    assert a_low.risk_level == RiskLevel.LOW
    assert a_high.risk_level == RiskLevel.CRITICAL

