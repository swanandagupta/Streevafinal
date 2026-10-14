"""
STREEVA — Phase 4 Autonomous Emergency Response System
app/emergency/notification_provider.py

Provider-independent Notification Provider abstraction:
- Constructs normalized emergency payloads.
- Dispatches notifications across abstracted channels (SMS, Push, Phone).
- Provides deterministic mock adapter recording calls, partial delivery, and failure states.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Dict, Set, Optional, Any
from .schemas import (
    EmergencyIncident,
    EmergencyContact,
    NotificationPayload,
    NotificationDeliveryResult,
    LocationQuality
)


class INotificationProvider(ABC):
    """Abstract interface for emergency notification delivery."""

    @abstractmethod
    def send_emergency_notification(
        self,
        incident: EmergencyIncident,
        contact: EmergencyContact,
        payload: NotificationPayload
    ) -> NotificationDeliveryResult:
        pass


class MockNotificationProvider(INotificationProvider):
    """
    Deterministic mock notification provider for testing and replays.
    Tracks all calls and supports simulated partial/total failure modes.
    """

    def __init__(self):
        self.dispatched_records: List[Dict[str, Any]] = []
        self.failing_contact_ids: Set[str] = set()
        self.simulate_network_failure: bool = False

    def send_emergency_notification(
        self,
        incident: EmergencyIncident,
        contact: EmergencyContact,
        payload: NotificationPayload
    ) -> NotificationDeliveryResult:
        now = datetime.now(timezone.utc)
        record = {
            "incident_id": incident.incident_id,
            "contact_id": contact.contact_id,
            "destination": contact.destination,
            "destination_type": contact.destination_type.value,
            "payload": payload.model_dump(mode="json"),
            "timestamp": now
        }
        self.dispatched_records.append(record)

        # 1. Total network failure simulation
        if self.simulate_network_failure:
            return NotificationDeliveryResult(
                contact_id=contact.contact_id,
                destination=contact.destination,
                success=False,
                delivered_at=None,
                error_message="Network offline: cellular/SMS gateway unreachable"
            )

        # 2. Targeted contact failure simulation
        if contact.contact_id in self.failing_contact_ids:
            return NotificationDeliveryResult(
                contact_id=contact.contact_id,
                destination=contact.destination,
                success=False,
                delivered_at=None,
                error_message=f"Delivery failed to destination {contact.destination}: recipient carrier rejected"
            )

        # 3. Successful delivery
        return NotificationDeliveryResult(
            contact_id=contact.contact_id,
            destination=contact.destination,
            success=True,
            delivered_at=now,
            error_message=None
        )

    def set_failing_contacts(self, contact_ids: Set[str]):
        """Configures specific contact IDs to fail delivery."""
        self.failing_contact_ids = set(contact_ids)

    def set_network_failure(self, failure: bool):
        """Simulates global network failure."""
        self.simulate_network_failure = failure

    def clear(self):
        self.dispatched_records.clear()
        self.failing_contact_ids.clear()
        self.simulate_network_failure = False
