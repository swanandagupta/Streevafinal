"""
STREEVA Route Adherence Regression Test Suite.

Audits and verifies:
1. Start -> Immediate End produces None (Not 99.4%, not 0.0%)
2. Insufficient GPS observations (< 3 fixes or < 50m distance) produces None
3. Genuine journey with 100% adherence produces 100.0%
4. Genuine journey with deviation calculates exact ratio (e.g. 70.0%)
5. Journey with GPS noise / poor accuracy (> 60m uncertainty) filters noise out
6. End-to-end API lifecycle via FastAPI TestClient
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.guardian.monitor import GuardianMonitor
from app.guardian.journey_state import (
    GuardianConfig,
    JourneyState,
    JourneyStartRequest,
    JourneyUpdateRequest,
    JourneyEndRequest
)

# Reference polyline in Chennai (~550m northwards)
CHENNAI_ROUTE = [
    {"lat": 13.0827, "lng": 80.2707},
    {"lat": 13.0837, "lng": 80.2707},
    {"lat": 13.0847, "lng": 80.2707},
    {"lat": 13.0857, "lng": 80.2707},
    {"lat": 13.0867, "lng": 80.2707},
    {"lat": 13.0877, "lng": 80.2707},
]


@pytest.fixture
def monitor():
    """Provides a fresh GuardianMonitor instance."""
    mon = GuardianMonitor(config=GuardianConfig(
        corridor_radius_m=50.0,
        gps_accuracy_ceiling_m=60.0
    ))
    mon.reset()
    return mon


@pytest.fixture
def client():
    """FastAPI TestClient for HTTP API verification."""
    return TestClient(app)


def test_start_immediate_end_produces_none(monitor):
    """
    REGRESSION: Starting a journey and immediately ending it with zero telemetry
    must yield None for adherence, 0.0 for distance travelled, and 0 valid observations.
    It MUST NOT invent 99.4% or 100.0%.
    """
    t0 = datetime(2026, 9, 16, 10, 0, 0, tzinfo=timezone.utc)
    start_req = JourneyStartRequest(
        journey_id="journey_immediate_end",
        source_lat=13.0827,
        source_lng=80.2707,
        destination_lat=13.0877,
        destination_lng=80.2707,
        expected_route=CHENNAI_ROUTE,
        timestamp=t0
    )
    start_snap = monitor.start_journey(start_req)
    assert start_snap.route_adherence_percent is None
    assert start_snap.distance_travelled_m == 0.0
    assert start_snap.valid_observations_count == 0

    # User ends journey 2 seconds later with no telemetry
    end_snap = monitor.end_journey(JourneyEndRequest(
        journey_id="journey_immediate_end",
        reason="User cancelled immediately",
        timestamp=t0 + timedelta(seconds=2)
    ))

    assert end_snap.route_adherence_percent is None, "Immediate end must not produce a fabricated percentage"
    assert end_snap.distance_travelled_m == 0.0
    assert end_snap.valid_observations_count == 0
    assert end_snap.actual_duration_s == 2.0


def test_insufficient_gps_observations_produces_none(monitor):
    """
    REGRESSION: Adherence requires at least 3 valid observations and >= 50m cumulative displacement.
    Fewer fixes or stationary jitter cannot establish route adherence.
    """
    t0 = datetime(2026, 9, 16, 10, 0, 0, tzinfo=timezone.utc)
    monitor.start_journey(JourneyStartRequest(
        journey_id="journey_few_obs",
        source_lat=13.0827,
        source_lng=80.2707,
        destination_lat=13.0877,
        destination_lng=80.2707,
        expected_route=CHENNAI_ROUTE,
        timestamp=t0
    ))

    # Single initial GPS fix
    snap1 = monitor.update_telemetry(JourneyUpdateRequest(
        journey_id="journey_few_obs",
        latitude=13.0827,
        longitude=80.2707,
        gps_accuracy=10.0,
        timestamp=t0 + timedelta(seconds=5)
    ))
    assert snap1.valid_observations_count == 1
    assert snap1.route_adherence_percent is None, "A single GPS fix cannot produce adherence"

    # Second fix 20m away (valid = 2 < 3)
    snap2 = monitor.update_telemetry(JourneyUpdateRequest(
        journey_id="journey_few_obs",
        latitude=13.08288,
        longitude=80.2707,
        gps_accuracy=10.0,
        timestamp=t0 + timedelta(seconds=10)
    ))
    assert snap2.valid_observations_count == 2
    assert snap2.route_adherence_percent is None, "Two observations cannot establish statistical adherence"

    # End journey
    end_snap = monitor.end_journey(JourneyEndRequest(
        journey_id="journey_few_obs",
        reason="Aborted early",
        timestamp=t0 + timedelta(seconds=12)
    ))
    assert end_snap.route_adherence_percent is None


def test_stationary_near_zero_distance_produces_none(monitor):
    """
    REGRESSION: Multiple fixes received while stationary (e.g. user sitting at start location)
    have displacement < 50m. They must NOT report 100% adherence.
    """
    t0 = datetime(2026, 9, 16, 10, 0, 0, tzinfo=timezone.utc)
    monitor.start_journey(JourneyStartRequest(
        journey_id="journey_stationary",
        source_lat=13.0827,
        source_lng=80.2707,
        destination_lat=13.0877,
        destination_lng=80.2707,
        expected_route=CHENNAI_ROUTE,
        timestamp=t0
    ))

    # 5 fixes at the exact same location
    for i in range(1, 6):
        snap = monitor.update_telemetry(JourneyUpdateRequest(
            journey_id="journey_stationary",
            latitude=13.0827,
            longitude=80.2707,
            gps_accuracy=8.0,
            timestamp=t0 + timedelta(seconds=i * 5)
        ))

    assert snap.valid_observations_count == 5
    assert snap.distance_travelled_m < 5.0
    assert snap.route_adherence_percent is None, "Zero-distance journeys must not produce misleading adherence"


def test_genuine_journey_with_100_percent_adherence(monitor):
    """
    REGRESSION: A real journey where traveler advances along the canonical polyline
    covering >50m with all observations inside the 50m corridor must yield 100.0%.
    """
    t0 = datetime(2026, 9, 16, 10, 0, 0, tzinfo=timezone.utc)
    monitor.start_journey(JourneyStartRequest(
        journey_id="journey_perfect",
        source_lat=13.0827,
        source_lng=80.2707,
        destination_lat=13.0877,
        destination_lng=80.2707,
        expected_route=CHENNAI_ROUTE,
        timestamp=t0
    ))

    # 6 points along the polyline (~111m apart)
    for idx, pt in enumerate(CHENNAI_ROUTE):
        snap = monitor.update_telemetry(JourneyUpdateRequest(
            journey_id="journey_perfect",
            latitude=pt["lat"],
            longitude=pt["lng"],
            gps_accuracy=10.0,
            timestamp=t0 + timedelta(seconds=(idx + 1) * 20)
        ))

    assert snap.valid_observations_count == 6
    assert snap.distance_travelled_m > 500.0
    assert snap.route_adherence_percent == 100.0

    end_snap = monitor.end_journey(JourneyEndRequest(
        journey_id="journey_perfect",
        reason="Arrived safely",
        timestamp=t0 + timedelta(seconds=140)
    ))
    assert end_snap.route_adherence_percent == 100.0
    assert end_snap.valid_observations_count == 6
    assert end_snap.distance_travelled_m > 500.0


def test_genuine_journey_with_deviation(monitor):
    """
    REGRESSION: A real journey with 10 valid movement observations:
    - 7 on-route points (cross-track ~ 0m)
    - 3 deviated points (cross-track ~ 150m > 50m corridor)
    Adherence must be exactly 70.0%.
    """
    t0 = datetime(2026, 9, 16, 10, 0, 0, tzinfo=timezone.utc)
    monitor.start_journey(JourneyStartRequest(
        journey_id="journey_deviated",
        source_lat=13.0827,
        source_lng=80.2707,
        destination_lat=13.0877,
        destination_lng=80.2707,
        expected_route=CHENNAI_ROUTE,
        timestamp=t0
    ))

    # 4 on-route points
    for i in range(4):
        monitor.update_telemetry(JourneyUpdateRequest(
            journey_id="journey_deviated",
            latitude=13.0827 + i * 0.0008,
            longitude=80.2707,
            gps_accuracy=10.0,
            timestamp=t0 + timedelta(seconds=(i + 1) * 15)
        ))

    # 3 deviated points (offset longitude by ~150m: 0.0014 deg lng ~ 152m)
    for i in range(3):
        monitor.update_telemetry(JourneyUpdateRequest(
            journey_id="journey_deviated",
            latitude=13.0850 + i * 0.0005,
            longitude=80.2707 + 0.0020,  # ~215m off corridor
            gps_accuracy=10.0,
            timestamp=t0 + timedelta(seconds=(5 + i) * 15)
        ))

    # 3 more on-route points
    for i in range(3):
        monitor.update_telemetry(JourneyUpdateRequest(
            journey_id="journey_deviated",
            latitude=13.0865 + i * 0.0004,
            longitude=80.2707,
            gps_accuracy=10.0,
            timestamp=t0 + timedelta(seconds=(8 + i) * 15)
        ))

    end_snap = monitor.end_journey(JourneyEndRequest(
        journey_id="journey_deviated",
        reason="Destination reached with detour",
        timestamp=t0 + timedelta(seconds=180)
    ))

    # Total valid observations = 10 (4 + 3 + 3)
    # Conforming observations = 7 (4 + 3)
    # Adherence = 7 / 10 * 100.0 = 70.0%
    assert end_snap.valid_observations_count == 10
    assert end_snap.route_adherence_percent == 70.0


def test_journey_with_gps_noise_and_poor_accuracy(monitor):
    """
    REGRESSION: Observations with poor GPS accuracy (> 60m uncertainty)
    must be excluded as degraded noise. They must NOT falsely lower adherence.
    """
    t0 = datetime(2026, 9, 16, 10, 0, 0, tzinfo=timezone.utc)
    monitor.start_journey(JourneyStartRequest(
        journey_id="journey_gps_noise",
        source_lat=13.0827,
        source_lng=80.2707,
        destination_lat=13.0877,
        destination_lng=80.2707,
        expected_route=CHENNAI_ROUTE,
        timestamp=t0
    ))

    # 4 valid points directly on-route with good accuracy (10m <= 60m)
    for i in range(4):
        monitor.update_telemetry(JourneyUpdateRequest(
            journey_id="journey_gps_noise",
            latitude=13.0827 + i * 0.0010,
            longitude=80.2707,
            gps_accuracy=10.0,
            timestamp=t0 + timedelta(seconds=(i + 1) * 20)
        ))

    # 3 degraded noisy points far off route with accuracy 95m (> 60m ceiling)
    for i in range(3):
        monitor.update_telemetry(JourneyUpdateRequest(
            journey_id="journey_gps_noise",
            latitude=13.0850,
            longitude=80.2750,  # 450m away
            gps_accuracy=95.0,  # Poor accuracy!
            timestamp=t0 + timedelta(seconds=(5 + i) * 20)
        ))

    end_snap = monitor.end_journey(JourneyEndRequest(
        journey_id="journey_gps_noise",
        reason="Finished",
        timestamp=t0 + timedelta(seconds=160)
    ))

    # Only the 4 valid points count. The 3 noisy readings are excluded.
    assert end_snap.valid_observations_count == 4
    # All 4 valid points were on route -> 100.0%
    assert end_snap.route_adherence_percent == 100.0


def test_api_immediate_end_returns_null_adherence(client):
    """
    REGRESSION via FastAPI HTTP endpoints:
    Verifies that POST /api/v1/guardian/journey/end returns route_adherence_percent as null
    when a journey is immediately ended without valid travel.
    """
    # Start journey
    resp_start = client.post("/guardian/journey/start", json={
        "journey_id": "api_test_immediate",
        "source_lat": 13.0827,
        "source_lng": 80.2707,
        "destination_lat": 13.0877,
        "destination_lng": 80.2707,
        "expected_route": CHENNAI_ROUTE
    })
    assert resp_start.status_code == 200
    data_start = resp_start.json()
    assert data_start["route_adherence_percent"] is None
    assert data_start["distance_travelled_m"] == 0.0

    # End immediately
    resp_end = client.post("/guardian/journey/end", json={
        "journey_id": "api_test_immediate",
        "reason": "Immediate end test"
    })
    assert resp_end.status_code == 200
    data_end = resp_end.json()
    assert data_end["route_adherence_percent"] is None
    assert data_end["distance_travelled_m"] == 0.0
    assert data_end["valid_observations_count"] == 0
