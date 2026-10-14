"""
STREEVA — Phase 5 Offline Guardian & Connectivity Resilience
app/offline/connectivity.py

Explicit connectivity state machine and manager:
- States: ONLINE, DEGRADED, OFFLINE, RECONNECTING
- Validates transitions, tracks timestamps, reasons, and sync timestamps
- Provider-independent network quality representation
"""

from datetime import datetime, timezone
from typing import Optional, Set, Tuple
import logging

from .schemas import ConnectivityState, ConnectivityInfo

logger = logging.getLogger(__name__)


class InvalidConnectivityTransitionError(ValueError):
    """Raised when an invalid connectivity transition is requested."""
    pass


class ConnectivityManager:
    """
    Manages network connectivity state transitions and metadata.
    Separates connectivity state from safety risk evaluation.
    """

    # Allowed state transitions: (source_state, target_state)
    VALID_TRANSITIONS: Set[Tuple[ConnectivityState, ConnectivityState]] = {
        (ConnectivityState.ONLINE, ConnectivityState.DEGRADED),
        (ConnectivityState.ONLINE, ConnectivityState.OFFLINE),
        (ConnectivityState.DEGRADED, ConnectivityState.ONLINE),
        (ConnectivityState.DEGRADED, ConnectivityState.OFFLINE),
        (ConnectivityState.OFFLINE, ConnectivityState.RECONNECTING),
        (ConnectivityState.OFFLINE, ConnectivityState.ONLINE),  # Direct recovery allowance
        (ConnectivityState.RECONNECTING, ConnectivityState.ONLINE),
        (ConnectivityState.RECONNECTING, ConnectivityState.OFFLINE),
        (ConnectivityState.RECONNECTING, ConnectivityState.DEGRADED),
    }

    def __init__(self, initial_state: ConnectivityState = ConnectivityState.ONLINE):
        now = datetime.now(timezone.utc)
        self._state: ConnectivityState = initial_state
        self._changed_at: datetime = now
        self._last_online_at: Optional[datetime] = now if initial_state == ConnectivityState.ONLINE else None
        self._last_successful_sync_at: Optional[datetime] = None
        self._reason: str = f"Initial state established as {initial_state.value}"

    @property
    def current_state(self) -> ConnectivityState:
        return self._state

    @property
    def is_online(self) -> bool:
        return self._state == ConnectivityState.ONLINE

    @property
    def is_offline(self) -> bool:
        return self._state == ConnectivityState.OFFLINE

    @property
    def is_degraded(self) -> bool:
        return self._state == ConnectivityState.DEGRADED

    @property
    def is_reconnecting(self) -> bool:
        return self._state == ConnectivityState.RECONNECTING

    @property
    def network_available(self) -> bool:
        # DEGRADED and ONLINE have network; OFFLINE has none; RECONNECTING has tentative network
        return self._state in (ConnectivityState.ONLINE, ConnectivityState.DEGRADED)

    def transition_to(
        self,
        new_state: ConnectivityState,
        reason: str = "State transition requested",
        timestamp: Optional[datetime] = None
    ) -> ConnectivityInfo:
        """
        Transitions the manager to a new connectivity state.
        Validates transition legality. Idempotent if state is unchanged.
        """
        now = timestamp or datetime.now(timezone.utc)

        # Idempotent if state unchanged
        if new_state == self._state:
            self._reason = reason
            return self.get_status()

        # Check validity
        if (self._state, new_state) not in self.VALID_TRANSITIONS:
            raise InvalidConnectivityTransitionError(
                f"Invalid connectivity transition: {self._state.value} -> {new_state.value}"
            )

        previous_state = self._state
        self._state = new_state
        self._changed_at = now
        self._reason = reason

        if new_state == ConnectivityState.ONLINE:
            self._last_online_at = now

        logger.info(
            f"[ConnectivityManager] Transitioned: {previous_state.value} -> {new_state.value} | Reason: {reason}"
        )
        return self.get_status()

    def record_successful_sync(self, timestamp: Optional[datetime] = None) -> None:
        """Records the timestamp of a confirmed successful state reconciliation."""
        self._last_successful_sync_at = timestamp or datetime.now(timezone.utc)

    def get_status(self) -> ConnectivityInfo:
        """Returns the full connectivity status representation."""
        return ConnectivityInfo(
            state=self._state,
            changed_at=self._changed_at,
            last_online_at=self._last_online_at,
            last_successful_sync_at=self._last_successful_sync_at,
            network_available=self.network_available,
            reason=self._reason
        )

    def reset(self, initial_state: ConnectivityState = ConnectivityState.ONLINE) -> None:
        """Resets the state machine for deterministic testing."""
        now = datetime.now(timezone.utc)
        self._state = initial_state
        self._changed_at = now
        self._last_online_at = now if initial_state == ConnectivityState.ONLINE else None
        self._last_successful_sync_at = None
        self._reason = f"Reset to {initial_state.value}"
