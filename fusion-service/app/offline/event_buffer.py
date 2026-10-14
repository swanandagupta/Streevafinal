"""
STREEVA — Phase 5 Offline Guardian & Connectivity Resilience
app/offline/event_buffer.py

Durable Local Event Buffer:
- Enforces strictly monotonic sequence numbering for deterministic ordering.
- Buffers safety events, telemetry, snapshots, assessments, decisions, and emergency transitions locally.
- Persists into SQLite so state survives application restart.
- Handles duplicate deduplication idempotently.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import uuid
import logging

from .schemas import BufferedEvent, BufferedEventType, SyncStatus
from .persistence import OfflinePersistenceManager

logger = logging.getLogger(__name__)


class LocalEventBuffer:
    """
    Local append-only event buffer with monotonic sequence numbers.
    Maintains ordering across offline journeys and restarts.
    """

    def __init__(self, persistence_manager: Optional[OfflinePersistenceManager] = None, max_size: int = 10000):
        self._persistence: OfflinePersistenceManager = persistence_manager or OfflinePersistenceManager()
        self._max_size: int = max_size
        self._events: List[BufferedEvent] = []
        self._event_ids: set = set()
        self._sequence_counter: int = 0
        self._initialize_from_persistence()

    def _initialize_from_persistence(self) -> None:
        """Restores buffered events and monotonic sequence counter from SQLite."""
        try:
            stored = self._persistence.get_buffered_events()
            for evt in stored:
                if evt.event_id not in self._event_ids:
                    self._events.append(evt)
                    self._event_ids.add(evt.event_id)
                if evt.sequence_number > self._sequence_counter:
                    self._sequence_counter = evt.sequence_number
            logger.info(
                f"[LocalEventBuffer] Restored {len(self._events)} events from persistence. "
                f"Sequence counter at {self._sequence_counter}"
            )
        except Exception as e:
            logger.warning(f"[LocalEventBuffer] Could not restore from persistence: {e}")

    @property
    def current_sequence(self) -> int:
        return self._sequence_counter

    @property
    def total_count(self) -> int:
        return len(self._events)

    def buffer_event(
        self,
        journey_id: str,
        event_type: BufferedEventType,
        payload: Dict[str, Any],
        source_timestamp: Optional[datetime] = None,
        event_id: Optional[str] = None
    ) -> BufferedEvent:
        """
        Appends an event to the local buffer with a strictly monotonic sequence number.
        Deduplicates if event_id already exists.
        """
        now = datetime.now(timezone.utc)
        src_ts = source_timestamp or now
        evt_id = event_id or f"evt-{uuid.uuid4().hex[:12]}"

        # Deduplicate if event already known
        if evt_id in self._event_ids:
            for e in self._events:
                if e.event_id == evt_id:
                    return e

        self._sequence_counter += 1
        seq = self._sequence_counter

        event = BufferedEvent(
            event_id=evt_id,
            journey_id=journey_id,
            event_type=event_type,
            payload=payload,
            created_at=now,
            source_timestamp=src_ts,
            sequence_number=seq,
            sync_status=SyncStatus.PENDING,
            retry_count=0,
            last_attempt_at=None
        )

        self._events.append(event)
        self._event_ids.add(evt_id)

        # Persist durably
        try:
            self._persistence.save_buffered_event(event)
        except Exception as e:
            logger.error(f"[LocalEventBuffer] Failed to persist event {evt_id}: {e}")

        logger.info(
            f"[LocalEventBuffer] Buffered seq={seq} type={event_type.value} id={evt_id} (journey={journey_id})"
        )
        return event

    def get_pending_events(self, journey_id: Optional[str] = None) -> List[BufferedEvent]:
        """Returns all events with PENDING or FAILED status, ordered by sequence number."""
        events = [
            e for e in self._events
            if e.sync_status in (SyncStatus.PENDING, SyncStatus.FAILED)
            and (journey_id is None or e.journey_id == journey_id)
        ]
        return sorted(events, key=lambda x: x.sequence_number)

    def get_all_events(self, journey_id: Optional[str] = None) -> List[BufferedEvent]:
        """Returns all buffered events ordered by sequence number."""
        events = [
            e for e in self._events
            if journey_id is None or e.journey_id == journey_id
        ]
        return sorted(events, key=lambda x: x.sequence_number)

    def update_sync_status(
        self,
        event_id: str,
        new_status: SyncStatus,
        last_attempt_at: Optional[datetime] = None,
        increment_retry: bool = False
    ) -> Optional[BufferedEvent]:
        """Updates the synchronization status of an event."""
        for e in self._events:
            if e.event_id == event_id:
                e.sync_status = new_status
                if last_attempt_at:
                    e.last_attempt_at = last_attempt_at
                if increment_retry:
                    e.retry_count += 1

                try:
                    self._persistence.save_buffered_event(e)
                except Exception as ex:
                    logger.error(f"[LocalEventBuffer] Failed updating event status {event_id}: {ex}")
                return e
        return None

    def clear(self) -> None:
        """Clears buffer in memory and persistence (for testing)."""
        self._events.clear()
        self._event_ids.clear()
        self._sequence_counter = 0
