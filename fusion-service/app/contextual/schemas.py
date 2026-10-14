"""
STREEVA — Phase 3 Contextual Safety Intelligence
app/contextual/schemas.py

Pydantic schemas and enums for Risk Fusion 2.0, Decision Engine, and Adaptive Sensor Manager.
"""

from enum import Enum
from typing import List, Dict, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"
    DEGRADED = "DEGRADED"


class DecisionTier(str, Enum):
    MONITOR = "MONITOR"
    ADAPT_MONITORING = "ADAPT_MONITORING"
    REQUEST_CHECK_IN = "REQUEST_CHECK_IN"
    ELEVATED_MONITORING = "ELEVATED_MONITORING"
    AUTONOMOUS_RESPONSE_REQUIRED = "AUTONOMOUS_RESPONSE_REQUIRED"
    DEGRADED_MONITORING = "DEGRADED_MONITORING"



class SensorProfile(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class NetworkState(str, Enum):
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"


class RiskFactor(BaseModel):
    """
    Structured explainability element for individual risk contributors.
    """
    name: str = Field(description="Identifier of the risk factor (e.g. 'ROUTE_DEVIATION').")
    contribution: float = Field(ge=0.0, le=100.0, description="Normalized point contribution to overall risk score.")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the observation/detector output.")
    state: str = Field(description="Operational state of the signal (e.g. 'DEVIATED', 'STOPPED', 'NORMAL').")
    reason: str = Field(description="Human-readable justification for the contribution.")


class BatteryContext(BaseModel):
    """
    Client battery status for adaptive sensing policy generation.
    """
    battery_level: float = Field(default=100.0, ge=0.0, le=100.0, description="Battery percentage (0.0 - 100.0).")
    is_charging: bool = Field(default=False, description="True if device is connected to power.")


class NetworkContext(BaseModel):
    """
    Client network connectivity status.
    """
    network_state: NetworkState = Field(default=NetworkState.ONLINE, description="Connectivity status.")
    signal_bars: Optional[int] = Field(default=4, ge=0, le=5, description="Signal strength indicator.")


class SensorPolicy(BaseModel):
    """
    Adaptive sensor management policy prescribing on-device sampling rates.
    NOTE: Policy specification only; does NOT interact directly with mobile hardware.
    """
    profile: SensorProfile = Field(description="Target sensing profile tier.")
    gps_interval_s: float = Field(description="Recommended GPS sampling interval in seconds.")
    accel_sampling_rate_hz: float = Field(description="Recommended accelerometer frequency in Hz.")
    gyro_enabled: bool = Field(description="Whether gyroscope should be actively sampled.")
    mic_duty_cycle_percent: float = Field(description="Microphone listening duty cycle percentage (0-100).")
    local_buffering_recommended: bool = Field(
        default=False,
        description="True if device should buffer raw high-frequency telemetry locally due to degraded network."
    )
    reason: str = Field(description="Transparent explanation for the assigned sensor policy.")


class DecisionOutput(BaseModel):
    """
    Decision Engine output separate from risk scoring.
    NOTE: Prescribes decision tier only; does NOT trigger actual emergency response.
    """
    decision_tier: DecisionTier = Field(description="Prescribed operational decision response tier.")
    hysteresis_state: str = Field(description="Current state within the hysteresis debounce tracker.")
    consecutive_observations: int = Field(description="Consecutive observations in this or higher tier.")
    requires_user_check_in: bool = Field(
        default=False,
        description="True if interactive check-in prompt is indicated (e.g. in REQUEST_CHECK_IN)."
    )
    reason: str = Field(description="Transparent justification for the decision tier.")


class JourneyRiskAssessment(BaseModel):
    """
    Consolidated Contextual Safety Risk Assessment.
    Unified representation combining Area Risk, Motion, Route Deviation, Unexpected Stop,
    Fall, Audio Distress, and Journey Context.
    """
    journey_id: str
    timestamp: datetime
    
    risk_score: float = Field(ge=0.0, le=100.0, description="Unified risk score clamped to [0.0, 100.0].")
    risk_level: RiskLevel = Field(description="Classification: LOW (0-24), MEDIUM (25-49), HIGH (50-74), CRITICAL (75-100).")
    
    # Individual component risk point contributions (after weights & normalization)
    area_risk: float = Field(ge=0.0, le=100.0)
    motion_risk: float = Field(ge=0.0, le=100.0)
    route_deviation_risk: float = Field(ge=0.0, le=100.0)
    unexpected_stop_risk: float = Field(ge=0.0, le=100.0)
    fall_risk: float = Field(ge=0.0, le=100.0)
    audio_distress_risk: float = Field(ge=0.0, le=100.0)
    
    overall_confidence: float = Field(ge=0.0, le=1.0, description="Blended measurement confidence.")
    telemetry_quality: str = Field(description="Telemetry status ('VALID', 'DEGRADED', 'STALE', 'MISSING', etc.)")
    
    active_factors: List[RiskFactor] = Field(default_factory=list, description="All active risk factors.")
    dominant_factor: Optional[str] = Field(default=None, description="Factor with highest point contribution.")
    
    temporal_context: Dict[str, Any] = Field(default_factory=dict, description="Persistence counts and decay metrics.")
    data_quality: Dict[str, Any] = Field(default_factory=dict, description="Signal availability and freshness audit.")
    
    decision: Optional[DecisionOutput] = Field(default=None, description="Associated decision logic output.")
    sensor_policy: Optional[SensorPolicy] = Field(default=None, description="Associated adaptive sensing policy.")


# --- API Request / Response Models ---

from ..guardian.journey_state import GuardianSnapshot


class ContextualSafetyRequest(BaseModel):
    """
    Request model for full contextual safety evaluation.
    """
    snapshot: GuardianSnapshot = Field(description="Guardian journey snapshot containing edge signals & context.")
    area_risk_score: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Area risk score if pre-fetched.")
    area_risk_confidence: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    motion_anomaly_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    battery: Optional[BatteryContext] = Field(default=None)
    network: Optional[NetworkContext] = Field(default=None)


class ContextualSafetyResponse(BaseModel):
    """
    Complete response returning risk assessment, decision output, and sensor policy.
    """
    assessment: JourneyRiskAssessment
    decision: DecisionOutput
    sensor_policy: SensorPolicy


class DecisionRequest(BaseModel):
    assessment: JourneyRiskAssessment


class SensorPolicyRequest(BaseModel):
    decision: DecisionOutput
    battery: Optional[BatteryContext] = None
    network: Optional[NetworkContext] = None
