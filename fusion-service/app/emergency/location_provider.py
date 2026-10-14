"""
STREEVA — Phase 4 Autonomous Emergency Response System
app/emergency/location_provider.py

Provider-independent Location Provider abstraction:
- Extracts trusted location from GuardianSnapshot or live fix.
- Explicitly classifies quality as VALID, STALE, or UNAVAILABLE.
- NEVER fabricates coordinates or substitutes (0, 0).
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import Optional
from .schemas import LocationResult, LocationQuality
from ..guardian.journey_state import GuardianSnapshot, TelemetryQuality


class ILocationProvider(ABC):
    """Abstract interface for emergency location acquisition."""

    @abstractmethod
    def get_current_location(
        self,
        snapshot: Optional[GuardianSnapshot] = None,
        manual_lat: Optional[float] = None,
        manual_lng: Optional[float] = None,
        manual_accuracy: Optional[float] = None,
        current_time: Optional[datetime] = None
    ) -> LocationResult:
        pass


class EmergencyLocationProvider(ILocationProvider):
    """
    Concrete location provider extracting trusted coordinates from telemetry.
    Strict invariant: Never invents or substitutes fake coordinates.
    """

    def __init__(self, stale_threshold_seconds: float = 45.0):
        self.stale_threshold_seconds = stale_threshold_seconds
        # Last known location cache: journey_id -> LocationResult
        self._last_known_locations: dict[str, LocationResult] = {}

    def get_current_location(
        self,
        snapshot: Optional[GuardianSnapshot] = None,
        manual_lat: Optional[float] = None,
        manual_lng: Optional[float] = None,
        manual_accuracy: Optional[float] = None,
        current_time: Optional[datetime] = None
    ) -> LocationResult:
        now = current_time or datetime.now(timezone.utc)

        # 1. Check explicit manual coordinates (e.g. from Manual SOS button payload)
        if manual_lat is not None and manual_lng is not None:
            res = LocationResult(
                latitude=manual_lat,
                longitude=manual_lng,
                accuracy=manual_accuracy or 10.0,
                timestamp=now,
                quality=LocationQuality.VALID,
                source="MANUAL_INPUT"
            )
            if snapshot and snapshot.journey_id:
                self._last_known_locations[snapshot.journey_id] = res
            return res

        # 2. Check GuardianSnapshot telemetry
        if snapshot is not None:
            journey_id = snapshot.journey_id
            lat = snapshot.current_lat
            lng = snapshot.current_lng
            acc = snapshot.gps_accuracy
            snap_time = snapshot.timestamp or now

            # If telemetry quality indicates missing or coordinates are absent
            if lat is None or lng is None or snapshot.telemetry_quality == TelemetryQuality.MISSING:
                # Check if we have a stale last known location
                if journey_id in self._last_known_locations:
                    cached = self._last_known_locations[journey_id]
                    return LocationResult(
                        latitude=cached.latitude,
                        longitude=cached.longitude,
                        accuracy=cached.accuracy,
                        timestamp=cached.timestamp,
                        quality=LocationQuality.STALE,
                        source="LAST_KNOWN_CACHE"
                    )
                return LocationResult(
                    latitude=None,
                    longitude=None,
                    accuracy=None,
                    timestamp=now,
                    quality=LocationQuality.UNAVAILABLE,
                    source="TELEMETRY_UNAVAILABLE"
                )

            # Determine freshness
            is_stale_quality = snapshot.telemetry_quality in [TelemetryQuality.STALE, TelemetryQuality.POOR_ACCURACY]
            is_stale_time = (now - snap_time).total_seconds() > self.stale_threshold_seconds

            quality = LocationQuality.STALE if (is_stale_quality or is_stale_time) else LocationQuality.VALID

            res = LocationResult(
                latitude=lat,
                longitude=lng,
                accuracy=acc,
                timestamp=snap_time,
                quality=quality,
                source="GUARDIAN_TELEMETRY"
            )
            self._last_known_locations[journey_id] = res
            return res

        # 3. No snapshot and no manual coordinates provided
        return LocationResult(
            latitude=None,
            longitude=None,
            accuracy=None,
            timestamp=now,
            quality=LocationQuality.UNAVAILABLE,
            source="TELEMETRY_UNAVAILABLE"
        )

    def clear(self):
        """Clears cached locations."""
        self._last_known_locations.clear()
