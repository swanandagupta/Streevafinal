# STREEVA — Unexpected Stop Detection (Phase 1B) Design Document

## 1. Overview
The **Unexpected Stop Detection Engine** is an Edge AI / telemetry-level safety component located in `fusion-service/app/edge/unexpected_stop.py`. It determines whether a traveler has halted unexpectedly during an active journey.

> [!IMPORTANT]
> **Heuristic / Telemetry Detector**:
> This module is a deterministic temporal and kinematic detector, **NOT an ML model**.
> Confidence scores represent telemetry signal quality and temporal persistence, not learned probabilities.

---

## 2. Core Detection Principles

### Velocity & Displacement Analysis
Rather than relying on device-reported speed or naive coordinate checks:
1. For successive GPS fixes $(P_{t-1}, P_t)$, displacement $\Delta d$ is calculated using the Haversine formula from Phase 1A.
2. Ground speed is derived as $v = \Delta d / \Delta t$.
3. If $\Delta t > 120.0$ seconds (telemetry discontinuity or app pause), the temporal baseline is reset cleanly to prevent phantom stops.

### Why Temporal Persistence is Essential
GPS frequently reports zero velocity or micro-jitter due to multipath signals, traffic stoplights, or waiting for pedestrian crossings.
- Human walking speed: $\approx 1.2 - 1.4$ m/s.
- Stationary threshold: $v < 0.5$ m/s ($\approx 1.8$ km/h).
- Standard urban traffic lights typically cycle in $30 - 45$ seconds.
- Therefore, a duration of $\ge 45$ seconds of continuous sub-threshold speed is required before escalating to `STOPPED`.

---

## 3. Configurable Parameters (`UnexpectedStopConfig`)

| Parameter | Default | Purpose |
|---|---|---|
| `stop_speed_threshold_mps` | `0.5 m/s` | Velocity below which a traveler is considered stationary. |
| `possible_stop_duration_s` | `15.0 s` | Duration of stillness before transitioning to `POSSIBLE_STOP`. |
| `minimum_stop_duration_s` | `45.0 s` | Duration of stillness required to confirm `STOPPED` state. |
| `recovery_speed_threshold_mps`| `1.0 m/s` | Hysteresis speed threshold required to recover toward `MOVING`. |
| `consecutive_recovery_observations` | `2` | Number of consecutive moving readings required to return to `MOVING`. |
| `gps_accuracy_limit_m` | `50.0 m` | Degraded GPS readings above this limit cannot trigger `STOPPED`. |
| `max_time_gap_s` | `120.0 s` | Discontinuity ceiling resetting temporal tracking. |

---

## 4. State Machine Lifecycle & Hysteresis

```
                [v < 0.5 m/s (still >= 15s)]
   ┌────────────────────────────────────────────────────────┐
   │                                                        │
   ▼                                                        │
MOVING <─────────────────────── POSSIBLE_STOP ──────────────┘
   ▲     [v >= 1.0 m/s]             │
   │                                │ [still >= 45s]
   │                                ▼
   │                             STOPPED
   │                                │
   │ [v >= 1.0 m/s (obs >= 2)]      │ [v >= 1.0 m/s (obs 1)]
   └──────────────────────────── RECOVERING
```

### Hysteresis Corridor
Speeds between $0.5$ m/s and $1.0$ m/s (e.g. slow pedestrian loitering or shuffling) remain in the current state, preventing rapid oscillations between `MOVING` and `STOPPED`.

---

## 5. GPS Accuracy Protection
- When GPS accuracy uncertainty exceeds $50.0$m, state transitions into `STOPPED` are suppressed.
- Confidence is scaled down linearly with increasing horizontal uncertainty.

---

## 6. Output Contract: `UnexpectedStopEvent`

```json
{
  "event_type": "UNEXPECTED_STOP",
  "is_stopped": true,
  "state": "STOPPED",
  "stationary_duration_s": 50.0,
  "speed_mps": 0.0,
  "confidence": 0.90,
  "gps_accuracy_m": 5.0,
  "latitude": 13.0600,
  "longitude": 80.2500,
  "timestamp": "2026-09-12T14:00:55Z",
  "journey_active": true,
  "details": "Unexpected stop confirmed: stationary for 50.0s (>= 45.0s threshold) at 0.00 m/s."
}
```
