"""
Comprehensive Unit Tests for Gyroscope & Accelerometer Fall Detection Engine (Phase 1C).

Covers:
- Normal walking baseline (~1.0g with small dynamics)
- Sub-threshold shock/spike (e.g. 1.8g < 2.5g threshold -> remains NORMAL)
- Impact without orientation change (e.g. jumping vertically -> clears to NORMAL)
- Impact with orientation change but with immediate resumed activity (dropped device/jogging -> clears to NORMAL)
- Genuine fall pattern: Impact (>= 2.5g) + Orientation change (>= 45 deg) + Stillness (>= 2.0s) -> FALL_DETECTED
- Post-fall movement recovery -> RECOVERED
- Sensor degradation:
    - Accel + Gyro mode (full angular tracking)
    - Accel-only mode (gravitational tilt angle without fake gyro fabrication)
- Unit conversion (automatic handling of SI m/s2 vs g units)
- Reset method
- REST API endpoint integration
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.edge.fall_detection import (
    FallDetector,
    FallDetectionConfig,
    FallState,
    SensorMode
)

client = TestClient(app)


@pytest.fixture
def detector():
    config = FallDetectionConfig(
        impact_threshold_g=2.5,
        orientation_change_threshold_deg=45.0,
        gyro_angular_velocity_threshold_dps=120.0,
        post_impact_inactivity_duration_s=2.0,
        inactivity_accel_variance_max=0.5,
        recovery_motion_threshold_g=0.6,
        consecutive_recovery_observations=2
    )
    return FallDetector(config=config)


def test_normal_walking_remains_normal(detector):
    """Steady walking (~1g total acceleration) remains in NORMAL state."""
    base_time = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    # Standing/walking upright: gravity primarily on Z axis
    for step in range(5):
        t = base_time + timedelta(seconds=step * 0.5)
        ev = detector.detect(
            accel_x=0.1, accel_y=0.2, accel_z=1.0,
            gyro_x=10.0, gyro_y=15.0, gyro_z=5.0,
            timestamp=t
        )
        assert ev.state == FallState.NORMAL
        assert not ev.is_fall
        assert ev.confidence > 0.8


def test_sub_threshold_acceleration_spike(detector):
    """Acceleration spike of 1.8g (below 2.5g impact threshold) stays NORMAL."""
    base_time = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)

    # Establish baseline
    detector.detect(accel_x=0.0, accel_y=0.0, accel_z=1.0, timestamp=base_time)

    # Spike to 1.8g (e.g. stepping down a curb)
    ev = detector.detect(accel_x=0.8, accel_y=0.8, accel_z=1.4, timestamp=base_time + timedelta(seconds=0.5))
    assert ev.state == FallState.NORMAL
    assert not ev.is_fall


def test_impact_without_orientation_change_clears_to_normal(detector):
    """Large vertical impact (e.g. jumping) without tilt change clears back to NORMAL."""
    base_time = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)

    # Baseline upright
    for i in range(5):
        detector.detect(accel_x=0.0, accel_y=0.0, accel_z=1.0, timestamp=base_time + timedelta(seconds=i * 0.2))

    # Impact spike 3.0g on Z axis (vertical jump landing), gyro rate small (20 deg/s)
    ev_impact = detector.detect(
        accel_x=0.0, accel_y=0.0, accel_z=3.0,
        gyro_x=5.0, gyro_y=10.0, gyro_z=5.0,
        timestamp=base_time + timedelta(seconds=1.2)
    )

    # No tilt occurred, posture stayed aligned with Z axis
    # Next sample verifies posture check
    ev_verify = detector.detect(
        accel_x=0.0, accel_y=0.0, accel_z=1.0,
        gyro_x=5.0, gyro_y=5.0, gyro_z=5.0,
        timestamp=base_time + timedelta(seconds=1.4)
    )
    assert ev_verify.state == FallState.NORMAL
    assert not ev_verify.is_fall
    assert "without significant orientation change" in ev_verify.details


def test_impact_with_resumed_activity_clears_to_normal(detector):
    """Impact + tilt followed by immediate vigorous motion (dropped phone picked up) does not trigger fall."""
    base_time = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)

    # Baseline
    detector.detect(accel_x=0.0, accel_y=0.0, accel_z=1.0, timestamp=base_time)

    # Impact with high rotational velocity (180 deg/s) -> POSSIBLE_FALL
    ev_impact = detector.detect(
        accel_x=2.2, accel_y=1.5, accel_z=0.5,  # ~2.7g
        gyro_x=120.0, gyro_y=100.0, gyro_z=60.0,
        timestamp=base_time + timedelta(seconds=0.5)
    )
    assert ev_impact.state in (FallState.POSSIBLE_IMPACT, FallState.POSSIBLE_FALL)

    # Immediate vigorous movement: 2.2g acceleration during post-impact check
    ev_active = detector.detect(
        accel_x=1.5, accel_y=1.5, accel_z=0.5,
        gyro_x=80.0, gyro_y=50.0, gyro_z=40.0,
        timestamp=base_time + timedelta(seconds=1.0)
    )
    assert ev_active.state == FallState.NORMAL
    assert "Active motion resumed" in ev_active.details


def test_genuine_fall_pattern_confirmed(detector):
    """
    Genuine fall scenario:
    1. Upright baseline (accel on Z)
    2. Violent impact (3.2g) with gyro rotation (160 deg/s)
    3. Posture flips to horizontal (accel on X/Y)
    4. Motionless stillness for >= 2.0s -> FALL_DETECTED
    """
    base_time = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)

    # Step 1: Upright baseline
    for i in range(5):
        detector.detect(accel_x=0.0, accel_y=0.0, accel_z=1.0, timestamp=base_time + timedelta(seconds=i * 0.2))

    # Step 2: Impact spike (3.2g) with intense rotation (160 deg/s)
    t_impact = base_time + timedelta(seconds=1.2)
    ev_impact = detector.detect(
        accel_x=2.5, accel_y=1.8, accel_z=0.8,  # ~3.18g
        gyro_x=120.0, gyro_y=90.0, gyro_z=50.0,
        timestamp=t_impact
    )
    assert ev_impact.state in (FallState.POSSIBLE_IMPACT, FallState.POSSIBLE_FALL)

    # Step 3: Victim is lying flat (accel on X axis ~1.0g), stationary for 2.2 seconds
    for step in range(1, 6):
        t_still = t_impact + timedelta(seconds=step * 0.5)
        ev_still = detector.detect(
            accel_x=1.0, accel_y=0.05, accel_z=0.05,  # ~1.0g resting horizontally
            gyro_x=1.0, gyro_y=1.0, gyro_z=1.0,       # Near-zero rotation
            timestamp=t_still
        )

    # After 2.5s of stillness, FALL_DETECTED must be confirmed
    assert ev_still.state == FallState.FALL_DETECTED
    assert ev_still.is_fall is True
    assert ev_still.confidence >= 0.70
    assert "confirmed fall" in ev_still.details.lower()


def test_recovery_after_confirmed_fall(detector):
    """Traveler stands up and moves actively after a fall -> transitions to RECOVERED."""
    base_time = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)

    # Drive into FALL_DETECTED
    detector.detect(accel_x=0.0, accel_y=0.0, accel_z=1.0, timestamp=base_time)
    t_imp = base_time + timedelta(seconds=1.0)
    detector.detect(accel_x=2.5, accel_y=1.8, accel_z=0.8, gyro_x=150.0, gyro_y=50.0, gyro_z=20.0, timestamp=t_imp)
    detector.detect(accel_x=1.0, accel_y=0.0, accel_z=0.0, gyro_x=0.0, gyro_y=0.0, gyro_z=0.0, timestamp=t_imp + timedelta(seconds=2.5))
    assert detector.current_state == FallState.FALL_DETECTED

    # Recovery motion: traveler struggles up (|a - 1.0| >= 0.6g)
    # Observation 1
    t_rec1 = t_imp + timedelta(seconds=3.0)
    ev_rec1 = detector.detect(accel_x=0.3, accel_y=0.3, accel_z=1.8, timestamp=t_rec1)
    assert ev_rec1.state == FallState.FALL_DETECTED  # Waiting for 2nd observation

    # Observation 2
    t_rec2 = t_imp + timedelta(seconds=3.5)
    ev_rec2 = detector.detect(accel_x=0.2, accel_y=0.2, accel_z=1.7, timestamp=t_rec2)
    assert ev_rec2.state == FallState.RECOVERED
    assert not ev_rec2.is_fall


def test_accel_only_graceful_degradation(detector):
    """
    When gyroscope is absent (None), detector uses gravitational tilt angle.
    Does NOT fabricate fake gyro values.
    """
    base_time = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)

    # Upright baseline on Z axis
    for i in range(5):
        detector.detect(accel_x=0.0, accel_y=0.0, accel_z=1.0, timestamp=base_time + timedelta(seconds=i * 0.2))

    # Impact spike on X axis (posture tilt from Z to X is 90 degrees)
    t_imp = base_time + timedelta(seconds=1.2)
    ev_imp = detector.detect(
        accel_x=3.0, accel_y=0.0, accel_z=0.0,  # 3g on X
        gyro_x=None, gyro_y=None, gyro_z=None,  # No gyroscope!
        timestamp=t_imp
    )
    assert ev_imp.sensor_mode == SensorMode.ACCEL_ONLY
    assert ev_imp.orientation_change_deg is not None
    assert ev_imp.orientation_change_deg > 60.0  # Gravitational tilt ~90 deg

    # Post-impact stillness on X axis (lying flat)
    t_still = t_imp + timedelta(seconds=2.5)
    ev_still = detector.detect(
        accel_x=1.0, accel_y=0.0, accel_z=0.0,
        gyro_x=None, gyro_y=None, gyro_z=None,
        timestamp=t_still
    )
    assert ev_still.state == FallState.FALL_DETECTED
    assert ev_still.sensor_mode == SensorMode.ACCEL_ONLY


def test_si_units_automatic_conversion(detector):
    """Accelerometer inputs in SI m/s2 (e.g. 9.81 m/s2, 28.0 m/s2) are converted to units of g."""
    base_time = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)

    # 9.81 m/s2 baseline
    detector.detect(accel_x=0.0, accel_y=0.0, accel_z=9.81, timestamp=base_time)

    # Impact in m/s2: 29.4 m/s2 (~3.0g)
    ev = detector.detect(accel_x=15.0, accel_y=15.0, accel_z=20.0, timestamp=base_time + timedelta(seconds=0.5))
    # Peak impact should be around ~3.0g
    assert 2.8 <= ev.impact_magnitude_g <= 3.2


def test_detector_reset(detector):
    """Reset clears history and restores state to NORMAL."""
    base_time = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    detector.detect(accel_x=0.0, accel_y=0.0, accel_z=1.0, timestamp=base_time)
    t_imp = base_time + timedelta(seconds=1.0)
    detector.detect(accel_x=3.0, accel_y=0.0, accel_z=0.0, gyro_x=150.0, gyro_y=0.0, gyro_z=0.0, timestamp=t_imp)
    detector.detect(accel_x=1.0, accel_y=0.0, accel_z=0.0, timestamp=t_imp + timedelta(seconds=2.5))
    assert detector.current_state == FallState.FALL_DETECTED

    detector.reset()
    assert detector.current_state == FallState.NORMAL
    assert detector.impact_time is None
    assert detector.peak_impact_g == 1.0


# --- API Endpoint Integration Tests ---

def test_api_fall_detection_endpoints():
    """POST /edge/fall/evaluate and /reset respond correctly."""
    payload = {
        "accel_x": 0.1,
        "accel_y": 0.2,
        "accel_z": 1.0,
        "gyro_x": 10.0,
        "gyro_y": 15.0,
        "gyro_z": 5.0
    }
    r = client.post("/edge/fall/evaluate", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["event_type"] == "FALL_DETECTED"
    assert data["state"] == "NORMAL"
    assert not data["is_fall"]
    assert data["sensor_mode"] == "accel_and_gyro"

    # Reset endpoint
    r_reset = client.post("/edge/fall/reset")
    assert r_reset.status_code == 200
    assert r_reset.json()["status"] == "reset"
    assert r_reset.json()["state"] == "NORMAL"
