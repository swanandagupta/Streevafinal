"""
STREEVA — Phase 5 Offline Guardian & Connectivity Resilience
app/offline/schemas.py

Pydantic schemas and enums for:
- Connectivity State Machine (ONLINE, DEGRADED, OFFLINE, RECONNECTING)
- Cached Active Journey Context
- Durable Local Event Buffer with Monotonic Sequencing
- SMS Fallback Abstraction
- Reconciliation & State Synchronization
"""

from __future__ import annotations
from enum import Enum
from typing import List, Dict, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field


class ConnectivityState(str, Enum):
    """
    Explicit network connectivity states.
    """
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    RECONNECTING = "RECONNECTING"


class SyncStatus(str, Enum):
    """
    Synchronization lifecycle status of a buffered event.
    """
    PENDING = "PENDING"
    SYNCING = "SYNCING"
    SYNCED = "SYNCED"
    FAILED = "FAILED"


class BufferedEventType(str, Enum):
    """
    Classifications of offline buffered events.
    """
    TELEMETRY = "TELEMETRY"
    GUARDIAN_SNAPSHOT = "GUARDIAN_SNAPSHOT"
    RISK_ASSESSMENT = "RISK_ASSESSMENT"
    DECISION = "DECISION"
    ROUTE_DEVIATION = "ROUTE_DEVIATION"
    UNEXPECTED_STOP = "UNEXPECTED_STOP"
    FALL = "FALL"
    AUDIO_DISTRESS = "AUDIO_DISTRESS"
    SENSOR_POLICY = "SENSOR_POLICY"
    EMERGENCY_INCIDENT = "EMERGENCY_INCIDENT"
    EMERGENCY_STATE_CHANGE = "EMERGENCY_STATE_CHANGE"
    NOTIFICATION_ATTEMPT = "NOTIFICATION_ATTEMPT"
    EVIDENCE_METADATA = "EVIDENCE_METADATA"


class SMSDeliveryStatus(str, Enum):
    """
    Status of offline SMS fallback dispatch.
    """
    SENT = "SENT"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class ConnectivityInfo(BaseModel):
    """
    Current connectivity manager status.
    """
    state: ConnectivityState
    changed_at: datetime
    last_online_at: Optional[datetime] = None
    last_successful_sync_at: Optional[datetime] = None
    network_available: bool = True
    reason: str = "Initial connection active"


class BufferedEvent(BaseModel):
    """
    A single durably buffered event with strictly monotonic sequencing.
    """
    event_id: str
    journey_id: str
    event_type: BufferedEventType
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    source_timestamp: datetime
    sequence_number: int = Field(description="Strictly monotonic sequence number for deterministic ordering")
    sync_status: SyncStatus = Field(default=SyncStatus.PENDING)
    retry_count: int = Field(default=0)
    last_attempt_at: Optional[datetime] = None


class CachedJourneyContext(BaseModel):
    """
    Cached local representation of the active journey to support offline continuity.
    """
    journey_id: str
    journey_state: str = "ACTIVE"
    source_lat: Optional[float] = None
    source_lng: Optional[float] = None
    dest_lat: Optional[float] = None
    dest_lng: Optional[float] = None
    expected_route: List[Dict[str, float]] = Field(default_factory=list)
    route_progress_percent: float = 0.0
    remaining_distance_m: float = 0.0
    eta: Optional[datetime] = None
    eta_source: str = "UNAVAILABLE"
    last_trusted_lat: Optional[float] = None
    last_trusted_lng: Optional[float] = None
    location_accuracy: Optional[float] = None
    telemetry_quality: str = "VALID"
    last_snapshot_timestamp: Optional[datetime] = None
    active_sensor_policy: Optional[str] = "MEDIUM"
    latest_risk_score: Optional[float] = None
    latest_risk_level: Optional[str] = None
    latest_decision_tier: Optional[str] = None
    active_incident_id: Optional[str] = None


class SMSDeliveryResult(BaseModel):
    """
    Result of an SMS fallback dispatch attempt.
    """
    recipient: str
    status: SMSDeliveryStatus
    delivered_at: Optional[datetime] = None
    message_id: Optional[str] = None
    error_message: Optional[str] = None


class ReconciliationSummary(BaseModel):
    """
    Audit result of a reconnection synchronization session.
    """
    reconciled_at: datetime
    total_events_processed: int
    events_synced: int
    events_failed: int
    journey_reconciled: bool
    incidents_reconciled: int
    final_connectivity: ConnectivityState
    details: str


# --- API Request Models ---

class UpdateConnectivityRequest(BaseModel):
    state: ConnectivityState
    reason: Optional[str] = "Network state updated"
    timestamp: Optional[datetime] = None


class ReconcileRequest(BaseModel):
    force_all: bool = False
    simulate_partial_failure: bool = False


class SMSTestRequest(BaseModel):
    incident_id: str
    recipient: str
    message: str
