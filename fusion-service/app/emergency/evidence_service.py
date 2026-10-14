"""
STREEVA — Phase 4 Autonomous Emergency Response System
app/emergency/evidence_service.py

Secure Evidence Package Service:
- Compiles verifiable evidence artifacts from real telemetry, edge events, and risk assessments.
- Strict invariant: NEVER invents synthetic audio recordings or raw sensor data.
- Computes cryptographic SHA-256 hash for audit integrity.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from .schemas import (
    EmergencyIncident,
    EvidenceItem,
    EvidencePackage,
    EvidenceType
)
from ..guardian.journey_state import GuardianSnapshot
from ..contextual.schemas import JourneyRiskAssessment


class EvidenceService:
    """
    Compiles verifiable, structured evidence packages for emergency incidents.
    """

    def __init__(self, hash_algorithm: str = "sha256"):
        self.hash_algorithm = hash_algorithm
        # incident_id -> EvidencePackage
        self._packages: Dict[str, EvidencePackage] = {}

    def compile_evidence_package(
        self,
        incident: EmergencyIncident,
        snapshot: Optional[GuardianSnapshot] = None,
        assessment: Optional[JourneyRiskAssessment] = None
    ) -> EvidencePackage:
        now = datetime.now(timezone.utc)
        items: List[EvidenceItem] = []

        # 1. Trigger Incident Evidence
        items.append(EvidenceItem(
            evidence_id=f"ev_trig_{uuid.uuid4().hex[:8]}",
            incident_id=incident.incident_id,
            type=EvidenceType.RESPONSE_EVENT,
            timestamp=incident.triggered_at,
            source="EMERGENCY_ORCHESTRATOR",
            metadata={
                "trigger_type": incident.trigger_type.value,
                "risk_score": incident.risk_score,
                "risk_level": incident.risk_level,
                "decision_tier": incident.decision_tier,
                "initial_state": incident.state.value
            },
            payload_summary=f"Emergency response initiated via {incident.trigger_type.value} with initial tier {incident.decision_tier}."
        ))

        # 2. Extract real events from GuardianSnapshot if available
        if snapshot is not None:
            # Telemetry snapshot
            items.append(EvidenceItem(
                evidence_id=f"ev_telem_{uuid.uuid4().hex[:8]}",
                incident_id=incident.incident_id,
                type=EvidenceType.TELEMETRY,
                timestamp=snapshot.timestamp or now,
                source="GUARDIAN_TELEMETRY",
                metadata={
                    "lat": snapshot.current_lat,
                    "lng": snapshot.current_lng,
                    "accuracy": snapshot.gps_accuracy,
                    "quality": snapshot.telemetry_quality.value,
                    "speed_mps": snapshot.smoothed_speed_mps
                },
                payload_summary=f"Position ({snapshot.current_lat}, {snapshot.current_lng}) with {snapshot.telemetry_quality.value} telemetry quality."
            ))

            # Journey context
            items.append(EvidenceItem(
                evidence_id=f"ev_ctx_{uuid.uuid4().hex[:8]}",
                incident_id=incident.incident_id,
                type=EvidenceType.JOURNEY_CONTEXT,
                timestamp=snapshot.timestamp or now,
                source="GUARDIAN_JOURNEY",
                metadata={
                    "journey_id": snapshot.journey_id,
                    "journey_state": snapshot.journey_state.value,
                    "progress_status": snapshot.progress_status.value,
                    "route_progress_percent": snapshot.route_progress_percent,
                    "remaining_distance_m": snapshot.remaining_distance_m
                },
                payload_summary=f"Journey in state {snapshot.journey_state.value} at {snapshot.route_progress_percent}% route progress."
            ))

            # Route Deviation
            if snapshot.route_deviation is not None:
                items.append(EvidenceItem(
                    evidence_id=f"ev_rd_{uuid.uuid4().hex[:8]}",
                    incident_id=incident.incident_id,
                    type=EvidenceType.ROUTE_DEVIATION_EVENT,
                    timestamp=snapshot.route_deviation.timestamp or now,
                    source="ROUTE_DEVIATION_DETECTOR",
                    metadata=snapshot.route_deviation.model_dump(mode="json"),
                    payload_summary=f"Route deviation status {snapshot.route_deviation.state} with confidence {snapshot.route_deviation.confidence}."
                ))

            # Unexpected Stop
            if snapshot.unexpected_stop is not None:
                items.append(EvidenceItem(
                    evidence_id=f"ev_us_{uuid.uuid4().hex[:8]}",
                    incident_id=incident.incident_id,
                    type=EvidenceType.UNEXPECTED_STOP_EVENT,
                    timestamp=snapshot.unexpected_stop.timestamp or now,
                    source="UNEXPECTED_STOP_DETECTOR",
                    metadata=snapshot.unexpected_stop.model_dump(mode="json"),
                    payload_summary=f"Unexpected stop status {snapshot.unexpected_stop.state} (duration {snapshot.unexpected_stop.stationary_duration_s}s)."
                ))

            # Kinematic Fall
            if snapshot.fall_event is not None:
                items.append(EvidenceItem(
                    evidence_id=f"ev_fall_{uuid.uuid4().hex[:8]}",
                    incident_id=incident.incident_id,
                    type=EvidenceType.FALL_EVENT,
                    timestamp=snapshot.fall_event.timestamp or now,
                    source="FALL_DETECTOR",
                    metadata=snapshot.fall_event.model_dump(mode="json"),
                    payload_summary=f"Kinematic fall status {snapshot.fall_event.state} with peak impact {snapshot.fall_event.impact_magnitude_g}g."
                ))

            # Audio Distress (metadata only — no raw fabricated audio!)
            if snapshot.audio_distress is not None:
                items.append(EvidenceItem(
                    evidence_id=f"ev_audio_{uuid.uuid4().hex[:8]}",
                    incident_id=incident.incident_id,
                    type=EvidenceType.AUDIO_DISTRESS_EVENT,
                    timestamp=snapshot.audio_distress.timestamp or now,
                    source="AUDIO_DISTRESS_DETECTOR",
                    metadata=snapshot.audio_distress.model_dump(mode="json"),
                    payload_summary=f"Audio distress status {snapshot.audio_distress.state} with model distress score {snapshot.audio_distress.distress_score}."
                ))

        # 3. Contextual Risk Assessment
        if assessment is not None:
            items.append(EvidenceItem(
                evidence_id=f"ev_risk_{uuid.uuid4().hex[:8]}",
                incident_id=incident.incident_id,
                type=EvidenceType.RISK_ASSESSMENT,
                timestamp=assessment.timestamp or now,
                source="CONTEXTUAL_RISK_ENGINE",
                metadata={
                    "risk_score": assessment.risk_score,
                    "risk_level": assessment.risk_level.value,
                    "overall_confidence": assessment.overall_confidence,
                    "dominant_factor": assessment.dominant_factor,
                    "active_factors": [f.model_dump(mode="json") for f in assessment.active_factors]
                },
                payload_summary=f"Risk score {assessment.risk_score}/100 ({assessment.risk_level.value}) dominant: {assessment.dominant_factor}."
            ))

        # 4. Compute cryptographic integrity hash
        serialized_evidence = json.dumps([item.model_dump(mode="json") for item in items], sort_keys=True)
        integrity_hash = hashlib.sha256(serialized_evidence.encode("utf-8")).hexdigest()

        package = EvidencePackage(
            package_id=f"evpkg_{uuid.uuid4().hex[:12]}",
            incident_id=incident.incident_id,
            compiled_at=now,
            items=items,
            integrity_hash=integrity_hash
        )

        self._packages[incident.incident_id] = package
        return package

    def get_package(self, incident_id: str) -> Optional[EvidencePackage]:
        return self._packages.get(incident_id)

    def clear(self):
        self._packages.clear()
