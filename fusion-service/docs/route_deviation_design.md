# STREEVA — Route Deviation Detection (Phase 1A) Design Document

## 1. Overview
The **Route Deviation Detection Engine** is an Edge AI / on-device safety module designed to continuously monitor a traveler's geographic trajectory against a planned journey route polyline. It computes the perpendicular cross-track distance in meters, evaluates temporal persistence against GPS noise, enforces a hysteresis recovery corridor, and outputs a structured `RouteDeviationEvent`.

> [!IMPORTANT]
> **Heuristic / Geometric Detector**:
> This module is a deterministic, geometric/heuristic edge detector, **NOT an ML model**.
> The `confidence` score represents geometric and GPS accuracy certainty, not a learned classification probability.

---

## 2. Mathematical Calculation: Cross-Track Distance

### Why Not Naive Coordinate Differences?
Naive differences ($\Delta \text{lat}$ or $\Delta \text{lng}$) fail because:
1. Degrees of longitude shrink as latitude increases ($\cos(\text{lat})$ scaling).
2. Straight lines on roads run at arbitrary angles; distance must be perpendicular to each linear segment rather than snapping only to route vertices.

### Local Equirectangular / ENU Metric Projection
For short urban journeys ($< 50$ km), a local Equirectangular projection centered at the query coordinates provides high precision (distortion $< 0.05\%$) without heavyweight GIS dependencies (e.g. GDAL/GEOS):

$$x = R \cdot (\lambda - \lambda_0) \cdot \cos(\phi_0)$$
$$y = R \cdot (\phi - \phi_0)$$

where $R = 6,371,000$ meters, $\phi_0 = \text{radians}(\text{lat})$, $\lambda_0 = \text{radians}(\text{lng})$.

### Perpendicular Segment Projection
For each segment $A(x_A, y_A) \to B(x_B, y_B)$ in the route polyline and query point $P(0, 0)$:
1. Vector $\vec{v} = B - A$ and vector $\vec{w} = P - A$.
2. Segment length squared: $\|\vec{v}\|^2 = v_x^2 + v_y^2$.
3. Projection scalar: $t = \frac{\vec{w} \cdot \vec{v}}{\|\vec{v}\|^2}$.
4. Clamped parameter: $t^* = \max(0.0, \min(1.0, t))$.
5. Closest point on segment: $Q = A + t^* \vec{v}$.
6. Perpendicular distance: $d = \|P - Q\| = \sqrt{(P_x - Q_x)^2 + (P_y - Q_y)^2}$.

The minimum distance $d$ across all segments $i \in [0, N-2]$ is the cross-track distance in meters, and $i$ identifies the `nearest_segment_index`.

---

## 3. Route Corridor & Configurable Thresholds

Urban GPS suffers from multipath reflections, tall building occlusion, and road widths (~15-25m). The detector utilizes configurable thresholds:

| Parameter | Default | Purpose |
|---|---|---|
| `deviation_threshold_m` | `50.0 m` | Beyond this distance, the traveler is outside the acceptable road corridor. |
| `normal_threshold_m` | `35.0 m` | Hysteresis recovery threshold; must come within 35m to recover. |
| `consecutive_deviations_required` | `3` | Temporal filter requiring 3 consecutive points $> 50$m to confirm `DEVIATED`. |
| `consecutive_recoveries_required` | `2` | Requires 2 consecutive points $\le 35$m to restore `NORMAL`. |
| `max_acceptable_gps_accuracy_m` | `60.0 m` | GPS uncertainty limit; degraded readings cannot trigger `DEVIATED`. |

---

## 4. State Machine Lifecycle & Hysteresis

```
                [d > 50m (obs 1)]
   ┌──────────────────────────────────────────────┐
   │                                              │
   ▼                                              │
NORMAL <─────────────────── POSSIBLE_DEVIATION ───┘
   ▲     [d <= 35m (cleared)]       │
   │                                │ [d > 50m (obs >= 3)]
   │                                ▼
   │                            DEVIATED
   │                                │
   │ [d <= 35m (obs >= 2)]          │ [d <= 35m (obs 1)]
   └─────────────────────────── RECOVERED
```

### Hysteresis Mechanism
When distance fluctuates between $35.0$m and $50.0$m (the intermediate buffer zone), the detector remains in its current state. This prevents rapid toggling (`NORMAL` $\to$ `DEVIATED` $\to$ `NORMAL` $\to$ `DEVIATED`) when walking along the edge of the corridor.

---

## 5. GPS Noise & Accuracy Protection

1. **Multipath / Spike Suppression**: A single GPS reading at $100$m distance only sets `POSSIBLE_DEVIATION` ($1$ of $3$). If the subsequent reading returns to the corridor, the tentative deviation dissipates back to `NORMAL`.
2. **Degraded GPS Accuracy**: When horizontal accuracy uncertainty $> 60$m (e.g. entering an underpass or dense high-rise corridor), state transitions into `DEVIATED` are suppressed and logged as degraded uncertainty.
3. **Confidence Scoring**: Heuristic confidence ($0.0 - 1.0$) factors in GPS horizontal accuracy, threshold margin, and temporal persistence.

---

## 6. Output Contract: `RouteDeviationEvent`

```json
{
  "event_type": "ROUTE_DEVIATION",
  "is_deviated": true,
  "state": "DEVIATED",
  "deviation_distance_m": 87.4,
  "threshold_m": 50.0,
  "recovery_threshold_m": 35.0,
  "confidence": 0.91,
  "nearest_segment_index": 3,
  "gps_accuracy_m": 8.0,
  "latitude": 13.0827,
  "longitude": 80.2707,
  "timestamp": "2026-09-12T17:24:10Z",
  "details": "Sustained deviation confirmed (87.4m > 50.0m) after 3 consecutive observations."
}
```

---

## 7. Future Integration: Guardian Mode & Mobile Application

1. **Mobile Application**:
   - The mobile application (React Native / Flutter) or route planner supplies the initial polyline array `[{"lat": ..., "lng": ...}, ...]` at journey start.
   - GPS telemetry points (with timestamp, lat, lng, and accuracy) stream periodically (e.g. 1Hz - 0.2Hz).
2. **Guardian Mode**:
   - Guardian Mode receives `RouteDeviationEvent` as an informational input signal.
   - If `is_deviated=True`, Guardian Mode can initiate a soft check-in ("Are you still on your way?") or escalate the situational awareness level.
   - **Crucially**: Route deviation does NOT directly trigger police/emergency SOS; it is an input signal to multi-factor decision logic.
