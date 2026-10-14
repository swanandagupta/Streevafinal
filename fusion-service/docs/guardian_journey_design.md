# STREEVA — Phase 2: Guardian Journey Intelligence Architecture & Technical Specification

> **CRITICAL ARCHITECTURAL BOUNDARY**  
> **GUARDIAN JOURNEY INTELLIGENCE ORCHESTRATES JOURNEY CONTEXT, NOT EMERGENCY ACTIONS.**  
> - **NO automatic SOS or emergency dispatch.**  
> - **NO emergency contact notifications or SMS alerts.**  
> - **NO 0–100 risk score calculation** (Risk Fusion remains an upstream consumer).  
> - **NO duplicate detector algorithms** (Guardian orchestrates and consumes Phase 1 events).  
> - **NO new ML models or retrained weights** (Phase 1 TFLite models remain byte-for-byte unchanged).

---

## 1. Purpose & Overview

The purpose of Phase 2 is to give STREEVA's existing edge detectors a real **Journey Context**.

While Phase 1 created isolated, modular Edge AI detectors (Route Deviation, Unexpected Stop, Fall Detection, Audio Distress), travelers exist within an active journey lifecycle. Guardian Journey Intelligence unifies:
1. **Journey State Machine**: `IDLE`, `STARTING`, `ACTIVE`, `DEGRADED`, `ARRIVING`, `ARRIVED`, `CANCELLED`.
2. **Route Corridor & Progress**: Continuous distance along route, remaining distance, and progress % with monotonic protection against GPS jitter.
3. **Stabilized ETA Intelligence**: Multi-source ETA abstraction with speed smoothing, zero-speed protection, and progress tracking (`MOVING_ON_SCHEDULE`, `SLOW_PROGRESS`, `STALLED`, `DELAYED`).
4. **Telemetry Quality Tracking**: Evaluates freshness and accuracy (`VALID`, `STALE`, `POOR_ACCURACY`, `RECOVERED`).
5. **Guardian Monitoring Loop**: The central orchestrator that ingests telemetry, feeds coordinates to Phase 1 detectors without duplicating logic, and produces a consolidated `GuardianSnapshot` for future Risk Fusion.

---

## 2. Architecture Diagram

```
                              TELEMETRY
               (GPS, Accuracy, Accel, Gyro, Audio)
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │    GUARDIAN MONITOR   │
                     │     (Orchestrator)    │
                     └───────────┬───────────┘
                                 │
      ┌──────────────────────────┼──────────────────────────┐
      │                          │                          │
      ▼                          ▼                          ▼
┌──────────────┐          ┌──────────────┐          ┌──────────────┐
│Journey State │          │Route Progress│          │ Stabilized   │
│   Machine    │          │  & Corridor  │          │     ETA      │
└──────────────┘          └──────────────┘          └──────────────┘
      │                          │                          │
      │                          ▼                          │
      │               ┌──────────────────────┐              │
      │               │  Telemetry Quality   │              │
      │               │(VALID/STALE/DEGRADED)│              │
      │               └──────────────────────┘              │
      │                          │                          │
      └──────────────────────────┼──────────────────────────┘
                                 │
                 Ingests Phase 1 Edge Events
          ┌──────────────────────┼──────────────────────┐
          │                      │                      │
          ▼                      ▼                      ▼
    Phase 1A Route         Phase 1B Stop           Phase 1C Fall
    DeviationEvent             Event                & 1D Audio
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │   GUARDIAN SNAPSHOT   │
                     └───────────┬───────────┘
                                 │
                                 ▼
                      [ FUTURE RISK FUSION ]
```

---

## 3. Journey State Machine (2A)

The journey state machine represents the physical lifecycle of a traveler's journey:

```
                      ┌──────────────────────┐
                      │         IDLE         │
                      └──────────┬───────────┘
                                 │ start_journey()
                                 ▼
                      ┌──────────────────────┐
                      │       STARTING       │
                      └──────────┬───────────┘
                                 │ valid movement (> 20m from start)
                                 ▼
       telemetry gap / ┌──────────────────────┐  near destination
       poor accuracy   │        ACTIVE        │ (dist < arrival_radius)
     ┌────────────────►│                      ├─────────────────┐
     │                 └─────────┬────────────┘                 │
     │                           │                              ▼
┌────┴─────┐                     │ cancel_journey()   ┌──────────────────┐
│ DEGRADED │                     │                    │     ARRIVING     │
└────┬─────┘                     ▼                    └─────────┬────────┘
     │ telemetry      ┌──────────────────────┐                  │ consecutive
     │ restored       │      CANCELLED       │                  │ confirmations
     └───────────────►└──────────────────────┘                  ▼
                                                      ┌──────────────────┐
                                                      │     ARRIVED      │
                                                      └──────────────────┘
```

### State Semantics
* **`IDLE`**: No journey underway.
* **`STARTING`**: Journey initialized with source/destination/route; waiting for meaningful displacement or speed.
* **`ACTIVE`**: Traveler is moving with acceptable telemetry quality.
* **`DEGRADED`**: Telemetry interrupted (time gap $> 30$s) or GPS accuracy uncertainty ($> 60$m) exceeds acceptable ceiling.
* **`ARRIVING`**: Traveler within arrival radius ($< 50$m); preliminary observation logged.
* **`ARRIVED`**: Confirmed destination arrival across consecutive valid observations.
* **`CANCELLED`**: User or system explicitly aborted the journey.

---

## 4. Route Corridor & Deterministic Progress (2B)

### 4.1 Corridor & Projection
* Uses local Equirectangular / East-North-Up metric projection.
* Authoritative cross-track distance is calculated using the existing Phase 1A geometry engine (`compute_cross_track_distance_m`).
* **Zero logic duplication**: Guardian owns the route context and corridor radius (`50.0`m); Phase 1A detector executes the geometric calculations.

### 4.2 Distance Along Route & Monotonic Safeguards
* Calculates cumulative distance along the polyline segments up to the nearest perpendicular projected point.
* **Monotonic Progress Safeguard**: GPS noise causes travelers to jitter backwards by small amounts (e.g. 10–30m). Guardian holds progress % constant if the backward jitter is within `monotonic_tolerance_m` (default 50m).
* Intentional major route reversals (e.g. turning around and walking $> 50$m back) adjust progress cleanly.

### 4.3 Arrival Confirmation
* Destination proximity check: $\text{distance} \le \text{arrival\_radius\_m}$ ($50.0$m).
* **GPS Accuracy Ceiling**: Requires accuracy $\le 40.0$m. Readings with high uncertainty are rejected to prevent premature arrival false alarms.
* **Consecutive Observations**: Requires 2 consecutive valid observations to confirm `ARRIVED`.

---

## 5. ETA Intelligence & Delay Tracking (2C)

### 5.1 Multi-Source Provenance
Guardian models ETA provenance cleanly:
* `ETASource.EXTERNAL`: Provided by dynamic navigation routing provider.
* `ETASource.ESTIMATED`: Deterministic fallback calculation.
* `ETASource.UNAVAILABLE`: When route is indeterminate.

### 5.2 Deterministic Fallback & Zero-Speed Protection
$$\text{EffectiveSpeed} = \begin{cases} 
v_{\text{smoothed}} & \text{if } v_{\text{smoothed}} \ge 0.5\text{ m/s} \\
v_{\text{default}} = 1.3\text{ m/s} & \text{if stationary / stopped}
\end{cases}$$
$$\text{RemainingSeconds} = \frac{\text{RemainingDistance}}{\text{EffectiveSpeed}}$$
$$\text{ETA} = t_{\text{current}} + \Delta t_{\text{remaining}}$$

* **Division-by-zero protection**: Stationary travelers (e.g. at stoplights) do not cause ETA to divide by zero or explode to infinity.

### 5.3 Progress & Delay Status
* **`MOVING_ON_SCHEDULE`**: Normal travel pace along expected route.
* **`SLOW_PROGRESS`**: Traveler moving slower than $0.8$ m/s without stopping.
* **`STALLED`**: Phase 1B `UnexpectedStopEvent` reports stopped state.
* **`DELAYED`**: ETA exceeds expected duration by more than `delay_threshold_s` ($180$s).

---

## 6. Telemetry Quality & Degradation (2D)

| Status | Condition | State Transition |
| :--- | :--- | :--- |
| **`VALID`** | Fresh update ($t_{\text{gap}} \le 30$s) and accuracy $\le 60$m | Maintained (`ACTIVE`) |
| **`POOR_ACCURACY`** | Accuracy uncertainty $> 60.0$m | $\to$ `DEGRADED` |
| **`STALE`** | Observation time gap $> 30.0$s | $\to$ `DEGRADED` |
| **`RECOVERED`** | Previously `DEGRADED`, now fresh & accurate | Restored (`ACTIVE` or `ARRIVING`) |

---

## 7. Guardian Snapshot Output Contract

```json
{
  "journey_id": "J-101",
  "timestamp": "2026-09-13T12:00:30Z",
  "journey_state": "ACTIVE",
  "current_lat": 13.0850,
  "current_lng": 80.2700,
  "gps_accuracy": 10.0,
  "telemetry_quality": "VALID",
  "degraded_reason": null,
  "route_progress_percent": 50.0,
  "distance_along_route_m": 556.0,
  "total_route_distance_m": 1112.0,
  "remaining_distance_m": 556.0,
  "eta": "2026-09-13T12:07:38Z",
  "eta_source": "ESTIMATED",
  "smoothed_speed_mps": 1.4,
  "arrival_status": "NOT_ARRIVED",
  "progress_status": "MOVING_ON_SCHEDULE",
  "route_deviation": { "is_deviated": false, "state": "NORMAL", ... },
  "unexpected_stop": { "is_stopped": false, "state": "MOVING", ... },
  "fall_event": null,
  "audio_distress": null,
  "active_anomalies": [],
  "details": "State: ACTIVE | Progress: 50.0% | Speed: 1.4 m/s | Remaining: 556m"
}
```

---

## 8. REST API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/guardian/journey/start` | Initializes active journey; sets state to `STARTING`. |
| `POST` | `/guardian/journey/update` | Ingests GPS/telemetry; updates progress, ETA, and edge detectors. |
| `POST` | `/guardian/journey/end` | Gracefully cancels/terminates journey (`CANCELLED`). |
| `POST` | `/guardian/journey/reset` | Resets Guardian monitor and all edge detectors to `IDLE`. |
| `GET` | `/guardian/journey/{journey_id}` | Fetches latest `GuardianSnapshot`. |

---

## 9. Journey Isolation & Zero Cross-Leakage

* Calling `start_journey` completely resets all detectors:
  - `route_deviation_detector.reset()`
  - `unexpected_stop_detector.reset()`
  - `fall_detector.reset()`
  - `audio_distress_detector.reset()`
  - `route_progress_engine.reset()`
  - `eta_engine.reset()`
* No counters, positions, or timestamps from Journey A persist into Journey B. Verified by automated unit tests.
