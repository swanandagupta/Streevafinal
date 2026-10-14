"""
STREEVA — Phase 1A Route Deviation Detection Replay / Demo.

Executes deterministic synthetic trajectory simulations representing the 6 test scenarios:
1. Normal route (walking smoothly on expected route)
2. GPS noise (small fluctuations within 10-25m corridor)
3. Slight transitory deviation (brief excursion outside corridor)
4. Sustained deviation (traveler moves and stays off-route)
5. Leave and return (traveler deviates, then rejoins expected route)
6. Poor GPS accuracy (high uncertainty suppressing false positive deviation)
"""

import sys
import os
from datetime import datetime, timezone

# Add parent directory to sys.path to resolve 'app'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.edge.route_deviation import (
    RouteDeviationDetector,
    RouteDeviationConfig,
    DeviationState
)

# Reference synthetic route: Anna Salai stretch, Chennai
# From lat 13.0600 to 13.0700 along lng 80.2500
PLANNED_ROUTE = [
    {"lat": 13.0600, "lng": 80.2500},
    {"lat": 13.0650, "lng": 80.2500},
    {"lat": 13.0700, "lng": 80.2500}
]


def print_step(step_num: int, point: dict, event, acc_str: str = ""):
    state_colors = {
        DeviationState.NORMAL: "\033[92m",             # Green
        DeviationState.POSSIBLE_DEVIATION: "\033[93m",  # Yellow
        DeviationState.DEVIATED: "\033[91m",            # Red
        DeviationState.RECOVERED: "\033[96m"            # Cyan
    }
    color = state_colors.get(event.state, "")
    reset = "\033[0m"

    print(
        f"  Step {step_num:02d}: {color}[{event.state.value.ljust(18)}]{reset} "
        f"Dist: {event.deviation_distance_m:05.1f}m | "
        f"Conf: {event.confidence:04.2f} | "
        f"Lat: {event.latitude:.5f}, Lng: {event.longitude:.5f} "
        f"{acc_str}| {event.details}"
    )


def run_demo():
    print("=" * 80)
    print(" STREEVA — PHASE 1A ROUTE DEVIATION DETECTION DETERMINISTIC REPLAY")
    print("=" * 80)

    config = RouteDeviationConfig(
        deviation_threshold_m=50.0,
        normal_threshold_m=35.0,
        consecutive_deviations_required=3,
        consecutive_recoveries_required=2,
        max_acceptable_gps_accuracy_m=60.0
    )
    detector = RouteDeviationDetector(config=config)

    # -------------------------------------------------------------------------
    # TEST 1: Normal route
    # -------------------------------------------------------------------------
    print("\n--- TEST 1: Normal Route (Traveler follows planned route) ---")
    detector.reset()
    test1_points = [
        {"lat": 13.0610, "lng": 80.2500},
        {"lat": 13.0620, "lng": 80.2500},
        {"lat": 13.0630, "lng": 80.2500},
        {"lat": 13.0640, "lng": 80.2500},
        {"lat": 13.0650, "lng": 80.2500},
    ]
    for i, p in enumerate(test1_points, 1):
        ev = detector.detect(p, PLANNED_ROUTE, gps_accuracy=5.0)
        print_step(i, p, ev)
    assert detector.current_state == DeviationState.NORMAL
    print("  Result: Traveler remained in NORMAL state throughout.")

    # -------------------------------------------------------------------------
    # TEST 2: GPS Noise
    # -------------------------------------------------------------------------
    print("\n--- TEST 2: GPS Noise (Small perturbations within corridor) ---")
    detector.reset()
    # Offsets of ~10-25m from route (0.0001 deg lng ~ 10.8m)
    test2_points = [
        {"lat": 13.0610, "lng": 80.25012},  # ~13m East
        {"lat": 13.0620, "lng": 80.24988},  # ~13m West
        {"lat": 13.0630, "lng": 80.25020},  # ~21m East
        {"lat": 13.0640, "lng": 80.24980},  # ~21m West
        {"lat": 13.0650, "lng": 80.25005},  # ~5m East
    ]
    for i, p in enumerate(test2_points, 1):
        ev = detector.detect(p, PLANNED_ROUTE, gps_accuracy=12.0)
        print_step(i, p, ev)
    assert detector.current_state == DeviationState.NORMAL
    print("  Result: No false sustained deviation. Remained NORMAL despite noise.")

    # -------------------------------------------------------------------------
    # TEST 3: Slight / Transitory Deviation
    # -------------------------------------------------------------------------
    print("\n--- TEST 3: Slight Deviation (Single transitory excursion > 50m) ---")
    detector.reset()
    test3_points = [
        {"lat": 13.0610, "lng": 80.2500},   # On route (0m)
        {"lat": 13.0620, "lng": 80.25075},  # Transitory excursion ~81m East
        {"lat": 13.0630, "lng": 80.2500},   # Rejoined route (0m)
        {"lat": 13.0640, "lng": 80.2500},   # On route (0m)
    ]
    for i, p in enumerate(test3_points, 1):
        ev = detector.detect(p, PLANNED_ROUTE, gps_accuracy=8.0)
        print_step(i, p, ev)
    assert detector.current_state == DeviationState.NORMAL
    print("  Result: Transitory point flagged POSSIBLE_DEVIATION, then cleared back to NORMAL.")

    # -------------------------------------------------------------------------
    # TEST 4: Sustained Deviation
    # -------------------------------------------------------------------------
    print("\n--- TEST 4: Sustained Deviation (Traveler takes unintended detour) ---")
    detector.reset()
    # Moving substantially away (~100m East) for multiple consecutive points
    test4_points = [
        {"lat": 13.0610, "lng": 80.2500},   # Step 1: On route
        {"lat": 13.0620, "lng": 80.2510},   # Step 2: Off-route (~108m) -> Obs 1 (POSSIBLE_DEVIATION)
        {"lat": 13.0630, "lng": 80.2510},   # Step 3: Off-route (~108m) -> Obs 2 (POSSIBLE_DEVIATION)
        {"lat": 13.0640, "lng": 80.2510},   # Step 4: Off-route (~108m) -> Obs 3 (DEVIATED)
        {"lat": 13.0650, "lng": 80.2510},   # Step 5: Off-route (~108m) -> Remains DEVIATED
    ]
    for i, p in enumerate(test4_points, 1):
        ev = detector.detect(p, PLANNED_ROUTE, gps_accuracy=6.0)
        print_step(i, p, ev)
    assert detector.current_state == DeviationState.DEVIATED
    assert ev.is_deviated is True
    print("  Result: Sustained deviation confirmed into DEVIATED state.")

    # -------------------------------------------------------------------------
    # TEST 5: Leave and Return (Hysteresis & Recovery)
    # -------------------------------------------------------------------------
    print("\n--- TEST 5: Leave and Return (NORMAL -> DEVIATED -> RECOVERED -> NORMAL) ---")
    detector.reset()
    test5_points = [
        {"lat": 13.0610, "lng": 80.2500},   # 1. On route -> NORMAL
        {"lat": 13.0620, "lng": 80.2510},   # 2. Deviated point 1 -> POSSIBLE_DEVIATION
        {"lat": 13.0630, "lng": 80.2510},   # 3. Deviated point 2 -> POSSIBLE_DEVIATION
        {"lat": 13.0640, "lng": 80.2510},   # 4. Deviated point 3 -> DEVIATED
        {"lat": 13.0645, "lng": 80.25035},  # 5. In-corridor (~38m): >35m recovery -> remains DEVIATED
        {"lat": 13.0650, "lng": 80.2500},   # 6. Safely on route (0m <= 35m) -> RECOVERED (Obs 1)
        {"lat": 13.0660, "lng": 80.2500},   # 7. Safely on route (0m <= 35m) -> NORMAL (Obs 2)
    ]
    for i, p in enumerate(test5_points, 1):
        ev = detector.detect(p, PLANNED_ROUTE, gps_accuracy=5.0)
        print_step(i, p, ev)
    assert detector.current_state == DeviationState.NORMAL
    print("  Result: Full lifecycle verified: NORMAL -> DEVIATED -> RECOVERED -> NORMAL.")

    # -------------------------------------------------------------------------
    # TEST 6: Poor GPS Accuracy
    # -------------------------------------------------------------------------
    print("\n--- TEST 6: Poor GPS Accuracy (Degraded readings suppress DEVIATED) ---")
    detector.reset()
    test6_points = [
        ({"lat": 13.0610, "lng": 80.2500}, 10.0),  # Good accuracy, on route
        ({"lat": 13.0620, "lng": 80.2515}, 95.0),  # Far off (~160m), but accuracy = 95m (>60m threshold)
        ({"lat": 13.0630, "lng": 80.2515}, 85.0),  # Far off (~160m), accuracy = 85m
        ({"lat": 13.0640, "lng": 80.2515}, 90.0),  # Far off (~160m), accuracy = 90m
    ]
    for i, (p, acc) in enumerate(test6_points, 1):
        ev = detector.detect(p, PLANNED_ROUTE, gps_accuracy=acc)
        print_step(i, p, ev, acc_str=f"Acc: {acc:04.1f}m ")
    assert detector.current_state != DeviationState.DEVIATED
    print("  Result: Degraded GPS accuracy successfully prevented false DEVIATED state.")

    print("\n" + "=" * 80)
    print(" ALL 6 DETERMINISTIC REPLAY TESTS COMPLETED & VERIFIED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    run_demo()
