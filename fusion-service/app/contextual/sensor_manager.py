"""
STREEVA — Phase 3 Contextual Safety Intelligence
app/contextual/sensor_manager.py

Adaptive Sensor Manager:
- Evaluates DecisionTier + Battery + Network context to produce a recommended SensorPolicy.
- Prescribes sensor sampling rates and duty cycles without manipulating hardware directly.
- Implements battery throttling for low-battery non-critical states.
- Recommends local high-frequency telemetry buffering when network is degraded or offline.
"""

from typing import Optional
from .schemas import (
    DecisionTier,
    SensorProfile,
    SensorPolicy,
    BatteryContext,
    NetworkContext,
    NetworkState,
    DecisionOutput
)
from .config import ContextualSafetyConfig


class AdaptiveSensorManager:
    """
    Translates operational decisions into edge sensor management policies.
    """

    def __init__(self, config: Optional[ContextualSafetyConfig] = None):
        self.config = config or ContextualSafetyConfig()

    def generate_policy(
        self,
        decision: DecisionOutput,
        battery: Optional[BatteryContext] = None,
        network: Optional[NetworkContext] = None
    ) -> SensorPolicy:
        """
        Determines the optimal sensor sampling policy.
        """
        tier = decision.decision_tier
        battery = battery or BatteryContext()
        network = network or NetworkContext()

        # 1. Base Policy by Decision Tier
        if tier == DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED:
            profile = SensorProfile.CRITICAL
            gps_interval = 1.0
            accel_hz = 100.0
            gyro = True
            mic_duty = 100.0
            base_reason = "CRITICAL risk decision tier: maximum sensor fidelity requested for active threat response."
        elif tier == DecisionTier.ELEVATED_MONITORING:
            profile = SensorProfile.HIGH
            gps_interval = 5.0
            accel_hz = 50.0
            gyro = True
            mic_duty = 50.0
            base_reason = "HIGH risk tier: elevated sensor frequency enabled (5s GPS, 50Hz motion, 50% mic)."
        elif tier in [DecisionTier.ADAPT_MONITORING, DecisionTier.REQUEST_CHECK_IN]:
            profile = SensorProfile.MEDIUM
            gps_interval = 15.0
            accel_hz = 25.0
            gyro = True
            mic_duty = 25.0
            base_reason = "MEDIUM risk tier: balanced standard monitoring (15s GPS, 25Hz motion, 25% mic)."
        elif tier == DecisionTier.DEGRADED_MONITORING:
            profile = SensorProfile.MEDIUM
            gps_interval = 15.0
            accel_hz = 25.0
            gyro = True
            mic_duty = 0.0
            base_reason = "DEGRADED_MONITORING tier: sensor telemetry missing; attempting active re-acquisition (15s GPS, 25Hz motion, gyro enabled)."
        else:
            profile = SensorProfile.LOW
            gps_interval = 60.0
            accel_hz = 10.0
            gyro = False
            mic_duty = 0.0
            base_reason = "LOW risk tier: conservative power-saving monitoring (60s GPS, 10Hz motion, mic inactive)."

        reasons = [base_reason]

        # 2. Battery Awareness Modifiers
        # Safety takes precedence: do not throttle if in CRITICAL profile
        if battery.battery_level <= 20.0 and not battery.is_charging:
            if profile == SensorProfile.CRITICAL:
                reasons.append(f"Low battery ({battery.battery_level}%), but safety takes precedence over power saving during CRITICAL events.")
            else:
                gps_interval *= 2.0
                accel_hz = max(5.0, accel_hz / 2.0)
                if profile == SensorProfile.MEDIUM:
                    mic_duty = 0.0
                    gyro = False
                reasons.append(f"Low battery optimization ({battery.battery_level}%): throttled GPS to {gps_interval}s and disabled secondary sensors.")
        elif battery.is_charging:
            reasons.append("Device connected to power; standard or elevated profile maintained.")

        # 3. Network & Telemetry Awareness Modifiers
        local_buffering = False
        if network.network_state in [NetworkState.DEGRADED, NetworkState.OFFLINE] or tier == DecisionTier.DEGRADED_MONITORING:
            local_buffering = True
            reasons.append(f"Degraded telemetry/network context: local sensor window buffering recommended on edge client.")

        return SensorPolicy(
            profile=profile,
            gps_interval_s=gps_interval,
            accel_sampling_rate_hz=accel_hz,
            gyro_enabled=gyro,
            mic_duty_cycle_percent=mic_duty,
            local_buffering_recommended=local_buffering,
            reason=" | ".join(reasons)
        )
