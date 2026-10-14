"""
STREEVA — Phase 3 Contextual Safety Intelligence
app/contextual/config.py

Configuration loader for Risk Fusion 2.0, Decision Engine, and Adaptive Sensor Manager.
"""

import os
import yaml
from pydantic import BaseModel, Field
from typing import Dict, Any


class ContextualSafetyConfig(BaseModel):
    # Signal Weights (sum to 1.0)
    weight_area_risk: float = 0.20
    weight_motion_anomaly: float = 0.15
    weight_route_deviation: float = 0.20
    weight_unexpected_stop: float = 0.15
    weight_fall_detection: float = 0.15
    weight_audio_distress: float = 0.15

    # Thresholds
    threshold_low_max: float = 24.99
    threshold_medium_max: float = 49.99
    threshold_high_max: float = 74.99

    # Contextual Interactions
    high_area_threshold: float = 60.0
    area_deviation_boost: float = 12.0
    stop_area_delay_boost: float = 10.0
    audio_fall_boost: float = 15.0
    audio_fall_correlation_window_s: float = 15.0


    # Temporal Decay
    fall_half_life_s: float = 120.0
    audio_half_life_s: float = 60.0
    general_half_life_s: float = 90.0

    # Hysteresis
    critical_escalation_consecutive: int = 2
    high_escalation_consecutive: int = 1
    deescalation_consecutive: int = 3
    deescalation_margin_points: float = 5.0


    # Sensor Profiles
    sensor_policies: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def load_from_yaml(cls, path: str = None) -> "ContextualSafetyConfig":
        if path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            path = os.path.join(base_dir, "configs", "contextual_safety_config.yaml")

        if not os.path.exists(path):
            return cls()

        with open(path, "r") as f:
            raw = yaml.safe_load(f) or {}

        weights = raw.get("fusion_weights", {})
        thresholds = raw.get("risk_thresholds", {})
        interactions = raw.get("contextual_interactions", {})
        temporal = raw.get("temporal_decay", {})
        hysteresis = raw.get("hysteresis", {})
        policies = raw.get("sensor_policies", {})

        return cls(
            weight_area_risk=weights.get("area_risk", 0.20),
            weight_motion_anomaly=weights.get("motion_anomaly", 0.15),
            weight_route_deviation=weights.get("route_deviation", 0.20),
            weight_unexpected_stop=weights.get("unexpected_stop", 0.15),
            weight_fall_detection=weights.get("fall_detection", 0.15),
            weight_audio_distress=weights.get("audio_distress", 0.15),
            threshold_low_max=thresholds.get("low_max", 24.99),
            threshold_medium_max=thresholds.get("medium_max", 49.99),
            threshold_high_max=thresholds.get("high_max", 74.99),
            high_area_threshold=interactions.get("high_area_threshold", 60.0),
            area_deviation_boost=interactions.get("area_deviation_boost", 12.0),
            stop_area_delay_boost=interactions.get("stop_area_delay_boost", 10.0),
            audio_fall_boost=interactions.get("audio_fall_boost", 15.0),
            audio_fall_correlation_window_s=interactions.get("audio_fall_correlation_window_s", 15.0),

            fall_half_life_s=temporal.get("fall_half_life_s", 120.0),
            audio_half_life_s=temporal.get("audio_half_life_s", 60.0),
            general_half_life_s=temporal.get("general_half_life_s", 90.0),
            critical_escalation_consecutive=hysteresis.get("critical_escalation_consecutive", 2),
            high_escalation_consecutive=hysteresis.get("high_escalation_consecutive", 2),
            deescalation_consecutive=hysteresis.get("deescalation_consecutive", 3),
            deescalation_margin_points=hysteresis.get("deescalation_margin_points", 5.0),
            sensor_policies=policies,
        )
