from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime

class TripPointCreate(BaseModel):
    timestamp: datetime
    lat: float
    lng: float
    accel_x: float
    accel_y: float
    accel_z: float
    accuracy: Optional[float] = Field(default=None, description="Optional GPS accuracy in meters")
    gyro_x: Optional[float] = Field(default=None, description="Optional gyroscope x in deg/s")
    gyro_y: Optional[float] = Field(default=None, description="Optional gyroscope y in deg/s")
    gyro_z: Optional[float] = Field(default=None, description="Optional gyroscope z in deg/s")

class TripCreate(BaseModel):
    trip_id: str
    label: str
    start_time: datetime
    end_time: datetime
    points: List[TripPointCreate]

class JourneyRiskRequest(BaseModel):
    points: List[TripPointCreate]
    audio_distress: Optional[float] = Field(default=None, description="Optional audio distress score [0-100]")

class FusionFactors(BaseModel):
    area_risk: float
    motion_anomaly: float
    audio_distress: Optional[float] = None

class JourneyRiskResponse(BaseModel):
    journey_risk_score: float
    classification: str
    fusion_factors: FusionFactors
    timestamp: datetime
    # Phase 3 Contextual Safety enrichments (optional for backwards compatibility)
    assessment: Optional[Any] = None
    decision: Optional[Any] = None
    sensor_policy: Optional[Any] = None



# --- Route Deviation Schemas (Phase 1A) ---
class LatLngPoint(BaseModel):
    lat: float
    lng: float


class RouteDeviationRequest(BaseModel):
    current_position: LatLngPoint
    route_polyline: List[LatLngPoint]
    gps_accuracy: Optional[float] = Field(default=None, description="Reported GPS horizontal accuracy in meters")
    timestamp: Optional[datetime] = None


from .edge.route_deviation import RouteDeviationEvent, DeviationState, RouteDeviationConfig


# --- Unexpected Stop Schemas (Phase 1B) ---
class UnexpectedStopRequest(BaseModel):
    current_position: LatLngPoint
    timestamp: Optional[datetime] = None
    gps_accuracy: Optional[float] = Field(default=None, description="Reported GPS horizontal accuracy in meters")
    journey_active: bool = Field(default=True, description="Indicates if an active journey is currently underway")


from .edge.unexpected_stop import UnexpectedStopEvent, StopState, UnexpectedStopConfig


# --- Gyroscope / Fall Detection Schemas (Phase 1C) ---
class FallDetectionRequest(BaseModel):
    accel_x: float
    accel_y: float
    accel_z: float
    gyro_x: Optional[float] = None
    gyro_y: Optional[float] = None
    gyro_z: Optional[float] = None
    timestamp: Optional[datetime] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


from .edge.fall_detection import FallDetectedEvent, FallState, SensorMode, FallDetectionConfig


# --- Distress Audio Schemas (Phase 1D) ---
class AudioDistressRequest(BaseModel):
    audio_samples: Optional[List[float]] = Field(default=None, description="1D array of audio float32 PCM samples")
    base64_audio: Optional[str] = Field(default=None, description="Base64 encoded 16-bit PCM or WAV bytes")
    file_path: Optional[str] = Field(default=None, description="Optional path to local WAV file for test/demo")
    sample_rate: int = Field(default=16000, description="Audio sampling rate in Hz")
    timestamp: Optional[datetime] = None


from .edge.audio_distress import AudioDistressEvent, DistressAudioState, AudioDistressConfig


# --- Guardian Journey Intelligence Schemas (Phase 2) ---
from .guardian import (
    JourneyState,
    TelemetryQuality,
    ArrivalStatus,
    ProgressStatus,
    ETASource,
    GuardianConfig,
    JourneyContext,
    GuardianSnapshot,
    JourneyStartRequest,
    JourneyUpdateRequest,
    JourneyEndRequest
)

# --- Contextual Safety Intelligence Schemas (Phase 3) ---
from .contextual import (
    RiskLevel,
    DecisionTier,
    SensorProfile,
    NetworkState,
    RiskFactor,
    BatteryContext,
    NetworkContext,
    SensorPolicy,
    DecisionOutput,
    JourneyRiskAssessment,
    ContextualSafetyRequest,
    ContextualSafetyResponse,
    DecisionRequest,
    SensorPolicyRequest
)

# --- Autonomous Emergency Response Schemas (Phase 4) ---
from .emergency import (
    EmergencyState,
    TriggerType,
    LocationQuality,
    DestinationType,
    EscalationLevel,
    AcknowledgementStatus,
    EvidenceType,
    LocationResult,
    EmergencyContact,
    NotificationPayload,
    NotificationDeliveryResult,
    EvidenceItem,
    EvidencePackage,
    IncidentTransitionRecord,
    IncidentContextSnapshot,
    EmergencyIncident,
    ManualSOSTriggerRequest,
    AutonomousTriggerRequest,
    CancelEmergencyRequest,
    AcknowledgeEmergencyRequest,
    AdvanceEmergencyRequest
)

# --- Offline Guardian & Connectivity Resilience Schemas (Phase 5) ---
from .offline import (
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



