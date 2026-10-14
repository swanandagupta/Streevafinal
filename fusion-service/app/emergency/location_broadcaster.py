"""
STREEVA — Phase 4 Autonomous Emergency Response System
app/emergency/location_broadcaster.py

Emergency Location Broadcaster abstraction:
- Publishes trusted emergency live location and journey updates.
- Maintains in-process broadcast record for tracking and downstream consumer adapters.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from .schemas import LocationResult, LocationQuality


class EmergencyLocationBroadcaster:
    """
    Publishes trusted real-time emergency coordinates and journey context.
    """

    def __init__(self):
        # incident_id -> List of broadcast updates
        self._broadcasts: Dict[str, List[Dict[str, Any]]] = {}

    def broadcast_emergency_location(
        self,
        incident_id: str,
        location: LocationResult,
        journey_id: Optional[str] = None,
        route_progress: Optional[float] = None
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        payload = {
            "incident_id": incident_id,
            "journey_id": journey_id,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "accuracy": location.accuracy,
            "location_quality": location.quality.value,
            "route_progress": route_progress,
            "timestamp": location.timestamp,
            "broadcast_at": now
        }

        if incident_id not in self._broadcasts:
            self._broadcasts[incident_id] = []
        self._broadcasts[incident_id].append(payload)

        return payload

    def get_latest_broadcast(self, incident_id: str) -> Optional[Dict[str, Any]]:
        records = self._broadcasts.get(incident_id, [])
        return records[-1] if records else None

    def get_all_broadcasts(self, incident_id: str) -> List[Dict[str, Any]]:
        return self._broadcasts.get(incident_id, [])

    def clear(self):
        self._broadcasts.clear()
