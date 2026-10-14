"""
STREEVA — Phase 3 Contextual Safety Intelligence
app/contextual/decision_engine.py

Decision Engine:
- Completely decoupled from risk scoring calculation.
- Evaluates JourneyRiskAssessment into structured operational response tiers.
- Enforces stateful hysteresis to prevent boundary flapping.
- Gated by signal confidence: low-confidence spikes cannot trigger critical actions.
- IMPORTANT: Prescribes decision tier only; does NOT trigger actual emergency response.
"""

from typing import Dict, Optional, Any
from .schemas import (
    RiskLevel,
    DecisionTier,
    DecisionOutput,
    JourneyRiskAssessment
)
from .config import ContextualSafetyConfig


class DecisionEngine:
    """
    Stateful Decision Engine with hysteresis debouncing and confidence gating.
    """

    def __init__(self, config: Optional[ContextualSafetyConfig] = None):
        self.config = config or ContextualSafetyConfig()
        # Per-journey state: journey_id -> { "current_tier": DecisionTier, "consecutive_high": int, "consecutive_low": int }
        self._states: Dict[str, Dict[str, Any]] = {}

    def evaluate(self, assessment: JourneyRiskAssessment) -> DecisionOutput:
        """
        Evaluates risk assessment and yields a debounced DecisionOutput.
        """
        journey_id = assessment.journey_id
        if journey_id not in self._states:
            self._states[journey_id] = {
                "current_tier": DecisionTier.MONITOR,
                "consecutive_escalation_count": 0,
                "consecutive_deescalation_count": 0,
                "last_score": assessment.risk_score
            }

        state = self._states[journey_id]
        score = assessment.risk_score
        conf = assessment.overall_confidence
        current_tier = state["current_tier"]

        # 0. Data Quality / Missing Telemetry Guard
        # "No evidence of danger" != "evidence of safety"
        if assessment.risk_level in [RiskLevel.UNKNOWN, RiskLevel.DEGRADED] or (conf == 0.0 and not assessment.active_factors):
            state["current_tier"] = DecisionTier.DEGRADED_MONITORING
            state["consecutive_escalation_count"] = 0
            state["consecutive_deescalation_count"] = 0
            state["last_score"] = score
            return DecisionOutput(
                decision_tier=DecisionTier.DEGRADED_MONITORING,
                hysteresis_state="DEGRADED_TELEMETRY",
                consecutive_observations=1,
                requires_user_check_in=False,
                reason="Telemetry unavailable: Operating in degraded monitoring mode (no evidence of danger != evidence of safety)."
            )

        # 1. Determine Target Tier Candidate from Instantaneous Score
        if score >= 75.0:
            target_candidate = DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED
        elif score >= 50.0:
            target_candidate = DecisionTier.ELEVATED_MONITORING
        elif score >= 38.0:
            target_candidate = DecisionTier.REQUEST_CHECK_IN
        elif score >= 25.0:
            target_candidate = DecisionTier.ADAPT_MONITORING
        else:
            target_candidate = DecisionTier.MONITOR

        # 2. Confidence Gating
        # A low-confidence signal (< 0.40) cannot escalate directly to CRITICAL (AUTONOMOUS_RESPONSE_REQUIRED)
        if target_candidate == DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED and conf < 0.40:
            target_candidate = DecisionTier.ELEVATED_MONITORING

        # 3. Check for Immediate Escalation Bypass (e.g. High-confidence Audio Distress + Fall)
        has_critical_interaction = any(
            f.name == "INTERACTION_AUDIO_DISTRESS_AND_FALL" and f.confidence >= 0.80
            for f in assessment.active_factors
        )

        # 4. Hysteresis & Debounce Logic
        resolved_tier = current_tier
        reason = ""

        # Escalation path
        if self._tier_rank(target_candidate) > self._tier_rank(current_tier):
            state["consecutive_deescalation_count"] = 0
            state["consecutive_escalation_count"] += 1

            # Check required consecutive observations
            req_count = 1
            if target_candidate == DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED:
                req_count = 1 if has_critical_interaction else self.config.critical_escalation_consecutive
            elif target_candidate == DecisionTier.ELEVATED_MONITORING:
                req_count = self.config.high_escalation_consecutive

            if state["consecutive_escalation_count"] >= req_count:
                resolved_tier = target_candidate
                reason = f"Escalated to {resolved_tier.value} after {state['consecutive_escalation_count']} consecutive observation(s) with risk score {score}."
            else:
                if target_candidate == DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED:
                    resolved_tier = DecisionTier.ELEVATED_MONITORING
                    reason = f"Elevated monitoring active while autonomous response confirmation is pending (observation {state['consecutive_escalation_count']}/{req_count}) with risk score {score}."
                else:
                    resolved_tier = current_tier
                    reason = f"Escalation to {target_candidate.value} pending: {state['consecutive_escalation_count']}/{req_count} consecutive observations."


        # De-escalation path
        elif self._tier_rank(target_candidate) < self._tier_rank(current_tier):
            state["consecutive_escalation_count"] = 0
            state["consecutive_deescalation_count"] += 1

            # Must stay below threshold for deescalation_consecutive counts
            if state["consecutive_deescalation_count"] >= self.config.deescalation_consecutive:
                resolved_tier = target_candidate
                reason = f"De-escalated to {resolved_tier.value} after {state['consecutive_deescalation_count']} sustained lower-risk observations."
            else:
                resolved_tier = current_tier
                reason = f"De-escalation held at {current_tier.value} (debouncing: {state['consecutive_deescalation_count']}/{self.config.deescalation_consecutive} observations below threshold)."

        # Steady state
        else:
            state["consecutive_escalation_count"] = max(1, state["consecutive_escalation_count"])
            state["consecutive_deescalation_count"] = 0
            resolved_tier = current_tier
            reason = f"Maintained {resolved_tier.value} based on steady risk score {score}."

        state["current_tier"] = resolved_tier
        state["last_score"] = score

        # Interactive Check-In indication
        requires_check_in = resolved_tier in [
            DecisionTier.REQUEST_CHECK_IN,
            DecisionTier.ELEVATED_MONITORING
        ]

        return DecisionOutput(
            decision_tier=resolved_tier,
            hysteresis_state=f"ESC_{state['consecutive_escalation_count']}_DEESC_{state['consecutive_deescalation_count']}",
            consecutive_observations=max(state["consecutive_escalation_count"], state["consecutive_deescalation_count"]),
            requires_user_check_in=requires_check_in,
            reason=reason
        )

    def _tier_rank(self, tier: DecisionTier) -> int:
        ranks = {
            DecisionTier.MONITOR: 0,
            DecisionTier.DEGRADED_MONITORING: 0,
            DecisionTier.ADAPT_MONITORING: 1,
            DecisionTier.REQUEST_CHECK_IN: 2,
            DecisionTier.ELEVATED_MONITORING: 3,
            DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED: 4
        }
        return ranks.get(tier, 0)

    def reset_journey(self, journey_id: str):
        """Resets hysteresis state for a specific journey."""
        if journey_id in self._states:
            del self._states[journey_id]

    def reset_all(self):
        """Resets all journey states."""
        self._states.clear()
