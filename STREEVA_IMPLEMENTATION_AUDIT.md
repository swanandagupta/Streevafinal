# STREEVA — Comprehensive Implementation Audit & Architectural Assessment Report

**Date:** September 2026  
**Auditor:** Antigravity AI Pair Programmer  
**Project:** STREEVA (AI-Powered Women's Personal Safety & Intelligent Travel System)  
**Workspace:** `c:\Users\swana\Desktop\Swananada\BTech\Project\STREEVA-main`  
**Mode:** READ-ONLY AUDIT (Zero code changes made)

---

## 1. Executive Summary

A comprehensive, read-only inspection of the entire STREEVA codebase was performed. The repository does not currently contain a mobile app (React Native / Flutter / Android), Node.js backend, PostGIS database, Redis cache, or Firebase configuration. 

Instead, the teammate has built **two production-grade Python FastAPI microservices**:
1. **`area-risk-service` (Port 8000):** A geospatial area safety risk engine combining historical NCRB 2014 crime priors, OpenStreetMap road topology (via OSMnx), Google Places POI density, WorldPop density, and TomTom live traffic flow, mapped onto Uber H3 hexagonal cells (~174m resolution).
2. **`fusion-service` (Port 8001):** A risk fusion and trip monitoring service that ingests streaming GPS and accelerometer telemetry, runs a trained 1D-CNN TensorFlow Lite model (`motion_anomaly.tflite` trained on UCI HAR) combined with jerk heuristics, queries `area-risk-service`, and blends area risk with motion anomaly risk. It includes an SQLite persistence layer, a WebSocket replay endpoint, a Python replay script, and a browser-based sensor data logger (`logger.html`).

Crucially, the audit revealed several critical broken dependencies in `area-risk-service` where a recent refactor towards an offline Parquet index and LightGBM model left missing binary artifacts, causing `GET /area-risk` to throw HTTP 503 by default.

---

## 2. Overall Project Structure

```
STREEVA-main/
├── .gitignore
├── dataset.json                         [NCRB 2014 IPC Crime dataset (906 KB)]
├── area-risk-service/                   [FastAPI Hyperlocal Risk Scoring Service]
│   ├── app/
│   │   ├── main.py                      [FastAPI app entry point & lifespan events]
│   │   ├── config.py                    [Pydantic settings, city config & scoring weights loader]
│   │   ├── api/
│   │   │   └── routes.py                [GET /area-risk, GET /health, GET /cache/stats]
│   │   ├── core/
│   │   │   ├── h3_utils.py              [Uber H3 hex indexing, distance, centroid calculations]
│   │   │   └── time_multiplier.py       [Time-of-day risk multipliers]
│   │   ├── models/
│   │   │   └── schemas.py               [Pydantic request/response schemas]
│   │   ├── scoring/
│   │   │   ├── base_scorer.py           [BaseRiskScorer ABC, FeatureSet & RiskResult dataclasses]
│   │   │   ├── weighted_scorer.py       [V1 transparent weighted linear risk formula]
│   │   │   ├── ml_risk_scorer.py        [V2 LightGBM model with SHAP explainability]
│   │   │   └── train_model.py           [LightGBM training script using synthetic/proxy targets]
│   │   ├── services/
│   │   │   ├── district_service.py      [Post-2019 TN district polygon lookup]
│   │   │   ├── macro_baseline_service.py[NCRB 2014 district crime score loader]
│   │   │   ├── offline_feature_service.py [Fast Parquet feature lookup]
│   │   │   ├── osm_service.py           [Online OSMnx road topology feature extractor]
│   │   │   ├── places_service.py        [Google Places New API POI extractor & OSM fallback]
│   │   │   ├── population_service.py    [WorldPop 100m GeoTIFF raster extractor]
│   │   │   └── tomtom_traffic_service.py[TomTom Traffic Flow API v4 real-time flow fetcher]
│   │   ├── static/
│   │   │   └── index.html               [Interactive Dark-mode Area Risk Dashboard UI]
│   │   └── utils/
│   │       ├── logger.py                [Structured JSON logging with structlog]
│   │       └── retry.py                 [Tenacity exponential backoff decorators]
│   ├── configs/
│   │   ├── city_config.yaml             [Chennai spatial bbox, time bands, H3 res-9]
│   │   └── scoring_weights.yaml         [Risk feature weights & classification thresholds]
│   ├── data/
│   │   ├── cache/                       [DiskCache JSON storage for OSM and TomTom]
│   │   ├── processed/
│   │   │   └── ncrb_district_lookup.json[Aggregated NCRB violent crime rates]
│   │   └── raw/
│   │       └── ncrb_ipc_crimes_2014.json[Raw NCRB IPC crimes dataset]
│   ├── notebooks/
│   │   └── area_risk_pipeline.ipynb     [Methodology walkthrough notebook]
│   ├── scripts/
│   │   ├── build_hex_layers.py          [Offline Parquet feature builder]
│   │   ├── build_training_target.py     [Empirical Bayes target shrinkage builder]
│   │   ├── demo_locations.py            [Qualitative validation script (6 Chennai locations)]
│   │   ├── download_worldpop.py         [WorldPop GeoTIFF downloader]
│   │   ├── ingest_ncrb.py               [NCRB data normalization script]
│   │   └── ingest_open_datasets.py      [Safecity & Nightlights ingestion stub]
│   ├── tests/
│   │   ├── api/test_routes.py           [FastAPI TestClient route tests]
│   │   ├── integration/test_cache.py    [Disk cache TTL and eviction tests]
│   │   └── unit/
│   │       ├── test_h3_utils.py         [H3 cell and distance tests]
│   │       ├── test_normalizer.py       [Sigmoid & min-max normalization tests]
│   │       └── test_scoring.py          [WeightedRiskScorer unit tests]
│   ├── requirements.txt                 [Service Python dependencies]
│   ├── pytest.ini                       [Test configuration]
│   └── .env.example                     [API key templates]
│
└── fusion-service/                      [FastAPI Risk Fusion & Journey Telemetry Service]
    ├── app/
    │   ├── main.py                      [FastAPI app entry point, CORS, DB initialization]
    │   ├── schemas.py                   [Pydantic models: TripCreate, JourneyRiskRequest/Response]
    │   ├── api/
    │   │   └── routes.py                [POST /log-trip, POST /journey-risk, WS /replay/{trip_id}]
    │   ├── db/
    │   │   ├── database.py              [SQLAlchemy SQLite engine & session setup]
    │   │   └── models.py                [Trip and TripPoint ORM models]
    │   ├── ml/
    │   │   └── motion_model.py          [ActivityStateClassifier: 1D-CNN TFLite + Jerk heuristic]
    │   └── scoring/
    │       └── fusion_scorer.py         [RiskFusionScorer: Blended weighted score]
    ├── data/
    │   └── UCI_HAR_Dataset.zip          [Smartphone Human Activity Recognition dataset (61 MB)]
    ├── docs/
    │   └── trip_collection.md           [Phone-based sensor collection guide using ngrok]
    ├── models/
    │   └── motion_anomaly.tflite        [Quantized 1D-CNN binary motion classifier (149 KB)]
    ├── notebooks/
    │   └── motion_anomaly_training.ipynb[1D-CNN motion training exploration notebook]
    ├── scripts/
    │   ├── demo_replay.py               [Terminal client streaming replay over WebSocket]
    │   └── train_motion_model.py        [End-to-end 1D-CNN model training script]
    ├── tests/
    │   └── test_fusion.py               [Unit & integration tests for fusion engine]
    ├── fusion_weights.yaml              [Weights for Area Risk, Motion Anomaly, Audio Distress]
    ├── fusion.db                        [SQLite database containing recorded trips]
    ├── logger.html                      [Web tool for recording GPS + accelerometer on mobile]
    └── requirements.txt                 [Service Python dependencies]
```

---

## 3. Architecture Mapping & Status

| Target STREEVA Module | Status | Existing Files | What Exists | Missing Work |
| :--- | :---: | :--- | :--- | :--- |
| **Authentication** | 🔴 MISSING | None | None | JWT/OAuth or Firebase Auth, user sessions, token verification |
| **Journey Setup** | 🟡 PARTIAL | `fusion-service/app/schemas.py`, `fusion-service/app/db/models.py` | Schema stores `trip_id`, `label`, `start_time`, `end_time` | Origin/destination inputs, emergency contact selection, route planning |
| **Guardian Mode** | 🟡 PARTIAL | `fusion-service/app/api/routes.py`, `demo_replay.py` | Windowed telemetry evaluation and WebSocket replay | State machine (IDLE, ACTIVE, DEVIATED, etc.), continuous background monitoring |
| **GPS Tracking** | 🟡 PARTIAL | `logger.html`, `fusion-service/app/schemas.py` | Browser Geolocation API captures `lat`/`lng` points | Native on-device GPS manager, background service, kalman filter / jitter smoothing |
| **Accelerometer** | ✅ COMPLETE | `fusion-service/app/ml/motion_model.py`, `logger.html` | Accelerometer ingestion, magnitude normalization, jerk calculation | Edge-native sensor reader for mobile (currently browser DeviceMotionEvent) |
| **Gyroscope** | 🔴 MISSING | None | None | Ingestion, rotational velocity tracking, tumble/fall detection |
| **Microphone** | 🔴 MISSING | None | None | Audio capture, permissions, edge feature extraction |
| **Edge Movement Analysis**| ⚠️ NEEDS MOD | `fusion-service/app/ml/motion_model.py` | 1D-CNN TFLite model detects steady vs dynamic state + jerk heuristic | Runs server-side in Python, not on edge device; only binary still vs move, not erratic/struggle |
| **Distress Audio** | 🔴 MISSING | `fusion-service/fusion_weights.yaml` | Placeholder weight (`audio_distress: 0.00`) | Audio classification model (screaming, distress keywords, gunshot, crying) |
| **Route Deviation** | 🔴 MISSING | None | None | Expected corridor generation, cross-track distance algorithm, deviation state |
| **Unexpected Stop** | 🔴 MISSING | `logger.html` (has a `stop-test` label) | Label exists in logger tool | Velocity zero-check timer, linger duration threshold, prompt state |
| **ETA Prediction** | 🔴 MISSING | None | None | Dynamic speed calculation, traffic delay factoring, distance to destination |
| **Risk Engine** | ✅ COMPLETE | `area-risk-service/app/scoring/` | Full multi-criteria area risk scoring (Weighted linear + LightGBM ML) | Re-align default scorer to weighted or provide missing ML model artifact |
| **Risk Fusion** | ✅ COMPLETE | `fusion-service/app/scoring/fusion_scorer.py` | Blends area risk, motion anomaly, and audio distress into [0, 100] | Dynamic factor weighting based on context and confidence |
| **Adaptive Sensor Manager**| 🔴 MISSING | None | None | State-based sensor throttling (LOW -> GPS; HIGH -> Audio/Motion) |
| **Decision Logic** | 🟡 PARTIAL | `fusion-scorer.py` (thresholds: Low, Med, High, Critical) | Maps score to 4 classification bands | Autonomous action triggers (notifications, safe havens, countdowns) |
| **Live Location Sharing** | 🟡 PARTIAL | `fusion-service/app/api/routes.py` (WebSocket replay) | Point streaming over WebSocket | Secure sharing token, recipient link, authenticated live channel |
| **Emergency Response** | 🔴 MISSING | None | None | Countdown timer, cancellation logic, autonomous trigger pipeline |
| **Emergency Contacts** | 🔴 MISSING | None | None | Contact schema, CRUD operations, priority ordering, dispatch channels |
| **Evidence Storage** | 🔴 MISSING | None | None | Tamper-proof audio/location clip storage, hash generation, metadata |
| **Push Notifications** | 🔴 MISSING | None | None | FCM / APNS push integration for check-in prompts and emergency alerts |
| **Offline Guardian Mode**| 🔴 MISSING | None | None | Local journey corridor caching, offline countdown, SMS fallback queue |
| **Maps** | 🟡 PARTIAL | `area-risk-service/app/services/osm_service.py` | OSMnx road topology & Overpass extraction | Client map display, route polyline rendering, safe havens display |
| **Traffic** | ✅ COMPLETE | `area-risk-service/app/services/tomtom_traffic_service.py` | Live TomTom Flow v4 API with speed ratio & disk caching | Connect traffic congestion directly into route ETA and risk modifier |
| **Weather** | 🔴 MISSING | None | None | Rain/storm/visibility API provider and risk coefficient |
| **Crime Data** | ✅ COMPLETE | `area-risk-service/data/raw/ncrb_ipc_crimes_2014.json` | District-wise 2014 NCRB violent crime normalization | Fine-grained hyperlocal incident synthesis / FIR proxy |
| **PostGIS** | 🔴 MISSING | None | Spatial logic currently runs in Python (H3 + Shapely + GeoPandas) | Dedicated PostgreSQL + PostGIS server |
| **Redis** | 🔴 MISSING | None | DiskCache (JSON on disk) is used instead of Redis | High-throughput in-memory geospatial caching |
| **Streaming** | 🟡 PARTIAL | `fusion-service/app/api/routes.py` | Native FastAPI WebSockets (`/replay/{trip_id}`) | Scalable message queue (MQTT / Kafka / Redis PubSub) |
| **Firebase** | 🔴 MISSING | None | None | Auth, Firestore profiles, Cloud Messaging, Storage |

---

## 4. Teammate's Work Breakdown

### Component 1: Hyperlocal Area Risk Scoring Engine (`area-risk-service`)
- **Location:** `area-risk-service/app/`
- **Purpose:** Calculates a transparent 0–100 risk score for any coordinate (lat, lng) in Chennai, factoring in historical crime, road isolation, commercial density, police distance, hospital distance, population density, and time of day.
- **How it works:**
  1. Maps (lat, lng) to an Uber H3 Resolution 9 cell (~174m radius).
  2. Resolves district crime from NCRB 2014 data.
  3. Evaluates road network density via OpenStreetMap / OSMnx.
  4. Queries Google Places (New API) for operational commercial POIs and distances to police/hospitals.
  5. Computes time multiplier (1.0x daytime up to 1.40x late night).
  6. Weights factors according to `configs/scoring_weights.yaml`.
- **Can we reuse it?:** **YES, 100%.** It is exceptionally well structured, robust, and provides clear mathematical explainability.
- **Required modifications:**
  - Fix default scorer behavior (currently defaults to `ml` which fails with 503 because `models/lgb_risk_scorer.txt` is missing; fallback should default to `weighted` or the model should be properly generated).
  - Restore online/cache fallback in `offline_feature_service.py` if `h3_hex_features.parquet` is absent.

### Component 2: TomTom Live Traffic Flow Service
- **Location:** `area-risk-service/app/services/tomtom_traffic_service.py`
- **Purpose:** Retrieves real-time traffic flow from TomTom API v4, calculating `currentSpeed / freeFlowSpeed` ratio.
- **How it works:** Queries TomTom segment data at zoom 10, caches results for 300 seconds in DiskCache, and handles fallbacks (`no_key`, `api_error`, `stale_cache`).
- **Can we reuse it?:** **YES.** It satisfies the requirement for modular, cost-effective traffic integration with clean fallbacks.

### Component 3: 1D-CNN Motion Classifier & Jerk Model
- **Location:** `fusion-service/app/ml/motion_model.py` & `fusion-service/models/motion_anomaly.tflite`
- **Purpose:** Analyzes raw 3-axis accelerometer data to classify movement states and detect sudden high-jerk movements.
- **How it works:** Runs a quantized 1D-CNN trained on UCI HAR (binary: 0 = steady [sitting/standing/laying], 1 = dynamic [walking/stairs]) using TFLite, and computes numerical jerk: `diff(sqrt(x^2+y^2+z^2)) / 15.0`. Blends CNN confidence and jerk into a 0–100 motion risk score.
- **Can we reuse it?:** **YES.**
- **Required modifications:** Add edge-friendly heuristics for running, sudden stops, and orientation tumble. Document the known limitation (trained on UCI HAR, not combat/violence).

### Component 4: Risk Fusion Scorer
- **Location:** `fusion-service/app/scoring/fusion_scorer.py`
- **Purpose:** Blends area risk, motion anomaly, and audio distress scores into a single composite risk score.
- **How it works:** Reads weights from `fusion_weights.yaml` (`0.60 * area + 0.40 * motion + 0.00 * audio`), normalizes and clamps to 0–100, and categorizes into Low (<25), Medium (25-50), High (50-75), and Critical (>=75).
- **Can we reuse it?:** **YES.** This directly matches Phase 3 of the target architecture.

### Component 5: Trip Logging & Telemetry Database
- **Location:** `fusion-service/app/db/`
- **Purpose:** Persists real mobile sensor sessions into SQLite (`fusion.db`) via SQLAlchemy ORM.
- **How it works:** Exposes `POST /log-trip` which accepts batch trip telemetry (`TripPoint`: timestamp, lat, lng, accel_x, accel_y, accel_z) and stores it with foreign keys.
- **Can we reuse it?:** **YES.** Can be readily extended to record route deviation, unexpected stops, and emergency events.

### Component 6: Sensor Logger Tool (`logger.html`)
- **Location:** `fusion-service/logger.html`
- **Purpose:** Mobile browser tool to record real GPS and 3-axis accelerometer data directly from a smartphone.
- **How it works:** Uses HTML5 Geolocation and `DeviceMotionEvent` APIs, buffers points, and allows exporting JSON or HTTP POST syncing to `POST /log-trip`.
- **Can we reuse it?:** **YES.** Excellent testing and data collection tool.

### Component 7: WebSocket Telemetry Replay & Demo Client
- **Location:** `fusion-service/app/api/routes.py` (`/replay/{trip_id}`) & `fusion-service/scripts/demo_replay.py`
- **Purpose:** Simulates a live journey by streaming recorded points over a WebSocket in a sliding window, computing real-time risk at each step.
- **Can we reuse it?:** **YES.** Provides an instant demonstration harness for evaluating the fusion engine.

---

## 5. Critical Architectural Issues & Gotchas Identified

1. **Missing ML Model Artifact (HTTP 503 Out-of-the-Box):**
   In `area-risk-service/app/api/routes.py`, `get_area_risk` defaults to `scorer: Literal["ml", "weighted"] = "ml"`. However, `models/lgb_risk_scorer.txt` does not exist in the repository, causing `_ml_scorer.model_loaded` to be `False`, which immediately returns an HTTP 503 error on any standard query!
2. **Missing Parquet Feature Store:**
   In `area-risk-service/app/services/offline_feature_service.py`, the code looks for `data/processed/h3_hex_features.parquet`. This file is not checked into git/the repo. As a result, all spatial lookups fall back to a hardcoded default dictionary where every feature score is `50.0`. The online fetchers (`osm_service.py`, `places_service.py`) were disconnected in `routes.py` in favor of this missing parquet file.
3. **Missing District GeoJSON:**
   `area-risk-service/app/services/district_service.py` references `data/processed/tn_districts_bbox.geojson`, which is missing, causing district polygon matching to return `None`.
4. **Missing Dependencies in `requirements.txt`:**
   `area-risk-service/app/scoring/ml_risk_scorer.py` imports `lightgbm` and `shap`, but neither is listed in `area-risk-service/requirements.txt`.
5. **Broken Unit Tests in `area-risk-service`:**
   In `area-risk-service/tests/api/test_routes.py`, the tests attempt to patch functions on `app.api.routes` (`compute_isolation_score`, `compute_commercial_density_score`, etc.) that were deleted during the teammate's refactor. Also, `test_missing_hour_returns_422` fails because `hour` was made optional.
6. **FeatureSet Dataclass Mismatch in `test_scoring.py`:**
   `app.scoring.base_scorer.FeatureSet` added `nightlight_mean_score` as a mandatory field, but `tests/unit/test_scoring.py` helper `_make_feature_set` omits it.
7. **`fusion-service` Silent Failure Handling:**
   In `fusion-service/app/api/routes.py`, when `AREA_RISK_URL` returns HTTP 503 (due to issue #1), it does not trigger an `httpx.RequestError`. Instead, `resp.status_code == 200` evaluates to `False`, silently defaulting `area_score = 50.0`.
8. **Audio Distress is Pure Mock:**
   In both services, `audio_distress` is hardcoded to `0.0`.
9. **Single-threaded SQLite Database:**
   `fusion.db` is used for both trip ingestion and WebSocket replay with `check_same_thread: False`, which will experience lock contention under concurrent load.
10. **Completely Missing Target Layers:**
    No mobile app code, no Firebase integration, no PostGIS, no autonomous emergency dispatch pipeline, no route deviation detector, no offline SMS queue.

---

## 6. Project Dependency Graph

### Current Implemented Flow:
```
                                  [logger.html]
                                        │ (HTTP / JSON)
                                        ▼
[area-risk-service]              [fusion-service]
 (Port 8000)                      (Port 8001)
  ├── NCRB 2014 (Crime Prior)      ├── SQLite (fusion.db)
  ├── TomTom Flow v4 (Traffic)     ├── 1D-CNN (motion_anomaly.tflite)
  ├── H3 Index (Res 9)             ├── Jerk Heuristic
  └── WeightedLinearScorer         └── RiskFusionScorer (0.6 Area + 0.4 Motion)
            │                               │
            └──────── (HTTP GET) ───────────┘
```

### Target End-State STREEVA Architecture:
```
                       [ STREEVA MOBILE APPLICATION ]
                                     │
      ┌──────────────────────────────┼──────────────────────────────┐
      ▼                              ▼                              ▼
 [Authentication]            [Journey Setup]              [Safety Companion]
 (Firebase / JWT)      (Source, Dest, Contacts, ETA)     (Guardian, SOS, Fake Call)
      │                              │                              │
      └──────────────────────────────┼──────────────────────────────┘
                                     ▼
                              [DEVICE SENSORS]
                 (GPS, Accel, Gyro, Mic, Wearable, Battery)
                                     │
                                     ▼
                            [EDGE AI LAYER]
           (Movement Analysis, Audio Distress, Deviation, Sudden Stop)
                                     │
                                     ▼
                          [GUARDIAN TRAVEL MODE]
               (Journey State: IDLE -> ACTIVE -> DEVIATED -> ...)
                                     │
                                     ▼
                     [AI DECISION & RISK FUSION ENGINE]
              (Area Risk + Movement + Audio + Traffic + Weather)
                                     │
                     ┌───────────────┴───────────────┐
                     ▼                               ▼
       [ADAPTIVE SENSOR MANAGER]             [DECISION LOGIC]
       (LOW -> MED -> HIGH -> CRIT)     (LOW / MED / HIGH / CRITICAL)
                                                     │
                                                     ▼
                                 [AUTONOMOUS EMERGENCY RESPONSE]
                                 ├── Live Location Sharing
                                 ├── Route Broadcast
                                 ├── Emergency Contact Dispatch
                                 ├── Secure Evidence Metadata
                                 └── Offline Guardian Fallback (SMS)
```

---

## 7. Recommended Module-by-Module Implementation Plan

### Phase 0: Existing Codebase Stabilization & Bug Fixing
- Fix `area-risk-service`: default scorer fallback to `weighted` when ML model is absent; ensure online feature extractors work if Parquet is absent; update `requirements.txt`.
- Fix the existing test suites in both `area-risk-service` and `fusion-service` so baseline tests pass 100%.

### Phase 1: Edge AI Layer
- Implement **Route Deviation Detection**: cross-track distance calculation against a corridor polyline.
- Implement **Unexpected Stop Detection**: stationary duration timer with velocity and accelerometer verification.
- Enhance **Movement Analysis**: detect running/struggling/falls using accelerometer + gyro heuristics.
- Implement **Distress Audio Detection**: edge audio feature classifier / distress loudness trigger.

### Phase 2: Guardian Travel Mode & Journey State Machine
- Implement journey setup data contracts (Source, Destination, Route geometry, Checkpoints, Emergency Contacts).
- Implement journey lifecycle state machine: `IDLE` -> `STARTING` -> `ACTIVE` -> `DEVIATED` -> `SUSPICIOUS` -> `HIGH_RISK` -> `EMERGENCY` -> `COMPLETED` / `CANCELLED`.
- Dynamic ETA computation incorporating distance, progress speed, and TomTom traffic congestion.

### Phase 3: AI Decision & Risk Fusion Engine Enhancement
- Expand `RiskFusionScorer` to dynamically ingest:
  - Base Area Risk (`area-risk-service`)
  - Movement Anomaly Risk (Phase 1)
  - Distress Audio Risk (Phase 1)
  - Route Deviation Risk (Phase 1)
  - Unexpected Stop Risk (Phase 1)
  - Real-time Traffic Congestion (`tomtom_traffic_service`)
  - Environmental / Weather Risk Provider (with abstraction)
- Classify fused threat score into Low, Medium, High, Critical.

### Phase 4: Adaptive Sensor Manager
- Implement policy-based sensor throttling:
  - `LOW` -> Minimal GPS polling (e.g. every 60s)
  - `MEDIUM` -> Standard GPS (every 15s) + Accelerometer windowing
  - `HIGH` -> Frequent GPS (every 5s) + Motion + Microphone monitoring
  - `CRITICAL` -> Maximum sensor sampling + Wearable heart rate check
- Incorporate battery level, permission state, and user privacy toggles.

### Phase 5: Autonomous Emergency Response System
- Emergency State Machine: `NORMAL` -> `SUSPICIOUS` -> `HIGH_RISK` -> `COUNTDOWN` -> `EMERGENCY` or `CANCELLED`.
- Countdown Timer with audio/vibration feedback and user cancel override ("I'm Safe").
- Multi-channel notification pipeline:
  - Emergency contact dispatch (SMS / Push / Webhook)
  - Live location sharing URL token generation
  - Incident evidence collection (audio clip & sensor snapshot hashing)
- Safeguards against false positives, network loss, and duplicate alerts.

### Phase 6: Offline Guardian Mode
- Local caching of journey corridor, emergency contacts, and risk thresholds.
- Device-local countdown execution during complete internet loss.
- Background SMS generation queue (`smsto:` intent / native SMS dispatcher) when cellular data is disconnected.
- Event synchronization upon network restoration.

### Phase 7: Mobile Application & Safety Companion UI
- Full modern UI implementation reflecting actual backend state:
  - Journey Setup Screen (Origin, Destination, Contacts, Mode)
  - Guardian Mode Active Screen (Map, Route, Live Risk Meter, Active Sensors, ETA)
  - Safety Companion (Guardian toggle, Fake Call simulation, Instant SOS)
  - Emergency Countdown / Active Emergency Screen (Cancel button, Notified status, Location sharing active indicator)

---

## 8. Summary & Next Immediate Steps

The existing work by your teammate provides a solid foundation for geospatial area risk and basic accelerometer motion analysis. By stabilizing Phase 0 and proceeding systematically through Phases 1 to 7, the project can achieve the full target STREEVA architecture without throwing away or rewriting any of the teammate's valuable work.
