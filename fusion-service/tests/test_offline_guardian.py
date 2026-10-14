"""
STREEVA — Phase 5 Offline Guardian & Connectivity Resilience Tests
tests/test_offline_guardian.py

Comprehensive tests for:
- Connectivity State Machine and transition validation
- Active Journey Caching and Location Freshness (STALE, UNAVAILABLE)
- Monotonic sequence numbering and event buffer persistence
- Process restart survival (journey, sequence number, incident continuity)
- Offline local safety monitoring reusing Phase 1-3 pipeline
- Offline emergency response, countdown, user cancellation, and authorization
- SMS fallback abstraction with explicit SENT, FAILED, UNAVAILABLE statuses
- Reconnection, reconciliation, partial failure, and conflict handling
- 16 Core Safety Invariants
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.offline.schemas import (
    ConnectivityState,
    SyncStatus,
    BufferedEventType,
    SMSDeliveryStatus,
    CachedJourneyContext
)
from app.offline.connectivity import ConnectivityManager, InvalidConnectivityTransitionError
from app.offline.journey_cache import ActiveJourneyCache
from app.offline.event_buffer import LocalEventBuffer
from app.offline.persistence import OfflinePersistenceManager
from app.offline.sms_fallback import MockSMSFallbackProvider
from app.offline.reconciliation import MockReconciliationService
from app.offline.guardian import OfflineGuardian

from app.guardian.journey_state import JourneyStartRequest, JourneyUpdateRequest, JourneyState
from app.contextual.schemas import DecisionTier, RiskLevel, DecisionOutput
from app.emergency.schemas import EmergencyState

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_offline_state():
    """Resets Offline Guardian and clears DB before each test."""
    client.post("/offline/reset")
    yield
    client.post("/offline/reset")


# ==============================================================================
# 1. Connectivity State Machine Tests
# ==============================================================================

def test_connectivity_state_machine_valid_transitions():
    cm = ConnectivityManager(ConnectivityState.ONLINE)
    assert cm.is_online
    assert cm.network_available

    # ONLINE -> DEGRADED
    info = cm.transition_to(ConnectivityState.DEGRADED, reason="Weak cellular RSSI")
    assert info.state == ConnectivityState.DEGRADED
    assert cm.is_degraded
    assert cm.network_available

    # DEGRADED -> OFFLINE
    info = cm.transition_to(ConnectivityState.OFFLINE, reason="Network interface dropped")
    assert info.state == ConnectivityState.OFFLINE
    assert cm.is_offline
    assert not cm.network_available

    # OFFLINE -> RECONNECTING
    info = cm.transition_to(ConnectivityState.RECONNECTING, reason="Cellular handshake initiated")
    assert info.state == ConnectivityState.RECONNECTING
    assert cm.is_reconnecting

    # RECONNECTING -> ONLINE
    info = cm.transition_to(ConnectivityState.ONLINE, reason="Sync completed")
    assert info.state == ConnectivityState.ONLINE
    assert cm.is_online


def test_connectivity_state_machine_invalid_transitions():
    cm = ConnectivityManager(ConnectivityState.OFFLINE)
    # OFFLINE -> DEGRADED directly is invalid (must go through RECONNECTING or ONLINE)
    with pytest.raises(InvalidConnectivityTransitionError):
        cm.transition_to(ConnectivityState.DEGRADED)


# ==============================================================================
# 2. Active Journey Cache & Location Freshness Tests
# ==============================================================================

def test_journey_cache_location_freshness():
    cache = ActiveJourneyCache(stale_threshold_seconds=10.0)
    now = datetime.now(timezone.utc)

    # 1. No location ever cached
    cache.cache_journey_start("j_test_1", timestamp=now)
    ctx = cache.get_context()
    assert ctx.telemetry_quality == "UNAVAILABLE"

    # 2. Update with valid coordinates
    cache.update_from_snapshot(lat=12.9716, lng=77.5946, accuracy=5.0, timestamp=now)
    ctx = cache.get_context()
    assert ctx.telemetry_quality == "VALID"
    assert ctx.last_trusted_lat == 12.9716

    # 3. Simulate passage of time beyond stale threshold
    cache._update_location_freshness(current_time=now + timedelta(seconds=25.0))
    ctx = cache.get_context()
    assert ctx.telemetry_quality == "STALE"
    # Never fabricated coordinates
    assert ctx.last_trusted_lat == 12.9716


# ==============================================================================
# 3. Local Event Buffer & Monotonic Sequencing Tests
# ==============================================================================

def test_event_buffer_strictly_monotonic_sequence():
    buffer = LocalEventBuffer()
    buffer.clear()

    e1 = buffer.buffer_event("j_test", BufferedEventType.TELEMETRY, {"lat": 12.0})
    e2 = buffer.buffer_event("j_test", BufferedEventType.GUARDIAN_SNAPSHOT, {"speed": 5.0})
    e3 = buffer.buffer_event("j_test", BufferedEventType.RISK_ASSESSMENT, {"risk": 20.0})

    assert e1.sequence_number == 1
    assert e2.sequence_number == 2
    assert e3.sequence_number == 3
    assert buffer.current_sequence == 3


def test_event_buffer_deduplication():
    buffer = LocalEventBuffer()
    buffer.clear()

    e1 = buffer.buffer_event("j_test", BufferedEventType.TELEMETRY, {"lat": 12.0}, event_id="fixed-evt-1")
    e2 = buffer.buffer_event("j_test", BufferedEventType.TELEMETRY, {"lat": 12.0}, event_id="fixed-evt-1")

    assert buffer.total_count == 1
    assert e1.event_id == e2.event_id
    assert e1.sequence_number == e2.sequence_number


# ==============================================================================
# 4. Persistence & Process Restart Recovery Test
# ==============================================================================

def test_process_restart_recovery():
    guardian_1 = OfflineGuardian()
    guardian_1.reset()

    # Start journey and go offline
    req = JourneyStartRequest(
        journey_id="j_restart_100",
        source_lat=12.9716,
        source_lng=77.5946,
        destination_lat=12.9800,
        destination_lng=77.6000,
        expected_route=[{"lat": 12.9716, "lng": 77.5946}, {"lat": 12.9800, "lng": 77.6000}]
    )
    guardian_1.start_journey(req)
    guardian_1.set_connectivity(ConnectivityState.OFFLINE, reason="User entered tunnel")

    # Buffer an update
    upd = JourneyUpdateRequest(
        journey_id="j_restart_100",
        latitude=12.9720,
        longitude=77.5950,
        gps_accuracy=4.0
    )
    guardian_1.process_telemetry(upd)
    seq_before = guardian_1.event_buffer.current_sequence

    # Simulate Process Restart by creating a completely new OfflineGuardian instance
    guardian_2 = OfflineGuardian()
    restored = guardian_2.restore_from_persistence("j_restart_100")

    assert restored is not None
    assert restored.journey_id == "j_restart_100"
    assert restored.journey_state == "ACTIVE"
    assert restored.last_trusted_lat == 12.9720
    # Verify sequence counter preserved and continues monotonically
    assert guardian_2.event_buffer.current_sequence == seq_before

    next_evt = guardian_2.event_buffer.buffer_event("j_restart_100", BufferedEventType.TELEMETRY, {"test": 1})
    assert next_evt.sequence_number == seq_before + 1


# ==============================================================================
# 5. Local Safety Monitoring Reusing Phase 1-3
# ==============================================================================

def test_offline_monitoring_normal_telemetry():
    guardian = OfflineGuardian()
    guardian.reset()

    req = JourneyStartRequest(
        journey_id="j_offline_norm",
        source_lat=12.9716,
        source_lng=77.5946,
        destination_lat=12.9800,
        destination_lng=77.6000,
        expected_route=[{"lat": 12.9716, "lng": 77.5946}, {"lat": 12.9800, "lng": 77.6000}]
    )
    guardian.start_journey(req)
    guardian.set_connectivity(ConnectivityState.OFFLINE, reason="Going offline")

    # Valid telemetry on route
    upd = JourneyUpdateRequest(
        journey_id="j_offline_norm",
        latitude=12.9718,
        longitude=77.5948,
        gps_accuracy=5.0
    )
    snapshot, assessment, decision = guardian.process_telemetry(upd)

    # Invariants 1 & 2: OFFLINE does not invent high danger or forced low danger
    assert snapshot.journey_state == JourneyState.ACTIVE
    assert assessment.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)
    assert decision.decision_tier in (DecisionTier.MONITOR, DecisionTier.REQUEST_CHECK_IN)


def test_offline_route_deviation():
    guardian = OfflineGuardian()
    guardian.reset()

    req = JourneyStartRequest(
        journey_id="j_offline_dev",
        source_lat=12.9716,
        source_lng=77.5946,
        destination_lat=12.9800,
        destination_lng=77.6000,
        expected_route=[{"lat": 12.9716, "lng": 77.5946}, {"lat": 12.9800, "lng": 77.6000}]
    )
    guardian.start_journey(req)
    guardian.set_connectivity(ConnectivityState.OFFLINE)

    # Move far off route (e.g. 500m away)
    upd = JourneyUpdateRequest(
        journey_id="j_offline_dev",
        latitude=12.9600,
        longitude=77.5800,
        gps_accuracy=5.0
    )
    snapshot, assessment, decision = guardian.process_telemetry(upd)

    # Phase 1A route deviation detector operated offline
    assert snapshot.route_deviation is not None
    assert snapshot.route_deviation.state.value in ("POSSIBLE_DEVIATION", "DEVIATED")
    assert assessment.route_deviation_risk > 0.0


# ==============================================================================
# 6. Offline Emergency Response, Countdown, Cancellation, and SMS Fallback
# ==============================================================================

def test_offline_emergency_trigger_and_countdown_progression():
    guardian = OfflineGuardian()
    guardian.reset()

    req = JourneyStartRequest(
        journey_id="j_offline_emg",
        source_lat=12.9716,
        source_lng=77.5946,
        destination_lat=12.9800,
        destination_lng=77.6000,
        expected_route=[{"lat": 12.9716, "lng": 77.5946}, {"lat": 12.9800, "lng": 77.6000}]
    )
    guardian.start_journey(req)
    guardian.set_connectivity(ConnectivityState.OFFLINE)

    # Valid telemetry update
    upd = JourneyUpdateRequest(
        journey_id="j_offline_emg",
        latitude=12.9600,
        longitude=77.5800
    )
    snapshot, assessment, _ = guardian.process_telemetry(upd)

    # Autonomous emergency decision
    dec_auto = DecisionOutput(
        decision_tier=DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED,
        hysteresis_state="AUTONOMOUS_CONFIRMED",
        consecutive_observations=2,
        reason="Autonomous response confirmed"
    )
    incident = guardian.handle_autonomous_decision("j_offline_emg", dec_auto, assessment, snapshot)
    assert incident is not None
    assert incident.state == EmergencyState.COUNTDOWN

    cached = guardian.journey_cache.get_context()
    assert cached.active_incident_id == incident.incident_id
    incident_id = cached.active_incident_id

    # Advance countdown offline
    inc = guardian.advance_emergency_countdown(incident_id, elapsed_seconds=5.0)
    assert inc.state == EmergencyState.COUNTDOWN
    assert inc.countdown_remaining_seconds == 10.0  # 15s config - 5s


def test_offline_emergency_cancellation():
    guardian = OfflineGuardian()
    guardian.reset()

    req = JourneyStartRequest(
        journey_id="j_offline_cancel",
        source_lat=12.9716,
        source_lng=77.5946,
        destination_lat=12.9800,
        destination_lng=77.6000
    )
    guardian.start_journey(req)
    guardian.set_connectivity(ConnectivityState.OFFLINE)

    upd = JourneyUpdateRequest(
        journey_id="j_offline_cancel",
        latitude=12.9716,
        longitude=77.5946
    )
    snapshot, assessment, _ = guardian.process_telemetry(upd)
    dec_auto = DecisionOutput(
        decision_tier=DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED,
        hysteresis_state="AUTONOMOUS_CONFIRMED",
        consecutive_observations=2,
        reason="Autonomous response confirmed"
    )
    incident = guardian.handle_autonomous_decision("j_offline_cancel", dec_auto, assessment, snapshot)
    incident_id = incident.incident_id

    # User cancels locally
    cancelled_inc = guardian.cancel_emergency(incident_id, reason="False alarm confirmed by user")
    assert cancelled_inc.state == EmergencyState.CANCELLED
    # Invariant 9: No notification represented as delivered
    assert cancelled_inc.notifications_delivered == 0


def test_offline_emergency_sms_fallback_sent():
    guardian = OfflineGuardian()
    guardian.reset()
    guardian.sms_provider.set_mode("SUCCESS")

    req = JourneyStartRequest(
        journey_id="j_sms_sent",
        source_lat=12.9716,
        source_lng=77.5946,
        destination_lat=12.9800,
        destination_lng=77.6000
    )
    guardian.start_journey(req)
    guardian.set_connectivity(ConnectivityState.OFFLINE)

    upd = JourneyUpdateRequest(
        journey_id="j_sms_sent",
        latitude=12.9716,
        longitude=77.5946
    )
    snapshot, assessment, _ = guardian.process_telemetry(upd)
    dec_auto = DecisionOutput(
        decision_tier=DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED,
        hysteresis_state="AUTONOMOUS_CONFIRMED",
        consecutive_observations=2,
        reason="Autonomous response confirmed"
    )
    incident = guardian.handle_autonomous_decision("j_sms_sent", dec_auto, assessment, snapshot)
    incident_id = incident.incident_id

    # Advance countdown until expiry
    inc = guardian.advance_emergency_countdown(incident_id, elapsed_seconds=20.0)
    assert inc.state == EmergencyState.NOTIFIED
    assert inc.notifications_delivered > 0
    assert any(r.success for r in inc.delivery_results)


def test_offline_emergency_sms_fallback_unavailable():
    guardian = OfflineGuardian()
    guardian.reset()
    guardian.sms_provider.set_mode("UNAVAILABLE")

    req = JourneyStartRequest(
        journey_id="j_sms_unavail",
        source_lat=12.9716,
        source_lng=77.5946,
        destination_lat=12.9800,
        destination_lng=77.6000
    )
    guardian.start_journey(req)
    guardian.set_connectivity(ConnectivityState.OFFLINE)

    upd = JourneyUpdateRequest(
        journey_id="j_sms_unavail",
        latitude=12.9716,
        longitude=77.5946
    )
    snapshot, assessment, _ = guardian.process_telemetry(upd)
    dec_auto = DecisionOutput(
        decision_tier=DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED,
        hysteresis_state="AUTONOMOUS_CONFIRMED",
        consecutive_observations=2,
        reason="Autonomous response confirmed"
    )
    incident = guardian.handle_autonomous_decision("j_sms_unavail", dec_auto, assessment, snapshot)
    incident_id = incident.incident_id

    # Advance countdown until expiry
    inc = guardian.advance_emergency_countdown(incident_id, elapsed_seconds=20.0)
    # Invariant 9: No fake success
    assert inc.state == EmergencyState.FAILED
    assert inc.notifications_delivered == 0
    assert all(not r.success for r in inc.delivery_results)


# ==============================================================================
# 7. Reconnection, Reconciliation, and Conflict Resolution Tests
# ==============================================================================

def test_reconnection_reconciliation_ordered_and_partial_failure():
    guardian = OfflineGuardian()
    guardian.reset()

    # Buffer several events
    guardian.event_buffer.buffer_event("j_sync", BufferedEventType.TELEMETRY, {"seq": 1})
    guardian.event_buffer.buffer_event("j_sync", BufferedEventType.GUARDIAN_SNAPSHOT, {"seq": 2})
    guardian.event_buffer.buffer_event("j_sync", BufferedEventType.RISK_ASSESSMENT, {"seq": 3})
    guardian.event_buffer.buffer_event("j_sync", BufferedEventType.DECISION, {"seq": 4})

    guardian.set_connectivity(ConnectivityState.OFFLINE)

    # 1. Simulate partial sync failure
    summary_partial = guardian.reconcile(simulate_partial_failure=True)
    assert summary_partial.events_failed > 0
    assert guardian.connectivity.current_state == ConnectivityState.DEGRADED

    # Pending events still exist for retry
    pending = guardian.event_buffer.get_pending_events()
    assert len(pending) == summary_partial.events_failed

    # 2. Retry with normal connection
    summary_success = guardian.reconcile(simulate_partial_failure=False)
    assert summary_success.events_failed == 0
    assert guardian.connectivity.current_state == ConnectivityState.ONLINE
    assert len(guardian.event_buffer.get_pending_events()) == 0


def test_conflict_resolution_safety_forward_progress():
    recon = MockReconciliationService()
    # Higher safety progress wins
    resolved = recon.resolve_incident_conflict(
        local_state="RESPONSE_AUTHORIZED",
        remote_state="COUNTDOWN"
    )
    assert resolved == "RESPONSE_AUTHORIZED"

    resolved_remote = recon.resolve_incident_conflict(
        local_state="TRIGGERED",
        remote_state="RESOLVED"
    )
    assert resolved_remote == "RESOLVED"


# ==============================================================================
# 8. API Surface Verification Tests
# ==============================================================================

def test_offline_api_endpoints():
    # 1. POST /offline/connectivity
    resp = client.post("/offline/connectivity", json={"state": "DEGRADED", "reason": "Weak signal"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "DEGRADED"

    # 2. GET /offline/status
    resp = client.get("/offline/status")
    assert resp.status_code == 200
    assert "connectivity" in resp.json()

    # 3. POST /offline/emergency/sms-test
    resp = client.post("/offline/emergency/sms-test", json={
        "incident_id": "inc_api_test",
        "recipient": "+919876543210",
        "message": "API SMS Fallback Test"
    })
    assert resp.status_code == 200
    assert resp.json()["status"] in ("SENT", "FAILED", "UNAVAILABLE")

    # 4. POST /offline/reconcile
    resp = client.post("/offline/reconcile", json={"simulate_partial_failure": False})
    assert resp.status_code == 200
    assert "events_synced" in resp.json()


# ==============================================================================
# 9. Safety Invariants (16 Invariants) & Edge Detector Verification Tests
# ==============================================================================

def test_invariant_1_and_2_offline_does_not_alter_risk_definitions():
    """
    INVARIANT 1: OFFLINE must NEVER automatically imply HIGH or CRITICAL risk.
    INVARIANT 2: OFFLINE must NEVER automatically imply LOW risk.
    """
    guardian = OfflineGuardian()
    guardian.reset()

    req = JourneyStartRequest(
        journey_id="j_inv_1_2",
        source_lat=12.9716,
        source_lng=77.5946,
        destination_lat=12.9800,
        destination_lng=77.6000
    )
    guardian.start_journey(req)
    guardian.set_connectivity(ConnectivityState.OFFLINE)

    upd = JourneyUpdateRequest(
        journey_id="j_inv_1_2",
        latitude=12.9717,
        longitude=77.5947
    )
    _, assessment, decision = guardian.process_telemetry(upd)

    # Risk score reflects sensor input, NOT offline state
    assert assessment.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)
    assert assessment.risk_score < 50.0
    assert decision.decision_tier != DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED


def test_invariant_3_missing_telemetry_retains_unknown_semantics():
    """
    INVARIANT 3: UNKNOWN/DEGRADED telemetry must retain Phase 3 semantics.
    Missing telemetry != LOW risk, but rather UNKNOWN -> DEGRADED_MONITORING.
    """
    guardian = OfflineGuardian()
    guardian.reset()

    req = JourneyStartRequest(
        journey_id="j_inv_3",
        source_lat=12.9716,
        source_lng=77.5946,
        destination_lat=12.9800,
        destination_lng=77.6000
    )
    guardian.start_journey(req)
    guardian.set_connectivity(ConnectivityState.OFFLINE)

    # Create empty snapshot simulating complete sensor outage
    now = datetime.now(timezone.utc)
    from app.guardian.journey_state import TelemetryQuality, ETASource, ArrivalStatus, ProgressStatus, GuardianSnapshot
    degraded_snapshot = GuardianSnapshot(
        journey_id="j_inv_3",
        timestamp=now,
        journey_state=JourneyState.DEGRADED,
        telemetry_quality=TelemetryQuality.MISSING,
        route_progress_percent=0.0,
        distance_along_route_m=0.0,
        total_route_distance_m=1000.0,
        remaining_distance_m=1000.0,
        eta_source=ETASource.UNAVAILABLE,
        smoothed_speed_mps=0.0,
        arrival_status=ArrivalStatus.NOT_ARRIVED,
        progress_status=ProgressStatus.UNKNOWN
    )
    assessment = guardian.fusion_engine.evaluate_risk(degraded_snapshot, area_risk_score=None)
    decision = guardian.decision_engine.evaluate(assessment)

    # Must be UNKNOWN and DEGRADED_MONITORING, NEVER LOW
    assert assessment.risk_level == RiskLevel.UNKNOWN
    assert decision.decision_tier == DecisionTier.DEGRADED_MONITORING


def test_invariant_7_and_8_same_incident_id_survives_reconnect():
    """
    INVARIANT 7: Offline autonomous response must use the SAME Phase 4 incident lifecycle.
    INVARIANT 8: The same emergency incident ID must survive offline/online transitions.
    """
    guardian = OfflineGuardian()
    guardian.reset()

    req = JourneyStartRequest(
        journey_id="j_inv_7_8",
        source_lat=12.9716,
        source_lng=77.5946,
        destination_lat=12.9800,
        destination_lng=77.6000
    )
    guardian.start_journey(req)
    guardian.set_connectivity(ConnectivityState.OFFLINE)

    upd = JourneyUpdateRequest(
        journey_id="j_inv_7_8",
        latitude=12.9716,
        longitude=77.5946
    )
    snapshot, assessment, _ = guardian.process_telemetry(upd)
    dec_auto = DecisionOutput(
        decision_tier=DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED,
        hysteresis_state="AUTONOMOUS_CONFIRMED",
        consecutive_observations=2,
        reason="Severe trigger"
    )
    inc = guardian.handle_autonomous_decision("j_inv_7_8", dec_auto, assessment, snapshot)
    initial_incident_id = inc.incident_id

    # Advance countdown offline
    guardian.advance_emergency_countdown(initial_incident_id, elapsed_seconds=20.0)

    # Reconnect to ONLINE
    guardian.reconcile()
    assert guardian.connectivity.is_online

    # Incident ID must remain identical
    persisted_inc = guardian.emergency_orchestrator.persistence.get_incident(initial_incident_id)
    assert persisted_inc is not None
    assert persisted_inc.incident_id == initial_incident_id


def test_invariant_10_and_11_location_never_fabricated_and_marked_stale():
    """
    INVARIANT 10: No unavailable location may result in fabricated coordinates.
    INVARIANT 11: Stale location must remain explicitly marked stale.
    """
    cache = ActiveJourneyCache(stale_threshold_seconds=5.0)
    t0 = datetime.now(timezone.utc)
    cache.cache_journey_start("j_inv_10", source_lat=12.9716, source_lng=77.5946, timestamp=t0)

    # Advance time by 10s without GPS updates
    cache._update_location_freshness(current_time=t0 + timedelta(seconds=10.0))
    ctx = cache.get_context()

    assert ctx.telemetry_quality == "STALE"
    # Never fabricated (0, 0)
    assert (ctx.last_trusted_lat, ctx.last_trusted_lng) == (12.9716, 77.5946)


def test_invariant_15_offline_countdown_runs_without_network():
    """
    INVARIANT 15: Offline countdown must not depend on network availability.
    """
    guardian = OfflineGuardian()
    guardian.reset()

    req = JourneyStartRequest(
        journey_id="j_inv_15",
        source_lat=12.9716,
        source_lng=77.5946,
        destination_lat=12.9800,
        destination_lng=77.6000
    )
    guardian.start_journey(req)
    guardian.set_connectivity(ConnectivityState.OFFLINE)

    upd = JourneyUpdateRequest(journey_id="j_inv_15", latitude=12.9716, longitude=77.5946)
    snapshot, assessment, _ = guardian.process_telemetry(upd)
    dec_auto = DecisionOutput(
        decision_tier=DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED,
        hysteresis_state="AUTONOMOUS_CONFIRMED",
        consecutive_observations=2,
        reason="Autonomous response confirmed"
    )
    inc = guardian.handle_autonomous_decision("j_inv_15", dec_auto, assessment, snapshot)

    # Advance 5 seconds locally
    inc_5s = guardian.advance_emergency_countdown(inc.incident_id, elapsed_seconds=5.0)
    assert inc_5s.state == EmergencyState.COUNTDOWN
    assert inc_5s.countdown_remaining_seconds == 10.0

    # Advance 10 more seconds locally
    inc_exp = guardian.advance_emergency_countdown(inc.incident_id, elapsed_seconds=10.0)
    assert inc_exp.countdown_remaining_seconds == 0.0
    assert inc_exp.state in (EmergencyState.NOTIFIED, EmergencyState.RESPONSE_AUTHORIZED, EmergencyState.FAILED)

