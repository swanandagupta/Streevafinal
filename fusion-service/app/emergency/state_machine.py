"""
STREEVA — Phase 4 Autonomous Emergency Response System
app/emergency/state_machine.py

Explicit, deterministic state machine enforcing valid transitions and rejection of arbitrary mutations.
"""

from datetime import datetime, timezone
from typing import Set, Dict
from .schemas import EmergencyState, EmergencyIncident, IncidentTransitionRecord


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal state transition is attempted."""
    pass


class EmergencyStateMachine:
    """
    Guards and executes valid lifecycle transitions for an EmergencyIncident.
    """

    # Allowed transitions map: CurrentState -> Set of Allowed Next States
    VALID_TRANSITIONS: Dict[EmergencyState, Set[EmergencyState]] = {
        EmergencyState.IDLE: {
            EmergencyState.TRIGGERED
        },
        EmergencyState.TRIGGERED: {
            EmergencyState.VERIFYING,
            EmergencyState.RESPONSE_AUTHORIZED,  # Immediate authorization bypass (e.g. instant SOS)
            EmergencyState.CANCELLED
        },
        EmergencyState.VERIFYING: {
            EmergencyState.COUNTDOWN,
            EmergencyState.RESPONSE_AUTHORIZED,
            EmergencyState.CANCELLED
        },
        EmergencyState.COUNTDOWN: {
            EmergencyState.RESPONSE_AUTHORIZED,
            EmergencyState.CANCELLED
        },
        EmergencyState.RESPONSE_AUTHORIZED: {
            EmergencyState.DISPATCHING,
            EmergencyState.CANCELLED
        },
        EmergencyState.DISPATCHING: {
            EmergencyState.NOTIFIED,
            EmergencyState.PARTIAL_FAILURE,
            EmergencyState.FAILED
        },
        EmergencyState.NOTIFIED: {
            EmergencyState.ACKNOWLEDGED,
            EmergencyState.ESCALATED,
            EmergencyState.RESOLVED
        },
        EmergencyState.PARTIAL_FAILURE: {
            EmergencyState.ESCALATED,
            EmergencyState.ACKNOWLEDGED,
            EmergencyState.FAILED,
            EmergencyState.RESOLVED
        },
        EmergencyState.FAILED: {
            EmergencyState.ESCALATED,
            EmergencyState.RESOLVED
        },
        EmergencyState.ESCALATED: {
            EmergencyState.DISPATCHING,
            EmergencyState.NOTIFIED,
            EmergencyState.ACKNOWLEDGED,
            EmergencyState.PARTIAL_FAILURE,
            EmergencyState.FAILED,
            EmergencyState.RESOLVED
        },
        EmergencyState.ACKNOWLEDGED: {
            EmergencyState.RESOLVED
        },
        EmergencyState.CANCELLED: set(),  # Terminal state
        EmergencyState.RESOLVED: set(),   # Terminal state
    }

    @classmethod
    def can_transition(cls, from_state: EmergencyState, to_state: EmergencyState) -> bool:
        """Checks whether a transition is allowed."""
        return to_state in cls.VALID_TRANSITIONS.get(from_state, set())

    @classmethod
    def transition(
        cls,
        incident: EmergencyIncident,
        target_state: EmergencyState,
        reason: str,
        timestamp: datetime = None
    ) -> EmergencyIncident:
        """
        Executes a validated state transition, updating incident timestamps and history audit.
        """
        current_state = incident.state
        if not cls.can_transition(current_state, target_state):
            raise InvalidStateTransitionError(
                f"Invalid state transition: Cannot transition incident {incident.incident_id} "
                f"from {current_state.value} to {target_state.value}. (Reason: {reason})"
            )

        ts = timestamp or datetime.now(timezone.utc)
        record = IncidentTransitionRecord(
            from_state=current_state,
            to_state=target_state,
            timestamp=ts,
            reason=reason
        )

        incident.history.append(record)
        incident.state = target_state

        # Update specific milestone timestamps
        if target_state == EmergencyState.COUNTDOWN and incident.countdown_started_at is None:
            incident.countdown_started_at = ts
        elif target_state == EmergencyState.RESPONSE_AUTHORIZED and incident.response_authorized_at is None:
            incident.response_authorized_at = ts
        elif target_state == EmergencyState.CANCELLED:
            incident.cancelled_at = ts
        elif target_state == EmergencyState.RESOLVED:
            incident.resolved_at = ts

        return incident
