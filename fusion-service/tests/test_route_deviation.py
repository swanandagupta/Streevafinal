"""
Comprehensive Unit Tests for Route Deviation Detection Engine (Phase 1A).

Covers:
- Straight route geometry (point exactly on, near, far from route)
- Multi-segment route and segment index resolution
- Perpendicular projection math vs endpoint snapping
- GPS noise tolerance within corridor
- Repeated observations and consecutive counter triggering DEVIATED
- Recovery and hysteresis (separate deviation vs recovery thresholds)
- Degraded GPS accuracy filtering
- Edge cases: empty route, single-point route, degenerate zero-length segment, invalid coordinates
- State machine reset
- API endpoints integration
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.edge.route_deviation import (
    RouteDeviationDetector,
    RouteDeviationConfig,
    DeviationState,
    haversine_distance_m,
    compute_cross_track_distance_m,
    _extract_lat_lng,
)

client = TestClient(app)


# --- 1. Geometric Math & Coordinate Extraction Tests ---

def test_extract_lat_lng_dict_and_object():
    """Coordinates can be extracted from dicts with lat/lng or latitude/longitude, or objects."""
    d1 = {"lat": 13.0827, "lng": 80.2707}
    lat, lng = _extract_lat_lng(d1)
    assert lat == 13.0827 and lng == 80.2707

    d2 = {"latitude": 12.98, "longitude": 80.22}
    lat2, lng2 = _extract_lat_lng(d2)
    assert lat2 == 12.98 and lng2 == 80.22

    class PointObj:
        def __init__(self, lat, lng):
            self.lat = lat
            self.lng = lng

    obj = PointObj(13.0, 80.2)
    lat3, lng3 = _extract_lat_lng(obj)
    assert lat3 == 13.0 and lng3 == 80.2


def test_extract_lat_lng_invalid_bounds():
    """Coordinates outside valid WGS-84 ranges raise ValueError."""
    with pytest.raises(ValueError, match="Invalid coordinate bounds"):
        _extract_lat_lng({"lat": 95.0, "lng": 80.0})

    with pytest.raises(ValueError, match="Invalid coordinate bounds"):
        _extract_lat_lng({"lat": 13.0, "lng": 185.0})


def test_haversine_known_distances():
    """Haversine formula produces accurate Earth distances."""
    # 0 distance between identical points
    assert haversine_distance_m(13.0827, 80.2707, 13.0827, 80.2707) == 0.0

    # 1 degree of latitude is approx 111.19 km
    d_lat = haversine_distance_m(13.0, 80.0, 14.0, 80.0)
    assert 110_000 < d_lat < 112_000


def test_point_exactly_on_straight_route():
    """Point directly on a straight line segment yields near-zero cross-track distance."""
    # Straight horizontal segment along lat 13.0827
    route = [
        {"lat": 13.0827, "lng": 80.2700},
        {"lat": 13.0827, "lng": 80.2800}
    ]
    # Midpoint of segment
    dist, idx = compute_cross_track_distance_m(13.0827, 80.2750, route)
    assert dist < 0.1
    assert idx == 0


def test_point_near_and_far_from_straight_route():
    """Calculates perpendicular distance off a straight segment accurately."""
    # Route along longitude 80.2700 from lat 13.0800 to 13.0900
    route = [
        {"lat": 13.0800, "lng": 80.2700},
        {"lat": 13.0900, "lng": 80.2700}
    ]

    # Point 10 meters east (at lat ~13.0850, 1 deg lng ~ 108.5 km, so 0.0001 deg ~ 10.85m)
    # Approx 0.0001 deg offset
    offset_lng = 80.2700 + (10.0 / (6_371_000.0 * 3.14159265 / 180.0 * 0.974))
    dist_near, idx_near = compute_cross_track_distance_m(13.0850, offset_lng, route)
    assert 9.0 < dist_near < 11.0
    assert idx_near == 0

    # Point ~100m east
    dist_far, idx_far = compute_cross_track_distance_m(13.0850, 80.2710, route)
    assert dist_far > 80.0
    assert idx_far == 0


def test_multi_segment_route_nearest_index():
    """Finds closest segment among multiple connected segments."""
    route = [
        {"lat": 13.0800, "lng": 80.2700},  # S0 start
        {"lat": 13.0850, "lng": 80.2700},  # S0 end / S1 start
        {"lat": 13.0850, "lng": 80.2800},  # S1 end / S2 start
        {"lat": 13.0900, "lng": 80.2800},  # S2 end
    ]

    # Point near S0
    _, idx0 = compute_cross_track_distance_m(13.0820, 80.2701, route)
    assert idx0 == 0

    # Point near S1
    _, idx1 = compute_cross_track_distance_m(13.0851, 80.2750, route)
    assert idx1 == 1

    # Point near S2
    _, idx2 = compute_cross_track_distance_m(13.0880, 80.2799, route)
    assert idx2 == 2


def test_empty_and_single_point_route():
    """Handles boundary cases: empty route and single-point route gracefully."""
    # Empty route
    dist_empty, idx_empty = compute_cross_track_distance_m(13.08, 80.27, [])
    assert dist_empty == 0.0
    assert idx_empty is None

    # Single-point route
    dist_single, idx_single = compute_cross_track_distance_m(13.08, 80.27, [{"lat": 13.081, "lng": 80.27}])
    assert dist_single > 100.0  # ~111m
    assert idx_single == 0


def test_degenerate_zero_length_segment():
    """Route with identical consecutive vertices does not cause division by zero."""
    route = [
        {"lat": 13.0800, "lng": 80.2700},
        {"lat": 13.0800, "lng": 80.2700},  # Identical
        {"lat": 13.0900, "lng": 80.2700}
    ]
    dist, idx = compute_cross_track_distance_m(13.0820, 80.2700, route)
    assert dist < 1.0


# --- 2. State Machine, Safeguards, & Noise Protection Tests ---

@pytest.fixture
def detector():
    config = RouteDeviationConfig(
        deviation_threshold_m=50.0,
        normal_threshold_m=35.0,
        consecutive_deviations_required=3,
        consecutive_recoveries_required=2,
        max_acceptable_gps_accuracy_m=60.0
    )
    return RouteDeviationDetector(config=config)


@pytest.fixture
def north_south_route():
    # Vertical line along lng 80.2700 from lat 13.0800 to 13.0900
    return [
        {"lat": 13.0800, "lng": 80.2700},
        {"lat": 13.0900, "lng": 80.2700}
    ]


def test_normal_route_remains_normal(detector, north_south_route):
    """Traveling directly along the route produces NORMAL state."""
    positions = [
        {"lat": 13.0810, "lng": 80.2700},
        {"lat": 13.0820, "lng": 80.2700},
        {"lat": 13.0830, "lng": 80.2700}
    ]
    for pos in positions:
        event = detector.detect(pos, north_south_route, gps_accuracy=5.0)
        assert event.state == DeviationState.NORMAL
        assert not event.is_deviated
        assert event.deviation_distance_m < 1.0
        assert event.confidence > 0.8


def test_gps_noise_within_corridor_does_not_trigger_deviation(detector, north_south_route):
    """Small GPS jitter (~10-25m) stays well within 50m corridor and remains NORMAL."""
    # Jittering +- 20m from route
    # ~0.00015 deg longitude offset is approx 16 meters
    jittered_positions = [
        {"lat": 13.0810, "lng": 80.27015},
        {"lat": 13.0820, "lng": 80.26985},
        {"lat": 13.0830, "lng": 80.27020},
        {"lat": 13.0840, "lng": 80.26990}
    ]
    for pos in jittered_positions:
        event = detector.detect(pos, north_south_route, gps_accuracy=10.0)
        assert event.state == DeviationState.NORMAL
        assert not event.is_deviated
        assert event.deviation_distance_m < 30.0


def test_transitory_spike_is_filtered_out(detector, north_south_route):
    """A single off-route reading transitions to POSSIBLE_DEVIATION, not DEVIATED, and clears if back on route."""
    # Step 1: Normal point on route
    ev1 = detector.detect({"lat": 13.0810, "lng": 80.2700}, north_south_route, gps_accuracy=8.0)
    assert ev1.state == DeviationState.NORMAL

    # Step 2: Single multipath spike ~100m away (lat 13.0820, lng 80.2710)
    ev2 = detector.detect({"lat": 13.0820, "lng": 80.2710}, north_south_route, gps_accuracy=8.0)
    assert ev2.state == DeviationState.POSSIBLE_DEVIATION
    assert not ev2.is_deviated
    assert ev2.deviation_distance_m > 80.0

    # Step 3: Next point returns to route (lat 13.0830, lng 80.2700)
    ev3 = detector.detect({"lat": 13.0830, "lng": 80.2700}, north_south_route, gps_accuracy=8.0)
    assert ev3.state == DeviationState.NORMAL
    assert not ev3.is_deviated


def test_sustained_deviation_requires_consecutive_observations(detector, north_south_route):
    """Requires 3 consecutive readings beyond 50m to transition to DEVIATED."""
    # Point ~90m east: lng 80.2709
    off_route_pos = {"lat": 13.0820, "lng": 80.2709}

    # Reading 1: POSSIBLE_DEVIATION (count = 1)
    ev1 = detector.detect(off_route_pos, north_south_route, gps_accuracy=8.0)
    assert ev1.state == DeviationState.POSSIBLE_DEVIATION
    assert not ev1.is_deviated

    # Reading 2: POSSIBLE_DEVIATION (count = 2)
    ev2 = detector.detect(off_route_pos, north_south_route, gps_accuracy=8.0)
    assert ev2.state == DeviationState.POSSIBLE_DEVIATION
    assert not ev2.is_deviated

    # Reading 3: DEVIATED (count = 3 >= 3)
    ev3 = detector.detect(off_route_pos, north_south_route, gps_accuracy=8.0)
    assert ev3.state == DeviationState.DEVIATED
    assert ev3.is_deviated
    assert ev3.confidence > 0.7


def test_recovery_and_hysteresis(detector, north_south_route):
    """
    Validates hysteresis:
    - Distance must drop <= 35m (normal_threshold) to recover.
    - Requires 2 consecutive recoveries to return to NORMAL.
    - Distance in between 35m and 50m stays in current state without oscillating.
    """
    off_route_pos = {"lat": 13.0820, "lng": 80.2709}  # ~90m off route
    on_route_pos = {"lat": 13.0850, "lng": 80.2700}   # 0m off route

    # Drive detector into DEVIATED
    for _ in range(3):
        detector.detect(off_route_pos, north_south_route, gps_accuracy=5.0)
    assert detector.current_state == DeviationState.DEVIATED

    # Hysteresis test: position ~42m away (between 35m and 50m)
    # Longitude offset ~0.00039 deg -> ~42m
    mid_corridor_pos = {"lat": 13.0830, "lng": 80.27039}
    ev_mid = detector.detect(mid_corridor_pos, north_south_route, gps_accuracy=5.0)
    # Stays DEVIATED because 42m > 35m recovery threshold
    assert ev_mid.state == DeviationState.DEVIATED
    assert 35.0 < ev_mid.deviation_distance_m < 50.0

    # Recovery Step 1: on route (0m <= 35m) -> RECOVERED
    ev_rec1 = detector.detect(on_route_pos, north_south_route, gps_accuracy=5.0)
    assert ev_rec1.state == DeviationState.RECOVERED
    assert not ev_rec1.is_deviated

    # Recovery Step 2: on route again (2nd observation) -> NORMAL
    ev_rec2 = detector.detect(on_route_pos, north_south_route, gps_accuracy=5.0)
    assert ev_rec2.state == DeviationState.NORMAL
    assert not ev_rec2.is_deviated


def test_poor_gps_accuracy_blocks_deviation(detector, north_south_route):
    """Readings with GPS accuracy worse than 60m do not trigger DEVIATED."""
    off_route_pos = {"lat": 13.0820, "lng": 80.2715}  # ~150m off route

    # Send 3 observations with poor accuracy (e.g. 90m uncertainty)
    for _ in range(3):
        ev = detector.detect(off_route_pos, north_south_route, gps_accuracy=90.0)

    # State must NOT be DEVIATED because accuracy was degraded
    assert ev.state != DeviationState.DEVIATED
    assert "exceeds acceptable threshold" in ev.details
    assert ev.confidence < 0.5


def test_detector_reset(detector, north_south_route):
    """Reset clears counters and restores state to NORMAL."""
    off_route_pos = {"lat": 13.0820, "lng": 80.2709}
    for _ in range(3):
        detector.detect(off_route_pos, north_south_route, gps_accuracy=5.0)
    assert detector.current_state == DeviationState.DEVIATED

    detector.reset()
    assert detector.current_state == DeviationState.NORMAL
    assert detector.consecutive_deviations == 0
    assert detector.consecutive_recoveries == 0


# --- 3. API Endpoint Integration Tests ---

def test_api_route_deviation_evaluate_endpoint():
    """POST /route-deviation/evaluate returns valid RouteDeviationEvent."""
    payload = {
        "current_position": {"lat": 13.0820, "lng": 80.2700},
        "route_polyline": [
            {"lat": 13.0800, "lng": 80.2700},
            {"lat": 13.0900, "lng": 80.2700}
        ],
        "gps_accuracy": 6.5
    }

    response = client.post("/route-deviation/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["event_type"] == "ROUTE_DEVIATION"
    assert data["state"] == "NORMAL"
    assert not data["is_deviated"]
    assert data["deviation_distance_m"] < 1.0
    assert data["gps_accuracy_m"] == 6.5
    assert data["nearest_segment_index"] == 0


def test_api_route_deviation_reset_endpoint():
    """POST /route-deviation/reset restores detector state to NORMAL."""
    response = client.post("/route-deviation/reset")
    assert response.status_code == 200
    assert response.json()["status"] == "reset"
    assert response.json()["state"] == "NORMAL"
