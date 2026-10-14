"""
STREEVA — Phase 5 Offline Guardian & Connectivity Resilience
app/offline/persistence.py

SQLAlchemy SQLite persistence models and manager for:
- Offline buffered events (durable append-only buffer)
- Cached journey context (survives app/process restart)
- Connectivity transition audit log
"""

from datetime import datetime, timezone
import json
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, String, Float, Integer, DateTime, Text, create_engine
from sqlalchemy.orm import Session

from ..db.database import Base, SessionLocal, engine
from .schemas import (
    BufferedEvent,
    BufferedEventType,
    SyncStatus,
    CachedJourneyContext,
    ConnectivityState,
    ConnectivityInfo
)


class OfflineEventDB(Base):
    """SQLAlchemy model for offline buffered events."""
    __tablename__ = "offline_buffered_events"

    event_id = Column(String, primary_key=True, index=True)
    journey_id = Column(String, index=True)
    event_type = Column(String, index=True)
    payload_json = Column(Text)
    created_at = Column(DateTime)
    source_timestamp = Column(DateTime)
    sequence_number = Column(Integer, index=True)
    sync_status = Column(String, index=True)
    retry_count = Column(Integer, default=0)
    last_attempt_at = Column(DateTime, nullable=True)


class CachedJourneyDB(Base):
    """SQLAlchemy model for locally cached journey state."""
    __tablename__ = "cached_journeys"

    journey_id = Column(String, primary_key=True, index=True)
    journey_state = Column(String)
    source_lat = Column(Float, nullable=True)
    source_lng = Column(Float, nullable=True)
    dest_lat = Column(Float, nullable=True)
    dest_lng = Column(Float, nullable=True)
    expected_route_json = Column(Text, nullable=True)
    route_progress_percent = Column(Float, default=0.0)
    remaining_distance_m = Column(Float, default=0.0)
    eta = Column(DateTime, nullable=True)
    eta_source = Column(String, default="UNAVAILABLE")
    last_trusted_lat = Column(Float, nullable=True)
    last_trusted_lng = Column(Float, nullable=True)
    location_accuracy = Column(Float, nullable=True)
    telemetry_quality = Column(String, default="VALID")
    last_snapshot_timestamp = Column(DateTime, nullable=True)
    active_sensor_policy = Column(String, default="MEDIUM")
    latest_risk_score = Column(Float, nullable=True)
    latest_risk_level = Column(String, nullable=True)
    latest_decision_tier = Column(String, nullable=True)
    active_incident_id = Column(String, nullable=True)
    updated_at = Column(DateTime)


class ConnectivityHistoryDB(Base):
    """SQLAlchemy model for network connectivity state transitions."""
    __tablename__ = "connectivity_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    state = Column(String, index=True)
    changed_at = Column(DateTime)
    reason = Column(Text)


# Create tables if not exist
Base.metadata.create_all(bind=engine)


class OfflinePersistenceManager:
    """
    Manages SQLite persistence for offline resilience data:
    events, cached journey, and connectivity history.
    """

    def __init__(self, session_factory=SessionLocal):
        self._session_factory = session_factory

    def save_buffered_event(self, event: BufferedEvent, db: Optional[Session] = None) -> None:
        """Persists a buffered event."""
        should_close = False
        if db is None:
            db = self._session_factory()
            should_close = True

        try:
            record = db.query(OfflineEventDB).filter(OfflineEventDB.event_id == event.event_id).first()
            if not record:
                record = OfflineEventDB(
                    event_id=event.event_id,
                    journey_id=event.journey_id,
                    event_type=event.event_type.value,
                    payload_json=json.dumps(event.payload),
                    created_at=event.created_at,
                    source_timestamp=event.source_timestamp,
                    sequence_number=event.sequence_number,
                    sync_status=event.sync_status.value,
                    retry_count=event.retry_count,
                    last_attempt_at=event.last_attempt_at
                )
                db.add(record)
            else:
                record.sync_status = event.sync_status.value
                record.retry_count = event.retry_count
                record.last_attempt_at = event.last_attempt_at
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            if should_close:
                db.close()

    def get_buffered_events(
        self,
        journey_id: Optional[str] = None,
        sync_status: Optional[SyncStatus] = None,
        db: Optional[Session] = None
    ) -> List[BufferedEvent]:
        """Retrieves buffered events ordered by sequence_number ascending."""
        should_close = False
        if db is None:
            db = self._session_factory()
            should_close = True

        try:
            query = db.query(OfflineEventDB)
            if journey_id:
                query = query.filter(OfflineEventDB.journey_id == journey_id)
            if sync_status:
                query = query.filter(OfflineEventDB.sync_status == sync_status.value)
            records = query.order_by(OfflineEventDB.sequence_number.asc()).all()

            result = []
            for r in records:
                result.append(BufferedEvent(
                    event_id=r.event_id,
                    journey_id=r.journey_id,
                    event_type=BufferedEventType(r.event_type),
                    payload=json.loads(r.payload_json) if r.payload_json else {},
                    created_at=r.created_at,
                    source_timestamp=r.source_timestamp,
                    sequence_number=r.sequence_number,
                    sync_status=SyncStatus(r.sync_status),
                    retry_count=r.retry_count,
                    last_attempt_at=r.last_attempt_at
                ))
            return result
        finally:
            if should_close:
                db.close()

    def save_cached_journey(self, context: CachedJourneyContext, db: Optional[Session] = None) -> None:
        """Persists or updates cached journey context."""
        should_close = False
        if db is None:
            db = self._session_factory()
            should_close = True

        try:
            record = db.query(CachedJourneyDB).filter(CachedJourneyDB.journey_id == context.journey_id).first()
            if not record:
                record = CachedJourneyDB(journey_id=context.journey_id)
                db.add(record)

            record.journey_state = context.journey_state
            record.source_lat = context.source_lat
            record.source_lng = context.source_lng
            record.dest_lat = context.dest_lat
            record.dest_lng = context.dest_lng
            record.expected_route_json = json.dumps(context.expected_route)
            record.route_progress_percent = context.route_progress_percent
            record.remaining_distance_m = context.remaining_distance_m
            record.eta = context.eta
            record.eta_source = context.eta_source
            record.last_trusted_lat = context.last_trusted_lat
            record.last_trusted_lng = context.last_trusted_lng
            record.location_accuracy = context.location_accuracy
            record.telemetry_quality = context.telemetry_quality
            record.last_snapshot_timestamp = context.last_snapshot_timestamp
            record.active_sensor_policy = context.active_sensor_policy
            record.latest_risk_score = context.latest_risk_score
            record.latest_risk_level = context.latest_risk_level
            record.latest_decision_tier = context.latest_decision_tier
            record.active_incident_id = context.active_incident_id
            record.updated_at = datetime.now(timezone.utc)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            if should_close:
                db.close()

    def load_cached_journey(self, journey_id: Optional[str] = None, db: Optional[Session] = None) -> Optional[CachedJourneyContext]:
        """Loads cached journey. If journey_id is None, returns the most recently updated active journey."""
        should_close = False
        if db is None:
            db = self._session_factory()
            should_close = True

        try:
            query = db.query(CachedJourneyDB)
            if journey_id:
                record = query.filter(CachedJourneyDB.journey_id == journey_id).first()
            else:
                record = query.order_by(CachedJourneyDB.updated_at.desc()).first()

            if not record:
                return None

            return CachedJourneyContext(
                journey_id=record.journey_id,
                journey_state=record.journey_state,
                source_lat=record.source_lat,
                source_lng=record.source_lng,
                dest_lat=record.dest_lat,
                dest_lng=record.dest_lng,
                expected_route=json.loads(record.expected_route_json) if record.expected_route_json else [],
                route_progress_percent=record.route_progress_percent,
                remaining_distance_m=record.remaining_distance_m,
                eta=record.eta,
                eta_source=record.eta_source,
                last_trusted_lat=record.last_trusted_lat,
                last_trusted_lng=record.last_trusted_lng,
                location_accuracy=record.location_accuracy,
                telemetry_quality=record.telemetry_quality,
                last_snapshot_timestamp=record.last_snapshot_timestamp,
                active_sensor_policy=record.active_sensor_policy,
                latest_risk_score=record.latest_risk_score,
                latest_risk_level=record.latest_risk_level,
                latest_decision_tier=record.latest_decision_tier,
                active_incident_id=record.active_incident_id
            )
        finally:
            if should_close:
                db.close()

    def record_connectivity_transition(self, state: ConnectivityState, reason: str, db: Optional[Session] = None) -> None:
        """Logs connectivity transition in SQLite."""
        should_close = False
        if db is None:
            db = self._session_factory()
            should_close = True

        try:
            record = ConnectivityHistoryDB(
                state=state.value,
                changed_at=datetime.now(timezone.utc),
                reason=reason
            )
            db.add(record)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            if should_close:
                db.close()

    def clear_all(self, db: Optional[Session] = None) -> None:
        """Clears all offline tables (for testing)."""
        should_close = False
        if db is None:
            db = self._session_factory()
            should_close = True

        try:
            db.query(OfflineEventDB).delete()
            db.query(CachedJourneyDB).delete()
            db.query(ConnectivityHistoryDB).delete()
            db.commit()
        finally:
            if should_close:
                db.close()
