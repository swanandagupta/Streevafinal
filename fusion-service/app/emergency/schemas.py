"""
STREEVA — Phase 4 Autonomous Emergency Response System
app/emergency/schemas.py

Pydantic schemas and enums for:
- Emergency State Machine
- Trigger Types (Manual SOS vs Autonomous Risk)
- Incident Context & Evidence Metadata
- Emergency Contact & Notification Abstractions
- Acknowledgement & Escalation Tracking
"""

from __future__ import annotations
from enum import Enum
from typing import List, Dict, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field


class EmergencyState(str, Enum):
    """
    Explicit, auditable lifecycle states of an emergency incident.
    """
    IDLE = "IDLE"
    TRIGGERED = "TRIGGERED"
    VERIFYING = "VERIFYING"
    COUNTDOWN = "COUNTDOWN"
    RESPONSE_AUTHORIZED = "RESPONSE_AUTHORIZED"
    DISPATCHING = "DISPATCHING"
    NOTIFIED = "NOTIFIED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"
    PARTIAL_FAILURE = "PARTIAL_FAILURE"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"


class TriggerType(str, Enum):
    """
    Explicit provenance of emergency trigger.
    """
    MANUAL_SOS = "MANUAL_SOS"
    AUTONOMOUS_RISK = "AUTONOMOUS_RISK"


class LocationQuality(str, Enum):
    """
    Quality classification of emergency location fix.
    """
    VALID = "VALID"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


class DestinationType(str, Enum):
    """
    Abstracted notification channel types.
    """
    PHONE = "PHONE"
    SMS = "SMS"
    PUSH = "PUSH"
    OTHER = "OTHER"


class EscalationLevel(str, Enum):
    """
    Hierarchical response escalation tiers.
    """
    LEVEL_0 = "LEVEL_0"  # Response initiated
    LEVEL_1 = "LEVEL_1"  # Primary emergency contacts
    LEVEL_2 = "LEVEL_2"  # Secondary emergency contacts / alternate paths
    LEVEL_3 = "LEVEL_3"  # External emergency-service boundary


class AcknowledgementStatus(str, Enum):
    """
    Incident acknowledgement status.
    """
    PENDING = "PENDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


class EvidenceType(str, Enum):
    """
    Evidence item classification.
    """
    TELEMETRY = "TELEMETRY"
    MOTION_EVENT = "MOTION_EVENT"
    FALL_EVENT = "FALL_EVENT"
    AUDIO_DISTRESS_EVENT = "AUDIO_DISTRESS_EVENT"
    ROUTE_DEVIATION_EVENT = "ROUTE_DEVIATION_EVENT"
    UNEXPECTED_STOP_EVENT = "UNEXPECTED_STOP_EVENT"
    JOURNEY_CONTEXT = "JOURNEY_CONTEXT"
    RISK_ASSESSMENT = "RISK_ASSESSMENT"
    RESPONSE_EVENT = "RESPONSE_EVENT"


# --- Location Abstraction ---

class LocationResult(BaseModel):
    """
    Structured location representation without fabricated coordinates.
    """
    latitude: Optional[float] = Field(default=None, description="GPS latitude, None if unavailable")
    longitude: Optional[float] = Field(default=None, description="GPS longitude, None if unavailable")
    accuracy: Optional[float] = Field(default=None, description="Horizontal accuracy in meters")
    timestamp: datetime = Field(description="Fix timestamp")
    quality: LocationQuality = Field(description="VALID, STALE, or UNAVAILABLE")
    source: str = Field(default="GPS", description="Telemetry origin identifier")


# --- Contact & Notification Abstractions ---

class EmergencyContact(BaseModel):
    """
    Provider-independent emergency contact record.
    """
    contact_id: str = Field(description="Unique contact ID")
    display_name: str = Field(description="Human-readable label/relation")
    destination_type: DestinationType = Field(default=DestinationType.SMS)
    destination: str = Field(description="Target phone number, push token, etc.")
    priority: int = Field(default=1, description="Priority ordering: 1 = primary, 2 = secondary")
    enabled: bool = Field(default=True, description="Whether this contact is currently active")


class NotificationPayload(BaseModel):
    """
    Normalized emergency notification payload.
    """
    incident_id: str
    emergency_status: EmergencyState
    trigger_type: TriggerType
    location: Optional[LocationResult] = None
    location_quality: LocationQuality
    journey_id: str
    risk_score: float
    risk_level: str
    dominant_risk_factor: Optional[str] = None
    timestamp: datetime
    message: str


class NotificationDeliveryResult(BaseModel):
    """
    Result of a notification delivery attempt to a single contact.
    """
    contact_id: str
    destination: str
    success: bool
    delivered_at: Optional[datetime] = None
    error_message: Optional[str] = None


# --- Evidence Package Abstraction ---

class EvidenceItem(BaseModel):
    """
    Single verifiable evidence item referencing real telemetry/event artifacts.
    """
    evidence_id: str
    incident_id: str
    type: EvidenceType
    timestamp: datetime
    source: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    payload_summary: str


class EvidencePackage(BaseModel):
    """
    Secure, sealed evidence package with audit hash.
    """
    package_id: str
    incident_id: str
    compiled_at: datetime
    items: List[EvidenceItem] = Field(default_factory=list)
    integrity_hash: str = Field(description="SHA-256 hash over serialized evidence items")


# --- Incident Context & Transition Audit ---

class IncidentTransitionRecord(BaseModel):
    """
    Auditable log of a state transition in the emergency state machine.
    """
    from_state: EmergencyState
    to_state: EmergencyState
    timestamp: datetime
    reason: str


class IncidentContextSnapshot(BaseModel):
    """
    Context snapshot at moment of trigger/authorization.
    """
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None
    location_accuracy: Optional[float] = None
    location_quality: LocationQuality = LocationQuality.UNAVAILABLE
    route_progress: Optional[float] = None
    remaining_distance: Optional[float] = None
    eta: Optional[datetime] = None
    journey_state: Optional[str] = None
    dominant_risk_factor: Optional[str] = None


class EmergencyIncident(BaseModel):
    """
    Comprehensive emergency incident tracking entity.
    """
    incident_id: str
    journey_id: str
    trigger_type: TriggerType
    risk_score: float = 0.0
    risk_level: str = "UNKNOWN"
    decision_tier: str = "MONITOR"
    state: EmergencyState = EmergencyState.IDLE
    created_at: datetime
    triggered_at: datetime
    countdown_started_at: Optional[datetime] = None
    countdown_seconds: float = 15.0
    countdown_remaining_seconds: Optional[float] = None
    response_authorized_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    context: IncidentContextSnapshot = Field(default_factory=IncidentContextSnapshot)

    contacts_targeted: List[str] = Field(default_factory=list)
    notifications_attempted: int = 0
    notifications_delivered: int = 0
    delivery_results: List[NotificationDeliveryResult] = Field(default_factory=list)
    acknowledgement_status: AcknowledgementStatus = AcknowledgementStatus.PENDING
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    escalation_level: EscalationLevel = EscalationLevel.LEVEL_0
    history: List[IncidentTransitionRecord] = Field(default_factory=list)
    evidence_package_id: Optional[str] = None


# --- API Request & Response Models ---

class ManualSOSTriggerRequest(BaseModel):
    """
    Manual emergency SOS initiation request.
    """
    journey_id: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accuracy: Optional[float] = None
    reason: Optional[str] = "User pressed manual SOS button"
    timestamp: Optional[datetime] = None


class AutonomousTriggerRequest(BaseModel):
    """
    Consumes a Phase 3 AUTONOMOUS_RESPONSE_REQUIRED decision.
    """
    journey_id: str
    decision_tier: str = Field(description="Must be AUTONOMOUS_RESPONSE_REQUIRED to trigger")
    risk_score: float
    risk_level: str
    dominant_factor: Optional[str] = None
    active_factors: List[str] = Field(default_factory=list)
    timestamp: Optional[datetime] = None


class CancelEmergencyRequest(BaseModel):
    """
    User cancellation request during COUNTDOWN or VERIFYING.
    """
    reason: Optional[str] = "User confirmed false alarm"


class AcknowledgeEmergencyRequest(BaseModel):
    """
    Emergency contact acknowledgement simulation.
    """
    contact_id: str
    acknowledged_by: Optional[str] = None
    notes: Optional[str] = "Contact acknowledged incident"


class AdvanceEmergencyRequest(BaseModel):
    """
    Advances countdown or simulates timeout deterministically for testing/replay.
    """
    elapsed_seconds: float = 15.0
