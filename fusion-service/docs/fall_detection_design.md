# STREEVA — Gyroscope & Fall Detection (Phase 1C) Design Document

## 1. Overview
The **Gyroscope & Accelerometer Fall Detection Engine** is an Edge AI motion analysis module located in `fusion-service/app/edge/fall_detection.py`. It detects accidental human falls while suppressing false alarms from everyday vigorous movements (e.g. running down stairs, jumping, or phone drops).

> [!IMPORTANT]
> **Heuristic Kinematic Detector**:
> This module is a deterministic multi-stage sensor detector, **NOT a trained fall-classification ML model**.
> It operates with graceful degradation: utilizing both accelerometer and gyroscope when available, and falling back to 3D gravitational tilt when gyroscope hardware is absent.

---

## 2. Multi-Stage Fall Kinematics

A true fall is characterized by three sequential kinematic phases:

```
               [1. Impact Spike: |a| >= 2.5g]
                             │
                             ▼
                      POSSIBLE_IMPACT
                             │
            [2. Orientation Change: >= 45 deg]
              (Gyro rate or Gravitational Tilt)
                             │
                             ▼
                       POSSIBLE_FALL
                             │
            [3. Post-Impact Stillness: >= 2.0s]
               (Low Acceleration Variance)
                             │
                             ▼
                       FALL_DETECTED
                             │
             [4. Recovery Movement: >= 0.6g]
                             │
                             ▼
                         RECOVERED
```

### Stage 1: Impact Spike
- Ground impact produces a rapid acceleration shock wave.
- Threshold: $|\vec{a}| \ge 2.5g$ ($\approx 24.5$ m/s$^2$). Normal walking peaks at $1.0g - 1.4g$.

### Stage 2: Posture / Orientation Change
- **With Gyroscope**: Rotational rate during impact exceeds $120^\circ$/s.
- **Without Gyroscope (Graceful Fallback)**: Computes gravitational tilt angle between pre-impact and post-impact acceleration vectors:
  $$\cos(\Delta\theta) = \frac{\vec{a}_{\text{pre}} \cdot \vec{a}_{\text{post}}}{\|\vec{a}_{\text{pre}}\| \|\vec{a}_{\text{post}}\|}$$
  $$\Delta\theta = \arccos(\text{clamp}(\cos(\Delta\theta), -1, 1)) \times \frac{180}{\pi}$$
  A standing person posture flips from vertical ($Z \approx 1g$) to horizontal ($X$ or $Y \approx 1g$), yielding $\Delta\theta \ge 45^\circ$.
  **No fake gyroscope values are fabricated**.

### Stage 3: Post-Impact Stillness
- An incapacitated person remains stationary on the ground for at least $2.0$ seconds.
- The detector calculates the sample variance of acceleration magnitude:
  $$\sigma^2 = \frac{1}{N-1}\sum (a_i - \bar{a})^2 \le 0.5$$
- If vigorous activity immediately resumes (e.g. the phone was dropped and picked up, or the user jumped and ran), the state clears back to `NORMAL`.

---

## 3. Configurable Parameters (`FallDetectionConfig`)

| Parameter | Default | Purpose |
|---|---|---|
| `impact_threshold_g` | `2.5g` | Ground impact acceleration threshold. |
| `orientation_change_threshold_deg` | `45.0 deg` | Angular posture change threshold. |
| `gyro_angular_velocity_threshold_dps` | `120.0 deg/s` | Rotational velocity confirming dynamic tumble. |
| `post_impact_inactivity_duration_s` | `2.0 s` | Required motionless window after impact. |
| `inactivity_accel_variance_max` | `0.5` | Variance ceiling defining stillness. |
| `recovery_motion_threshold_g` | `0.6g` | Deviation from 1.0g required to register standing up. |
| `consecutive_recovery_observations` | `2` | Confirmations required to transition to `RECOVERED`. |

---

## 4. Sensor Modes & Graceful Degradation

| Sensor Mode | Available Sensors | Methodology | Confidence |
|---|---|---|---|
| `accel_and_gyro` | 3-axis Accel + 3-axis Gyro | Full rotational angular velocity + impact + stillness | High ($0.91 - 1.0$) |
| `accel_only` | 3-axis Accel | 3D gravitational vector tilt + impact + stillness | Medium-High ($0.85 - 0.90$) |
| `insufficient_data`| None | Cannot evaluate | Zero |

---

## 5. Output Contract: `FallDetectedEvent`

```json
{
  "event_type": "FALL_DETECTED",
  "is_fall": true,
  "state": "FALL_DETECTED",
  "impact_magnitude_g": 3.18,
  "orientation_change_deg": 63.2,
  "confidence": 0.91,
  "sensor_mode": "accel_and_gyro",
  "timestamp": "2026-09-12T14:00:03Z",
  "latitude": 13.0600,
  "longitude": 80.2500,
  "details": "Fall confirmed: Impact 3.18g, orientation change 63.2 deg, post-impact stillness verified (2.0s, var=0.00)."
}
```
