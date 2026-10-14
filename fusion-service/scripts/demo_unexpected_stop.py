"""
STREEVA — Phase 1B Unexpected Stop Detection Deterministic Replay / Demo.

Executes deterministic simulations for the 5 scenarios required by the prompt:
1. Normal continuous movement (walking smoothly -> MOVING)
2. Brief GPS pause / noise (< 15s -> stays MOVING, no STOPPED event)
3. Stationary longer than threshold (>= 45s -> POSSIBLE_STOP -> STOPPED)
4. Stop and resume (MOVING -> STOPPED -> RECOVERED -> MOVING)
5. Poor GPS accuracy (> 50m -> suppresses false STOPPED transition)
"""

import sys
import os
from datetime import datetime, timezone, timedelta

# Add parent directory to sys.path to resolve 'app'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.edge.unexpected_stop import (
    UnexpectedStopDetector,
    UnexpectedStopConfig,
    StopState
)


def print_step(step_num: int, event, acc_str: str = ""):
    state_colors = {
        StopState.MOVING: "\033[92m",          # Green
        StopState.POSSIBLE_STOP: "\033[93m",   # Yellow
        StopState.STOPPED: "\033[91m",         # Red
        StopState.RECOVERING: "\033[96m"       # Cyan
    }
    color = state_colors.get(event.state, "")
    reset = "\033[0m"

    print(
        f"  Step {step_num:02d}: {color}[{event.state.value.ljust(15)}]{reset} "
        f"Speed: {event.speed_mps:04.2f}m/s | "
        f"Still: {event.stationary_duration_s:04.1f}s | "
        f"Conf: {event.confidence:04.2f} "
        f"{acc_str}| {event.details}"
    )


def run_demo():
    print("=" * 80)
    print(" STREEVA — PHASE 1B UNEXPECTED STOP DETECTION DETERMINISTIC REPLAY")
    print("=" * 80)

    config = UnexpectedStopConfig(
        stop_speed_threshold_mps=0.5,
        possible_stop_duration_s=15.0,
        minimum_stop_duration_s=45.0,
        recovery_speed_threshold_mps=1.0,
        consecutive_recovery_observations=2,
        gps_accuracy_limit_m=50.0
    )
    detector = UnexpectedStopDetector(config=config)
    base_time = datetime(2026, 9, 12, 14, 0, 0, tzinfo=timezone.utc)

    # -------------------------------------------------------------------------
    # TEST 1: Normal continuous movement
    # -------------------------------------------------------------------------
    print("\n--- TEST 1: Normal Continuous Movement (Traveler walking smoothly) ---")
    detector.reset()
    lat, lng = 13.0600, 80.2500
    for i in range(1, 6):
        t = base_time + timedelta(seconds=i * 5)
        lat += 0.000055  # ~6.1m in 5s (~1.22 m/s)
        ev = detector.detect({"lat": lat, "lng": lng}, timestamp=t, gps_accuracy=5.0)
        print_step(i, ev)
    assert detector.current_state == StopState.MOVING
    print("  Result: Traveler remained in MOVING state throughout.")

    # -------------------------------------------------------------------------
    # TEST 2: Brief GPS pause / noise
    # -------------------------------------------------------------------------
    print("\n--- TEST 2: Brief GPS Pause / Traffic Light (< 15s pause) ---")
    detector.reset()
    lat, lng = 13.0600, 80.2500
    # Step 1: Initial moving fix
    ev = detector.detect({"lat": lat, "lng": lng}, timestamp=base_time, gps_accuracy=5.0)
    print_step(1, ev)
    # Step 2: Traveler moving at 1.2 m/s
    lat += 0.00006
    ev = detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=5), gps_accuracy=5.0)
    print_step(2, ev)
    # Step 3: Brief pause for 10s at red light
    ev = detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=15), gps_accuracy=5.0)
    print_step(3, ev)
    # Step 4: Light turns green, movement resumes
    lat += 0.00006
    ev = detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=20), gps_accuracy=5.0)
    print_step(4, ev)
    assert detector.current_state == StopState.MOVING
    print("  Result: Brief pause did not trigger any false STOPPED event.")

    # -------------------------------------------------------------------------
    # TEST 3: Stationary longer than threshold
    # -------------------------------------------------------------------------
    print("\n--- TEST 3: Sustained Stationary Period (POSSIBLE_STOP -> STOPPED) ---")
    detector.reset()
    lat, lng = 13.0600, 80.2500
    # Moving at t=0
    detector.detect({"lat": lat, "lng": lng}, timestamp=base_time, gps_accuracy=5.0)
    lat += 0.00006
    ev1 = detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=5), gps_accuracy=5.0)
    print_step(1, ev1)
    # At t=25 (stationary for 20s >= 15s) -> POSSIBLE_STOP
    ev2 = detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=25), gps_accuracy=5.0)
    print_step(2, ev2)
    # At t=40 (stationary for 35s) -> stays POSSIBLE_STOP
    ev3 = detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=40), gps_accuracy=5.0)
    print_step(3, ev3)
    # At t=55 (stationary for 50s >= 45s) -> STOPPED
    ev4 = detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=55), gps_accuracy=5.0)
    print_step(4, ev4)
    assert detector.current_state == StopState.STOPPED
    assert ev4.is_stopped is True
    print("  Result: State successfully escalated to STOPPED after sustained stillness.")

    # -------------------------------------------------------------------------
    # TEST 4: Stop and resume (Hysteresis & Recovery)
    # -------------------------------------------------------------------------
    print("\n--- TEST 4: Stop and Resume (MOVING -> STOPPED -> RECOVERING -> MOVING) ---")
    detector.reset()
    lat, lng = 13.0600, 80.2500
    # Drive into STOPPED
    detector.detect({"lat": lat, "lng": lng}, timestamp=base_time, gps_accuracy=5.0)
    lat += 0.00006
    detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=5), gps_accuracy=5.0)
    ev_stop = detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=55), gps_accuracy=5.0)
    print_step(1, ev_stop)
    assert ev_stop.state == StopState.STOPPED

    # Step 2: Creep speed (~0.7 m/s, within hysteresis buffer 0.5 - 1.0 m/s) -> remains STOPPED
    lat += 0.00003
    ev_creep = detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=60), gps_accuracy=5.0)
    print_step(2, ev_creep)
    assert ev_creep.state == StopState.STOPPED

    # Step 3: Sustained movement obs 1 (~1.4 m/s >= 1.0 m/s) -> RECOVERING
    lat += 0.000065
    ev_rec1 = detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=65), gps_accuracy=5.0)
    print_step(3, ev_rec1)
    assert ev_rec1.state == StopState.RECOVERING

    # Step 4: Sustained movement obs 2 (~1.4 m/s) -> MOVING
    lat += 0.000065
    ev_rec2 = detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=70), gps_accuracy=5.0)
    print_step(4, ev_rec2)
    assert ev_rec2.state == StopState.MOVING
    print("  Result: Full lifecycle verified: MOVING -> STOPPED -> RECOVERING -> MOVING.")

    # -------------------------------------------------------------------------
    # TEST 5: Poor GPS accuracy
    # -------------------------------------------------------------------------
    print("\n--- TEST 5: Poor GPS Accuracy (Degraded signal suppresses STOPPED) ---")
    detector.reset()
    lat, lng = 13.0600, 80.2500
    ev1 = detector.detect({"lat": lat, "lng": lng}, timestamp=base_time, gps_accuracy=85.0)
    print_step(1, ev1, acc_str="Acc: 85.0m ")
    # Still stationary 60s later, but with degraded accuracy (85m > 50m limit)
    ev2 = detector.detect({"lat": lat, "lng": lng}, timestamp=base_time + timedelta(seconds=60), gps_accuracy=85.0)
    print_step(2, ev2, acc_str="Acc: 85.0m ")
    assert detector.current_state != StopState.STOPPED
    print("  Result: Degraded GPS accuracy successfully prevented false STOPPED state.")

    print("\n" + "=" * 80)
    print(" ALL 5 UNEXPECTED STOP DETERMINISTIC REPLAY SCENARIOS VERIFIED!")
    print("=" * 80)


if __name__ == "__main__":
    run_demo()
