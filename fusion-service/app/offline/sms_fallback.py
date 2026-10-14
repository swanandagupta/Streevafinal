"""
STREEVA — Phase 5 Offline Guardian & Connectivity Resilience
app/offline/sms_fallback.py

SMS Fallback Abstraction:
- ISMSFallbackProvider: Abstract base interface for offline emergency communications.
- MockSMSFallbackProvider: Deterministic provider for tests and replays with explicit SENT, FAILED, UNAVAILABLE outcomes.
- Enforces: Never pretend an offline notification was delivered when the provider failed or was unavailable.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import uuid
import logging

from .schemas import SMSDeliveryResult, SMSDeliveryStatus

logger = logging.getLogger(__name__)


class ISMSFallbackProvider(ABC):
    """
    Abstract interface for offline emergency SMS dispatch.
    Allows decoupling from cellular hardware/AT-command modems or SMS gateways.
    """

    @abstractmethod
    def send_sms(
        self,
        incident_id: str,
        recipient: str,
        message: str,
        payload: Optional[Dict[str, Any]] = None
    ) -> SMSDeliveryResult:
        """Attempts to send an SMS for an emergency incident."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the SMS modem/gateway is ready and operational."""
        pass


class MockSMSFallbackProvider(ISMSFallbackProvider):
    """
    Deterministic mock SMS provider for automated testing and replays.
    Configurable to succeed, fail, or be unavailable.
    Records delivery history.
    """

    def __init__(self, default_mode: str = "SUCCESS"):
        # Modes: "SUCCESS", "FAILURE", "UNAVAILABLE"
        self._mode: str = default_mode
        self._sent_messages: List[SMSDeliveryResult] = []

    def set_mode(self, mode: str) -> None:
        """Sets delivery behavior: 'SUCCESS', 'FAILURE', or 'UNAVAILABLE'."""
        self._mode = mode.upper()

    @property
    def mode(self) -> str:
        return self._mode

    def is_available(self) -> bool:
        return self._mode != "UNAVAILABLE"

    def send_sms(
        self,
        incident_id: str,
        recipient: str,
        message: str,
        payload: Optional[Dict[str, Any]] = None
    ) -> SMSDeliveryResult:
        now = datetime.now(timezone.utc)

        if self._mode == "UNAVAILABLE":
            result = SMSDeliveryResult(
                recipient=recipient,
                status=SMSDeliveryStatus.UNAVAILABLE,
                delivered_at=None,
                message_id=None,
                error_message="SMS fallback modem/carrier unavailable (cellular signal missing)"
            )
        elif self._mode == "FAILURE":
            result = SMSDeliveryResult(
                recipient=recipient,
                status=SMSDeliveryStatus.FAILED,
                delivered_at=None,
                message_id=None,
                error_message="SMS transmission rejected by mock SMS carrier"
            )
        else:
            # SUCCESS
            msg_id = f"sms-{uuid.uuid4().hex[:8]}"
            result = SMSDeliveryResult(
                recipient=recipient,
                status=SMSDeliveryStatus.SENT,
                delivered_at=now,
                message_id=msg_id,
                error_message=None
            )

        self._sent_messages.append(result)
        logger.info(
            f"[MockSMSFallbackProvider] SMS dispatch to {recipient} -> {result.status.value} (Incident: {incident_id})"
        )
        return result

    def get_history(self) -> List[SMSDeliveryResult]:
        return list(self._sent_messages)

    def clear_history(self) -> None:
        self._sent_messages.clear()
