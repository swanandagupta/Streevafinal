"""
STREEVA — Phase 5 Offline Guardian & Connectivity Resilience
app/offline/journey_cache.py

Active Journey Cache:
- Persists and caches active journey context locally to ensure safety continuity when network is lost.
- Caches established route polyline, ETA, location quality, sensor policy, and latest Phase 3 assessment.
- Enforces zero-fabrication of coordinates or routes: missing remains unavailable, old becomes stale.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import logging

from .schemas import CachedJourneyContext

logger = logging.getLogger(__name__)


class ActiveJourneyCache:
    """
    Maintains the local in-memory and restorable cache of the active journey.
    Used by Offline Guardian to continue local safety monitoring without network access.
    """

    def __init__(self, stale_threshold_seconds: float = 45.0):
        self._stale_threshold_seconds: float = stale_threshold_seconds
        self._cached_context: Optional[CachedJourneyContext] = None

    @property
    def has_active_journey(self) -> bool:
        return self._cached_context is not None and self._cached_context.journey_state == "ACTIVE"

    def get_context(self) -> Optional[CachedJourneyContext]:
        if self._cached_context is None:
            return None
        # Check location freshness dynamically
        self._update_location_freshness()
        return self._cached_context.model_copy()

    def set_context(self, context: CachedJourneyContext) -> None:
        """Sets or restores the cached journey context."""
        self._cached_context = context.model_copy()
        self._update_location_freshness()

    def cache_journey_start(
        self,
        journey_id: str,
        source_lat: Optional[float] = None,
        source_lng: Optional[float] = None,
        dest_lat: Optional[float] = None,
        dest_lng: Optional[float] = None,
        expected_route: Optional[List[Dict[str, float]]] = None,
        active_sensor_policy: str = "MEDIUM",
        timestamp: Optional[datetime] = None
    ) -> CachedJourneyContext:
        """Caches the start of a journey."""
        now = timestamp or datetime.now(timezone.utc)
        self._cached_context = CachedJourneyContext(
            journey_id=journey_id,
            journey_state="ACTIVE",
            source_lat=source_lat,
            source_lng=source_lng,
            dest_lat=dest_lat,
            dest_lng=dest_lng,
            expected_route=expected_route or [],
            route_progress_percent=0.0,
            remaining_distance_m=0.0,
            eta=None,
            eta_source="UNAVAILABLE",
            last_trusted_lat=source_lat,
            last_trusted_lng=source_lng,
            location_accuracy=10.0 if source_lat is not None else None,
            telemetry_quality="VALID" if source_lat is not None else "UNAVAILABLE",
            last_snapshot_timestamp=now,
            active_sensor_policy=active_sensor_policy,
            latest_risk_score=None,
            latest_risk_level=None,
            latest_decision_tier=None,
            active_incident_id=None
        )
        logger.info(f"[ActiveJourneyCache] Cached journey start for {journey_id}")
        return self._cached_context.model_copy()

    def update_from_snapshot(
        self,
        route_progress_percent: Optional[float] = None,
        remaining_distance_m: Optional[float] = None,
        eta: Optional[datetime] = None,
        eta_source: Optional[str] = None,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        accuracy: Optional[float] = None,
        active_sensor_policy: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> Optional[CachedJourneyContext]:
        """Updates journey progress and location from a local snapshot."""
        if not self._cached_context:
            return None

        now = timestamp or datetime.now(timezone.utc)
        if route_progress_percent is not None:
            self._cached_context.route_progress_percent = route_progress_percent
        if remaining_distance_m is not None:
            self._cached_context.remaining_distance_m = remaining_distance_m
        if eta is not None:
            self._cached_context.eta = eta
        if eta_source is not None:
            self._cached_context.eta_source = eta_source

        if lat is not None and lng is not None:
            self._cached_context.last_trusted_lat = lat
            self._cached_context.last_trusted_lng = lng
            self._cached_context.location_accuracy = accuracy
            self._cached_context.telemetry_quality = "VALID"
            self._cached_context.last_snapshot_timestamp = now

        if active_sensor_policy is not None:
            self._cached_context.active_sensor_policy = active_sensor_policy

        self._update_location_freshness(current_time=now)
        return self._cached_context.model_copy()

    def update_assessment_and_decision(
        self,
        risk_score: float,
        risk_level: str,
        decision_tier: str,
        active_incident_id: Optional[str] = None
    ) -> Optional[CachedJourneyContext]:
        """Updates the latest Phase 3 assessment and decision."""
        if not self._cached_context:
            return None

        self._cached_context.latest_risk_score = risk_score
        self._cached_context.latest_risk_level = risk_level
        self._cached_context.latest_decision_tier = decision_tier
        if active_incident_id is not None:
            self._cached_context.active_incident_id = active_incident_id

        return self._cached_context.model_copy()

    def set_journey_state(self, state: str) -> Optional[CachedJourneyContext]:
        """Updates the journey lifecycle state (e.g. COMPLETED, CANCELLED)."""
        if not self._cached_context:
            return None
        self._cached_context.journey_state = state
        return self._cached_context.model_copy()

    def _update_location_freshness(self, current_time: Optional[datetime] = None) -> None:
        """
        Ensures location freshness status:
        If no location ever received -> UNAVAILABLE.
        If location received but older than stale_threshold -> STALE.
        Otherwise -> VALID.
        """
        if not self._cached_context:
            return

        if self._cached_context.last_trusted_lat is None or self._cached_context.last_trusted_lng is None:
            self._cached_context.telemetry_quality = "UNAVAILABLE"
            return

        if self._cached_context.last_snapshot_timestamp is None:
            self._cached_context.telemetry_quality = "STALE"
            return

        now = current_time or datetime.now(timezone.utc)
        ts = self._cached_context.last_snapshot_timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        age_seconds = (now - ts).total_seconds()
        if age_seconds > self._stale_threshold_seconds:
            self._cached_context.telemetry_quality = "STALE"
            # If ETA was estimated, mark it stale/unavailable as well
            if self._cached_context.eta_source == "ESTIMATED":
                self._cached_context.eta_source = "DEGRADED"

    def clear(self) -> None:
        """Clears the active journey cache."""
        self._cached_context = None
