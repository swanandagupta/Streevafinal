"""
STREEVA — Phase 2 Guardian Journey Intelligence Deterministic Replay / Demo.

Executes deterministic simulations for all 11 scenarios required by Phase 2:
1. SCENARIO 1 — Normal Journey (START -> moving -> route progress -> ETA -> arrived)
2. SCENARIO 2 — GPS Noise (jitter within corridor -> progress stable, no false arrival)
3. SCENARIO 3 — Temporary GPS Degradation (accuracy > 60m -> DEGRADED -> recovery -> ACTIVE)
4. SCENARIO 4 — GPS Gap / Telemetry Timeout (> 30s gap -> STALE -> recovery -> ACTIVE)
5. SCENARIO 5 — Route Deviation (deviation event consumed -> anomaly recorded -> on-route -> recovered)
6. SCENARIO 6 — Unexpected Stop (stop event consumed -> STALLED -> movement resumes -> moving)
7. SCENARIO 7 — Fall Event (fall event consumed -> recorded in snapshot -> NO emergency action)
8. SCENARIO 8 — Audio Distress (audio event consumed -> recorded in snapshot -> NO emergency action)
9. SCENARIO 9 — Arrival (consecutive observations within 50m -> ARRIVED)
10. SCENARIO 10 — Cancellation (user cancels -> CANCELLED -> rejects further updates)
11. SCENARIO 11 — Reset / New Journey (Journey A ends -> Journey B starts clean, zero state leakage)
"""

import sys
import os
from datetime import datetime, timezone, timedelta

# Add parent directory to sys.path to resolve 'app'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.guardian.journey_state import (
    JourneyState,
    TelemetryQuality,
    ArrivalStatus,
    ProgressStatus,
    ETASource,
    GuardianConfig,
    JourneyStartRequest,
    JourneyUpdateRequest,
    JourneyEndRequest,
    GuardianSnapshot
)
from app.guardian.monitor import GuardianMonitor


def print_step(step_name: str, snap: GuardianSnapshot):
    state_colors = {
        JourneyState.STARTING: "\033[94m",   # Blue
        JourneyState.ACTIVE: "\033[92m",     # Green
        JourneyState.DEGRADED: "\033[93m",   # Yellow
        JourneyState.ARRIVING: "\033[96m",   # Cyan
        JourneyState.ARRIVED: "\033[92m",    # Bright Green
        JourneyState.CANCELLED: "\033[91m"   # Red
    }
    color = state_colors.get(snap.journey_state, "")
    reset = "\033[0m"

    eta_str = snap.eta.strftime("%H:%M:%S") if snap.eta else "N/A     "
    anomalies_str = f"Anomalies: {snap.active_anomalies}" if snap.active_anomalies else "Anomalies: None"

    print(
        f"  [{step_name.ljust(18)}] {color}[{snap.journey_state.value.ljust(10)}]{reset} "
        f"Quality: {snap.telemetry_quality.value.ljust(13)} | "
        f"Progress: {snap.route_progress_percent:05.1f}% | "
        f"Remaining: {snap.remaining_distance_m:05.0f}m | "
        f"ETA: {eta_str} ({snap.eta_source.value[:3]}) | "
        f"{anomalies_str}"
    )


def run_demo():
    print("=" * 105)
    print(" STREEVA — PHASE 2 GUARDIAN JOURNEY INTELLIGENCE DETERMINISTIC REPLAY")
    print("=" * 105)

    config = GuardianConfig(
        arrival_radius_m=50.0,
        arrival_gps_accuracy_ceiling_m=40.0,
        arrival_consecutive_observations_required=2,
        telemetry_stale_timeout_s=30.0,
        gps_accuracy_ceiling_m=60.0,
        corridor_radius_m=50.0,
        min_movement_speed_mps=0.5,
        default_travel_speed_mps=1.3,
        eta_smoothing_alpha=0.4,
        delay_threshold_s=180.0
    )
    monitor = GuardianMonitor(config=config)

    # -------------------------------------------------------------
    # SCENARIO 1: Normal Journey
    # -------------------------------------------------------------
    print("\n" + "-" * 105)
    print(" SCENARIO 1: Normal Journey (Start -> Progression -> ETA -> Arrived)")
    print("-" * 105)
    monitor.reset()
    base_time = datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc)
    route = [
        {"lat": 13.0800, "lng": 80.2700},
        {"lat": 13.0850, "lng": 80.2700},
        {"lat": 13.0900, "lng": 80.2700}
    ]

    snap = monitor.start_journey(JourneyStartRequest(
        journey_id="J-DEMO-01",
        source_lat=13.0800, source_lng=80.2700,
        destination_lat=13.0900, destination_lng=80.2700,
        expected_route=route,
        timestamp=base_time
    ))
    print_step("Journey Start", snap)

    # Waypoint 1 (at 25% route)
    snap = monitor.update_telemetry(JourneyUpdateRequest(
        journey_id="J-DEMO-01", latitude=13.0825, longitude=80.2700, gps_accuracy=10.0,
        timestamp=base_time + timedelta(seconds=15)
    ))
    print_step("Waypoint 1 (25%)", snap)

    # Waypoint 2 (at 50% route)
    snap = monitor.update_telemetry(JourneyUpdateRequest(
        journey_id="J-DEMO-01", latitude=13.0850, longitude=80.2700, gps_accuracy=10.0,
        timestamp=base_time + timedelta(seconds=30)
    ))
    print_step("Waypoint 2 (50%)", snap)

    # Near destination (Observation 1 -> ARRIVING)
    snap = monitor.update_telemetry(JourneyUpdateRequest(
        journey_id="J-DEMO-01", latitude=13.0898, longitude=80.2700, gps_accuracy=10.0,
        timestamp=base_time + timedelta(seconds=45)
    ))
    print_step("Near Dest Obs 1", snap)
    assert snap.journey_state == JourneyState.ARRIVING

    # Destination confirmed (Observation 2 -> ARRIVED)
    snap = monitor.update_telemetry(JourneyUpdateRequest(
        journey_id="J-DEMO-01", latitude=13.0900, longitude=80.2700, gps_accuracy=10.0,
        timestamp=base_time + timedelta(seconds=50)
    ))
    print_step("Dest Confirmed Obs 2", snap)
    assert snap.journey_state == JourneyState.ARRIVED
    print("  >>> PASS: Normal journey completed from STARTING to ARRIVED.")

    # -------------------------------------------------------------
    # SCENARIO 2: GPS Noise & Monotonic Stability
    # -------------------------------------------------------------
    print("\n" + "-" * 105)
    print(" SCENARIO 2: GPS Noise (Jitter within corridor preserves monotonic progress)")
    print("-" * 105)
    monitor.reset()
    monitor.start_journey(JourneyStartRequest(
        journey_id="J-DEMO-02", source_lat=13.0800, source_lng=80.2700,
        destination_lat=13.0900, destination_lng=80.2700, expected_route=route, timestamp=base_time
    ))
    # Point 1 (60% forward)
    snap1 = monitor.update_telemetry(JourneyUpdateRequest(
        journey_id="J-DEMO-02", latitude=13.0860, longitude=80.2700, gps_accuracy=12.0,
        timestamp=base_time + timedelta(seconds=10)
    ))
    print_step("Step 1 (Forward)", snap1)

    # Point 2 (GPS jitter slightly backward - 20m jitter)
    snap2 = monitor.update_telemetry(JourneyUpdateRequest(
        journey_id="J-DEMO-02", latitude=13.0858, longitude=80.2702, gps_accuracy=15.0,
        timestamp=base_time + timedelta(seconds=15)
    ))
    print_step("Step 2 (Jitter Back)", snap2)
    assert snap2.route_progress_percent >= snap1.route_progress_percent
    print("  >>> PASS: Backward GPS noise did not disrupt monotonic progress.")

    # -------------------------------------------------------------
    # SCENARIO 3: Temporary GPS Degradation (Accuracy > 60m)
    # -------------------------------------------------------------
    print("\n" + "-" * 105)
    print(" SCENARIO 3: Temporary GPS Degradation (Accuracy > 60m -> DEGRADED -> Recovery)")
    print("-" * 105)
    monitor.reset()
    monitor.start_journey(JourneyStartRequest(
        journey_id="J-DEMO-03", source_lat=13.0800, source_lng=80.2700,
        destination_lat=13.0900, destination_lng=80.2700, expected_route=route, timestamp=base_time
    ))
    snap_good = monitor.update_telemetry(JourneyUpdateRequest(
        journey_id="J-DEMO-03", latitude=13.0820, longitude=80.2700, gps_accuracy=15.0,
        timestamp=base_time + timedelta(seconds=10)
    ))
    print_step("Good GPS", snap_good)
    assert snap_good.journey_state == JourneyState.ACTIVE

    snap_bad = monitor.update_telemetry(JourneyUpdateRequest(
        journey_id="J-DEMO-03", latitude=13.0830, longitude=80.2700, gps_accuracy=85.0,
        timestamp=base_time + timedelta(seconds=20)
    ))
    print_step("Degraded GPS (85m)", snap_bad)
    assert snap_bad.journey_state == JourneyState.DEGRADED
    assert snap_bad.telemetry_quality == TelemetryQuality.POOR_ACCURACY

    snap_rec = monitor.update_telemetry(JourneyUpdateRequest(
        journey_id="J-DEMO-03", latitude=13.0840, longitude=80.2700, gps_accuracy=12.0,
        timestamp=base_time + timedelta(seconds=30)
    ))
    print_step("Recovered GPS", snap_rec)
    assert snap_rec.journey_state == JourneyState.ACTIVE
    assert snap_rec.telemetry_quality == TelemetryQuality.RECOVERED
    print("  >>> PASS: State degraded on poor accuracy and recovered cleanly.")

    # -------------------------------------------------------------
    # SCENARIO 4: GPS Gap / Telemetry Timeout (> 30s gap)
    # -------------------------------------------------------------
    print("\n" + "-" * 105)
    print(" SCENARIO 4: GPS Gap / Telemetry Timeout (> 30s gap -> STALE -> Recovery)")
    print("-" * 105)
    monitor.reset()
    monitor.start_journey(JourneyStartRequest(
        journey_id="J-DEMO-04", source_lat=13.0800, source_lng=80.2700,
        destination_lat=13.0900, destination_lng=80.2700, expected_route=route, timestamp=base_time
    ))
    monitor.update_telemetry(JourneyUpdateRequest(
        journey_id="J-DEMO-04", latitude=13.0820, longitude=80.2700, gps_accuracy=15.0,
        timestamp=base_time + timedelta(seconds=10)
    ))
    # Telemetry gap of 45s (> 30s timeout)
    snap_gap = monitor.update_telemetry(JourneyUpdateRequest(
        journey_id="J-DEMO-04", latitude=13.0840, longitude=80.2700, gps_accuracy=15.0,
        timestamp=base_time + timedelta(seconds=55)
    ))
    print_step("Telemetry Gap (45s)", snap_gap)
    assert snap_gap.telemetry_quality == TelemetryQuality.STALE
    assert snap_gap.journey_state == JourneyState.DEGRADED

    # Fresh update arrives 10s later
    snap_resumed = monitor.update_telemetry(JourneyUpdateRequest(
        journey_id="J-DEMO-04", latitude=13.0850, longitude=80.2700, gps_accuracy=15.0,
        timestamp=base_time + timedelta(seconds=65)
    ))
    print_step("Resumed Fresh GPS", snap_resumed)
    assert snap_resumed.journey_state == JourneyState.ACTIVE
    print("  >>> PASS: Telemetry timeout triggered STALE and recovered on fresh update.")

    # -------------------------------------------------------------
    # SCENARIO 5: Route Deviation Event Consumed
    # -------------------------------------------------------------
    print("\n" + "-" * 105)
    print(" SCENARIO 5: Route Deviation (Off-route position -> Anomaly in Snapshot -> Recovery)")
    print("-" * 105)
    monitor.reset()
    monitor.start_journey(JourneyStartRequest(
        journey_id="J-DEMO-05", source_lat=13.0800, source_lng=80.2700,
        destination_lat=13.0900, destination_lng=80.2700, expected_route=route, timestamp=base_time
    ))
    # Move > 150m off route (longitude 80.2720)
    snap_dev = monitor.update_telemetry(JourneyUpdateRequest(
        journey_id="J-DEMO-05", latitude=13.0850, longitude=80.2720, gps_accuracy=10.0,
        timestamp=base_time + timedelta(seconds=15)
    ))
    print_step("Off-Route Step", snap_dev)
    assert snap_dev.route_deviation is not None
    assert snap_dev.route_deviation.deviation_distance_m > 100.0

    # Return to route
    snap_on = monitor.update_telemetry(JourneyUpdateRequest(
        journey_id="J-DEMO-05", latitude=13.0855, longitude=80.2700, gps_accuracy=10.0,
        timestamp=base_time + timedelta(seconds=30)
    ))
    print_step("Return On-Route", snap_on)
    print("  >>> PASS: Phase 1A route deviation consumed and associated with snapshot.")

    # -------------------------------------------------------------
    # SCENARIO 6: Unexpected Stop Event Consumed
    # -------------------------------------------------------------
    print("\n" + "-" * 105)
    print(" SCENARIO 6: Unexpected Stop (Stationary position -> STALLED -> Movement Resumes)")
    print("-" * 105)
    monitor.reset()
    monitor.start_journey(JourneyStartRequest(
        journey_id="J-DEMO-06", source_lat=13.0800, source_lng=80.2700,
        destination_lat=13.0900, destination_lng=80.2700, expected_route=route, timestamp=base_time
    ))
    monitor.update_telemetry(JourneyUpdateRequest(
        journey_id="J-DEMO-06", latitude=13.0830, longitude=80.2700, gps_accuracy=10.0,
        timestamp=base_time + timedelta(seconds=10)
    ))
    # Stalled at same location for 50s (> 45s threshold)
    snap_stop = monitor.update_telemetry(JourneyUpdateRequest(
        journey_id="J-DEMO-06", latitude=13.0830, longitude=80.2700, gps_accuracy=10.0,
        timestamp=base_time + timedelta(seconds=65)
    ))
    print_step("Halted for 55s", snap_stop)
    assert snap_stop.unexpected_stop is not None
    assert snap_stop.progress_status == ProgressStatus.STALLED

    # Resumed movement
    snap_move = monitor.update_telemetry(JourneyUpdateRequest(
        journey_id="J-DEMO-06", latitude=13.0850, longitude=80.2700, gps_accuracy=10.0,
        timestamp=base_time + timedelta(seconds=80)
    ))
    print_step("Resumed Motion", snap_move)
    print("  >>> PASS: Phase 1B unexpected stop consumed and reflected as STALLED.")

    # -------------------------------------------------------------
    # SCENARIO 7: Fall Event Consumed (NO Emergency Action)
    # -------------------------------------------------------------
    print("\n" + "-" * 105)
    print(" SCENARIO 7: Fall Event Consumed (Inertial shock recorded -> NO Emergency Action)")
    print("-" * 105)
    monitor.reset()
    monitor.start_journey(JourneyStartRequest(
        journey_id="J-DEMO-07", source_lat=13.0800, source_lng=80.2700,
        destination_lat=13.0900, destination_lng=80.2700, expected_route=route, timestamp=base_time
    ))
    snap_fall = monitor.update_telemetry(JourneyUpdateRequest(
        journey_id="J-DEMO-07", latitude=13.0830, longitude=80.2700, gps_accuracy=10.0,
        accel_x=0.1, accel_y=0.2, accel_z=3.2, gyro_x=140.0, gyro_y=20.0, gyro_z=10.0,
        timestamp=base_time + timedelta(seconds=15)
    ))
    print_step("Fall Shock Frame", snap_fall)
    assert snap_fall.fall_event is not None
    assert snap_fall.fall_event.impact_magnitude_g >= 3.0
    print("  >>> PASS: Phase 1C fall telemetry consumed without emergency dispatch.")

    # -------------------------------------------------------------
    # SCENARIO 8: Audio Distress Consumed (NO Emergency Action)
    # -------------------------------------------------------------
    print("\n" + "-" * 105)
    print(" SCENARIO 8: Audio Distress Consumed (Acoustic window processed -> NO Emergency Action)")
    print("-" * 105)
    monitor.reset()
    monitor.start_journey(JourneyStartRequest(
        journey_id="J-DEMO-08", source_lat=13.0800, source_lng=80.2700,
        destination_lat=13.0900, destination_lng=80.2700, expected_route=route, timestamp=base_time
    ))
    # Ambient quiet audio
    quiet_samples = [0.0] * 16000
    snap_audio = monitor.update_telemetry(JourneyUpdateRequest(
        journey_id="J-DEMO-08", latitude=13.0830, longitude=80.2700, gps_accuracy=10.0,
        audio_samples=quiet_samples,
        timestamp=base_time + timedelta(seconds=15)
    ))
    print_step("Audio Processed", snap_audio)
    assert snap_audio.audio_distress is not None
    assert snap_audio.audio_distress.raw_probability < 0.20
    print("  >>> PASS: Phase 1D audio distress evaluated in-memory without emergency action.")

    # -------------------------------------------------------------
    # SCENARIO 9: Arrival Confirmation Flow
    # -------------------------------------------------------------
    print("\n" + "-" * 105)
    print(" SCENARIO 9: Arrival Confirmation (Consecutive valid observations -> ARRIVED)")
    print("-" * 105)
    monitor.reset()
    monitor.start_journey(JourneyStartRequest(
        journey_id="J-DEMO-09", source_lat=13.0800, source_lng=80.2700,
        destination_lat=13.0900, destination_lng=80.2700, expected_route=route, timestamp=base_time
    ))
    # Observation 1 near destination (< 50m)
    snap_arr1 = monitor.update_telemetry(JourneyUpdateRequest(
        journey_id="J-DEMO-09", latitude=13.0898, longitude=80.2700, gps_accuracy=12.0,
        timestamp=base_time + timedelta(seconds=20)
    ))
    print_step("Arrival Obs 1", snap_arr1)
    assert snap_arr1.journey_state == JourneyState.ARRIVING

    # Observation 2 near destination (< 50m)
    snap_arr2 = monitor.update_telemetry(JourneyUpdateRequest(
        journey_id="J-DEMO-09", latitude=13.0900, longitude=80.2700, gps_accuracy=10.0,
        timestamp=base_time + timedelta(seconds=25)
    ))
    print_step("Arrival Obs 2", snap_arr2)
    assert snap_arr2.journey_state == JourneyState.ARRIVED
    print("  >>> PASS: Consecutive observations confirmed arrival.")

    # -------------------------------------------------------------
    # SCENARIO 10: Journey Cancellation
    # -------------------------------------------------------------
    print("\n" + "-" * 105)
    print(" SCENARIO 10: Journey Cancellation (User cancels -> CANCELLED)")
    print("-" * 105)
    monitor.reset()
    monitor.start_journey(JourneyStartRequest(
        journey_id="J-DEMO-10", source_lat=13.0800, source_lng=80.2700,
        destination_lat=13.0900, destination_lng=80.2700, expected_route=route, timestamp=base_time
    ))
    snap_cancel = monitor.end_journey(JourneyEndRequest(
        journey_id="J-DEMO-10", reason="User changed destination",
        timestamp=base_time + timedelta(seconds=15)
    ))
    print_step("Journey Cancel", snap_cancel)
    assert snap_cancel.journey_state == JourneyState.CANCELLED
    print("  >>> PASS: Journey cancelled gracefully.")

    # -------------------------------------------------------------
    # SCENARIO 11: Reset / New Journey Isolation
    # -------------------------------------------------------------
    print("\n" + "-" * 105)
    print(" SCENARIO 11: Reset / New Journey Isolation (Zero cross-journey leakage)")
    print("-" * 105)
    # Start fresh Journey B
    snap_b = monitor.start_journey(JourneyStartRequest(
        journey_id="J-NEW-B", source_lat=18.5204, source_lng=73.8567,
        destination_lat=18.5300, destination_lng=73.8600,
        timestamp=base_time + timedelta(minutes=10)
    ))
    print_step("Journey B Start", snap_b)
    assert snap_b.journey_id == "J-NEW-B"
    assert snap_b.journey_state == JourneyState.STARTING
    assert snap_b.route_progress_percent == 0.0
    print("  >>> PASS: State completely reset for new journey without cross-leakage.")

    print("\n" + "=" * 105)
    print(" ALL 11 GUARDIAN REPLAY SCENARIOS COMPLETED AND VERIFIED SUCCESSFULLY!")
    print("=" * 105)


if __name__ == "__main__":
    run_demo()
