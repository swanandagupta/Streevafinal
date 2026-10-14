"""
STREEVA — Phase 4 Autonomous Emergency Response System
app/emergency/contact_service.py

Provider-independent Emergency Contact Service:
- Manages priority-ordered emergency contacts.
- Filters active/enabled contacts.
- Supports tiered escalation contact resolution.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from .schemas import EmergencyContact, DestinationType, EscalationLevel


class IEmergencyContactService(ABC):
    """Abstract interface for resolving emergency contacts."""

    @abstractmethod
    def get_contacts_for_journey(
        self,
        journey_id: str,
        escalation_level: EscalationLevel = EscalationLevel.LEVEL_1
    ) -> List[EmergencyContact]:
        pass


class MockEmergencyContactService(IEmergencyContactService):
    """
    In-memory, deterministic contact registry for testing and replay.
    """

    def __init__(self):
        # journey_id -> List[EmergencyContact]
        self._registry: Dict[str, List[EmergencyContact]] = {}
        # Default global contacts if none registered for a journey
        self._default_contacts: List[EmergencyContact] = [
            EmergencyContact(
                contact_id="c_primary_1",
                display_name="Primary Guardian",
                destination_type=DestinationType.SMS,
                destination="+1-555-0101",
                priority=1,
                enabled=True
            ),
            EmergencyContact(
                contact_id="c_primary_2",
                display_name="Emergency Contact 2",
                destination_type=DestinationType.SMS,
                destination="+1-555-0102",
                priority=1,
                enabled=True
            ),
            EmergencyContact(
                contact_id="c_secondary_1",
                display_name="Secondary Kin",
                destination_type=DestinationType.PHONE,
                destination="+1-555-0199",
                priority=2,
                enabled=True
            ),
            EmergencyContact(
                contact_id="c_disabled_1",
                display_name="Inactive Contact",
                destination_type=DestinationType.PUSH,
                destination="token_disabled",
                priority=1,
                enabled=False
            )
        ]

    def register_contacts(self, journey_id: str, contacts: List[EmergencyContact]):
        """Sets contacts for a specific journey."""
        self._registry[journey_id] = contacts

    def get_contacts_for_journey(
        self,
        journey_id: str,
        escalation_level: EscalationLevel = EscalationLevel.LEVEL_1
    ) -> List[EmergencyContact]:
        contacts = self._registry.get(journey_id, self._default_contacts)
        
        # Filter enabled only
        active = [c for c in contacts if c.enabled]

        # Filter by escalation tier
        if escalation_level == EscalationLevel.LEVEL_1:
            # Primary contacts (priority 1)
            selected = [c for c in active if c.priority == 1]
        elif escalation_level == EscalationLevel.LEVEL_2:
            # Secondary contacts (priority >= 2)
            selected = [c for c in active if c.priority >= 2]
        elif escalation_level == EscalationLevel.LEVEL_3:
            # Emergency service tier / all contacts fallback
            selected = [c for c in active if c.priority >= 1]
        else:
            selected = [c for c in active if c.priority == 1]

        # Sort strictly by priority
        return sorted(selected, key=lambda c: c.priority)

    def clear(self):
        self._registry.clear()
