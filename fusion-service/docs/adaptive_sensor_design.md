# STREEVA — Adaptive Sensor Manager Specification
`fusion-service/docs/adaptive_sensor_design.md`

## 1. Overview
The Adaptive Sensor Manager bridges decision intelligence with mobile hardware sensing policy. Rather than sampling GPS, accelerometer, gyroscope, and microphone at maximum frequency indefinitely (which exhausts mobile battery within hours), the Adaptive Sensor Manager generates dynamic **SensorPolicy** prescriptions adapted to:
- Operational Decision Tier (`MONITOR`, `ADAPT_MONITORING`, `REQUEST_CHECK_IN`, `ELEVATED_MONITORING`, `AUTONOMOUS_RESPONSE_REQUIRED`)
- Device battery level and charging state
- Network connectivity status (`ONLINE`, `DEGRADED`, `OFFLINE`)

> [!NOTE]
> The Adaptive Sensor Manager generates **policy objects only**. It does not interact with mobile hardware or OS sensor drivers directly.

---

## 2. Sensor Profiles & Sampling Tiers

| Profile Tier | Decision Tier | GPS Sampling Interval | Accelerometer | Gyroscope | Microphone Duty Cycle |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **`LOW`** | `MONITOR` | 60.0 seconds | 10 Hz (Low duty) | Inactive (False) | Inactive (0%) |
| **`MEDIUM`** | `ADAPT_MONITORING`, `REQUEST_CHECK_IN` | 15.0 seconds | 25 Hz | Active (True) | 25% Periodic Sampling |
| **`HIGH`** | `ELEVATED_MONITORING` | 5.0 seconds | 50 Hz | Active (True) | 50% Frequent Sampling |
| **`CRITICAL`** | `AUTONOMOUS_RESPONSE_REQUIRED` | 1.0 second | 100 Hz | Active (True) | 100% Continuous Stream |

---

## 3. Battery Awareness & Throttling
- **Low Battery Threshold**: When battery is $\le 20\%$ and device is **not charging**:
  - In `LOW`, `MEDIUM`, and `HIGH` profiles: GPS interval is doubled (e.g. 15s $\rightarrow$ 30s), accelerometer sampling rate is halved, and secondary sensors (gyro/mic) are deactivated in `MEDIUM`.
  - In `CRITICAL` profile: **Safety takes precedence over battery conservation**. Maximum sensing fidelity (1s GPS, 100Hz motion, 100% mic) is strictly maintained.
- **Charging State**: When `is_charging` is True, power throttling is bypassed.

---

## 4. Network Awareness & Edge Telemetry Buffering
When network connectivity is reported as `DEGRADED` or `OFFLINE`:
- `local_buffering_recommended` is set to `True`.
- Recommends that the mobile client store high-frequency inertial and GPS snapshots in an encrypted local FIFO ring buffer, rather than attempting failed HTTP/WebSocket transmissions.
- When network connectivity returns to `ONLINE`, buffered telemetry can be replayed and synchronized with `fusion-service`.

---

## 5. Schema Contract

```json
{
  "profile": "HIGH",
  "gps_interval_s": 5.0,
  "accel_sampling_rate_hz": 50.0,
  "gyro_enabled": true,
  "mic_duty_cycle_percent": 50.0,
  "local_buffering_recommended": false,
  "reason": "HIGH risk tier: elevated sensor frequency enabled (5s GPS, 50Hz motion, 50% mic). | Device connected to power; standard or elevated profile maintained."
}
```

---

## 6. Future Mobile Implementation
In future mobile phases (React Native / Flutter / Android):
- The mobile background service queries `/sensors/policy` or receives `sensor_policy` within the response of `/journey-risk` or `/contextual-safety/evaluate`.
- The native GPS provider dynamically adjusts `locationRequest.setInterval()` based on `gps_interval_s`.
- The sensor listener unregisters or adjusts sampling delays for `SensorManager.SENSOR_DELAY_FASTEST` vs `SENSOR_DELAY_NORMAL`.
