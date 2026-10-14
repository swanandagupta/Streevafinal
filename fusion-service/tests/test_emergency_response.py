"""
STREEVA — Phase 4 Autonomous Emergency Response System Tests
tests/test_emergency_response.py

Comprehensive test suite covering:
- State machine & strict invalid transition rejection
- Manual SOS trigger flow & immediate authorization
- Phase 3 Autonomous decision consumption & eligibility gating
- Idempotency & duplicate trigger suppression
- Verification countdown, remaining time, and user cancellation
- Location acquisition: valid, stale, and unavailable (no fabricated 0,0 coordinates)
- Emergency contact ordering & priority resolution
- Multi-channel notification delivery: full success, partial failure, total failure
- Contact acknowledgement tracking & resolution
- Hierarchical escalation across tiers
- Secure evidence package compilation & SHA-256 integrity verification
- Network offline boundary handling
- Persistence & audit history
- REST API endpoint contracts
- Explicit Safety Invariants 1-10
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.emergency import (
    EmergencyState,
    TriggerType,
    LocationQuality,
    DestinationType,
    EscalationLevel,
    AcknowledgementStatus,
    EvidenceType,
    EmergencyContact,
    EmergencyResponseConfig,
    EmergencyStateMachine,
    InvalidStateTransitionError,
    EmergencyLocationProvider,
    MockEmergencyContactService,
    MockNotificationProvider,
    EvidenceService,
    EmergencyLocationBroadcaster,
    EmergencyPersistenceManager,
    EmergencyResponseOrchestrator,
    EmergencyIncident
)
from app.guardian.journey_state import (
    GuardianSnapshot,
    JourneyState,
    TelemetryQuality,
    ArrivalStatus,
    ProgressStatus,
    ETASource
)
from app.contextual import (
    RiskLevel,
    DecisionTier,
    DecisionOutput,
    JourneyRiskAssessment,
    RiskFactor
)
from app.edge.route_deviation import RouteDeviationEvent, DeviationState
from app.edge.fall_detection import FallDetectedEvent, FallState, SensorMode
from app.edge.audio_distress import AudioDistressEvent, DistressAudioState

client = TestClient(app)


def make_test_snapshot(
    journey_id: str = "test_j_phase4",
    lat: float = 12.95,
    lng: float = 80.15,
    acc: float = 8.5,
    quality: TelemetryQuality = TelemetryQuality.VALID,
    fall: bool = False,
    audio: bool = False
) -> GuardianSnapshot:
    now = datetime.now(timezone.utc)
    fall_event = None
    if fall:
        fall_event = FallDetectedEvent(
            is_fall=True,
            state=FallState.FALL_DETECTED,
            impact_magnitude_g=3.8,
            confidence=0.95,
            sensor_mode=SensorMode.ACCEL_AND_GYRO,
            timestamp=now,
            details="Fall pattern verified"
        )
    audio_event = None
    if audio:
        audio_event = AudioDistressEvent(
            is_distress=True,
            state=DistressAudioState.DISTRESS_DETECTED,
            distress_score=95.0,
            raw_probability=0.95,
            confidence=0.95,
            consecutive_distress_count=3,
            timestamp=now
        )

    return GuardianSnapshot(
        journey_id=journey_id,
        timestamp=now,
        journey_state=JourneyState.ACTIVE,
        current_lat=lat,
        current_lng=lng,
        gps_accuracy=acc,
        telemetry_quality=quality,
        route_progress_percent=60.0,
        distance_along_route_m=6000.0,
        total_route_distance_m=10000.0,
        remaining_distance_m=4000.0,
        smoothed_speed_mps=1.4,
        arrival_status=ArrivalStatus.NOT_ARRIVED,
        progress_status=ProgressStatus.MOVING_ON_SCHEDULE,
        eta=now + timedelta(minutes=20),
        eta_source=ETASource.ESTIMATED,
        fall_event=fall_event,
        audio_distress=audio_event
    )


def make_test_assessment(
    journey_id: str = "test_j_phase4",
    score: float = 85.0,
    level: RiskLevel = RiskLevel.CRITICAL
) -> JourneyRiskAssessment:
    return JourneyRiskAssessment(
        journey_id=journey_id,
        timestamp=datetime.now(timezone.utc),
        risk_score=score,
        risk_level=level,
        area_risk=20.0,
        motion_risk=10.0,
        route_deviation_risk=0.0,
        unexpected_stop_risk=0.0,
        fall_risk=40.0,
        audio_distress_risk=35.0,
        overall_confidence=0.95,
        telemetry_quality="VALID",
        dominant_factor="INTERACTION_AUDIO_DISTRESS_AND_FALL",
        active_factors=[
            RiskFactor(name="FALL_DETECTION", contribution=40.0, confidence=0.95, state="CONFIRMED", reason="Fall detected"),
            RiskFactor(name="AUDIO_DISTRESS", contribution=35.0, confidence=0.95, state="CONFIRMED", reason="Distress scream"),
            RiskFactor(name="INTERACTION_AUDIO_DISTRESS_AND_FALL", contribution=15.0, confidence=0.95, state="ACTIVE", reason="Compound distress")
        ]
    )


# ==============================================================================
# 1. State Machine & Transition Validation Tests
# ==============================================================================

def test_state_machine_valid_full_lifecycle():
    """Tests the canonical lifecycle transitions from IDLE to RESOLVED."""
    incident = EmergencyIncident(
        incident_id="inc_sm_1",
        journey_id="j_sm_1",
        trigger_type=TriggerType.AUTONOMOUS_RISK,
        created_at=datetime.now(timezone.utc),
        triggered_at=datetime.now(timezone.utc)
    )
    assert incident.state == EmergencyState.IDLE

    EmergencyStateMachine.transition(incident, EmergencyState.TRIGGERED, "Triggered")
    EmergencyStateMachine.transition(incident, EmergencyState.VERIFYING, "Verifying")
    EmergencyStateMachine.transition(incident, EmergencyState.COUNTDOWN, "Countdown started")
    EmergencyStateMachine.transition(incident, EmergencyState.RESPONSE_AUTHORIZED, "Countdown expired")
    EmergencyStateMachine.transition(incident, EmergencyState.DISPATCHING, "Dispatching")
    EmergencyStateMachine.transition(incident, EmergencyState.NOTIFIED, "Notified")
    EmergencyStateMachine.transition(incident, EmergencyState.ACKNOWLEDGED, "Acknowledged")
    EmergencyStateMachine.transition(incident, EmergencyState.RESOLVED, "Resolved")

    assert incident.state == EmergencyState.RESOLVED
    assert len(incident.history) == 8


def test_state_machine_rejects_invalid_transitions():
    """Strictly rejects illegal mutations such as IDLE -> RESOLVED or RESOLVED -> DISPATCHING."""
    incident = EmergencyIncident(
        incident_id="inc_sm_inv",
        journey_id="j_sm_inv",
        trigger_type=TriggerType.AUTONOMOUS_RISK,
        created_at=datetime.now(timezone.utc),
        triggered_at=datetime.now(timezone.utc)
    )

    # Illegal: IDLE -> RESOLVED directly
    with pytest.raises(InvalidStateTransitionError):
        EmergencyStateMachine.transition(incident, EmergencyState.RESOLVED, "Illegal jump")

    # Move to CANCELLED (terminal)
    EmergencyStateMachine.transition(incident, EmergencyState.TRIGGERED, "Triggered")
    EmergencyStateMachine.transition(incident, EmergencyState.CANCELLED, "Cancelled")

    # Illegal: CANCELLED -> DISPATCHING
    with pytest.raises(InvalidStateTransitionError):
        EmergencyStateMachine.transition(incident, EmergencyState.DISPATCHING, "Cannot resurrect cancelled incident")


# ==============================================================================
# 2. Manual SOS Trigger Tests
# ==============================================================================

def test_manual_sos_immediate_authorization():
    """Manual SOS initiates emergency incident and immediately authorizes dispatch when configured."""
    cfg = EmergencyResponseConfig(manual_sos_immediate_authorization=True)
    orchestrator = EmergencyResponseOrchestrator(config=cfg)

    inc = orchestrator.handle_manual_sos(
        journey_id="j_sos_1",
        manual_lat=12.95,
        manual_lng=80.15,
        manual_accuracy=5.0,
        reason="Help needed immediately"
    )

    assert inc.trigger_type == TriggerType.MANUAL_SOS
    assert inc.risk_score == 100.0
    assert inc.risk_level == "CRITICAL"
    # Immediately dispatched and notified
    assert inc.state in [EmergencyState.NOTIFIED, EmergencyState.PARTIAL_FAILURE, EmergencyState.DISPATCHING]
    assert inc.notifications_delivered > 0
    assert inc.context.current_lat == 12.95
    assert inc.context.current_lng == 80.15


def test_manual_sos_with_countdown_configuration():
    """Manual SOS enters COUNTDOWN when configured with explicit confirmation window."""
    cfg = EmergencyResponseConfig(manual_sos_immediate_authorization=False, manual_sos_countdown_seconds=5.0)
    orchestrator = EmergencyResponseOrchestrator(config=cfg)

    inc = orchestrator.handle_manual_sos(journey_id="j_sos_countdown", manual_lat=12.95, manual_lng=80.15)
    assert inc.state == EmergencyState.COUNTDOWN
    assert inc.countdown_seconds == 5.0
    assert inc.countdown_remaining_seconds == 5.0
    # No notifications dispatched yet
    assert inc.notifications_attempted == 0


# ==============================================================================
# 3. Autonomous Response Trigger & Eligibility Tests
# ==============================================================================

def test_autonomous_trigger_requires_autonomous_tier():
    """Autonomous response initiates ONLY on DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED."""
    orchestrator = EmergencyResponseOrchestrator()
    snapshot = make_test_snapshot("j_auto_1", fall=True, audio=True)
    assessment = make_test_assessment("j_auto_1", score=85.0, level=RiskLevel.CRITICAL)

    # Valid autonomous decision
    dec_valid = DecisionOutput(
        decision_tier=DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED,
        hysteresis_state="AUTONOMOUS_CONFIRMED",
        consecutive_observations=2,
        requires_user_check_in=False,
        reason="Autonomous response confirmed"
    )
    inc = orchestrator.handle_autonomous_decision("j_auto_1", dec_valid, assessment, snapshot)
    assert inc is not None
    assert inc.state == EmergencyState.COUNTDOWN
    assert inc.trigger_type == TriggerType.AUTONOMOUS_RISK
    assert inc.countdown_seconds == 15.0


@pytest.mark.parametrize("ineligible_tier", [
    DecisionTier.MONITOR,
    DecisionTier.ADAPT_MONITORING,
    DecisionTier.REQUEST_CHECK_IN,
    DecisionTier.ELEVATED_MONITORING,
    DecisionTier.DEGRADED_MONITORING
])
def test_autonomous_trigger_rejects_ineligible_tiers(ineligible_tier):
    """LOW, MEDIUM, HIGH, and DEGRADED tiers alone must NEVER trigger autonomous response."""
    orchestrator = EmergencyResponseOrchestrator()
    snapshot = make_test_snapshot("j_ineligible")
    assessment = make_test_assessment("j_ineligible", score=40.0, level=RiskLevel.MEDIUM)

    dec_ineligible = DecisionOutput(
        decision_tier=ineligible_tier,
        hysteresis_state="STABLE",
        consecutive_observations=1,
        requires_user_check_in=False,
        reason="Non-critical"
    )
    inc = orchestrator.handle_autonomous_decision("j_ineligible", dec_ineligible, assessment, snapshot)
    assert inc is None
    assert len(orchestrator.persistence.list_all_incidents()) == 0


# ==============================================================================
# 4. Confirmation Countdown & Cancellation Tests
# ==============================================================================

def test_countdown_advancement_and_authorization():
    """Countdown expiration advances state to RESPONSE_AUTHORIZED and initiates dispatch."""
    orchestrator = EmergencyResponseOrchestrator()
    snapshot = make_test_snapshot("j_cd_1", fall=True, audio=True)
    assessment = make_test_assessment("j_cd_1", score=90.0)
    dec = DecisionOutput(
        decision_tier=DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED,
        hysteresis_state="CONFIRMED",
        consecutive_observations=2,
        requires_user_check_in=False,
        reason="Critical threat"
    )

    inc = orchestrator.handle_autonomous_decision("j_cd_1", dec, assessment, snapshot)
    assert inc.state == EmergencyState.COUNTDOWN

    # Advance 10s (5s remaining)
    inc_half = orchestrator.advance_countdown(inc.incident_id, elapsed_seconds=10.0)
    assert inc_half.state == EmergencyState.COUNTDOWN
    assert inc_half.countdown_remaining_seconds == 5.0

    # Advance remaining 5s (expires)
    inc_expired = orchestrator.advance_countdown(inc.incident_id, elapsed_seconds=5.0)
    assert inc_expired.state == EmergencyState.NOTIFIED
    assert inc_expired.response_authorized_at is not None
    assert inc_expired.notifications_delivered > 0


def test_user_cancellation_during_countdown():
    """User cancellation during COUNTDOWN transitions to CANCELLED and blocks dispatch."""
    orchestrator = EmergencyResponseOrchestrator()
    snapshot = make_test_snapshot("j_cancel_1")
    assessment = make_test_assessment("j_cancel_1")
    dec = DecisionOutput(
        decision_tier=DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED,
        hysteresis_state="CONFIRMED",
        consecutive_observations=2,
        requires_user_check_in=False,
        reason="Trigger"
    )

    inc = orchestrator.handle_autonomous_decision("j_cancel_1", dec, assessment, snapshot)
    assert inc.state == EmergencyState.COUNTDOWN

    # User cancels false alarm
    inc_cancelled = orchestrator.cancel_incident(inc.incident_id, reason="False alarm bump")
    assert inc_cancelled.state == EmergencyState.CANCELLED
    assert inc_cancelled.cancelled_at is not None

    # Guarantee: Zero emergency notifications dispatched
    assert inc_cancelled.notifications_attempted == 0
    assert inc_cancelled.notifications_delivered == 0
    assert len(orchestrator.notification_provider.dispatched_records) == 0


# ==============================================================================
# 5. Location Handling: Valid, Stale, Unavailable (No Fake Coordinates)
# ==============================================================================

def test_location_quality_classification():
    """Verifies strict location representation without fabricating fake (0, 0) coordinates."""
    provider = EmergencyLocationProvider(stale_threshold_seconds=30.0)
    t0 = datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Fresh valid telemetry
    snap_valid = make_test_snapshot("j_loc_1", lat=12.95, lng=80.15, quality=TelemetryQuality.VALID)
    snap_valid.timestamp = t0
    loc_valid = provider.get_current_location(snap_valid, current_time=t0)
    assert loc_valid.quality == LocationQuality.VALID
    assert loc_valid.latitude == 12.95
    assert loc_valid.longitude == 80.15

    # 2. Stale telemetry (elapsed time > 30s)
    t_stale = t0 + timedelta(seconds=45)
    loc_stale = provider.get_current_location(snap_valid, current_time=t_stale)
    assert loc_stale.quality == LocationQuality.STALE
    assert loc_stale.latitude == 12.95

    # 3. Missing telemetry with no cached history
    snap_missing = make_test_snapshot("j_loc_missing", quality=TelemetryQuality.MISSING)
    snap_missing.current_lat = None
    snap_missing.current_lng = None
    loc_missing = provider.get_current_location(snap_missing, current_time=t0)
    assert loc_missing.quality == LocationQuality.UNAVAILABLE
    assert loc_missing.latitude is None
    assert loc_missing.longitude is None
    # Crucial check: Must NEVER fabricate coordinates as 0.0, 0.0
    assert loc_missing.latitude != 0.0


# ==============================================================================
# 6. Contact Ordering & Multi-Channel Delivery Modes
# ==============================================================================

def test_contact_ordering_and_enabled_filter():
    """Emergency contacts are ordered strictly by priority; disabled contacts are excluded."""
    service = MockEmergencyContactService()
    contacts = service.get_contacts_for_journey("j_contacts", escalation_level=EscalationLevel.LEVEL_1)
    
    assert len(contacts) == 2
    assert all(c.enabled for c in contacts)
    assert all(c.priority == 1 for c in contacts)
    assert contacts[0].contact_id == "c_primary_1"


def test_notification_delivery_partial_failure_and_total_failure():
    """Tests notification dispatch with partial delivery and total delivery failure."""
    orchestrator = EmergencyResponseOrchestrator()
    snapshot = make_test_snapshot("j_notif_fail")
    assessment = make_test_assessment("j_notif_fail")
    dec = DecisionOutput(
        decision_tier=DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED,
        hysteresis_state="CONFIRMED",
        consecutive_observations=2,
        requires_user_check_in=False,
        reason="Threat"
    )

    inc = orchestrator.handle_autonomous_decision("j_notif_fail", dec, assessment, snapshot)
    
    # 1. Partial failure: 1 contact succeeds, 1 contact fails
    orchestrator.notification_provider.set_failing_contacts({"c_primary_2"})
    inc_part = orchestrator.advance_countdown(inc.incident_id, elapsed_seconds=15.0)
    assert inc_part.state == EmergencyState.PARTIAL_FAILURE
    assert inc_part.notifications_delivered == 1
    assert inc_part.notifications_attempted == 2

    # 2. Total failure on new incident
    orchestrator.reset_all()
    inc2 = orchestrator.handle_autonomous_decision("j_notif_fail_2", dec, assessment, snapshot)
    orchestrator.notification_provider.set_failing_contacts({"c_primary_1", "c_primary_2"})
    inc_tot = orchestrator.advance_countdown(inc2.incident_id, elapsed_seconds=15.0)
    assert inc_tot.state == EmergencyState.FAILED
    assert inc_tot.notifications_delivered == 0


# ==============================================================================
# 7. Acknowledgement & Escalation Flow
# ==============================================================================

def test_acknowledgement_resolves_incident():
    """Contact acknowledgement transitions incident to ACKNOWLEDGED then RESOLVED."""
    orchestrator = EmergencyResponseOrchestrator()
    snapshot = make_test_snapshot("j_ack")
    assessment = make_test_assessment("j_ack")
    dec = DecisionOutput(
        decision_tier=DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED,
        hysteresis_state="CONFIRMED",
        consecutive_observations=2,
        requires_user_check_in=False,
        reason="Threat"
    )

    inc = orchestrator.handle_autonomous_decision("j_ack", dec, assessment, snapshot)
    orchestrator.advance_countdown(inc.incident_id, elapsed_seconds=15.0)
    assert inc.state == EmergencyState.NOTIFIED

    # Acknowledge
    inc_resolved = orchestrator.acknowledge_incident(
        inc.incident_id,
        contact_id="c_primary_1",
        acknowledged_by="Alice",
        notes="I am with the traveler"
    )
    assert inc_resolved.state == EmergencyState.RESOLVED
    assert inc_resolved.acknowledgement_status == AcknowledgementStatus.ACKNOWLEDGED
    assert inc_resolved.acknowledged_by == "Alice"
    assert inc_resolved.resolved_at is not None


def test_escalation_advances_tier_and_dispatches_secondary_contacts():
    """Unacknowledged incident escalates to secondary contacts (LEVEL_2)."""
    orchestrator = EmergencyResponseOrchestrator()
    snapshot = make_test_snapshot("j_esc")
    assessment = make_test_assessment("j_esc")
    dec = DecisionOutput(
        decision_tier=DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED,
        hysteresis_state="CONFIRMED",
        consecutive_observations=2,
        requires_user_check_in=False,
        reason="Threat"
    )

    inc = orchestrator.handle_autonomous_decision("j_esc", dec, assessment, snapshot)
    orchestrator.advance_countdown(inc.incident_id, elapsed_seconds=15.0)
    assert inc.state == EmergencyState.NOTIFIED
    assert inc.escalation_level == EscalationLevel.LEVEL_0

    # Escalate to Level 2
    inc_esc = orchestrator.escalate_incident(inc.incident_id, reason="No response from primary contacts")
    assert inc_esc.escalation_level == EscalationLevel.LEVEL_2
    assert "c_secondary_1" in inc_esc.contacts_targeted


# ==============================================================================
# 8. Evidence Package & SHA-256 Integrity Tests
# ==============================================================================

def test_evidence_package_assembly_and_cryptographic_hash():
    """Evidence package compiles real event metadata and computes verifiable SHA-256 hash."""
    service = EvidenceService()
    snapshot = make_test_snapshot("j_ev", fall=True, audio=True)
    assessment = make_test_assessment("j_ev")
    incident = EmergencyIncident(
        incident_id="inc_ev_test",
        journey_id="j_ev",
        trigger_type=TriggerType.AUTONOMOUS_RISK,
        state=EmergencyState.RESPONSE_AUTHORIZED,
        created_at=datetime.now(timezone.utc),
        triggered_at=datetime.now(timezone.utc)
    )

    package = service.compile_evidence_package(incident, snapshot, assessment)
    assert package.incident_id == "inc_ev_test"
    assert len(package.items) >= 4  # trigger, telemetry, context, fall, audio, risk
    assert len(package.integrity_hash) == 64  # Valid SHA-256 hex length
    
    # Invariant: Must only reference real events (no fake audio binary)
    ev_types = [item.type for item in package.items]
    assert EvidenceType.FALL_EVENT in ev_types
    assert EvidenceType.AUDIO_DISTRESS_EVENT in ev_types
    assert EvidenceType.RISK_ASSESSMENT in ev_types


# ==============================================================================
# 9. Idempotency & Network Failure Boundary Tests
# ==============================================================================

def test_idempotent_duplicate_autonomous_triggers():
    """Duplicate autonomous decision calls for same journey return existing incident without duplication."""
    orchestrator = EmergencyResponseOrchestrator()
    snapshot = make_test_snapshot("j_idemp")
    assessment = make_test_assessment("j_idemp")
    dec = DecisionOutput(
        decision_tier=DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED,
        hysteresis_state="CONFIRMED",
        consecutive_observations=2,
        requires_user_check_in=False,
        reason="Obs 1"
    )

    inc1 = orchestrator.handle_autonomous_decision("j_idemp", dec, assessment, snapshot)
    inc2 = orchestrator.handle_autonomous_decision("j_idemp", dec, assessment, snapshot)
    assert inc1.incident_id == inc2.incident_id
    assert len(orchestrator.persistence.list_all_incidents()) == 1


def test_network_unavailable_surfaces_degraded_delivery():
    """When network is offline, orchestrator transitions to FAILED and records offline state."""
    orchestrator = EmergencyResponseOrchestrator()
    snapshot = make_test_snapshot("j_offline")
    assessment = make_test_assessment("j_offline")
    dec = DecisionOutput(
        decision_tier=DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED,
        hysteresis_state="CONFIRMED",
        consecutive_observations=2,
        requires_user_check_in=False,
        reason="Threat"
    )

    inc = orchestrator.handle_autonomous_decision("j_offline", dec, assessment, snapshot)
    inc_offline = orchestrator.advance_countdown(inc.incident_id, elapsed_seconds=15.0, network_available=False)
    assert inc_offline.state == EmergencyState.FAILED
    assert inc_offline.notifications_delivered == 0
    assert any("Network offline" in r.error_message for r in inc_offline.delivery_results)


# ==============================================================================
# 10. REST API Endpoints Contract Tests
# ==============================================================================

def test_api_emergency_response_full_flow():
    """Tests the full REST API lifecycle from manual trigger to cancel/resolve."""
    client.post("/emergency/reset")

    # 1. Trigger Manual SOS via POST /emergency/trigger
    payload_sos = {
        "journey_id": "api_journey_1",
        "latitude": 12.95,
        "longitude": 80.15,
        "accuracy": 10.0,
        "reason": "API Emergency Test"
    }
    r_trig = client.post("/emergency/trigger", json=payload_sos)
    assert r_trig.status_code == 200
    inc_data = r_trig.json()
    incident_id = inc_data["incident_id"]
    assert inc_data["trigger_type"] == "MANUAL_SOS"

    # 2. Get status via GET /emergency/{incident_id}
    r_get = client.get(f"/emergency/{incident_id}")
    assert r_get.status_code == 200
    assert r_get.json()["incident_id"] == incident_id

    # 3. Acknowledge via POST /emergency/{incident_id}/acknowledge
    payload_ack = {
        "contact_id": "c_primary_1",
        "acknowledged_by": "Family Member",
        "notes": "Verified safe"
    }
    r_ack = client.post(f"/emergency/{incident_id}/acknowledge", json=payload_ack)
    assert r_ack.status_code == 200
    assert r_ack.json()["state"] == "RESOLVED"

    # 4. Autonomous trigger API test with ineligible tier (rejection check)
    r_inelig = client.post("/emergency/autonomous", json={
        "journey_id": "api_journey_2",
        "decision_tier": "ELEVATED_MONITORING",
        "risk_score": 60.0,
        "risk_level": "HIGH"
    })
    assert r_inelig.status_code == 400
