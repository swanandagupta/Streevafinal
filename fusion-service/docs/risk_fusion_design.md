# STREEVA — Risk Fusion 2.0 Architectural Specification
`fusion-service/docs/risk_fusion_design.md`

## 1. Overview & Objective
Risk Fusion 2.0 transforms isolated, heterogeneous edge and geospatial signals into a unified, contextual safety risk score and explainable factor breakdown. It ingests:
- Geospatial area crime & road network isolation priors from `area-risk-service`
- Kinematic motion anomaly scores (1D-CNN + jerk heuristic)
- Route deviation cross-track status from Phase 1A
- Unexpected stationary stops from Phase 1B
- Gyroscope/accelerometer multi-stage fall detection from Phase 1C
- Acoustic vocal distress probabilities from Phase 1D
- Journey context, route progress, and telemetry quality from Phase 2 Guardian

### Architectural Pipeline
```
               
---

## 2. Signal Normalization Table
All incoming heterogeneous signals are mapped into a standardized $[0.0, 1.0]$ contribution scale:

| Signal | Raw Input Range / Domain | Normalized Value ($v_i$) | State Contribution |
| :--- | :--- | :---: | :--- |
| **Area Risk** | $[0, 100]$ points | $\text{score} / 100.0$ | Continuous |
| **Motion Anomaly** | $[0, 100]$ score | $\text{score} / 100.0$ | Continuous |
| **Route Deviation** | `NORMAL`, `POSSIBLE_DEVIATION`, `DEVIATED` | $0.0$, $0.4$, $1.0$ | Single transitory spike damped by $0.75\times$ |
| **Unexpected Stop** | `MOVING`, `POSSIBLE_STOP`, `STOPPED` | $0.0$, $0.5$, $1.0$ | Continuous stationary duration |
| **Fall Detection** | `NORMAL`, `SUSPECTED`, `FALL_DETECTED` | $0.0$, $0.5$, $1.0$ | Subject to exponential recency decay |
| **Audio Distress** | `NORMAL`, `POSSIBLE_DISTRESS`, `DISTRESS_DETECTED` | $0.0$, $0.5 \times p$, $1.0 \times p$ | Scaled by CNN probability $p \in [0, 1]$ and decay |

---

## 3. Dynamic Weight Re-normalization for Missing Signals
Base weights configured in `configs/contextual_safety_config.yaml`:
- Area Risk: $0.20$
- Route Deviation: $0.20$
- Unexpected Stop: $0.15$
- Motion Anomaly: $0.15$
- Fall Detection: $0.15$
- Audio Distress: $0.15$
- **Total**: $1.00$

When a signal is unavailable (e.g. device without microphone permission, or offline without area risk cache), the engine does **not** assume risk is zero. Instead:
1. The missing signal is flagged `UNAVAILABLE` in `data_quality.signals`.
2. Effective weights for available signals are dynamically re-normalized:
   $$w'_i = \frac{w_i}{\sum_{j \in \text{available}} w_j}$$
3. If all signals are missing, the assessment reports `risk_score = 0.0`, `overall_confidence = 0.0`, and surfaces data quality degradation explicitly.

---

## 4. Temporal Persistence & Recency Decay
A single isolated sensor noise spike must not dominate journey risk. Conversely, a severe physical shock (like a fall) from 10 minutes ago should not permanently poison instantaneous assessment.

### Exponential Half-Life Decay
For shock and transient acoustic events:
$$\text{decay\_multiplier} = \exp\left(-\frac{\ln(2) \cdot \Delta t}{T_{\text{half-life}}}\right)$$
- $T_{\text{fall}} = 120$ seconds
- $T_{\text{audio}} = 60$ seconds
- $T_{\text{general}} = 90$ seconds

---

## 5. Contextual Interaction Modifiers
Compounded threats where multiple warning signals co-occur receive transparent, bounded additive boosts:
1. **High Area Risk ($> 60.0$) + Confirmed Route Deviation**: $+12.0$ points boost.
2. **Unexpected Stop + High Area Risk + Delayed Journey**: $+10.0$ points boost.
3. **High Audio Distress ($> 0.70$) + Confirmed Fall**: $+15.0$ points boost.

All final risk scores are strictly clamped to $[0.0, 100.0]$.

---

## 6. Risk Scoring & Classification Boundaries

| Risk Score Range | Classification Tier | Operational Meaning |
| :---: | :---: | :--- |
| **$0.00 - 24.99$** | `LOW` | Normal journey progression; safe baseline. |
| **$25.00 - 49.99$** | `MEDIUM` | Isolated concern or elevated ambient risk; standard monitoring. |
| **$50.00 - 74.99$** | `HIGH` | Confirmed anomaly (e.g. deviation or fall); elevated monitoring active. |
| **$75.00 - 100.00$** | `CRITICAL` | Severe multi-factor threat or confirmed physical distress. |

---

## 7. Explainability Structure
Every assessment emits a structured list of active `RiskFactor` records and designates a `dominant_factor`:
```json
{
  "name": "ROUTE_DEVIATION",
  "contribution": 50.0,
  "confidence": 0.92,
  "state": "DEVIATED",
  "reason": "Route deviation status DEVIATED (cross-track: 85.0m)."
}
```

---

## 8. Decision Engine Separation & Hysteresis
Decision logic is completely decoupled from risk score calculation:
- `LOW` $\rightarrow$ `MONITOR`
- `MEDIUM` $\rightarrow$ `ADAPT_MONITORING` / `REQUEST_CHECK_IN`
- `HIGH` $\rightarrow$ `ELEVATED_MONITORING`
- `CRITICAL` $\rightarrow$ `AUTONOMOUS_RESPONSE_REQUIRED`

### Hysteresis / Debouncing Rules
- **Escalation**:
  - Escalating to `AUTONOMOUS_RESPONSE_REQUIRED` requires 2 consecutive observations $\ge 75.0$ (unless concurrent high-confidence audio distress + fall is detected).
  - During the 1st observation of a critical threat, the decision engine immediately escalates to `ELEVATED_MONITORING` to ensure client sensors are primed.
- **De-escalation**:
  - Requires 3 consecutive observations below lower threshold before stepping down, preventing rapid oscillation on fluctuating scores.

---

## 9. Strict Architectural Boundaries
- 🚫 **NO automatic emergency calls or SOS dispatch.**
- 🚫 **NO SMS generation or contact notification.**
- 🚫 **NO mobile UI or hardware sensor polling.**
- Output serves purely as intelligence and policy recommendation for downstream layers.
