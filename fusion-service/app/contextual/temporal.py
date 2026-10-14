"""
STREEVA — Phase 3 Contextual Safety Intelligence
app/contextual/temporal.py

Temporal persistence reasoning, observation counting, and recency decay calculation.
"""

import math
from datetime import datetime
from typing import Dict, Any, Optional
from .config import ContextualSafetyConfig


class TemporalSignalTracker:
    """
    Maintains temporal persistence and observation histories per journey.
    Applies exponential half-life decay to shock events to prevent ancient events
    from permanently poisoning instantaneous risk.
    """

    def __init__(self, config: Optional[ContextualSafetyConfig] = None):
        self.config = config or ContextualSafetyConfig()
        # Storage: journey_id -> { signal_name: { "last_time": datetime, "consecutive_count": int, "active": bool } }
        self._histories: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def update_signal(
        self,
        journey_id: str,
        signal_name: str,
        is_active: bool,
        timestamp: datetime
    ) -> Dict[str, Any]:
        """
        Updates consecutive count and timestamp for a given signal.
        Returns temporal metadata dict.
        """
        if journey_id not in self._histories:
            self._histories[journey_id] = {}

        if signal_name not in self._histories[journey_id]:
            self._histories[journey_id][signal_name] = {
                "last_active_time": None,
                "consecutive_count": 0,
                "total_occurrences": 0,
                "first_detected_time": None
            }

        rec = self._histories[journey_id][signal_name]

        if is_active:
            rec["consecutive_count"] += 1
            rec["total_occurrences"] += 1
            rec["last_active_time"] = timestamp
            if rec["first_detected_time"] is None:
                rec["first_detected_time"] = timestamp
        else:
            rec["consecutive_count"] = 0
            # Keep last_active_time to allow decay calculation

        decay = self.compute_recency_decay(signal_name, rec["last_active_time"], timestamp)

        return {
            "signal_name": signal_name,
            "is_active": is_active,
            "consecutive_count": rec["consecutive_count"],
            "total_occurrences": rec["total_occurrences"],
            "last_active_time": rec["last_active_time"],
            "decay_multiplier": decay
        }

    def compute_recency_decay(
        self,
        signal_name: str,
        last_time: Optional[datetime],
        current_time: datetime
    ) -> float:
        """
        Computes exponential decay factor [0.0, 1.0] using configured half-life:
        decay = exp(-ln(2) * delta_t / half_life)
        """
        if last_time is None or current_time is None:
            return 0.0

        delta_s = (current_time - last_time).total_seconds()
        if delta_s <= 0:
            return 1.0

        if signal_name == "fall":
            half_life = self.config.fall_half_life_s
        elif signal_name == "audio_distress":
            half_life = self.config.audio_half_life_s
        else:
            half_life = self.config.general_half_life_s

        if half_life <= 0:
            return 1.0

        decay = math.exp(-math.log(2.0) * delta_s / half_life)
        return max(0.0, min(1.0, decay))

    def get_summary(self, journey_id: str) -> Dict[str, Any]:
        """Returns all tracked signals for a journey."""
        return self._histories.get(journey_id, {})

    def reset_journey(self, journey_id: str):
        """Clears temporal state for a journey."""
        if journey_id in self._histories:
            del self._histories[journey_id]

    def reset_all(self):
        """Clears all journey tracking."""
        self._histories.clear()
