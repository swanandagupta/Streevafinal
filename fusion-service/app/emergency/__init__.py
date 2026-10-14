"""
STREEVA — Phase 4 Autonomous Emergency Response System
app/emergency/__init__.py
"""

from .schemas import (
    EmergencyState,
    TriggerType,
    LocationQuality,
    DestinationType,
    EscalationLevel,
    AcknowledgementStatus,
    EvidenceType,
    LocationResult,
    EmergencyContact,
    NotificationPayload,
    NotificationDeliveryResult,
    EvidenceItem,
    EvidencePackage,
    IncidentTransitionRecord,
    IncidentContextSnapshot,
    EmergencyIncident,
    ManualSOSTriggerRequest,
    AutonomousTriggerRequest,
    CancelEmergencyRequest,
    AcknowledgeEmergencyRequest,
    AdvanceEmergencyRequest
)
from .config import EmergencyResponseConfig
from .state_machine import EmergencyStateMachine, InvalidStateTransitionError
from .location_provider import ILocationProvider, EmergencyLocationProvider
from .contact_service import IEmergencyContactService, MockEmergencyContactService
from .notification_provider import INotificationProvider, MockNotificationProvider
from .evidence_service import EvidenceService
from .location_broadcaster import EmergencyLocationBroadcaster
from .persistence import EmergencyPersistenceManager, IncidentDB, IncidentHistoryDB
from .orchestrator import EmergencyResponseOrchestrator

__all__ = [
    "EmergencyState",
    "TriggerType",
    "LocationQuality",
    "DestinationType",
    "EscalationLevel",
    "AcknowledgementStatus",
    "EvidenceType",
    "LocationResult",
    "EmergencyContact",
    "NotificationPayload",
    "NotificationDeliveryResult",
    "EvidenceItem",
    "EvidencePackage",
    "IncidentTransitionRecord",
    "IncidentContextSnapshot",
    "EmergencyIncident",
    "ManualSOSTriggerRequest",
    "AutonomousTriggerRequest",
    "CancelEmergencyRequest",
    "AcknowledgeEmergencyRequest",
    "AdvanceEmergencyRequest",
    "EmergencyResponseConfig",
    "EmergencyStateMachine",
    "InvalidStateTransitionError",
    "ILocationProvider",
    "EmergencyLocationProvider",
    "IEmergencyContactService",
    "MockEmergencyContactService",
    "INotificationProvider",
    "MockNotificationProvider",
    "EvidenceService",
    "EmergencyLocationBroadcaster",
    "EmergencyPersistenceManager",
    "IncidentDB",
    "IncidentHistoryDB",
    "EmergencyResponseOrchestrator"
]
