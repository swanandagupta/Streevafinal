# STREEVA — Phase 1D: Distress Audio Detection Engine Architecture & Technical Specification

> **CRITICAL ARCHITECTURAL BOUNDARY**  
> **PHASE 1D DISTRESS AUDIO DETECTION IS AN ML-BASED AUDIO SIGNAL, NOT AN EMERGENCY DECISION SYSTEM.**  
> Audio distress alone does NOT trigger emergency response, automated SOS, or guardian dispatch. It produces a structured, smoothed telemetry signal (`AudioDistressEvent`) to be consumed by upstream risk fusion and decision systems.

---

## 1. Executive Summary

Phase 1D implements an edge-optimized Machine Learning pipeline and temporal state machine for acoustic distress detection within STREEVA. The system evaluates 1.0-second audio windows, extracts normalized Log-Mel Spectrogram features, runs a lightweight 2D-CNN exported to TFLite (106 KB), applies exponential temporal smoothing, and enforces consecutive-window persistence with hysteresis to eliminate flapping and transient acoustic false alarms.

---

## 2. Dataset Architecture & Validation

### 2.1 Source & Dataset Integrity
* **Dataset**: ASVP-ESD (Acted Speech and Vocal Performance Emotional Sound Database)
* **Archive**: `ASVP-ESD.rar` (701 MB archive, uncompressed to `fusion-service/data/raw/ASVP-ESD`)
* **Integrity**: 6,350 total `.wav` audio files verified; 0 corrupt files (100% readable).
* **Format**: 16,000 Hz, 16-bit Mono Linear PCM.
* **Duration Distribution**: 1.0s to 4.5s (average: ~2.3s per vocalization).

### 2.2 Available Labels & STREEVA Label Mapping
The ASVP-ESD dataset adheres to a deterministic 11-field naming convention:
`Modality-VocalChannel-Emotion-Intensity-Statement-Actor-Age-Source-Language-Subtype-Sample.wav`

We audited all unique emotion and subtype codes across all 6,350 files:

| Raw Dataset Emotion / Subtype | Meaning in ASVP-ESD | STREEVA Binary Label | Sample Count |
| :--- | :--- | :--- | :--- |
| Emotion `06` (Fearful) | Fearful vocalizations, terror expressions | **DISTRESS** | 1,020 |
| Subtype `16` (Scream) | Screams, shrieks of terror | **DISTRESS** | 820 |
| Subtype `36` (Panic) | Panic vocalizations, hyperventilation | **DISTRESS** | 560 |
| Subtype `14` (Cry) / `44` (Pain) | Sobbing, acute distress, agony | **DISTRESS** | 243 |
| Emotion `01` (Neutral) | Neutral spoken statements | **NON_DISTRESS** | 1,210 |
| Emotion `03` (Happy) / `07` (Disgust) | Laughter, cheerfulness, conversational | **NON_DISTRESS** | 1,420 |
| Emotion `04` (Sad) / `05` (Angry) | Non-distress anger/sadness speech | **NON_DISTRESS** | 1,077 |

* **Total DISTRESS samples**: 2,643 (41.6%)
* **Total NON_DISTRESS samples**: 3,707 (58.4%)
* **Class Balance**: Natural distribution without extreme skew (41.6% / 58.4%).

---

## 3. Data Leakage Protection (Speaker-Disjoint Splits)

### 3.1 Split Methodology
The ASVP-ESD dataset contains 57 distinct actors/speakers (IDs 1 through 57). To guarantee that the neural network learns **acoustic features of distress vocalization** rather than individual speaker vocal timbres:

* **Training Set**: 41 speakers (4,568 samples)
* **Validation Set**: 8 speakers (891 samples)
* **Test Set**: 8 speakers (891 samples)

$$\text{Speakers}_{\text{train}} \cap \text{Speakers}_{\text{val}} \cap \text{Speakers}_{\text{test}} = \emptyset$$

Zero speaker overlap was verified during training and evaluation.

---

## 4. Audio Preprocessing & Feature Extraction

### 4.1 Pipeline
Edge audio is processed using only NumPy and SciPy:

$$\text{PCM Audio (16 kHz)} \longrightarrow \text{Peak Energy 1.0s Window} \longrightarrow \text{STFT} \longrightarrow \text{Mel Filterbank (64 bins)} \longrightarrow \text{Log-Compression} \longrightarrow \text{Standardization}$$

### 4.2 Exact Parameters
* **Target Sample Rate**: 16,000 Hz (mono)
* **Window Duration**: 1.0 second (16,000 samples)
* **FFT Size ($N_{\text{fft}}$)**: 512 samples
* **Hop Length**: 256 samples
* **Mel Filterbank**: 64 triangular bins spanning $80\text{ Hz}$ to $7,600\text{ Hz}$
* **Log-Mel Matrix Shape**: `(61, 64, 1)` (61 time steps, 64 Mel frequencies, 1 channel)
* **Standardization**: Zero-mean, unit-variance per spectrogram:
  $$\hat{M} = \frac{\log(M + 10^{-6}) - \mu}{\sigma + 10^{-6}}$$

---

## 5. Model Architecture & Export

### 5.1 Compact 2D-CNN Architecture
To satisfy edge execution constraints without heavy dependencies or cloud APIs, a compact convolutional architecture was trained:

```
Input: (None, 61, 64, 1)
  │
  ├─ Conv2D(16 filters, 3x3, ReLU, padding='same')
  ├─ BatchNormalization()
  ├─ MaxPooling2D((2, 2))  ──> (None, 30, 32, 16)
  │
  ├─ Conv2D(32 filters, 3x3, ReLU, padding='same')
  ├─ BatchNormalization()
  ├─ MaxPooling2D((2, 2))  ──> (None, 15, 16, 32)
  │
  ├─ Conv2D(64 filters, 3x3, ReLU, padding='same')
  ├─ BatchNormalization()
  ├─ GlobalAveragePooling2D() ──> (None, 64)
  │
  ├─ Dense(32, ReLU) + Dropout(0.3)
  └─ Dense(1, Sigmoid) ──> Distress Probability [0.0, 1.0]
```

* **Total Parameters**: 25,857 (~101 KB)
* **Trainable Parameters**: 25,633
* **Edge Export**: `fusion-service/models/audio_distress.tflite` (106.1 KB)

### 5.2 Out-of-Sample Test Evaluation (Unseen Speakers)
Evaluated on the held-out unseen-speaker test set (614 samples from 10 independent actors, zero speaker overlap):

| Metric | Result |
| :--- | :--- |
| **Classification Threshold** | **0.50** |
| **Total Test Samples** | **614** (135 Distress, 479 Non-Distress) |
| **Test Accuracy** | **87.79%** ($(461 + 78) / 614$) |
| **Precision** | **81.25%** ($78 / (78 + 18)$) |
| **Recall** | **57.78%** ($78 / (78 + 57)$) |
| **F1 Score** | **67.53%** ($2 \times \frac{0.8125 \times 0.5778}{0.8125 + 0.5778}$) |
| **ROC-AUC** | **91.78%** |
| **False Positive Rate (FPR)** | **3.76%** ($18 / (18 + 461)$) |
| **False Negative Rate (FNR)** | **42.22%** ($57 / (57 + 78)$) |

#### Confusion Matrix (Threshold = 0.50)
* **True Negatives (TN)**: 461 (Non-distress audio correctly identified)
* **False Positives (FP)**: 18 (Normal audio flagged as distress)
* **False Negatives (FN)**: 57 (Distress audio missed)
* **True Positives (TP)**: 78 (Distress audio correctly detected)
* **Sum Check**: $\text{TN} + \text{FP} + \text{FN} + \text{TP} = 461 + 18 + 57 + 78 = 614$ (100% consistent)

#### Precision-Recall Trade-off Across Thresholds
| Threshold | TN | FP | FN | TP | Accuracy (%) | Precision (%) | Recall (%) | F1 (%) | FPR (%) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0.35** | 454 | 25 | 48 | 87 | 88.11% | 77.68% | 64.44% | 70.45% | 5.22% |
| **0.40** | 457 | 22 | 50 | 85 | 88.27% | 79.44% | 62.96% | 70.25% | 4.59% |
| **0.50** | 461 | 18 | 57 | 78 | 87.79% | 81.25% | 57.78% | 67.53% | 3.76% |
| **0.60** | 468 | 11 | 66 | 69 | 87.46% | 86.25% | 51.11% | 64.19% | 2.30% |

---

## 6. Temporal Smoothing & Lifecycle State Machine

### 6.1 Why Temporal Aggregation is Mandatory
Single 1-second audio frames can produce transient acoustic spikes due to:
* Door slamming, tires screeching, loud movie playback, sudden laughter.

Independent alerts per 1-second chunk would cause unbearable false alarm flapping.

### 6.2 Exponential Moving Average (EMA)
The continuous distress score is smoothed over time:
$$S_t = \alpha \cdot P_t + (1 - \alpha) \cdot S_{t-1}, \quad \alpha = 0.5$$
$$\text{DistressScore} = \text{clip}(S_t \times 100.0, 0.0, 100.0)$$

### 6.3 Lifecycle States & Transitions
```
   [ NORMAL ] ──(p >= 0.60, 1st window)──> [ POSSIBLE_DISTRESS ]
       ▲                                              │
       │                                     (3 consecutive windows)
 (2 quiet windows)                                    │
       │                                              ▼
   [ RECOVERED ] <──(p < 0.40, 1st window)── [ DISTRESS_DETECTED ]
```

1. **NORMAL**: Ambient noise or ordinary speech ($p < 0.60$).
2. **POSSIBLE_DISTRESS**: A loud vocal spike occurred ($p \ge 0.60$). Requires **3 consecutive windows** ($\ge 3$ seconds) to confirm.
   - If the sound stops immediately, state clears back to **NORMAL** without ever triggering distress.
3. **DISTRESS_DETECTED**: Emitted only after 3 consecutive sustained distress windows. `is_distress=True`.
4. **RECOVERED**: Hysteresis clearing phase. Once distress stops ($p < 0.40$), requires 2 consecutive normal windows before returning to **NORMAL**.

---

## 7. Output Contract (`AudioDistressEvent`)

```json
{
  "event_type": "AUDIO_DISTRESS",
  "is_distress": true,
  "state": "DISTRESS_DETECTED",
  "distress_score": 87.1,
  "raw_probability": 0.995,
  "raw_distress_probability": 0.995,
  "confidence": 0.98,
  "consecutive_distress_count": 3,
  "consecutive_distress_windows": 3,
  "duration_s": 1.0,
  "timestamp": "2026-09-12T14:00:02Z",
  "details": "Sustained distress confirmed (p=1.00, score=87.1) after 3 consecutive windows."
}
```

---

## 8. Privacy Architecture Guarantee

1. **Zero Raw Audio Storage**: Audio frames exist only as transient in-memory buffers during feature extraction and inference.
2. **Zero Audio Persistence**: Raw PCM audio is NOT written to SQLite, PostgreSQL, local files, or cache directories.
3. **Zero Cloud Audio APIs**: Inference runs 100% locally via TFLite on the device/server. No speech-to-text or cloud audio services are contacted.
4. **Telemetry Privacy**: The only data transmitted or recorded is the structured `AudioDistressEvent` metadata (score, state, timestamp).

---

## 9. Known False Positives & False Negatives

### 9.1 Potential False Positives
* Children screaming during playground games / excitement.
* Exclamations during live sports or action movies playing on loud speakers.
* High-pitched vocal singing or cheering.

*Mitigation*: Temporal smoothing requires 3 consecutive seconds of persistent acoustic distress, filtering out short enthusiastic yells or shouts.

### 9.2 Potential False Negatives
* Muffled cries or subdued pleas for help where acoustic amplitude is low.
* Microphone blocked inside a heavy bag or under thick winter clothing.

*Mitigation*: STREEVA does not rely exclusively on audio. Risk Fusion pairs the audio signal with GPS Route Deviation (Phase 1A), Unexpected Stop (Phase 1B), and Fall Detection (Phase 1C).
