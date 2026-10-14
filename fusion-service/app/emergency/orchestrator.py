"""
STREEVA — Phase 4 Autonomous Emergency Response System
app/emergency/orchestrator.py

Autonomous Emergency Response Orchestrator:
- Consumes Phase 3 AUTONOMOUS_RESPONSE_REQUIRED decisions.
- Manages Manual SOS trigger flow.
- Enforces strict confirmation countdown and cancellation windows.
- Resolves location, contacts, and compiles verifiable evidence.
- Coordinates multi-channel notifications and acknowledgement tracking.
- Implements hierarchical escalation and deterministic idempotency.
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from .schemas import (
    EmergencyIncident,
    EmergencyState,
    TriggerType,
    LocationResult,
    LocationQuality,
    IncidentContextSnapshot,
    NotificationPayload,
    NotificationDeliveryResult,
    AcknowledgementStatus,
    EscalationLevel
)
from .config import EmergencyResponseConfig
from .state_machine import EmergencyStateMachine, InvalidStateTransitionError
from .location_provider import ILocationProvider, EmergencyLocationProvider
from .contact_service import IEmergencyContactService, MockEmergencyContactService
from .notification_provider import INotificationProvider, MockNotificationProvider
from .evidence_service import EvidenceService
from .location_broadcaster import EmergencyLocationBroadcaster
from .persistence import EmergencyPersistenceManager

from ..contextual.schemas import DecisionOutput, DecisionTier, JourneyRiskAssessment
from ..guardian.journey_state import GuardianSnapshot


class EmergencyResponseOrchestrator:
    """
    Central orchestration engine for autonomous and manual emergency response.
    """

    def __init__(
        self,
        config: Optional[EmergencyResponseConfig] = None,
        location_provider: Optional[ILocationProvider] = None,
        contact_service: Optional[IEmergencyContactService] = None,
        notification_provider: Optional[INotificationProvider] = None,
        evidence_service: Optional[EvidenceService] = None,
        location_broadcaster: Optional[EmergencyLocationBroadcaster] = None,
        persistence_manager: Optional[EmergencyPersistenceManager] = None,
    ):
        self.config = config or EmergencyResponseConfig()
        self.location_provider = location_provider or EmergencyLocationProvider(
            stale_threshold_seconds=self.config.location_stale_threshold_seconds
        )
        self.contact_service = contact_service or MockEmergencyContactService()
        self.notification_provider = notification_provider or MockNotificationProvider()
        self.evidence_service = evidence_service or EvidenceService(
            hash_algorithm=self.config.evidence_hash_algorithm
        )
        self.location_broadcaster = location_broadcaster or EmergencyLocationBroadcaster()
        self.persistence = persistence_manager or EmergencyPersistenceManager()

        # Cache of snapshots and assessments per journey for evidence compilation
        self._snapshots: Dict[str, GuardianSnapshot] = {}
        self._assessments: Dict[str, JourneyRiskAssessment] = {}

    def register_journey_context(
        self,
        journey_id: str,
        snapshot: Optional[GuardianSnapshot] = None,
        assessment: Optional[JourneyRiskAssessment] = None
    ):
        """Stores the latest journey context artifacts for evidence assembly."""
        if snapshot is not None:
            self._snapshots[journey_id] = snapshot
        if assessment is not None:
            self._assessments[journey_id] = assessment

    # --------------------------------------------------------------------------
    # 1. Autonomous Trigger Flow (Phase 3 -> Phase 4 Boundary)
    # --------------------------------------------------------------------------

    def handle_autonomous_decision(
        self,
        journey_id: str,
        decision: DecisionOutput,
        assessment: JourneyRiskAssessment,
        snapshot: Optional[GuardianSnapshot] = None,
        db: Optional[Session] = None,
        current_time: Optional[datetime] = None
    ) -> Optional[EmergencyIncident]:
        """
        Consumes Phase 3 DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED.
        Rejects non-autonomous decisions.
        Enforces idempotency: reuses existing active incident.
        """
        now = current_time or datetime.now(timezone.utc)
        self.register_journey_context(journey_id, snapshot, assessment)

        # 1. Eligibility Check: ONLY AUTONOMOUS_RESPONSE_REQUIRED is permitted
        if decision.decision_tier != DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED:
            return None

        # 2. Idempotency Check: Don't duplicate active incident for same journey
        existing = self.persistence.find_active_incident_for_journey(journey_id)
        if existing is not None:
            return existing

        # 3. Location Acquisition (Never fabricate coordinates)
        loc = self.location_provider.get_current_location(snapshot=snapshot, current_time=now)
        ctx_snapshot = self._build_context_snapshot(snapshot, assessment, loc)

        # 4. Create Incident in IDLE -> TRIGGERED
        incident_id = f"inc_auto_{uuid.uuid4().hex[:8]}"
        incident = EmergencyIncident(
            incident_id=incident_id,
            journey_id=journey_id,
            trigger_type=TriggerType.AUTONOMOUS_RISK,
            risk_score=assessment.risk_score,
            risk_level=assessment.risk_level.value,
            decision_tier=decision.decision_tier.value,
            state=EmergencyState.IDLE,
            created_at=now,
            triggered_at=now,
            countdown_seconds=self.config.emergency_countdown_seconds,
            countdown_remaining_seconds=self.config.emergency_countdown_seconds,
            context=ctx_snapshot,
            escalation_level=EscalationLevel.LEVEL_0
        )

        EmergencyStateMachine.transition(
            incident,
            EmergencyState.TRIGGERED,
            f"Autonomous response triggered by Phase 3 decision ({decision.decision_tier.value}, score: {assessment.risk_score}).",
            timestamp=now
        )

        # 5. Move to VERIFYING -> COUNTDOWN
        EmergencyStateMachine.transition(
            incident,
            EmergencyState.VERIFYING,
            "Verifying sensor context and initiating confirmation countdown.",
            timestamp=now
        )
        EmergencyStateMachine.transition(
            incident,
            EmergencyState.COUNTDOWN,
            f"Confirmation countdown active for {self.config.emergency_countdown_seconds}s.",
            timestamp=now
        )

        # 6. Publish live location broadcast
        self.location_broadcaster.broadcast_emergency_location(
            incident_id=incident.incident_id,
            location=loc,
            journey_id=journey_id,
            route_progress=ctx_snapshot.route_progress
        )

        self.persistence.save_incident(incident, db=db)
        return incident

    # --------------------------------------------------------------------------
    # 2. Manual SOS Trigger Flow
    # --------------------------------------------------------------------------

    def handle_manual_sos(
        self,
        journey_id: str,
        manual_lat: Optional[float] = None,
        manual_lng: Optional[float] = None,
        manual_accuracy: Optional[float] = None,
        reason: str = "User pressed manual SOS button",
        snapshot: Optional[GuardianSnapshot] = None,
        db: Optional[Session] = None,
        current_time: Optional[datetime] = None
    ) -> EmergencyIncident:
        """
        Processes explicit Manual SOS, bypassing risk qualification.
        """
        now = current_time or datetime.now(timezone.utc)
        if snapshot is not None:
            self._snapshots[journey_id] = snapshot

        # Check existing active incident
        existing = self.persistence.find_active_incident_for_journey(journey_id)
        if existing is not None:
            return existing

        # Location acquisition
        loc = self.location_provider.get_current_location(
            snapshot=snapshot or self._snapshots.get(journey_id),
            manual_lat=manual_lat,
            manual_lng=manual_lng,
            manual_accuracy=manual_accuracy,
            current_time=now
        )
        ctx_snapshot = self._build_context_snapshot(snapshot or self._snapshots.get(journey_id), None, loc)

        incident_id = f"inc_manual_{uuid.uuid4().hex[:8]}"
        countdown_secs = (
            self.config.manual_sos_countdown_seconds
            if not self.config.manual_sos_immediate_authorization
            else 0.0
        )

        incident = EmergencyIncident(
            incident_id=incident_id,
            journey_id=journey_id,
            trigger_type=TriggerType.MANUAL_SOS,
            risk_score=100.0,
            risk_level="CRITICAL",
            decision_tier="MANUAL_SOS",
            state=EmergencyState.IDLE,
            created_at=now,
            triggered_at=now,
            countdown_seconds=countdown_secs,
            countdown_remaining_seconds=countdown_secs,
            context=ctx_snapshot,
            escalation_level=EscalationLevel.LEVEL_0
        )

        EmergencyStateMachine.transition(
            incident,
            EmergencyState.TRIGGERED,
            f"Manual SOS triggered: {reason}",
            timestamp=now
        )

        # Broadcast location
        self.location_broadcaster.broadcast_emergency_location(
            incident_id=incident.incident_id,
            location=loc,
            journey_id=journey_id,
            route_progress=ctx_snapshot.route_progress
        )

        if self.config.manual_sos_immediate_authorization:
            # Immediate authorization bypass
            EmergencyStateMachine.transition(
                incident,
                EmergencyState.RESPONSE_AUTHORIZED,
                "Manual SOS immediate authorization configured; dispatching immediately.",
                timestamp=now
            )
            # Compile evidence and dispatch
            self._compile_evidence(incident)
            self.dispatch_response(incident, db=db, current_time=now)
        else:
            # Enforce manual countdown window
            EmergencyStateMachine.transition(
                incident,
                EmergencyState.VERIFYING,
                "Verifying manual SOS request.",
                timestamp=now
            )
            EmergencyStateMachine.transition(
                incident,
                EmergencyState.COUNTDOWN,
                f"Manual SOS countdown active for {countdown_secs}s.",
                timestamp=now
            )

        self.persistence.save_incident(incident, db=db)
        return incident

    # --------------------------------------------------------------------------
    # 3. Confirmation Countdown & State Advancement
    # --------------------------------------------------------------------------

    def advance_countdown(
        self,
        incident_id: str,
        elapsed_seconds: float = 15.0,
        network_available: bool = True,
        db: Optional[Session] = None,
        current_time: Optional[datetime] = None
    ) -> EmergencyIncident:
        """
        Advances the countdown timer deterministically.
        If countdown reaches <= 0, transitions to RESPONSE_AUTHORIZED and dispatches.
        """
        now = current_time or datetime.now(timezone.utc)
        incident = self.persistence.get_incident(incident_id, db=db)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found.")

        if incident.state == EmergencyState.COUNTDOWN:
            rem = (incident.countdown_remaining_seconds or incident.countdown_seconds) - elapsed_seconds
            incident.countdown_remaining_seconds = max(0.0, rem)

            if incident.countdown_remaining_seconds <= 0.0:
                EmergencyStateMachine.transition(
                    incident,
                    EmergencyState.RESPONSE_AUTHORIZED,
                    f"Countdown window expired ({incident.countdown_seconds}s elapsed); response authorized.",
                    timestamp=now
                )
                self._compile_evidence(incident)
                self.dispatch_response(incident, network_available=network_available, db=db, current_time=now)

        self.persistence.save_incident(incident, db=db)
        return incident

    # --------------------------------------------------------------------------
    # 4. Cancellation Handling
    # --------------------------------------------------------------------------

    def cancel_incident(
        self,
        incident_id: str,
        reason: str = "User confirmed false alarm",
        db: Optional[Session] = None,
        current_time: Optional[datetime] = None
    ) -> EmergencyIncident:
        """
        Cancels an active incident during VERIFYING, COUNTDOWN, or authorized before dispatch.
        Guarantees: No emergency notifications are sent once cancelled.
        """
        now = current_time or datetime.now(timezone.utc)
        incident = self.persistence.get_incident(incident_id, db=db)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found.")

        if not EmergencyStateMachine.can_transition(incident.state, EmergencyState.CANCELLED):
            raise InvalidStateTransitionError(
                f"Cannot cancel incident {incident_id} in state {incident.state.value}."
            )

        EmergencyStateMachine.transition(
            incident,
            EmergencyState.CANCELLED,
            f"Cancelled by user: {reason}",
            timestamp=now
        )
        self.persistence.save_incident(incident, db=db)
        return incident

    # --------------------------------------------------------------------------
    # 5. Notification Dispatch
    # --------------------------------------------------------------------------

    def dispatch_response(
        self,
        incident: EmergencyIncident,
        network_available: bool = True,
        db: Optional[Session] = None,
        current_time: Optional[datetime] = None
    ) -> EmergencyIncident:
        """
        Resolves emergency contacts and dispatches notifications.
        Surfaces network failure and partial delivery states explicitly.
        """
        now = current_time or datetime.now(timezone.utc)

        # Transition to DISPATCHING
        EmergencyStateMachine.transition(
            incident,
            EmergencyState.DISPATCHING,
            f"Initiating notification dispatch at {incident.escalation_level.value}.",
            timestamp=now
        )

        # Resolve contacts for current escalation level
        target_contacts = self.contact_service.get_contacts_for_journey(
            journey_id=incident.journey_id,
            escalation_level=incident.escalation_level
        )
        incident.contacts_targeted = [c.contact_id for c in target_contacts]

        # Check network availability boundary
        if not network_available:
            fail_results = [
                NotificationDeliveryResult(
                    contact_id=c.contact_id,
                    destination=c.destination,
                    success=False,
                    delivered_at=None,
                    error_message="Network offline: emergency delivery failed"
                )
                for c in target_contacts
            ]
            incident.delivery_results.extend(fail_results)
            incident.notifications_attempted += len(target_contacts)
            EmergencyStateMachine.transition(
                incident,
                EmergencyState.FAILED,
                "Network offline: all notification attempts failed due to lack of network connectivity.",
                timestamp=now
            )
            self.persistence.save_incident(incident, db=db)
            return incident

        # If no contacts available at this tier
        if not target_contacts:
            EmergencyStateMachine.transition(
                incident,
                EmergencyState.FAILED,
                f"No enabled emergency contacts configured for {incident.escalation_level.value}.",
                timestamp=now
            )
            self.persistence.save_incident(incident, db=db)
            return incident

        # Construct notification payload
        loc = self.location_provider.get_current_location(snapshot=self._snapshots.get(incident.journey_id))
        payload = NotificationPayload(
            incident_id=incident.incident_id,
            emergency_status=EmergencyState.DISPATCHING,
            trigger_type=incident.trigger_type,
            location=loc,
            location_quality=loc.quality,
            journey_id=incident.journey_id,
            risk_score=incident.risk_score,
            risk_level=incident.risk_level,
            dominant_risk_factor=incident.context.dominant_risk_factor,
            timestamp=now,
            message=f"EMERGENCY ALERT: {incident.trigger_type.value} reported for journey {incident.journey_id}."
        )

        delivery_results: List[NotificationDeliveryResult] = []
        for contact in target_contacts:
            res = self.notification_provider.send_emergency_notification(incident, contact, payload)
            delivery_results.append(res)

        incident.delivery_results.extend(delivery_results)
        incident.notifications_attempted += len(delivery_results)
        success_count = sum(1 for r in delivery_results if r.success)
        incident.notifications_delivered += success_count

        # Evaluate dispatch outcome
        if success_count == len(delivery_results):
            EmergencyStateMachine.transition(
                incident,
                EmergencyState.NOTIFIED,
                f"All {success_count} emergency notifications successfully dispatched.",
                timestamp=now
            )
        elif success_count > 0:
            EmergencyStateMachine.transition(
                incident,
                EmergencyState.PARTIAL_FAILURE,
                f"Partial delivery: {success_count}/{len(delivery_results)} notifications delivered.",
                timestamp=now
            )
        else:
            EmergencyStateMachine.transition(
                incident,
                EmergencyState.FAILED,
                "Total failure: All notification delivery attempts failed.",
                timestamp=now
            )

        self.persistence.save_incident(incident, db=db)
        return incident

    # --------------------------------------------------------------------------
    # 6. Acknowledgement Tracking
    # --------------------------------------------------------------------------

    def acknowledge_incident(
        self,
        incident_id: str,
        contact_id: str,
        acknowledged_by: Optional[str] = None,
        notes: str = "Contact acknowledged emergency",
        db: Optional[Session] = None,
        current_time: Optional[datetime] = None
    ) -> EmergencyIncident:
        """
        Records acknowledgement and transitions state machine to RESOLVED.
        """
        now = current_time or datetime.now(timezone.utc)
        incident = self.persistence.get_incident(incident_id, db=db)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found.")

        incident.acknowledgement_status = AcknowledgementStatus.ACKNOWLEDGED
        incident.acknowledged_by = acknowledged_by or contact_id
        incident.acknowledged_at = now

        # Transition: current state -> ACKNOWLEDGED -> RESOLVED
        EmergencyStateMachine.transition(
            incident,
            EmergencyState.ACKNOWLEDGED,
            f"Acknowledged by {incident.acknowledged_by}: {notes}",
            timestamp=now
        )
        EmergencyStateMachine.transition(
            incident,
            EmergencyState.RESOLVED,
            "Incident resolved following verified contact acknowledgement.",
            timestamp=now
        )

        self.persistence.save_incident(incident, db=db)
        return incident

    # --------------------------------------------------------------------------
    # 7. Escalation Flow
    # --------------------------------------------------------------------------

    def escalate_incident(
        self,
        incident_id: str,
        reason: str = "No acknowledgement received within timeout window",
        network_available: bool = True,
        db: Optional[Session] = None,
        current_time: Optional[datetime] = None
    ) -> EmergencyIncident:
        """
        Escalates incident to the next hierarchy level and re-dispatches.
        """
        now = current_time or datetime.now(timezone.utc)
        incident = self.persistence.get_incident(incident_id, db=db)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found.")

        # Determine next escalation tier
        current_lvl = incident.escalation_level
        if current_lvl in [EscalationLevel.LEVEL_0, EscalationLevel.LEVEL_1]:
            next_lvl = EscalationLevel.LEVEL_2
        elif current_lvl == EscalationLevel.LEVEL_2:
            next_lvl = EscalationLevel.LEVEL_3
        else:
            # At max tier
            next_lvl = EscalationLevel.LEVEL_3

        incident.escalation_level = next_lvl
        EmergencyStateMachine.transition(
            incident,
            EmergencyState.ESCALATED,
            f"Escalating to {next_lvl.value}: {reason}",
            timestamp=now
        )

        # Dispatch next tier
        self.dispatch_response(incident, network_available=network_available, db=db, current_time=now)
        self.persistence.save_incident(incident, db=db)
        return incident

    # --------------------------------------------------------------------------
    # Helpers
    # --------------------------------------------------------------------------

    def _compile_evidence(self, incident: EmergencyIncident):
        """Compiles evidence package using registered artifacts."""
        snap = self._snapshots.get(incident.journey_id)
        assess = self._assessments.get(incident.journey_id)
        pkg = self.evidence_service.compile_evidence_package(
            incident=incident,
            snapshot=snap,
            assessment=assess
        )
        incident.evidence_package_id = pkg.package_id

    def _build_context_snapshot(
        self,
        snapshot: Optional[GuardianSnapshot],
        assessment: Optional[JourneyRiskAssessment],
        location: LocationResult
    ) -> IncidentContextSnapshot:
        return IncidentContextSnapshot(
            current_lat=location.latitude,
            current_lng=location.longitude,
            location_accuracy=location.accuracy,
            location_quality=location.quality,
            route_progress=snapshot.route_progress_percent if snapshot else None,
            remaining_distance=snapshot.remaining_distance_m if snapshot else None,
            eta=snapshot.eta if snapshot else None,
            journey_state=snapshot.journey_state.value if snapshot else None,
            dominant_risk_factor=assessment.dominant_factor if assessment else None
        )

    def reset_all(self):
        """Resets all in-memory states and mock adapters for test isolation."""
        self.persistence.clear()
        self.location_provider.clear()
        self.contact_service.clear()
        self.notification_provider.clear()
        self.evidence_service.clear()
        self.location_broadcaster.clear()
        self._snapshots.clear()
        self._assessments.clear()
