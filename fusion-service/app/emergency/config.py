"""
STREEVA — Phase 4 Autonomous Emergency Response System
app/emergency/config.py

Configuration loader for Autonomous Emergency Response Orchestrator.
"""

import os
import yaml
from pydantic import BaseModel, Field
from typing import Optional


class EmergencyResponseConfig(BaseModel):
    # Confirmation Countdown
    emergency_countdown_seconds: float = 15.0
    manual_sos_immediate_authorization: bool = True
    manual_sos_countdown_seconds: float = 0.0

    # Escalation & Acknowledgement Timeouts
    acknowledgement_timeout_seconds: float = 60.0
    max_escalation_level: int = 3

    # Location Handling
    location_stale_threshold_seconds: float = 45.0
    allow_dispatch_without_location: bool = True

    # Evidence Packaging
    evidence_hash_algorithm: str = "sha256"

    @classmethod
    def load_from_yaml(cls, path: Optional[str] = None) -> "EmergencyResponseConfig":
        if path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            path = os.path.join(base_dir, "configs", "emergency_config.yaml")

        if not os.path.exists(path):
            return cls()

        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}

        return cls(**data)
