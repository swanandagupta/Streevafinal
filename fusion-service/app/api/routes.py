import os
import httpx
import asyncio
import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from ..db import database, models
from .. import schemas
from ..ml.motion_model import ActivityStateClassifier
from ..scoring.fusion_scorer import RiskFusionScorer
from ..edge.route_deviation import RouteDeviationDetector
from ..edge.unexpected_stop import UnexpectedStopDetector
from ..edge.fall_detection import FallDetector
from ..edge.audio_distress import AudioDistressDetector
from ..guardian.monitor import GuardianMonitor
from ..contextual import (
    ContextualRiskFusionEngine,
    DecisionEngine,
    AdaptiveSensorManager,
    ContextualSafetyRequest,
    ContextualSafetyResponse,
    DecisionRequest,
    SensorPolicyRequest
)
from ..emergency import EmergencyResponseOrchestrator
from ..offline import (
    OfflineGuardian,
    ConnectivityState,
    InvalidConnectivityTransitionError,
    UpdateConnectivityRequest,
    ReconcileRequest,
    SMSTestRequest
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize ML model, Scorer, Edge Detectors, Guardian Orchestrator, Phase 3 Engines, Phase 4 Orchestrator, Phase 5 Offline Guardian
motion_model = ActivityStateClassifier()
fusion_scorer = RiskFusionScorer()
route_deviation_detector = RouteDeviationDetector()
unexpected_stop_detector = UnexpectedStopDetector()
fall_detector = FallDetector()
audio_distress_detector = AudioDistressDetector()
guardian_monitor = GuardianMonitor()

contextual_fusion_engine = ContextualRiskFusionEngine()
decision_engine = DecisionEngine()
adaptive_sensor_manager = AdaptiveSensorManager()

emergency_orchestrator = EmergencyResponseOrchestrator()
offline_guardian = OfflineGuardian(
    monitor=guardian_monitor,
    fusion_engine=contextual_fusion_engine,
    decision_engine=decision_engine,
    emergency_orchestrator=emergency_orchestrator
)

AREA_RISK_URL = os.getenv("AREA_RISK_URL", "http://localhost:8000/area-risk")


@router.post("/log-trip", status_code=201)
def log_trip(trip: schemas.TripCreate, db: Session = Depends(database.get_db)):
    """
    Saves a real sensor-logged trip from the logger tool into SQLite.
    """
    db_trip = models.Trip(
        id=trip.trip_id,
        label=trip.label,
        start_time=trip.start_time,
        end_time=trip.end_time
    )
    db.add(db_trip)
    
    db_points = [
        models.TripPoint(
            trip_id=trip.trip_id,
            timestamp=p.timestamp,
            lat=p.lat,
            lng=p.lng,
            accel_x=p.accel_x,
            accel_y=p.accel_y,
            accel_z=p.accel_z,
            accuracy=getattr(p, "accuracy", None),
            gyro_x=getattr(p, "gyro_x", None),
            gyro_y=getattr(p, "gyro_y", None),
            gyro_z=getattr(p, "gyro_z", None)
        ) for p in trip.points
    ]
    db.bulk_save_objects(db_points)
    db.commit()
    
    return {"message": f"Successfully logged trip {trip.trip_id} with {len(db_points)} points."}


# --- Edge AI: Phase 1A Route Deviation ---
@router.post("/route-deviation/evaluate", response_model=schemas.RouteDeviationEvent)
def evaluate_route_deviation(request: schemas.RouteDeviationRequest):
    """
    Evaluates a single GPS observation against an expected route polyline.
    Emits a structured RouteDeviationEvent with cross-track distance, state machine status,
    and heuristic confidence.
    """
    event = route_deviation_detector.detect(
        current_position=request.current_position.model_dump(),
        route_polyline=[p.model_dump() for p in request.route_polyline],
        gps_accuracy=request.gps_accuracy,
        timestamp=request.timestamp
    )
    return event


@router.post("/route-deviation/reset")
def reset_route_deviation():
    """Resets the route deviation state machine to NORMAL."""
    route_deviation_detector.reset()
    return {"status": "reset", "state": route_deviation_detector.current_state.value}


# --- Edge AI: Phase 1B Unexpected Stop ---
@router.post("/edge/unexpected-stop/evaluate", response_model=schemas.UnexpectedStopEvent)
def evaluate_unexpected_stop(request: schemas.UnexpectedStopRequest):
    """
    Evaluates a GPS position against movement history for unexpected stopping.
    """
    event = unexpected_stop_detector.detect(
        current_position=request.current_position.model_dump(),
        timestamp=request.timestamp,
        gps_accuracy=request.gps_accuracy,
        journey_active=request.journey_active
    )
    return event


@router.post("/edge/unexpected-stop/reset")
def reset_unexpected_stop():
    """Resets the unexpected stop detector to MOVING."""
    unexpected_stop_detector.reset()
    return {"status": "reset", "state": unexpected_stop_detector.current_state.value}


# --- Edge AI: Phase 1C Gyroscope / Fall Detection ---
@router.post("/edge/fall/evaluate", response_model=schemas.FallDetectedEvent)
def evaluate_fall_detection(request: schemas.FallDetectionRequest):
    """
    Evaluates an inertial frame for impact spikes, orientation shifts, and post-impact stillness.
    """
    event = fall_detector.detect(
        accel_x=request.accel_x,
        accel_y=request.accel_y,
        accel_z=request.accel_z,
        gyro_x=request.gyro_x,
        gyro_y=request.gyro_y,
        gyro_z=request.gyro_z,
        timestamp=request.timestamp,
        latitude=request.latitude,
        longitude=request.longitude
    )
    return event


@router.post("/edge/fall/reset")
def reset_fall_detector():
    """Resets the fall detector to NORMAL."""
    fall_detector.reset()
    return {"status": "reset", "state": fall_detector.current_state.value}


# --- Edge AI: Phase 1D Distress Audio Detection ---
@router.post("/edge/audio/evaluate", response_model=schemas.AudioDistressEvent)
def evaluate_audio_distress(request: schemas.AudioDistressRequest):
    """
    Evaluates an audio window (PCM samples, base64 PCM, or filepath) for distress vocalizations.
    Applies Log-Mel feature extraction, TFLite lightweight classification, and temporal smoothing.
    """
    event = audio_distress_detector.process_audio_window(
        audio_data=request.audio_samples,
        base64_audio=request.base64_audio,
        file_path=request.file_path,
        sample_rate=request.sample_rate,
        timestamp=request.timestamp
    )
    return event


@router.post("/edge/audio/reset")
def reset_audio_detector():
    """Resets the audio distress detector to NORMAL."""
    audio_distress_detector.reset()
    return {"status": "reset", "state": audio_distress_detector.current_state.value}


# --- Guardian Journey Intelligence (Phase 2) ---
@router.post("/guardian/journey/start", response_model=schemas.GuardianSnapshot)
def start_guardian_journey(request: schemas.JourneyStartRequest):
    """
    Initializes an active traveler journey with source, destination, and expected polyline.
    Cleans previous state and sets journey_state to STARTING.
    """
    return guardian_monitor.start_journey(request)


@router.post("/guardian/journey/update", response_model=schemas.GuardianSnapshot)
def update_guardian_journey(request: schemas.JourneyUpdateRequest):
    """
    Ingests live telemetry for an active journey.
    Updates route progress, stabilized ETA, evaluates Edge AI anomalies, and yields GuardianSnapshot.
    """
    try:
        return guardian_monitor.update_telemetry(request)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/guardian/journey/end", response_model=schemas.GuardianSnapshot)
def end_guardian_journey(request: schemas.JourneyEndRequest):
    """
    Explicitly ends or cancels an active journey.
    """
    try:
        return guardian_monitor.end_journey(request)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/guardian/journey/reset")
def reset_guardian_journey():
    """
    Completely resets the Guardian monitor and all underlying Edge detectors.
    """
    guardian_monitor.reset()
    return {"status": "reset", "state": "IDLE"}


@router.get("/guardian/journey/{journey_id}", response_model=schemas.GuardianSnapshot)
def get_guardian_journey_snapshot(journey_id: str):
    """
    Retrieves the latest GuardianSnapshot for the specified journey.
    """
    try:
        return guardian_monitor.get_snapshot(journey_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- Contextual Safety Intelligence (Phase 3) ---

@router.post("/contextual-safety/evaluate", response_model=schemas.ContextualSafetyResponse)
def evaluate_contextual_safety(request: schemas.ContextualSafetyRequest):
    """
    Evaluates unified Risk Fusion 2.0, Decision Engine tier, and Adaptive Sensor Policy.
    NOTE: Prescribes decision tier and policy only; does NOT trigger emergency dispatch.
    """
    assessment = contextual_fusion_engine.evaluate_risk(
        snapshot=request.snapshot,
        area_risk_score=request.area_risk_score,
        area_risk_confidence=request.area_risk_confidence or 1.0,
        motion_anomaly_score=request.motion_anomaly_score
    )
    decision = decision_engine.evaluate(assessment)
    policy = adaptive_sensor_manager.generate_policy(
        decision=decision,
        battery=request.battery,
        network=request.network
    )
    assessment.decision = decision
    assessment.sensor_policy = policy
    return schemas.ContextualSafetyResponse(
        assessment=assessment,
        decision=decision,
        sensor_policy=policy
    )


@router.post("/decision/evaluate", response_model=schemas.DecisionOutput)
def evaluate_decision_tier(request: schemas.DecisionRequest):
    """
    Evaluates an existing JourneyRiskAssessment through the stateful Decision Engine with hysteresis.
    """
    return decision_engine.evaluate(request.assessment)


@router.post("/sensors/policy", response_model=schemas.SensorPolicy)
def evaluate_sensor_policy(request: schemas.SensorPolicyRequest):
    """
    Computes an Adaptive Sensor Policy based on Decision tier, Battery, and Network context.
    """
    return adaptive_sensor_manager.generate_policy(
        decision=request.decision,
        battery=request.battery,
        network=request.network
    )


@router.post("/contextual-safety/reset")
def reset_contextual_safety():
    """
    Resets all temporal tracking and decision engine hysteresis state.
    """
    contextual_fusion_engine.temporal_tracker.reset_all()
    decision_engine.reset_all()
    return {"status": "reset", "phase": "3"}


# --- Autonomous Emergency Response (Phase 4) ---

@router.post("/emergency/trigger", response_model=schemas.EmergencyIncident)
def trigger_manual_sos(request: schemas.ManualSOSTriggerRequest, db: Session = Depends(database.get_db)):
    """
    Initiates an explicit Manual SOS emergency trigger.
    Bypasses automatic risk qualification.
    """
    snapshot = None
    try:
        snapshot = guardian_monitor.get_snapshot(request.journey_id)
    except ValueError:
        pass

    return emergency_orchestrator.handle_manual_sos(
        journey_id=request.journey_id,
        manual_lat=request.latitude,
        manual_lng=request.longitude,
        manual_accuracy=request.accuracy,
        reason=request.reason or "User pressed manual SOS button",
        snapshot=snapshot,
        db=db,
        current_time=request.timestamp
    )


@router.post("/emergency/autonomous", response_model=schemas.EmergencyIncident)
def trigger_autonomous_response(request: schemas.AutonomousTriggerRequest, db: Session = Depends(database.get_db)):
    """
    Consumes a Phase 3 AUTONOMOUS_RESPONSE_REQUIRED decision.
    Rejects any non-autonomous decisions.
    """
    if request.decision_tier != schemas.DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Decision tier '{request.decision_tier}' is ineligible for autonomous emergency response. Must be AUTONOMOUS_RESPONSE_REQUIRED."
        )

    snapshot = None
    try:
        snapshot = guardian_monitor.get_snapshot(request.journey_id)
    except ValueError:
        pass

    decision = schemas.DecisionOutput(
        decision_tier=schemas.DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED,
        hysteresis_state="AUTONOMOUS_CONFIRMED",
        consecutive_observations=2,
        requires_user_check_in=False,
        reason=f"Risk score {request.risk_score} in {request.risk_level} tier."
    )
    assessment = schemas.JourneyRiskAssessment(
        journey_id=request.journey_id,
        timestamp=request.timestamp or datetime.now(timezone.utc),
        risk_score=request.risk_score,
        risk_level=schemas.RiskLevel(request.risk_level),
        area_risk=20.0,
        motion_risk=10.0,
        route_deviation_risk=0.0,
        unexpected_stop_risk=0.0,
        fall_risk=40.0,
        audio_distress_risk=30.0,
        overall_confidence=0.95,
        telemetry_quality="VALID",
        dominant_factor=request.dominant_factor,
        active_factors=[
            schemas.RiskFactor(
                name=factor,
                contribution=50.0,
                confidence=0.9,
                state="ACTIVE",
                reason=f"Active factor {factor}"
            )
            for factor in request.active_factors
        ]
    )

    incident = emergency_orchestrator.handle_autonomous_decision(
        journey_id=request.journey_id,
        decision=decision,
        assessment=assessment,
        snapshot=snapshot,
        db=db,
        current_time=request.timestamp
    )
    if incident is None:
        raise HTTPException(status_code=400, detail="Failed to initialize emergency incident.")
    return incident


@router.get("/emergency/{incident_id}", response_model=schemas.EmergencyIncident)
def get_emergency_incident(incident_id: str, db: Session = Depends(database.get_db)):
    """
    Retrieves the current state and audit history of an emergency incident.
    """
    incident = emergency_orchestrator.persistence.get_incident(incident_id, db=db)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found.")
    return incident


@router.post("/emergency/{incident_id}/cancel", response_model=schemas.EmergencyIncident)
def cancel_emergency_incident(incident_id: str, request: schemas.CancelEmergencyRequest, db: Session = Depends(database.get_db)):
    """
    Cancels an active emergency incident during allowed confirmation/countdown states.
    """
    try:
        return emergency_orchestrator.cancel_incident(
            incident_id=incident_id,
            reason=request.reason or "User confirmed false alarm",
            db=db
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except schemas.InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/emergency/{incident_id}/acknowledge", response_model=schemas.EmergencyIncident)
def acknowledge_emergency_incident(incident_id: str, request: schemas.AcknowledgeEmergencyRequest, db: Session = Depends(database.get_db)):
    """
    Simulates emergency contact acknowledgement and resolves the incident.
    """
    try:
        return emergency_orchestrator.acknowledge_incident(
            incident_id=incident_id,
            contact_id=request.contact_id,
            acknowledged_by=request.acknowledged_by,
            notes=request.notes or "Contact acknowledged emergency",
            db=db
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except schemas.InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/emergency/{incident_id}/advance", response_model=schemas.EmergencyIncident)
def advance_emergency_countdown(incident_id: str, request: schemas.AdvanceEmergencyRequest, db: Session = Depends(database.get_db)):
    """
    Advances countdown or simulates expiry deterministically for testing and replay.
    """
    try:
        return emergency_orchestrator.advance_countdown(
            incident_id=incident_id,
            elapsed_seconds=request.elapsed_seconds,
            db=db
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except schemas.InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/emergency/reset")
def reset_emergency_response():
    """
    Resets all Phase 4 emergency orchestrator, persistence, and mock provider states.
    """
    emergency_orchestrator.reset_all()
    return {"status": "reset", "phase": "4"}


# ==============================================================================
# Phase 5: Offline Guardian & Connectivity Resilience Endpoints
# ==============================================================================

@router.post("/offline/connectivity", response_model=schemas.ConnectivityInfo)
def update_connectivity(request: schemas.UpdateConnectivityRequest):
    """
    Updates the connectivity state machine explicitly (ONLINE, DEGRADED, OFFLINE, RECONNECTING).
    """
    try:
        return offline_guardian.set_connectivity(
            new_state=request.state,
            reason=request.reason or "Connectivity state updated via API",
            timestamp=request.timestamp
        )
    except InvalidConnectivityTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/offline/status")
def get_offline_status():
    """
    Retrieves current offline guardian status, active journey state, and buffer statistics.
    """
    return offline_guardian.get_status_summary()


@router.get("/offline/journey", response_model=schemas.CachedJourneyContext)
def get_cached_journey():
    """
    Retrieves the locally cached journey context. Returns 404 if no active cached journey.
    """
    cached = offline_guardian.journey_cache.get_context()
    if not cached:
        raise HTTPException(status_code=404, detail="No cached journey found.")
    return cached


@router.get("/offline/buffer")
def get_offline_buffer():
    """
    Retrieves summary and list of durably buffered offline events.
    """
    pending = offline_guardian.event_buffer.get_pending_events()
    all_events = offline_guardian.event_buffer.get_all_events()
    return {
        "total_buffered_events": len(all_events),
        "pending_events_count": len(pending),
        "current_sequence_number": offline_guardian.event_buffer.current_sequence,
        "events": [e.model_dump() for e in all_events]
    }


@router.post("/offline/reconcile", response_model=schemas.ReconciliationSummary)
def trigger_reconciliation(request: schemas.ReconcileRequest):
    """
    Deterministically reconciles buffered offline state upon reconnection.
    """
    return offline_guardian.reconcile(
        simulate_partial_failure=request.simulate_partial_failure
    )


@router.post("/offline/emergency/sms-test", response_model=schemas.SMSDeliveryResult)
def test_sms_fallback(request: schemas.SMSTestRequest):
    """
    Deterministically tests the offline SMS fallback provider.
    """
    return offline_guardian.sms_provider.send_sms(
        incident_id=request.incident_id,
        recipient=request.recipient,
        message=request.message
    )


@router.post("/offline/reset")
def reset_offline_guardian():
    """
    Resets all Phase 5 offline guardian states, buffers, and SQLite persistence.
    """
    offline_guardian.reset()
    return {"status": "reset", "phase": "5"}


@router.post("/journey-risk", response_model=schemas.JourneyRiskResponse)

async def compute_journey_risk(request: schemas.JourneyRiskRequest):
    """
    Computes a live fused risk score based on recent GPS & accelerometer window.
    """
    if not request.points:
        raise HTTPException(status_code=400, detail="No points provided")
        
    latest_point = request.points[-1]
    
    # 1. Compute Motion Risk Score (ActivityStateClassifier + Jerk)
    # Extract raw x, y, z tuples for the model
    accel_data = [(p.accel_x, p.accel_y, p.accel_z) for p in request.points]
    motion_score = motion_model.predict_motion_score(accel_data)
    
    # 2. Fetch Area Risk Score (HTTP Call to Area Risk Service)
    async with httpx.AsyncClient() as client:
        try:
            hour = latest_point.timestamp.hour if latest_point.timestamp else datetime.utcnow().hour
            logger.info(f"Querying Area Risk Service at {AREA_RISK_URL} for lat={latest_point.lat}, lng={latest_point.lng}, hour={hour}")
            resp = await client.get(
                AREA_RISK_URL, 
                params={"lat": latest_point.lat, "lng": latest_point.lng, "hour": hour},
                timeout=5.0
            )
            if resp.status_code == 200:
                data = resp.json()
                area_score = data.get("risk_score")
                if area_score is None:
                    logger.error(f"Area Risk Service response missing 'risk_score': {resp.text}")
                    raise HTTPException(status_code=502, detail="Area Risk Service response malformed: missing 'risk_score'")
            else:
                logger.error(f"Area Risk Service returned HTTP {resp.status_code} at {AREA_RISK_URL}: {resp.text}")
                raise HTTPException(
                    status_code=502,
                    detail=f"Area Risk Service returned HTTP {resp.status_code}: {resp.text}"
                )
        except httpx.RequestError as e:
            logger.error(f"Failed to reach Area Risk Service at {AREA_RISK_URL}: {e}")
            raise HTTPException(
                status_code=503,
                detail=f"Area Risk Service unreachable at {AREA_RISK_URL}: {e}"
            )

    # 3. Fuse Scores
    audio_score = request.audio_distress if getattr(request, "audio_distress", None) is not None else 0.0
    fused_score, classification = fusion_scorer.compute_risk(
        area_risk=area_score,
        motion_anomaly=motion_score,
        audio_distress=audio_score
    )
    
    return schemas.JourneyRiskResponse(
        journey_risk_score=round(fused_score, 1),
        classification=classification,
        fusion_factors=schemas.FusionFactors(
            area_risk=round(area_score, 1),
            motion_anomaly=round(motion_score, 1),
            audio_distress=round(audio_score, 1)
        ),
        timestamp=datetime.utcnow()
    )


@router.websocket("/replay/{trip_id}")
async def replay_trip(websocket: WebSocket, trip_id: str, db: Session = Depends(database.get_db)):
    """
    Replays a real stored trip over WebSocket, calculating dynamic risk.
    """
    await websocket.accept()
    
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if not trip:
        await websocket.send_text("Trip not found")
        await websocket.close()
        return
        
    points = sorted(trip.points, key=lambda p: p.timestamp)
    if not points:
        await websocket.send_text("Trip has no points")
        await websocket.close()
        return

    # Sliding window logic to match our model's expectation
    window_size = 30 # Just an example moving window for smooth motion evaluation
    recent_points = []
    
    try:
        for p in points:
            # Construct a TripPointCreate equivalent for the function
            point_data = schemas.TripPointCreate(
                timestamp=p.timestamp,
                lat=p.lat,
                lng=p.lng,
                accel_x=p.accel_x,
                accel_y=p.accel_y,
                accel_z=p.accel_z
            )
            
            recent_points.append(point_data)
            if len(recent_points) > window_size:
                recent_points.pop(0)
                
            # Compute risk
            req = schemas.JourneyRiskRequest(points=recent_points)
            try:
                risk_resp = await compute_journey_risk(req)
                # Stream to client
                await websocket.send_text(risk_resp.model_dump_json())
            except HTTPException as exc:
                logger.error(f"Replay compute error: {exc.detail}")
                await websocket.send_text(json.dumps({"error": exc.detail}))
            
            # Simulate real-time delay
            await asyncio.sleep(0.5)
            
        await websocket.send_text("Replay complete")
        await websocket.close()
    except WebSocketDisconnect:
        print("Client disconnected")
