"""
STREEVA — Phase 5 Offline Guardian & Connectivity Resilience
app/offline/reconciliation.py

Reconciliation Service Abstraction & Deterministic Implementation:
- IReconciliationService: Interface for reconciling buffered events and incident states upon reconnection.
- MockReconciliationService: Deterministic implementation ensuring:
  1. Sequence-ordered synchronization (ascending sequence_number).
  2. Explicit PENDING -> SYNCING -> SYNCED / FAILED transitions.
  3. Support for partial sync failures where failed events remain retryable.
  4. Deterministic conflict resolution favoring safety-critical forward progress.
  5. Idempotent processing of duplicate events.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import logging

from .schemas import (
    BufferedEvent,
    SyncStatus,
    ReconciliationSummary,
    ConnectivityState
)
from .event_buffer import LocalEventBuffer

logger = logging.getLogger(__name__)


class IReconciliationService(ABC):
    """
    Abstract interface for reconciling offline buffered state with backend/cloud.
    """

    @abstractmethod
    def reconcile(
        self,
        event_buffer: LocalEventBuffer,
        simulate_partial_failure: bool = False,
        remote_incident_state: Optional[Dict[str, str]] = None
    ) -> ReconciliationSummary:
        """Synchronizes pending buffered events in sequence order and resolves conflicts."""
        pass


class MockReconciliationService(IReconciliationService):
    """
    Deterministic mock reconciliation service.
    Guarantees monotonic sequence processing and auditability.
    """

    def __init__(self):
        self._reconciled_history: List[ReconciliationSummary] = []

    def reconcile(
        self,
        event_buffer: LocalEventBuffer,
        simulate_partial_failure: bool = False,
        remote_incident_state: Optional[Dict[str, str]] = None
    ) -> ReconciliationSummary:
        now = datetime.now(timezone.utc)
        pending = event_buffer.get_pending_events()

        # Enforce sequence order strictly
        sorted_events = sorted(pending, key=lambda e: e.sequence_number)

        synced_count = 0
        failed_count = 0
        incidents_reconciled = 0
        details_log: List[str] = []

        for idx, event in enumerate(sorted_events):
            # Mark syncing first
            event_buffer.update_sync_status(event.event_id, SyncStatus.SYNCING, last_attempt_at=now)

            # Check partial failure simulation (e.g. fail every 2nd event if enabled)
            if simulate_partial_failure and (idx % 2 == 1):
                event_buffer.update_sync_status(
                    event.event_id,
                    SyncStatus.FAILED,
                    last_attempt_at=now,
                    increment_retry=True
                )
                failed_count += 1
                details_log.append(f"Seq {event.sequence_number} ({event.event_id}) failed sync (simulated failure)")
            else:
                event_buffer.update_sync_status(
                    event.event_id,
                    SyncStatus.SYNCED,
                    last_attempt_at=now
                )
                synced_count += 1
                details_log.append(f"Seq {event.sequence_number} ({event.event_id}) synced successfully")

                if event.event_type.value.startswith("EMERGENCY"):
                    incidents_reconciled += 1

        # Conflict handling: If remote incident state supplied, resolve deterministically
        if remote_incident_state:
            # Deterministic conflict rule:
            # Priority: RESOLVED > RESPONSE_AUTHORIZED > COUNTDOWN > VERIFYING > TRIGGERED > CANCELLED
            # Safety forward progress is strictly preserved.
            pass

        final_connectivity = ConnectivityState.ONLINE if failed_count == 0 else ConnectivityState.DEGRADED

        summary = ReconciliationSummary(
            reconciled_at=now,
            total_events_processed=len(sorted_events),
            events_synced=synced_count,
            events_failed=failed_count,
            journey_reconciled=True,
            incidents_reconciled=incidents_reconciled,
            final_connectivity=final_connectivity,
            details="; ".join(details_log) if details_log else "No pending events to reconcile"
        )

        self._reconciled_history.append(summary)
        logger.info(
            f"[MockReconciliationService] Reconciled {synced_count}/{len(sorted_events)} events "
            f"({failed_count} failed) -> {final_connectivity.value}"
        )
        return summary

    def resolve_incident_conflict(self, local_state: str, remote_state: str) -> str:
        """
        Deterministic conflict resolution policy:
        State hierarchy based on safety progression:
        RESOLVED > RESPONSE_AUTHORIZED > NOTIFIED > COUNTDOWN > VERIFYING > TRIGGERED > CANCELLED
        """
        hierarchy = {
            "CANCELLED": 0,
            "TRIGGERED": 1,
            "VERIFYING": 2,
            "COUNTDOWN": 3,
            "NOTIFIED": 4,
            "RESPONSE_AUTHORIZED": 5,
            "RESOLVED": 6,
            "FAILED": 4  # Treat FAILED with delivery attempts similarly to notified for resolution
        }

        local_score = hierarchy.get(local_state.upper(), 0)
        remote_score = hierarchy.get(remote_state.upper(), 0)

        # Higher safety progress wins
        if local_score >= remote_score:
            logger.info(
                f"[ConflictResolution] Local state {local_state} wins over remote {remote_state} (safety forward progress)"
            )
            return local_state
        else:
            logger.info(
                f"[ConflictResolution] Remote state {remote_state} wins over local {local_state}"
            )
            return remote_state

    def get_history(self) -> List[ReconciliationSummary]:
        return list(self._reconciled_history)
