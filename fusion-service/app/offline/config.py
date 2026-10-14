"""
STREEVA — Phase 5 Offline Guardian & Connectivity Resilience
app/offline/config.py

Configuration loader for Offline Guardian and Connectivity Resilience.
"""

import os
import yaml
from pydantic import BaseModel
from typing import Optional


class OfflineGuardianConfig(BaseModel):
    # Connectivity Thresholds
    degraded_latency_ms: float = 1500.0
    heartbeat_interval_seconds: float = 30.0

    # Event Buffer & Reconciliation
    max_buffered_events: int = 10000
    reconciliation_batch_size: int = 50
    max_sync_retries: int = 3

    # Location Freshness
    offline_location_stale_seconds: float = 45.0

    # SMS Fallback Defaults
    sms_fallback_enabled: bool = True
    sms_gateway_timeout_seconds: float = 10.0

    # Offline Countdown
    offline_emergency_countdown_seconds: float = 15.0

    @classmethod
    def load_from_yaml(cls, path: Optional[str] = None) -> "OfflineGuardianConfig":
        if path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            path = os.path.join(base_dir, "configs", "offline_config.yaml")

        if not os.path.exists(path):
            return cls()

        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}

        return cls(**data)
