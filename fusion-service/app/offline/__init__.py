"""
STREEVA — Phase 5 Offline Guardian & Connectivity Resilience
app/offline/__init__.py
"""

from .schemas import (
    ConnectivityState,
    ConnectivityInfo,
    BufferedEvent,
    BufferedEventType,
    SyncStatus,
    CachedJourneyContext,
    SMSDeliveryStatus,
    SMSDeliveryResult,
    ReconciliationSummary,
    UpdateConnectivityRequest,
    ReconcileRequest,
    SMSTestRequest
)
from .config import OfflineGuardianConfig
from .connectivity import ConnectivityManager, InvalidConnectivityTransitionError
from .journey_cache import ActiveJourneyCache
from .event_buffer import LocalEventBuffer
from .persistence import (
    OfflinePersistenceManager,
    OfflineEventDB,
    CachedJourneyDB,
    ConnectivityHistoryDB
)
from .sms_fallback import ISMSFallbackProvider, MockSMSFallbackProvider
from .reconciliation import IReconciliationService, MockReconciliationService
from .guardian import OfflineGuardian

__all__ = [
    "ConnectivityState",
    "ConnectivityInfo",
    "BufferedEvent",
    "BufferedEventType",
    "SyncStatus",
    "CachedJourneyContext",
    "SMSDeliveryStatus",
    "SMSDeliveryResult",
    "ReconciliationSummary",
    "UpdateConnectivityRequest",
    "ReconcileRequest",
    "SMSTestRequest",
    "OfflineGuardianConfig",
    "ConnectivityManager",
    "InvalidConnectivityTransitionError",
    "ActiveJourneyCache",
    "LocalEventBuffer",
    "OfflinePersistenceManager",
    "OfflineEventDB",
    "CachedJourneyDB",
    "ConnectivityHistoryDB",
    "ISMSFallbackProvider",
    "MockSMSFallbackProvider",
    "IReconciliationService",
    "MockReconciliationService",
    "OfflineGuardian",
]
