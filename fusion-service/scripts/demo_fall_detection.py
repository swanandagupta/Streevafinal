"""
STREEVA — Phase 1C Gyroscope & Accelerometer Fall Detection Deterministic Replay / Demo.

Executes deterministic simulations for the 6 scenarios required by the prompt:
1. Normal walking (steady ~1.0g motion -> NORMAL)
2. Small acceleration spike (< 2.5g -> NORMAL, no false fall)
3. Large impact + orientation change + post-impact inactivity -> FALL_DETECTED
4. Large acceleration caused by normal activity (e.g. jumping or jogging) -> Clears to NORMAL
5. Fall followed by movement recovery (FALL_DETECTED -> RECOVERED)
6. Gyroscope unavailable (Graceful degradation to gravitational tilt, no fake gyro values)
"""

import sys
import os
from datetime import datetime, timezone, timedelta

# Add parent directory to sys.path to resolve 'app'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.edge.fall_detection import (
    FallDetector,
    FallDetectionConfig,
    FallState,
    SensorMode
)


def print_step(step_num: int, event, mode_str: str = ""):
    state_colors = {
        FallState.NORMAL: "\033[92m",            # Green
        FallState.POSSIBLE_IMPACT: "\033[93m",   # Yellow
        FallState.POSSIBLE_FALL: "\033[93m",     # Yellow
        FallState.FALL_DETECTED: "\033[91m",     # Red
        FallState.RECOVERED: "\033[96m"          # Cyan
    }
    color = state_colors.get(event.state, "")
    reset = "\033[0m"

    tilt_str = f"Tilt: {event.orientation_change_deg:04.1f} deg" if event.orientation_change_deg is not None else "Tilt: None    "
    print(
        f"  Step {step_num:02d}: {color}[{event.state.value.ljust(16)}]{reset} "
        f"Impact: {event.impact_magnitude_g:04.2f}g | "
        f"{tilt_str} | "
        f"Conf: {event.confidence:04.2f} "
        f"{mode_str}| {event.details}"
    )


def run_demo():
    print("=" * 80)
    print(" STREEVA — PHASE 1C FALL DETECTION DETERMINISTIC REPLAY")
    print("=" * 80)

    config = FallDetectionConfig(
        impact_threshold_g=2.5,
        orientation_change_threshold_deg=45.0,
        gyro_angular_velocity_threshold_dps=120.0,
        post_impact_inactivity_duration_s=2.0,
        inactivity_accel_variance_max=0.5,
        recovery_motion_threshold_g=0.6,
        consecutive_recovery_observations=2
    )
    detector = FallDetector(config=config)
    base_time = datetime(2026, 9, 12, 14, 0, 0, tzinfo=timezone.utc)

    # -------------------------------------------------------------------------
    # TEST 1: Normal walking
    # -------------------------------------------------------------------------
    print("\n--- TEST 1: Normal Walking (Steady ~1.0g acceleration) ---")
    detector.reset()
    for i in range(1, 5):
        t = base_time + timedelta(seconds=i * 0.5)
        ev = detector.detect(accel_x=0.1, accel_y=0.2, accel_z=1.0, gyro_x=10.0, gyro_y=15.0, gyro_z=5.0, timestamp=t)
        print_step(i, ev)
    assert detector.current_state == FallState.NORMAL
    print("  Result: Normal walking maintained in NORMAL state.")

    # -------------------------------------------------------------------------
    # TEST 2: Small acceleration spike
    # -------------------------------------------------------------------------
    print("\n--- TEST 2: Small Acceleration Spike (< 2.5g threshold) ---")
    detector.reset()
    # Baseline
    detector.detect(accel_x=0.0, accel_y=0.0, accel_z=1.0, timestamp=base_time)
    # 1.8g step down
    ev_spike = detector.detect(accel_x=0.8, accel_y=0.8, accel_z=1.4, timestamp=base_time + timedelta(seconds=0.5))
    print_step(1, ev_spike)
    assert detector.current_state == FallState.NORMAL
    print("  Result: Minor spike below 2.5g ignored. Remained NORMAL.")

    # -------------------------------------------------------------------------
    # TEST 3: Genuine fall pattern (Impact + Orientation + Inactivity)
    # -------------------------------------------------------------------------
    print("\n--- TEST 3: Genuine Fall (Impact >= 2.5g + Tilt >= 45 deg + Inactivity >= 2.0s) ---")
    detector.reset()
    # Baseline upright
    for i in range(3):
        detector.detect(accel_x=0.0, accel_y=0.0, accel_z=1.0, timestamp=base_time + timedelta(seconds=i * 0.2))

    # Step 1: Violent Impact (3.2g) with intense gyro rotation (160 deg/s)
    t_imp = base_time + timedelta(seconds=1.0)
    ev_imp = detector.detect(
        accel_x=2.5, accel_y=1.8, accel_z=0.8,
        gyro_x=120.0, gyro_y=90.0, gyro_z=50.0,
        timestamp=t_imp
    )
    print_step(1, ev_imp)
    assert ev_imp.state in (FallState.POSSIBLE_IMPACT, FallState.POSSIBLE_FALL)

    # Step 2: Post-impact stillness (victim lying motionless on ground for 2.5s)
    for step in range(1, 6):
        t_still = t_imp + timedelta(seconds=step * 0.5)
        ev_still = detector.detect(
            accel_x=1.0, accel_y=0.05, accel_z=0.05,
            gyro_x=1.0, gyro_y=1.0, gyro_z=1.0,
            timestamp=t_still
        )
        print_step(step + 1, ev_still)

    assert detector.current_state == FallState.FALL_DETECTED
    assert ev_still.is_fall is True
    print("  Result: Confirmed fall successfully registered into FALL_DETECTED state.")

    # -------------------------------------------------------------------------
    # TEST 4: Large acceleration caused by normal activity (e.g. vertical jump)
    # -------------------------------------------------------------------------
    print("\n--- TEST 4: High Acceleration from Normal Activity (Vertical Jump landing) ---")
    detector.reset()
    # Baseline
    for i in range(3):
        detector.detect(accel_x=0.0, accel_y=0.0, accel_z=1.0, timestamp=base_time + timedelta(seconds=i * 0.2))

    # High impact (3.1g on Z axis), but orientation remains vertical (tilt < 45 deg)
    t_jump = base_time + timedelta(seconds=1.0)
    ev_jump = detector.detect(
        accel_x=0.1, accel_y=0.1, accel_z=3.1,
        gyro_x=10.0, gyro_y=15.0, gyro_z=5.0,
        timestamp=t_jump
    )
    print_step(1, ev_jump)

    # Next sample: vertical posture confirmed without orientation change
    ev_verify = detector.detect(
        accel_x=0.0, accel_y=0.0, accel_z=1.0,
        gyro_x=5.0, gyro_y=5.0, gyro_z=5.0,
        timestamp=t_jump + timedelta(seconds=0.2)
    )
    print_step(2, ev_verify)
    assert detector.current_state == FallState.NORMAL
    print("  Result: Jump cleared back to NORMAL due to lack of orientation change.")

    # -------------------------------------------------------------------------
    # TEST 5: Fall followed by movement recovery
    # -------------------------------------------------------------------------
    print("\n--- TEST 5: Fall Followed by Recovery (FALL_DETECTED -> RECOVERED) ---")
    detector.reset()
    detector.detect(accel_x=0.0, accel_y=0.0, accel_z=1.0, timestamp=base_time)
    t_fall = base_time + timedelta(seconds=1.0)
    detector.detect(accel_x=2.5, accel_y=1.8, accel_z=0.8, gyro_x=150.0, gyro_y=50.0, gyro_z=20.0, timestamp=t_fall)
    ev_fallen = detector.detect(accel_x=1.0, accel_y=0.0, accel_z=0.0, gyro_x=0.0, gyro_y=0.0, gyro_z=0.0, timestamp=t_fall + timedelta(seconds=2.5))
    print_step(1, ev_fallen)
    assert ev_fallen.state == FallState.FALL_DETECTED

    # Recovery motion: traveler struggles up (|a - 1.0| >= 0.6g)
    ev_rec1 = detector.detect(accel_x=0.3, accel_y=0.3, accel_z=1.8, timestamp=t_fall + timedelta(seconds=3.0))
    print_step(2, ev_rec1)
    ev_rec2 = detector.detect(accel_x=0.2, accel_y=0.2, accel_z=1.7, timestamp=t_fall + timedelta(seconds=3.5))
    print_step(3, ev_rec2)
    assert detector.current_state == FallState.RECOVERED
    print("  Result: Confirmed recovery transition to RECOVERED state.")

    # -------------------------------------------------------------------------
    # TEST 6: Gyroscope unavailable (Graceful degradation)
    # -------------------------------------------------------------------------
    print("\n--- TEST 6: Gyroscope Unavailable (Graceful degradation via tilt angle) ---")
    detector.reset()
    # Baseline on Z axis
    for i in range(3):
        detector.detect(accel_x=0.0, accel_y=0.0, accel_z=1.0, timestamp=base_time + timedelta(seconds=i * 0.2))

    # Impact spike on X axis without gyroscope (None)
    t_deg = base_time + timedelta(seconds=1.0)
    ev_deg_imp = detector.detect(
        accel_x=3.0, accel_y=0.0, accel_z=0.0,
        gyro_x=None, gyro_y=None, gyro_z=None,
        timestamp=t_deg
    )
    print_step(1, ev_deg_imp, mode_str="[ACCEL_ONLY] ")
    assert ev_deg_imp.sensor_mode == SensorMode.ACCEL_ONLY
    assert ev_deg_imp.orientation_change_deg is not None
    assert ev_deg_imp.orientation_change_deg > 60.0

    # Stillness on ground without gyroscope
    ev_deg_still = detector.detect(
        accel_x=1.0, accel_y=0.0, accel_z=0.0,
        gyro_x=None, gyro_y=None, gyro_z=None,
        timestamp=t_deg + timedelta(seconds=2.5)
    )
    print_step(2, ev_deg_still, mode_str="[ACCEL_ONLY] ")
    assert ev_deg_still.state == FallState.FALL_DETECTED
    assert ev_deg_still.sensor_mode == SensorMode.ACCEL_ONLY
    print("  Result: Accel-only fallback successfully detected fall without fabricating fake gyro data.")

    print("\n" + "=" * 80)
    print(" ALL 6 FALL DETECTION DETERMINISTIC REPLAY SCENARIOS VERIFIED!")
    print("=" * 80)


if __name__ == "__main__":
    run_demo()
