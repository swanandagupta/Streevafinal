"""
STREEVA — Phase 5 Offline Guardian & Connectivity Resilience
app/offline/guardian.py

OfflineGuardian Central Coordinator:
- Sits around the frozen Phase 1-4 pipeline.
- Preserves active journey continuity when network connectivity is lost or degraded.
- Buffers events with monotonic sequence numbers into durable SQLite storage.
- Operates local safety monitoring using existing Phase 1 detectors, GuardianMonitor, and Phase 3 Fusion & Decision Engine.
- Integrates Phase 4 EmergencyResponseOrchestrator for offline countdowns, user cancellation, and SMS fallback.
- Reconciles buffered state upon reconnection without duplicating incidents or fabricating telemetry.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
import logging
import uuid

from .schemas import (
    ConnectivityState,
    ConnectivityInfo,
    BufferedEvent,
    BufferedEventType,
    SyncStatus,
    CachedJourneyContext,
    SMSDeliveryResult,
    SMSDeliveryStatus,
    ReconciliationSummary
)
from .config import OfflineGuardianConfig
from .connectivity import ConnectivityManager
from .journey_cache import ActiveJourneyCache
from .event_buffer import LocalEventBuffer
from .persistence import OfflinePersistenceManager
from .sms_fallback import ISMSFallbackProvider, MockSMSFallbackProvider
from .reconciliation import IReconciliationService, MockReconciliationService

# Reuse Phase 1-4 frozen components
from ..guardian.journey_state import JourneyStartRequest, JourneyUpdateRequest, JourneyState, TelemetryQuality
from ..guardian.monitor import GuardianMonitor, GuardianSnapshot
from ..contextual.schemas import JourneyRiskAssessment, DecisionOutput, DecisionTier, RiskLevel
from ..contextual.fusion_engine import ContextualRiskFusionEngine
from ..contextual.decision_engine import DecisionEngine
from ..emergency.orchestrator import EmergencyResponseOrchestrator
from ..emergency.schemas import (
    EmergencyIncident,
    EmergencyState,
    NotificationDeliveryResult,
    EscalationLevel
)

logger = logging.getLogger(__name__)


class OfflineGuardian:
    """
    Offline Guardian Resilience Layer.
    Wraps Phase 1-4 components, manages connectivity transitions, buffers events,
    handles local emergency countdown, offline SMS fallback, and reconnection synchronization.
    """

    def __init__(
        self,
        config: Optional[OfflineGuardianConfig] = None,
        persistence_manager: Optional[OfflinePersistenceManager] = None,
        sms_provider: Optional[ISMSFallbackProvider] = None,
        reconciliation_service: Optional[IReconciliationService] = None,
        monitor: Optional[GuardianMonitor] = None,
        fusion_engine: Optional[ContextualRiskFusionEngine] = None,
        decision_engine: Optional[DecisionEngine] = None,
        emergency_orchestrator: Optional[EmergencyResponseOrchestrator] = None
    ):
        self.config: OfflineGuardianConfig = config or OfflineGuardianConfig.load_from_yaml()
        self.persistence: OfflinePersistenceManager = persistence_manager or OfflinePersistenceManager()
        self.connectivity: ConnectivityManager = ConnectivityManager(ConnectivityState.ONLINE)
        self.journey_cache: ActiveJourneyCache = ActiveJourneyCache(
            stale_threshold_seconds=self.config.offline_location_stale_seconds
        )
        self.event_buffer: LocalEventBuffer = LocalEventBuffer(
            persistence_manager=self.persistence,
            max_size=self.config.max_buffered_events
        )
        self.sms_provider: ISMSFallbackProvider = sms_provider or MockSMSFallbackProvider()
        self.reconciliation_service: IReconciliationService = reconciliation_service or MockReconciliationService()

        # Reused verified components
        self.monitor: GuardianMonitor = monitor or GuardianMonitor()
        self.fusion_engine: ContextualRiskFusionEngine = fusion_engine or ContextualRiskFusionEngine()
        self.decision_engine: DecisionEngine = decision_engine or DecisionEngine()
        self.emergency_orchestrator: EmergencyResponseOrchestrator = (
            emergency_orchestrator or EmergencyResponseOrchestrator()
        )

        self._last_decision: Optional[DecisionOutput] = None

    # --------------------------------------------------------------------------
    # 1. Connectivity Lifecycle
    # --------------------------------------------------------------------------

    def set_connectivity(
        self,
        new_state: ConnectivityState,
        reason: str = "State transition",
        timestamp: Optional[datetime] = None
    ) -> ConnectivityInfo:
        """Transitions connectivity state, records transition in audit log."""
        info = self.connectivity.transition_to(new_state, reason=reason, timestamp=timestamp)
        try:
            self.persistence.record_connectivity_transition(new_state, reason=reason)
        except Exception as e:
            logger.warning(f"[OfflineGuardian] Could not record connectivity transition: {e}")

        # Buffer state change event if active journey exists
        if self.journey_cache.has_active_journey:
            cached = self.journey_cache.get_context()
            if cached:
                self.event_buffer.buffer_event(
                    journey_id=cached.journey_id,
                    event_type=BufferedEventType.SENSOR_POLICY,
                    payload={"new_state": new_state.value, "reason": reason},
                    source_timestamp=timestamp
                )

        return info

    def get_connectivity_status(self) -> ConnectivityInfo:
        return self.connectivity.get_status()

    # --------------------------------------------------------------------------
    # 2. Journey Start & Caching
    # --------------------------------------------------------------------------

    def start_journey(self, request: JourneyStartRequest) -> GuardianSnapshot:
        """
        Starts a journey in GuardianMonitor and caches journey context locally.
        Persists cached journey so it survives restarts.
        """
        snapshot = self.monitor.start_journey(request)

        # Cache journey context locally
        expected_route = []
        if request.expected_route:
            for p in request.expected_route:
                if isinstance(p, dict):
                    lat = p.get("lat") or p.get("latitude")
                    lng = p.get("lng") or p.get("longitude")
                    if lat is not None and lng is not None:
                        expected_route.append({"lat": float(lat), "lng": float(lng)})

        cached = self.journey_cache.cache_journey_start(
            journey_id=request.journey_id,
            source_lat=request.source_lat,
            source_lng=request.source_lng,
            dest_lat=request.destination_lat,
            dest_lng=request.destination_lng,
            expected_route=expected_route,
            active_sensor_policy="MEDIUM",
            timestamp=request.timestamp
        )

        # Persist to SQLite
        try:
            self.persistence.save_cached_journey(cached)
        except Exception as e:
            logger.warning(f"[OfflineGuardian] Could not persist cached journey: {e}")

        # Buffer initial snapshot
        self.event_buffer.buffer_event(
            journey_id=request.journey_id,
            event_type=BufferedEventType.GUARDIAN_SNAPSHOT,
            payload={
                "journey_state": snapshot.journey_state.value,
                "current_lat": snapshot.current_lat,
                "current_lng": snapshot.current_lng,
                "telemetry_quality": snapshot.telemetry_quality.value
            },
            source_timestamp=request.timestamp
        )

        return snapshot

    # --------------------------------------------------------------------------
    # 3. Local Telemetry Ingestion & Safety Monitoring
    # --------------------------------------------------------------------------

    def process_telemetry(
        self,
        request: JourneyUpdateRequest,
        area_risk_score: Optional[float] = None
    ) -> Tuple[GuardianSnapshot, JourneyRiskAssessment, DecisionOutput]:
        """
        Processes telemetry through the existing Phase 1-3 pipeline.
        Works seamlessly offline using local sensor streams.
        Buffers events with monotonic sequence numbers.
        Triggers Phase 4 emergency if autonomous response is required.
        """
        now = request.timestamp or datetime.now(timezone.utc)

        # 1. Buffer raw telemetry event
        self.event_buffer.buffer_event(
            journey_id=request.journey_id,
            event_type=BufferedEventType.TELEMETRY,
            payload={
                "latitude": request.latitude,
                "longitude": request.longitude,
                "gps_accuracy_m": request.gps_accuracy,
                "network_state": self.connectivity.current_state.value
            },
            source_timestamp=now
        )

        # 2. Process through Phase 1 & 2 GuardianMonitor
        snapshot = self.monitor.update_telemetry(request)

        # 3. Update local journey cache
        lat = snapshot.current_lat
        lng = snapshot.current_lng
        acc = request.gps_accuracy

        # Update cache location and route progress
        self.journey_cache.update_from_snapshot(
            route_progress_percent=snapshot.route_progress_percent,
            remaining_distance_m=snapshot.remaining_distance_m,
            eta=snapshot.eta,
            eta_source=snapshot.eta_source.value if hasattr(snapshot.eta_source, "value") else str(snapshot.eta_source),
            lat=lat,
            lng=lng,
            accuracy=acc,
            timestamp=now
        )

        # Buffer snapshot event
        self.event_buffer.buffer_event(
            journey_id=request.journey_id,
            event_type=BufferedEventType.GUARDIAN_SNAPSHOT,
            payload={
                "journey_state": snapshot.journey_state.value,
                "route_deviation": snapshot.route_deviation.state.value if snapshot.route_deviation else None,
                "unexpected_stop": snapshot.unexpected_stop.state.value if snapshot.unexpected_stop else None,
                "fall_detected": snapshot.fall_event.is_fall if snapshot.fall_event else False,
                "audio_distress_detected": snapshot.audio_distress.is_distress if snapshot.audio_distress else False
            },
            source_timestamp=now
        )

        # Buffer specific edge detector triggers if fired
        if snapshot.route_deviation and getattr(snapshot.route_deviation, "is_deviated", False):
            self.event_buffer.buffer_event(
                journey_id=request.journey_id,
                event_type=BufferedEventType.ROUTE_DEVIATION,
                payload={"deviation": snapshot.route_deviation.state.value},
                source_timestamp=now
            )
        if snapshot.unexpected_stop and getattr(snapshot.unexpected_stop, "is_stopped", False):
            self.event_buffer.buffer_event(
                journey_id=request.journey_id,
                event_type=BufferedEventType.UNEXPECTED_STOP,
                payload={"stop": snapshot.unexpected_stop.state.value},
                source_timestamp=now
            )
        if snapshot.fall_event and getattr(snapshot.fall_event, "is_fall", False):
            self.event_buffer.buffer_event(
                journey_id=request.journey_id,
                event_type=BufferedEventType.FALL,
                payload={"fall": True},
                source_timestamp=now
            )
        if snapshot.audio_distress and getattr(snapshot.audio_distress, "is_distress", False):
            self.event_buffer.buffer_event(
                journey_id=request.journey_id,
                event_type=BufferedEventType.AUDIO_DISTRESS,
                payload={"audio_distress": True},
                source_timestamp=now
            )

        # 4. Phase 3 Risk Fusion
        # If offline, area risk is not queried from cloud; dynamic weight renormalization applies
        effective_area_risk = area_risk_score if self.connectivity.network_available else None
        assessment = self.fusion_engine.evaluate_risk(
            snapshot=snapshot,
            area_risk_score=effective_area_risk
        )

        # Buffer risk assessment
        self.event_buffer.buffer_event(
            journey_id=request.journey_id,
            event_type=BufferedEventType.RISK_ASSESSMENT,
            payload={
                "risk_score": assessment.risk_score,
                "risk_level": assessment.risk_level.value,
                "confidence": assessment.overall_confidence
            },
            source_timestamp=now
        )

        # 5. Phase 3 Decision Engine
        decision = self.decision_engine.evaluate(assessment)
        self._last_decision = decision

        # Buffer decision
        self.event_buffer.buffer_event(
            journey_id=request.journey_id,
            event_type=BufferedEventType.DECISION,
            payload={
                "decision_tier": decision.decision_tier.value,
                "reason": decision.reason or ""
            },
            source_timestamp=now
        )

        # 6. Check Autonomous Emergency Trigger
        active_inc_id = None
        if decision.decision_tier == DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED:
            incident = self.handle_autonomous_decision(
                journey_id=request.journey_id,
                decision=decision,
                assessment=assessment,
                snapshot=snapshot,
                current_time=now
            )
            if incident:
                active_inc_id = incident.incident_id

        # Update cache with latest assessment & decision
        self.journey_cache.update_assessment_and_decision(
            risk_score=assessment.risk_score,
            risk_level=assessment.risk_level.value,
            decision_tier=decision.decision_tier.value,
            active_incident_id=active_inc_id
        )

        cached_ctx = self.journey_cache.get_context()
        if cached_ctx:
            try:
                self.persistence.save_cached_journey(cached_ctx)
            except Exception as ex:
                logger.warning(f"[OfflineGuardian] Failed updating cached journey in DB: {ex}")

        return snapshot, assessment, decision

    def handle_autonomous_decision(
        self,
        journey_id: str,
        decision: DecisionOutput,
        assessment: JourneyRiskAssessment,
        snapshot: Optional[GuardianSnapshot] = None,
        current_time: Optional[datetime] = None
    ) -> Optional[EmergencyIncident]:
        """
        Processes an autonomous emergency decision through Phase 4 orchestrator.
        Buffers emergency incident event and records active incident in local cache.
        """
        now = current_time or datetime.now(timezone.utc)
        incident = self.emergency_orchestrator.handle_autonomous_decision(
            journey_id=journey_id,
            decision=decision,
            assessment=assessment,
            snapshot=snapshot,
            current_time=now
        )
        if incident:
            self.journey_cache.update_assessment_and_decision(
                risk_score=assessment.risk_score,
                risk_level=assessment.risk_level.value,
                decision_tier=decision.decision_tier.value,
                active_incident_id=incident.incident_id
            )
            self.event_buffer.buffer_event(
                journey_id=journey_id,
                event_type=BufferedEventType.EMERGENCY_INCIDENT,
                payload={
                    "incident_id": incident.incident_id,
                    "state": incident.state.value,
                    "risk_score": incident.risk_score,
                    "trigger_type": incident.trigger_type.value
                },
                source_timestamp=now
            )
            cached_ctx = self.journey_cache.get_context()
            if cached_ctx:
                try:
                    self.persistence.save_cached_journey(cached_ctx)
                except Exception as ex:
                    logger.warning(f"[OfflineGuardian] Failed updating cached journey in DB: {ex}")

        return incident

    # --------------------------------------------------------------------------
    # 4. Offline Emergency Response & SMS Fallback
    # --------------------------------------------------------------------------

    def advance_emergency_countdown(
        self,
        incident_id: str,
        elapsed_seconds: float = 15.0,
        current_time: Optional[datetime] = None
    ) -> EmergencyIncident:
        """
        Advances the countdown timer locally without depending on server time or cloud connectivity.
        When countdown expires, handles dispatch either via network (if online) or via SMS fallback (if offline).
        """
        now = current_time or datetime.now(timezone.utc)
        net_avail = self.connectivity.network_available

        # Advance countdown through Phase 4 orchestrator
        incident = self.emergency_orchestrator.advance_countdown(
            incident_id=incident_id,
            elapsed_seconds=elapsed_seconds,
            network_available=net_avail,
            current_time=now
        )

        # Buffer state change
        self.event_buffer.buffer_event(
            journey_id=incident.journey_id,
            event_type=BufferedEventType.EMERGENCY_STATE_CHANGE,
            payload={
                "incident_id": incident_id,
                "state": incident.state.value,
                "remaining_seconds": incident.countdown_remaining_seconds
            },
            source_timestamp=now
        )

        # If offline and response authorized, attempt SMS fallback
        if not net_avail and incident.state in (EmergencyState.RESPONSE_AUTHORIZED, EmergencyState.FAILED):
            self._execute_offline_sms_fallback(incident, current_time=now)

        return incident

    def _execute_offline_sms_fallback(
        self,
        incident: EmergencyIncident,
        current_time: Optional[datetime] = None
    ) -> None:
        """
        Attempts SMS fallback for target emergency contacts when offline.
        Strict rule: Never pretend delivery succeeded if provider failed or was unavailable!
        """
        now = current_time or datetime.now(timezone.utc)
        target_contacts = self.emergency_orchestrator.contact_service.get_contacts_for_journey(
            journey_id=incident.journey_id,
            escalation_level=incident.escalation_level
        )

        if not target_contacts:
            logger.warning(f"[OfflineGuardian] No contacts found for SMS fallback for incident {incident.incident_id}")
            return

        sms_results: List[NotificationDeliveryResult] = []
        any_sent = False

        for c in target_contacts:
            phone = getattr(c, "phone_number", None) or c.destination
            loc_lat = incident.context.current_lat if incident.context else None
            loc_lng = incident.context.current_lng if incident.context else None
            sms_res = self.sms_provider.send_sms(
                incident_id=incident.incident_id,
                recipient=phone,
                message=f"STREEVA EMERGENCY ALERT for Journey {incident.journey_id}. Location: {loc_lat},{loc_lng}",
                payload={"incident_id": incident.incident_id}
            )

            # Buffer notification attempt
            self.event_buffer.buffer_event(
                journey_id=incident.journey_id,
                event_type=BufferedEventType.NOTIFICATION_ATTEMPT,
                payload={
                    "incident_id": incident.incident_id,
                    "recipient": phone,
                    "status": sms_res.status.value,
                    "error": sms_res.error_message
                },
                source_timestamp=now
            )

            success = (sms_res.status == SMSDeliveryStatus.SENT)
            if success:
                any_sent = True

            sms_results.append(NotificationDeliveryResult(
                contact_id=c.contact_id,
                destination=phone,
                success=success,
                delivered_at=sms_res.delivered_at,
                error_message=sms_res.error_message
            ))

        incident.delivery_results = sms_results
        incident.notifications_attempted = len(sms_results)

        if any_sent:
            incident.state = EmergencyState.NOTIFIED
            incident.notifications_delivered = sum(1 for r in sms_results if r.success)
        else:
            incident.state = EmergencyState.FAILED
            incident.notifications_delivered = 0

        # Persist updated incident
        self.emergency_orchestrator.persistence.save_incident(incident)

    def cancel_emergency(
        self,
        incident_id: str,
        reason: str = "User cancelled locally",
        current_time: Optional[datetime] = None
    ) -> EmergencyIncident:
        """
        Cancels the active emergency incident locally.
        Guarantees no false notifications are marked delivered.
        """
        now = current_time or datetime.now(timezone.utc)
        incident = self.emergency_orchestrator.cancel_incident(
            incident_id=incident_id,
            reason=reason,
            current_time=now
        )

        self.event_buffer.buffer_event(
            journey_id=incident.journey_id,
            event_type=BufferedEventType.EMERGENCY_STATE_CHANGE,
            payload={"incident_id": incident_id, "state": incident.state.value, "reason": reason},
            source_timestamp=now
        )
        return incident

    # --------------------------------------------------------------------------
    # 5. Reconnection & Reconciliation
    # --------------------------------------------------------------------------

    def reconcile(self, simulate_partial_failure: bool = False) -> ReconciliationSummary:
        """
        Executes reconnection reconciliation.
        Transitions state to RECONNECTING, reconciles events in strict sequence order,
        and transitions to ONLINE (or DEGRADED if partial sync failure occurs).
        """
        # Move to RECONNECTING if currently OFFLINE
        if self.connectivity.is_offline:
            self.set_connectivity(ConnectivityState.RECONNECTING, reason="Reconnection sync initiated")

        summary = self.reconciliation_service.reconcile(
            event_buffer=self.event_buffer,
            simulate_partial_failure=simulate_partial_failure
        )

        if summary.events_failed == 0:
            self.set_connectivity(ConnectivityState.ONLINE, reason="Reconnection sync completed successfully")
            self.connectivity.record_successful_sync()
        else:
            self.set_connectivity(ConnectivityState.DEGRADED, reason=f"Sync partially completed: {summary.events_failed} failed")

        return summary

    # --------------------------------------------------------------------------
    # 6. Persistence & Process Restart Recovery
    # --------------------------------------------------------------------------

    def restore_from_persistence(self, journey_id: Optional[str] = None) -> Optional[CachedJourneyContext]:
        """
        Restores offline guardian state from SQLite after a process restart.
        Restores cached journey, event buffer sequence, and active incident continuity.
        """
        cached = self.persistence.load_cached_journey(journey_id=journey_id)
        if not cached:
            return None

        self.journey_cache.set_context(cached)

        # Restore monitor context if journey is active
        if cached.journey_state == "ACTIVE":
            start_req = JourneyStartRequest(
                journey_id=cached.journey_id,
                source_lat=cached.source_lat or 0.0,
                source_lng=cached.source_lng or 0.0,
                destination_lat=cached.dest_lat or 0.0,
                destination_lng=cached.dest_lng or 0.0,
                expected_route=cached.expected_route,
                timestamp=cached.last_snapshot_timestamp
            )
            self.monitor.start_journey(start_req)

        # Re-initialize event buffer from persistence
        self.event_buffer = LocalEventBuffer(
            persistence_manager=self.persistence,
            max_size=self.config.max_buffered_events
        )

        logger.info(f"[OfflineGuardian] Successfully restored state for journey {cached.journey_id} from SQLite.")
        return cached

    # --------------------------------------------------------------------------
    # 7. Summary & Diagnostics
    # --------------------------------------------------------------------------

    def get_status_summary(self) -> Dict[str, Any]:
        """Returns diagnostic summary of Offline Guardian state."""
        ctx = self.journey_cache.get_context()
        conn = self.connectivity.get_status()
        pending = self.event_buffer.get_pending_events()

        return {
            "connectivity": conn.model_dump(),
            "has_active_journey": self.journey_cache.has_active_journey,
            "journey_id": ctx.journey_id if ctx else None,
            "journey_state": ctx.journey_state if ctx else None,
            "location_quality": ctx.telemetry_quality if ctx else None,
            "total_buffered_events": self.event_buffer.total_count,
            "pending_buffered_events": len(pending),
            "sequence_number": self.event_buffer.current_sequence,
            "active_incident_id": ctx.active_incident_id if ctx else None,
            "sms_provider_mode": getattr(self.sms_provider, "mode", "UNKNOWN")
        }

    def reset(self) -> None:
        """Resets all in-memory and database state (for testing)."""
        self.connectivity.reset()
        self.journey_cache.clear()
        self.event_buffer.clear()
        self.monitor.reset()
        self.emergency_orchestrator.reset_all()
        self.persistence.clear_all()
        self._last_decision = None
