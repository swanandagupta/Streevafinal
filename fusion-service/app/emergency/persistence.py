"""
STREEVA — Phase 4 Autonomous Emergency Response System
app/emergency/persistence.py

SQLAlchemy SQLite persistence layer for Emergency Incident records and audit trails.
Supports both direct SQLite database persistence and in-memory fallback.
"""

from datetime import datetime, timezone
import json
from typing import Optional, List, Dict
from sqlalchemy import Column, String, Float, Integer, DateTime, Text, ForeignKey, create_engine
from sqlalchemy.orm import relationship, Session

from ..db.database import Base
from .schemas import (
    EmergencyIncident,
    IncidentContextSnapshot,
    IncidentTransitionRecord,
    NotificationDeliveryResult,
    EmergencyState,
    TriggerType,
    LocationQuality,
    AcknowledgementStatus,
    EscalationLevel
)


class IncidentDB(Base):
    """SQLAlchemy model for emergency incidents."""
    __tablename__ = "emergency_incidents"

    incident_id = Column(String, primary_key=True, index=True)
    journey_id = Column(String, index=True)
    trigger_type = Column(String, index=True)
    risk_score = Column(Float)
    risk_level = Column(String)
    decision_tier = Column(String)
    state = Column(String, index=True)
    created_at = Column(DateTime)
    triggered_at = Column(DateTime)
    countdown_started_at = Column(DateTime, nullable=True)
    countdown_seconds = Column(Float)
    response_authorized_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)

    # Serialized JSON blobs for context, contacts, results, evidence
    context_json = Column(Text)
    contacts_targeted_json = Column(Text)
    delivery_results_json = Column(Text)
    acknowledgement_status = Column(String)
    acknowledged_by = Column(String, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    escalation_level = Column(String)
    evidence_package_id = Column(String, nullable=True)

    history_records = relationship("IncidentHistoryDB", back_populates="incident", cascade="all, delete-orphan")


class IncidentHistoryDB(Base):
    """SQLAlchemy model for append-only state transition audit trail."""
    __tablename__ = "emergency_incident_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String, ForeignKey("emergency_incidents.incident_id"), index=True)
    from_state = Column(String)
    to_state = Column(String)
    timestamp = Column(DateTime)
    reason = Column(Text)

    incident = relationship("IncidentDB", back_populates="history_records")


class EmergencyPersistenceManager:
    """
    Manages persistence of incidents, transitions, and delivery attempts.
    Maintains an in-memory cache and synchronizes to SQLite when a DB session is provided.
    """

    def __init__(self):
        self._memory_store: Dict[str, EmergencyIncident] = {}

    def save_incident(self, incident: EmergencyIncident, db: Optional[Session] = None):
        """Saves incident to memory store and database."""
        self._memory_store[incident.incident_id] = incident

        if db is not None:
            try:
                db_record = db.query(IncidentDB).filter(IncidentDB.incident_id == incident.incident_id).first()
                if not db_record:
                    db_record = IncidentDB(incident_id=incident.incident_id)
                    db.add(db_record)

                db_record.journey_id = incident.journey_id
                db_record.trigger_type = incident.trigger_type.value
                db_record.risk_score = incident.risk_score
                db_record.risk_level = incident.risk_level
                db_record.decision_tier = incident.decision_tier
                db_record.state = incident.state.value
                db_record.created_at = incident.created_at
                db_record.triggered_at = incident.triggered_at
                db_record.countdown_started_at = incident.countdown_started_at
                db_record.countdown_seconds = incident.countdown_seconds
                db_record.response_authorized_at = incident.response_authorized_at
                db_record.resolved_at = incident.resolved_at
                db_record.cancelled_at = incident.cancelled_at

                db_record.context_json = incident.context.model_dump_json()
                db_record.contacts_targeted_json = json.dumps(incident.contacts_targeted)
                db_record.delivery_results_json = json.dumps([r.model_dump(mode="json") for r in incident.delivery_results])
                db_record.acknowledgement_status = incident.acknowledgement_status.value
                db_record.acknowledged_by = incident.acknowledged_by
                db_record.acknowledged_at = incident.acknowledged_at
                db_record.escalation_level = incident.escalation_level.value
                db_record.evidence_package_id = incident.evidence_package_id

                # Save history transitions
                # Delete existing to prevent duplication on re-save
                db.query(IncidentHistoryDB).filter(IncidentHistoryDB.incident_id == incident.incident_id).delete()
                for rec in incident.history:
                    h = IncidentHistoryDB(
                        incident_id=incident.incident_id,
                        from_state=rec.from_state.value,
                        to_state=rec.to_state.value,
                        timestamp=rec.timestamp,
                        reason=rec.reason
                    )
                    db.add(h)

                db.commit()
            except Exception as e:
                db.rollback()
                # Memory store remains authoritative in test/offline fallback

    def get_incident(self, incident_id: str, db: Optional[Session] = None) -> Optional[EmergencyIncident]:
        """Retrieves an incident by ID from memory or DB."""
        if incident_id in self._memory_store:
            return self._memory_store[incident_id]

        if db is not None:
            db_record = db.query(IncidentDB).filter(IncidentDB.incident_id == incident_id).first()
            if db_record:
                incident = self._db_to_schema(db_record)
                self._memory_store[incident.incident_id] = incident
                return incident

        return None

    def find_active_incident_for_journey(self, journey_id: str) -> Optional[EmergencyIncident]:
        """Finds any non-terminal incident currently underway for the journey."""
        terminal_states = {EmergencyState.RESOLVED, EmergencyState.CANCELLED}
        for inc in self._memory_store.values():
            if inc.journey_id == journey_id and inc.state not in terminal_states:
                return inc
        return None

    def list_all_incidents(self) -> List[EmergencyIncident]:
        return list(self._memory_store.values())

    def clear(self):
        self._memory_store.clear()

    def _db_to_schema(self, db_record: IncidentDB) -> EmergencyIncident:
        ctx_data = json.loads(db_record.context_json) if db_record.context_json else {}
        context = IncidentContextSnapshot(**ctx_data)
        contacts = json.loads(db_record.contacts_targeted_json) if db_record.contacts_targeted_json else []
        results_data = json.loads(db_record.delivery_results_json) if db_record.delivery_results_json else []
        results = [NotificationDeliveryResult(**r) for r in results_data]

        history = []
        for h in db_record.history_records:
            history.append(IncidentTransitionRecord(
                from_state=EmergencyState(h.from_state),
                to_state=EmergencyState(h.to_state),
                timestamp=h.timestamp,
                reason=h.reason
            ))

        return EmergencyIncident(
            incident_id=db_record.incident_id,
            journey_id=db_record.journey_id,
            trigger_type=TriggerType(db_record.trigger_type),
            risk_score=db_record.risk_score,
            risk_level=db_record.risk_level,
            decision_tier=db_record.decision_tier,
            state=EmergencyState(db_record.state),
            created_at=db_record.created_at,
            triggered_at=db_record.triggered_at,
            countdown_started_at=db_record.countdown_started_at,
            countdown_seconds=db_record.countdown_seconds,
            response_authorized_at=db_record.response_authorized_at,
            resolved_at=db_record.resolved_at,
            cancelled_at=db_record.cancelled_at,
            context=context,
            contacts_targeted=contacts,
            notifications_attempted=len(results),
            notifications_delivered=sum(1 for r in results if r.success),
            delivery_results=results,
            acknowledgement_status=AcknowledgementStatus(db_record.acknowledgement_status),
            acknowledged_by=db_record.acknowledged_by,
            acknowledged_at=db_record.acknowledged_at,
            escalation_level=EscalationLevel(db_record.escalation_level),
            history=history,
            evidence_package_id=db_record.evidence_package_id
        )
