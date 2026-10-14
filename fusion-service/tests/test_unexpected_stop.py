"""
Comprehensive Unit Tests for Unexpected Stop Detection Engine (Phase 1B).

Covers:
- Continuous normal movement (speed ~1.2 m/s -> MOVING)
- Brief stationary period (< 15s -> remains MOVING)
- Intermediate stationary pause (15s <= t < 45s -> POSSIBLE_STOP)
- Sustained stationary period (>= 45s -> STOPPED)
- Recovery and hysteresis (speed >= 1.0 m/s with consecutive observations)
- GPS noise and micro-jitter handling
- Poor GPS accuracy filtering (> 50m uncertainty blocks STOPPED)
- Telemetry time gaps (> 120s resets baseline)
- Inactive journey handling (bypasses alerts)
- Detector reset method
- REST API endpoint integration
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.edge.unexpected_stop import (
    UnexpectedStopDetector,
    UnexpectedStopConfig,
    StopState
)

client = TestClient(app)


@pytest.fixture
def detector():
    config = UnexpectedStopConfig(
        stop_speed_threshold_mps=0.5,
        possible_stop_duration_s=15.0,
        minimum_stop_duration_s=45.0,
        recovery_speed_threshold_mps=1.0,
        consecutive_recovery_observations=2,
        gps_accuracy_limit_m=50.0,
        max_time_gap_s=120.0
    )
    return UnexpectedStopDetector(config=config)


def test_continuous_normal_movement(detector):
    """Traveler walking at ~1.2 m/s remains in MOVING state."""
    base_time = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    # Walking North along longitude 80.2500 (~0.000011 deg lat per second is ~1.22 m/s)
    lat = 13.0600
    lng = 80.2500

    for step in range(5):
        t = base_time + timedelta(seconds=step * 5)
        lat += 0.000055  # ~6.1 meters in 5s (~1.22 m/s)
        ev = detector.detect({"lat": lat, "lng": lng}, timestamp=t, gps_accuracy=5.0)
        assert ev.state == StopState.MOVING
        assert not ev.is_stopped
        assert ev.stationary_duration_s == 0.0
        assert ev.speed_mps > 1.0


def test_brief_pause_remains_moving(detector):
    """Pausing for 10 seconds (e.g. tying shoelace) does not trigger stop alert."""
    base_time = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    lat, lng = 13.0600, 80.2500

    # Moving initially
    detector.detect({"lat": lat, "lng": lng}, timestamp=base_time, gps_accuracy=5.0)
    lat += 0.0001
    detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=5), gps_accuracy=5.0)

    # Pauses at same coordinates for 10 seconds (< 15s possible_stop threshold)
    ev = detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=15), gps_accuracy=5.0)
    assert ev.state == StopState.MOVING
    assert not ev.is_stopped
    assert 9.0 <= ev.stationary_duration_s <= 11.0


def test_possible_stop_transition(detector):
    """Remaining stationary between 15s and 45s transitions to POSSIBLE_STOP."""
    base_time = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    lat, lng = 13.0600, 80.2500

    detector.detect({"lat": lat, "lng": lng}, timestamp=base_time, gps_accuracy=5.0)
    lat += 0.0001
    detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=5), gps_accuracy=5.0)

    # Stationary for 25s (from t=5 to t=30)
    ev = detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=30), gps_accuracy=5.0)
    assert ev.state == StopState.POSSIBLE_STOP
    assert not ev.is_stopped
    assert 24.0 <= ev.stationary_duration_s <= 26.0


def test_sustained_stationary_triggers_stopped(detector):
    """Remaining stationary for >= 45s confirms STOPPED state."""
    base_time = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    lat, lng = 13.0600, 80.2500

    detector.detect({"lat": lat, "lng": lng}, timestamp=base_time, gps_accuracy=5.0)
    lat += 0.0001
    detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=5), gps_accuracy=5.0)

    # Check at 55s (stationary for 50s >= 45s)
    ev = detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=55), gps_accuracy=5.0)
    assert ev.state == StopState.STOPPED
    assert ev.is_stopped is True
    assert ev.stationary_duration_s >= 45.0
    assert ev.confidence > 0.7


def test_recovery_with_hysteresis(detector):
    """
    Validates hysteresis:
    - Speed must reach recovery threshold (>= 1.0 m/s).
    - Requires 2 consecutive observations to restore MOVING state.
    - Creeping speed between 0.5 and 1.0 m/s stays in intermediate state.
    """
    base_time = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    lat, lng = 13.0600, 80.2500

    # Drive into STOPPED
    detector.detect({"lat": lat, "lng": lng}, timestamp=base_time, gps_accuracy=5.0)
    lat += 0.0001
    detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=5), gps_accuracy=5.0)
    detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=55), gps_accuracy=5.0)
    assert detector.current_state == StopState.STOPPED

    # Creeping speed: moves ~3.5m in 5s (~0.7 m/s, between 0.5 and 1.0 m/s)
    lat += 0.000032
    ev_creep = detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=60), gps_accuracy=5.0)
    # Stays STOPPED because 0.7 m/s < 1.0 m/s recovery threshold
    assert ev_creep.state == StopState.STOPPED

    # Recovery observation 1: moves ~7m in 5s (~1.4 m/s >= 1.0 m/s) -> RECOVERING
    lat += 0.000063
    ev_rec1 = detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=65), gps_accuracy=5.0)
    assert ev_rec1.state == StopState.RECOVERING
    assert not ev_rec1.is_stopped

    # Recovery observation 2: moves another ~7m in 5s (~1.4 m/s) -> MOVING
    lat += 0.000063
    ev_rec2 = detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=70), gps_accuracy=5.0)
    assert ev_rec2.state == StopState.MOVING
    assert not ev_rec2.is_stopped
    assert ev_rec2.stationary_duration_s == 0.0


def test_poor_gps_accuracy_blocks_stopped(detector):
    """Readings with GPS accuracy worse than 50m do not trigger STOPPED."""
    base_time = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    lat, lng = 13.0600, 80.2500

    detector.detect({"lat": lat, "lng": lng}, timestamp=base_time, gps_accuracy=80.0)
    # Stationary for 60s, but with degraded accuracy (80m > 50m)
    ev = detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=60), gps_accuracy=80.0)
    assert ev.state != StopState.STOPPED
    assert "exceeds limit" in ev.details
    assert ev.confidence < 0.5


def test_time_gap_resets_baseline(detector):
    """Large gaps in telemetry (> 120s) reset velocity calculation cleanly."""
    base_time = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    lat, lng = 13.0600, 80.2500

    detector.detect({"lat": lat, "lng": lng}, timestamp=base_time, gps_accuracy=5.0)

    # 300s later (5 minutes gap)
    ev = detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=300), gps_accuracy=5.0)
    assert ev.state == StopState.MOVING
    assert ev.speed_mps == 0.0


def test_journey_inactive_bypasses_stop(detector):
    """When journey_active=False, stops are expected and do not trigger alert states."""
    base_time = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    lat, lng = 13.0600, 80.2500

    detector.detect({"lat": lat, "lng": lng}, timestamp=base_time, gps_accuracy=5.0, journey_active=False)
    ev = detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=60), gps_accuracy=5.0, journey_active=False)
    assert ev.state == StopState.MOVING
    assert not ev.is_stopped
    assert "Journey inactive" in ev.details


def test_detector_reset(detector):
    """Reset clears timers and restores state to MOVING."""
    base_time = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    lat, lng = 13.0600, 80.2500

    detector.detect({"lat": lat, "lng": lng}, timestamp=base_time, gps_accuracy=5.0)
    lat += 0.0001
    detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=5), gps_accuracy=5.0)
    detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=60), gps_accuracy=5.0)
    assert detector.current_state == StopState.STOPPED

    detector.reset()
    assert detector.current_state == StopState.MOVING
    assert detector.stationary_start_time is None
    assert detector.last_position is None


# --- API Endpoint Integration Tests ---

def test_api_unexpected_stop_endpoints():
    """POST /edge/unexpected-stop/evaluate and /reset respond correctly."""
    base_time = datetime.now(timezone.utc)
    payload1 = {
        "current_position": {"lat": 13.0600, "lng": 80.2500},
        "timestamp": base_time.isoformat(),
        "gps_accuracy": 5.0,
        "journey_active": True
    }
    r1 = client.post("/edge/unexpected-stop/evaluate", json=payload1)
    assert r1.status_code == 200
    assert r1.json()["event_type"] == "UNEXPECTED_STOP"
    assert r1.json()["state"] == "MOVING"

    # Reset endpoint
    r_reset = client.post("/edge/unexpected-stop/reset")
    assert r_reset.status_code == 200
    assert r_reset.json()["status"] == "reset"
    assert r_reset.json()["state"] == "MOVING"
