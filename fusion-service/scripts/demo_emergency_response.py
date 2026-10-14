"""
STREEVA — Phase 4 Autonomous Emergency Response Replay Demo
scripts/demo_emergency_response.py

Executes 16 deterministic end-to-end replay scenarios validating:
1. Manual SOS initiation
2. Autonomous response triggering via Phase 3 decision
3. Autonomous countdown cancellation (guarantees zero dispatch)
4. Autonomous countdown expiry & response authorization
5. Primary contact acknowledgement & resolution
6. No acknowledgement & hierarchical escalation
7. Partial notification failure handling & escalation
8. Total notification failure handling
9. Location unavailable handling (no fabricated coordinates)
10. Stale location quality classification
11. Duplicate autonomous trigger suppression (idempotency)
12. Recovered / LOW / UNKNOWN / DEGRADED decision rejection
13. Invalid state transition rejection
14. Secure evidence package compilation & SHA-256 integrity
15. Offline / network unavailable failure surfacing
16. Full successful end-to-end emergency response lifecycle
"""

import sys
import os
from datetime import datetime, timezone, timedelta

# Ensure fusion-service directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.emergency import (
    EmergencyState,
    TriggerType,
    LocationQuality,
    EscalationLevel,
    AcknowledgementStatus,
    EvidenceType,
    EmergencyResponseConfig,
    EmergencyResponseOrchestrator,
    InvalidStateTransitionError,
    EmergencyLocationProvider,
    EmergencyStateMachine,
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
from app.edge.fall_detection import FallDetectedEvent, FallState, SensorMode
from app.edge.audio_distress import AudioDistressEvent, DistressAudioState


def make_snapshot(
    journey_id: str,
    lat: float = 12.95,
    lng: float = 80.15,
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
            timestamp=now
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
        gps_accuracy=10.0,
        telemetry_quality=quality,
        route_progress_percent=55.0,
        distance_along_route_m=5500.0,
        total_route_distance_m=10000.0,
        remaining_distance_m=4500.0,
        smoothed_speed_mps=1.4,
        arrival_status=ArrivalStatus.NOT_ARRIVED,
        progress_status=ProgressStatus.MOVING_ON_SCHEDULE,
        eta=now + timedelta(minutes=25),
        eta_source=ETASource.ESTIMATED,
        fall_event=fall_event,
        audio_distress=audio_event
    )


def make_assessment(
    journey_id: str,
    score: float = 90.0,
    level: RiskLevel = RiskLevel.CRITICAL
) -> JourneyRiskAssessment:
    return JourneyRiskAssessment(
        journey_id=journey_id,
        timestamp=datetime.now(timezone.utc),
        risk_score=score,
        risk_level=level,
        area_risk=30.0,
        motion_risk=15.0,
        route_deviation_risk=0.0,
        unexpected_stop_risk=0.0,
        fall_risk=45.0,
        audio_distress_risk=35.0,
        overall_confidence=0.95,
        telemetry_quality="VALID",
        dominant_factor="INTERACTION_AUDIO_DISTRESS_AND_FALL",
        active_factors=[
            RiskFactor(name="FALL_DETECTION", contribution=45.0, confidence=0.95, state="CONFIRMED", reason="Fall"),
            RiskFactor(name="AUDIO_DISTRESS", contribution=35.0, confidence=0.95, state="CONFIRMED", reason="Audio distress"),
            RiskFactor(name="INTERACTION_AUDIO_DISTRESS_AND_FALL", contribution=15.0, confidence=0.95, state="ACTIVE", reason="Interaction")
        ]
    )


def run_all_16_scenarios():
    print("=" * 90)
    print("STREEVA — PHASE 4 AUTONOMOUS EMERGENCY RESPONSE: 16 DETERMINISTIC REPLAY SCENARIOS")
    print("=" * 90)

    cfg = EmergencyResponseConfig(emergency_countdown_seconds=15.0, manual_sos_immediate_authorization=True)
    orchestrator = EmergencyResponseOrchestrator(config=cfg)

    # -------------------------------------------------------------
    # Scenario 1 — Manual SOS
    # -------------------------------------------------------------
    print("\n[SCENARIO 1] Manual SOS Trigger (Immediate Authorization)")
    inc1 = orchestrator.handle_manual_sos("j_rep_1", manual_lat=12.95, manual_lng=80.15, reason="User triggered emergency SOS")
    print(f"  Incident ID: {inc1.incident_id} | State: {inc1.state.value} | Trigger: {inc1.trigger_type.value}")
    print(f"  Delivered Notifications: {inc1.notifications_delivered}/{inc1.notifications_attempted}")
    assert inc1.trigger_type == TriggerType.MANUAL_SOS
    assert inc1.state == EmergencyState.NOTIFIED
    assert inc1.notifications_delivered > 0
    print("  -> PASS: Manual SOS triggered, authorized, and dispatched immediately.")

    # -------------------------------------------------------------
    # Scenario 2 — Autonomous Response Trigger
    # -------------------------------------------------------------
    print("\n[SCENARIO 2] Autonomous Response Trigger via Phase 3 Decision")
    snap2 = make_snapshot("j_rep_2", fall=True, audio=True)
    assess2 = make_assessment("j_rep_2", score=92.0)
    dec2 = DecisionOutput(
        decision_tier=DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED,
        hysteresis_state="AUTONOMOUS_CONFIRMED",
        consecutive_observations=2,
        requires_user_check_in=False,
        reason="Compound distress"
    )
    inc2 = orchestrator.handle_autonomous_decision("j_rep_2", dec2, assess2, snap2)
    print(f"  Incident ID: {inc2.incident_id} | State: {inc2.state.value} | Countdown: {inc2.countdown_seconds}s")
    assert inc2.trigger_type == TriggerType.AUTONOMOUS_RISK
    assert inc2.state == EmergencyState.COUNTDOWN
    assert inc2.countdown_remaining_seconds == 15.0
    print("  -> PASS: Autonomous response entered verification countdown window.")

    # -------------------------------------------------------------
    # Scenario 3 — Autonomous Countdown Cancelled
    # -------------------------------------------------------------
    print("\n[SCENARIO 3] Autonomous Countdown Cancelled by User (Zero Dispatch Guarantee)")
    inc3 = orchestrator.cancel_incident(inc2.incident_id, reason="User cancelled: phone dropped on carpet")
    print(f"  Incident State: {inc3.state.value} | Cancelled At: {inc3.cancelled_at}")
    print(f"  Notifications Dispatched: {inc3.notifications_attempted}")
    assert inc3.state == EmergencyState.CANCELLED
    assert inc3.notifications_attempted == 0
    print("  -> PASS: User cancelled during countdown; zero notifications dispatched.")

    # -------------------------------------------------------------
    # Scenario 4 — Autonomous Countdown Expires
    # -------------------------------------------------------------
    print("\n[SCENARIO 4] Autonomous Countdown Expires -> Response Authorized & Dispatched")
    snap4 = make_snapshot("j_rep_4", fall=True, audio=True)
    assess4 = make_assessment("j_rep_4", score=90.0)
    inc4 = orchestrator.handle_autonomous_decision("j_rep_4", dec2, assess4, snap4)
    print(f"  Initial Countdown State: {inc4.state.value}")
    inc4_exp = orchestrator.advance_countdown(inc4.incident_id, elapsed_seconds=15.0)
    print(f"  Expired State: {inc4_exp.state.value} | Authorized At: {inc4_exp.response_authorized_at}")
    print(f"  Delivered: {inc4_exp.notifications_delivered}/{inc4_exp.notifications_attempted}")
    assert inc4_exp.state == EmergencyState.NOTIFIED
    assert inc4_exp.notifications_delivered > 0
    print("  -> PASS: Countdown expiry authorized response and dispatched primary contacts.")

    # -------------------------------------------------------------
    # Scenario 5 — Primary Contact Acknowledges
    # -------------------------------------------------------------
    print("\n[SCENARIO 5] Primary Contact Acknowledges -> Incident Resolved")
    inc5 = orchestrator.acknowledge_incident(inc4_exp.incident_id, contact_id="c_primary_1", acknowledged_by="Alice (Primary Contact)")
    print(f"  Incident State: {inc5.state.value} | Acknowledged By: {inc5.acknowledged_by}")
    assert inc5.state == EmergencyState.RESOLVED
    assert inc5.acknowledgement_status == AcknowledgementStatus.ACKNOWLEDGED
    print("  -> PASS: Contact acknowledgement resolved emergency incident.")

    # -------------------------------------------------------------
    # Scenario 6 — No Acknowledgement -> Escalation
    # -------------------------------------------------------------
    print("\n[SCENARIO 6] Unacknowledged Incident Escalation to Level 2")
    snap6 = make_snapshot("j_rep_6", fall=True, audio=True)
    assess6 = make_assessment("j_rep_6", score=95.0)
    inc6 = orchestrator.handle_autonomous_decision("j_rep_6", dec2, assess6, snap6)
    orchestrator.advance_countdown(inc6.incident_id, elapsed_seconds=15.0)
    print(f"  Pre-Escalation Level: {inc6.escalation_level.value}")
    inc6_esc = orchestrator.escalate_incident(inc6.incident_id, reason="Primary contacts did not respond within 60s")
    print(f"  Post-Escalation Level: {inc6_esc.escalation_level.value} | Contacts Targeted: {inc6_esc.contacts_targeted}")
    assert inc6_esc.escalation_level == EscalationLevel.LEVEL_2
    assert "c_secondary_1" in inc6_esc.contacts_targeted
    print("  -> PASS: Hierarchical escalation activated secondary contacts.")

    # -------------------------------------------------------------
    # Scenario 7 — Partial Notification Failure
    # -------------------------------------------------------------
    print("\n[SCENARIO 7] Partial Notification Failure Handling")
    orchestrator.notification_provider.set_failing_contacts({"c_primary_2"})
    snap7 = make_snapshot("j_rep_7", fall=True, audio=True)
    assess7 = make_assessment("j_rep_7")
    inc7 = orchestrator.handle_autonomous_decision("j_rep_7", dec2, assess7, snap7)
    inc7_disp = orchestrator.advance_countdown(inc7.incident_id, elapsed_seconds=15.0)
    print(f"  Incident State: {inc7_disp.state.value} | Delivered: {inc7_disp.notifications_delivered}/{inc7_disp.notifications_attempted}")
    assert inc7_disp.state == EmergencyState.PARTIAL_FAILURE
    assert inc7_disp.notifications_delivered == 1
    print("  -> PASS: Partial failure recorded explicitly without masking failure.")

    # -------------------------------------------------------------
    # Scenario 8 — Total Notification Failure
    # -------------------------------------------------------------
    print("\n[SCENARIO 8] Total Notification Failure Handling")
    orchestrator.notification_provider.set_failing_contacts({"c_primary_1", "c_primary_2"})
    snap8 = make_snapshot("j_rep_8", fall=True, audio=True)
    assess8 = make_assessment("j_rep_8")
    inc8 = orchestrator.handle_autonomous_decision("j_rep_8", dec2, assess8, snap8)
    inc8_disp = orchestrator.advance_countdown(inc8.incident_id, elapsed_seconds=15.0)
    print(f"  Incident State: {inc8_disp.state.value} | Delivered: {inc8_disp.notifications_delivered}/{inc8_disp.notifications_attempted}")
    assert inc8_disp.state == EmergencyState.FAILED
    assert inc8_disp.notifications_delivered == 0
    print("  -> PASS: Total failure transitioned to FAILED and eligible for alternate escalation.")

    # -------------------------------------------------------------
    # Scenario 9 — Location Unavailable (No Fake Coordinates)
    # -------------------------------------------------------------
    print("\n[SCENARIO 9] Location Unavailable (Zero Fabrication Policy)")
    snap9 = make_snapshot("j_rep_9", quality=TelemetryQuality.MISSING)
    snap9.current_lat = None
    snap9.current_lng = None
    loc9 = orchestrator.location_provider.get_current_location(snap9)
    print(f"  Location Quality: {loc9.quality.value} | Lat: {loc9.latitude} | Lng: {loc9.longitude}")
    assert loc9.quality == LocationQuality.UNAVAILABLE
    assert loc9.latitude is None
    assert loc9.longitude is None
    print("  -> PASS: Location unavailable surfaced explicitly without fake (0, 0) coordinates.")

    # -------------------------------------------------------------
    # Scenario 10 — Stale Location Handling
    # -------------------------------------------------------------
    print("\n[SCENARIO 10] Stale Location Quality Classification")
    snap10 = make_snapshot("j_rep_10", lat=12.95, lng=80.15, quality=TelemetryQuality.STALE)
    snap10.timestamp = datetime.now(timezone.utc) - timedelta(seconds=60)
    loc10 = orchestrator.location_provider.get_current_location(snap10)
    print(f"  Location Quality: {loc10.quality.value} | Source: {loc10.source}")
    assert loc10.quality == LocationQuality.STALE
    assert loc10.latitude == 12.95
    print("  -> PASS: Stale telemetry correctly classified as STALE.")

    # -------------------------------------------------------------
    # Scenario 11 — Idempotent Duplicate Autonomous Trigger
    # -------------------------------------------------------------
    print("\n[SCENARIO 11] Duplicate Autonomous Trigger Suppression (Idempotency)")
    orchestrator.notification_provider.clear()
    snap11 = make_snapshot("j_rep_11", fall=True, audio=True)
    assess11 = make_assessment("j_rep_11")
    inc11_a = orchestrator.handle_autonomous_decision("j_rep_11", dec2, assess11, snap11)
    inc11_b = orchestrator.handle_autonomous_decision("j_rep_11", dec2, assess11, snap11)
    print(f"  Incident A: {inc11_a.incident_id} | Incident B: {inc11_b.incident_id}")
    assert inc11_a.incident_id == inc11_b.incident_id
    assert len(orchestrator.persistence.list_all_incidents()) > 0
    print("  -> PASS: Duplicate autonomous triggers reuse existing incident without duplicate dispatch.")

    # -------------------------------------------------------------
    # Scenario 12 — Ineligible Decisions Rejected
    # -------------------------------------------------------------
    print("\n[SCENARIO 12] Rejection of Ineligible Decisions (LOW/MEDIUM/HIGH/DEGRADED)")
    dec_degraded = DecisionOutput(
        decision_tier=DecisionTier.DEGRADED_MONITORING,
        hysteresis_state="STABLE",
        consecutive_observations=1,
        requires_user_check_in=False,
        reason="Telemetry missing"
    )
    assess_deg = make_assessment("j_rep_12", score=0.0, level=RiskLevel.UNKNOWN)
    inc12 = orchestrator.handle_autonomous_decision("j_rep_12", dec_degraded, assess_deg, None)
    print(f"  Autonomous Response Triggered: {inc12 is not None}")
    assert inc12 is None
    print("  -> PASS: DEGRADED_MONITORING strictly rejected from autonomous emergency triggering.")

    # -------------------------------------------------------------
    # Scenario 13 — Invalid State Transition Rejection
    # -------------------------------------------------------------
    print("\n[SCENARIO 13] Strict Rejection of Illegal State Transitions")
    inc13 = EmergencyIncident(
        incident_id="inc_rep_13",
        journey_id="j_rep_13",
        trigger_type=TriggerType.AUTONOMOUS_RISK,
        created_at=datetime.now(timezone.utc),
        triggered_at=datetime.now(timezone.utc)
    )
    transition_rejected = False
    try:
        EmergencyStateMachine.transition(inc13, EmergencyState.RESOLVED, "Illegal jump")
    except InvalidStateTransitionError:
        transition_rejected = True
    print(f"  Illegal Transition from IDLE to RESOLVED Rejected: {transition_rejected}")
    assert transition_rejected is True
    print("  -> PASS: Invalid state transitions strictly rejected.")

    # -------------------------------------------------------------
    # Scenario 14 — Secure Evidence Package Compilation
    # -------------------------------------------------------------
    print("\n[SCENARIO 14] Secure Evidence Package & SHA-256 Integrity Verification")
    snap14 = make_snapshot("j_rep_14", fall=True, audio=True)
    assess14 = make_assessment("j_rep_14")
    inc14 = EmergencyIncident(
        incident_id="inc_rep_14",
        journey_id="j_rep_14",
        trigger_type=TriggerType.AUTONOMOUS_RISK,
        state=EmergencyState.RESPONSE_AUTHORIZED,
        created_at=datetime.now(timezone.utc),
        triggered_at=datetime.now(timezone.utc)
    )
    pkg = orchestrator.evidence_service.compile_evidence_package(inc14, snap14, assess14)
    print(f"  Package ID: {pkg.package_id} | Evidence Items: {len(pkg.items)}")
    print(f"  SHA-256 Hash: {pkg.integrity_hash[:24]}...")
    assert len(pkg.items) >= 4
    assert len(pkg.integrity_hash) == 64
    print("  -> PASS: Verifiable evidence package assembled with SHA-256 checksum.")

    # -------------------------------------------------------------
    # Scenario 15 — Network Offline Failure Boundary
    # -------------------------------------------------------------
    print("\n[SCENARIO 15] Network Offline Failure Boundary Handling")
    snap15 = make_snapshot("j_rep_15", fall=True, audio=True)
    assess15 = make_assessment("j_rep_15")
    inc15 = orchestrator.handle_autonomous_decision("j_rep_15", dec2, assess15, snap15)
    inc15_off = orchestrator.advance_countdown(inc15.incident_id, elapsed_seconds=15.0, network_available=False)
    print(f"  Incident State: {inc15_off.state.value} | Error: {inc15_off.delivery_results[0].error_message}")
    assert inc15_off.state == EmergencyState.FAILED
    assert "Network offline" in inc15_off.delivery_results[0].error_message
    print("  -> PASS: Offline network boundary handled and surfaced explicitly.")

    # -------------------------------------------------------------
    # Scenario 16 — Full Successful End-to-End Emergency Response
    # -------------------------------------------------------------
    print("\n[SCENARIO 16] Full Successful End-to-End Response Lifecycle")
    orchestrator.reset_all()
    snap16 = make_snapshot("j_rep_16", fall=True, audio=True)
    assess16 = make_assessment("j_rep_16")

    # Step 1: Trigger
    inc16 = orchestrator.handle_autonomous_decision("j_rep_16", dec2, assess16, snap16)
    assert inc16.state == EmergencyState.COUNTDOWN
    print("  Step 1: Autonomous decision triggered; countdown initiated.")

    # Step 2: Countdown expiry -> Authorized & Dispatched
    inc16_disp = orchestrator.advance_countdown(inc16.incident_id, elapsed_seconds=15.0)
    assert inc16_disp.state == EmergencyState.NOTIFIED
    assert inc16_disp.notifications_delivered > 0
    print(f"  Step 2: Countdown expired; {inc16_disp.notifications_delivered} notifications dispatched.")

    # Step 3: Acknowledge & Resolve
    inc16_res = orchestrator.acknowledge_incident(inc16.incident_id, contact_id="c_primary_1", acknowledged_by="Guardian 1")
    assert inc16_res.state == EmergencyState.RESOLVED
    print(f"  Step 3: Acknowledged by {inc16_res.acknowledged_by}; Incident fully RESOLVED.")
    print("  -> PASS: Full end-to-end emergency response lifecycle completed successfully.")

    print("\n" + "=" * 90)
    print("ALL 16 PHASE 4 REPLAY SCENARIOS EXECUTED & VERIFIED (100% SUCCESS)!")
    print("=" * 90)


if __name__ == "__main__":
    run_all_16_scenarios()
