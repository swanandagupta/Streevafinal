# STREEVA — Remaining Work & Engineering Completion Roadmap

**Document Purpose**: Objective, unvarnished audit of completed versus remaining work across engineering, research validation, and production readiness, with prioritized tasks for academic final submission.

---

## 1. Objective Completion Metrics

To avoid arbitrary estimates, completion is calculated across three distinct dimensions:

### 1.1 Engineering Architecture Completion: **88%**
* **Implemented & Unit Tested Modules**: 22 / 25
  - Precomputed H3 Spatial Risk Store: **100%**
  - Edge Anomaly Detectors (Route Deviation, Unexpected Stop, Fall, Audio): **100%**
  - Guardian Journey State Machine & Progress Engine: **100%**
  - Contextual Risk Fusion 2.0 with Dynamic Renormalization: **100%**
  - Adaptive Sensor Manager & Stateful Decision Engine: **100%**
  - Autonomous Emergency Orchestrator & State Machine: **100%**
  - Offline SQLite Monotonic Event Buffer & Reconciliation: **95%**
  - React/TypeScript Phase 6 Mobile Application: **90%**
  - *Remaining*: Safer-route routing engine, real WebSocket backend bridge.

### 1.2 Research & Experimental Validation: **72%**
* **Completed Empirical Benchmarks**:
  - Out-of-sample unseen-speaker audio evaluation ($N = 614$, 87.79% accuracy): **100%**
  - Coordinate data provenance and geographic boundary audit: **100%**
  - 153 passing fusion unit/scenario tests: **100%**
  - 77 passing area risk scoring tests: **100%**
* *Remaining*:
  - Formal ablation study script with statistical $p$-value computation: **40%**
  - Live IMU phone drop vs fall empirical dataset on physical devices: **30%**

### 1.3 Production Readiness: **38%**
* **Completed Production Foundations**:
  - Modular, decoupled microservice architecture (FastAPI + Pydantic + SQLite): **100%**
  - Type-safe React frontend with zero TypeScript compile errors: **100%**
* *Incomplete Production Integrations (By Design for Academic Prototype)*:
  - Real Cellular SMS Gateway (Twilio / AWS SNS): **Mocked (10%)**
  - Real PSAP (112 India) Emergency CAD Dispatch: **Mocked (10%)**
  - Production Cloud Push Notifications (FCM / APNs): **Mocked (10%)**
  - Pan-India H3 Hexagonal Risk Parquet: **Greater Chennai Only (15%)**

---

## 2. Priority-Ranked Remaining Work Matrix

| Item ID | Task Description | Category | Impact | Effort | Research Value | Demo Value | Safety Value | Priority Rank |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **RW-01** | Create parameterized Monte-Carlo ablation test script (`run_fusion_ablation.py`) | Before Final Report | High | Low | **Very High** | Medium | High | **P0 (Critical)** |
| **RW-02** | Add explicit `RouteSafetyProfile` aggregator endpoint to `area-risk-service` | Before Final Demo | High | Low | High | **Very High** | High | **P0 (Critical)** |
| **RW-03** | Fix `district_service.py` non-TN district mapping (handle outside TN gracefully without assuming Kanchipuram) | Before Final Report | Medium | Low | High | Low | Medium | **P1 (High)** |
| **RW-04** | Harden offline reconciliation to prevent deadlock when one event has invalid schema | Before Final Demo | Medium | Medium | Medium | Medium | High | **P1 (High)** |
| **RW-05** | Collect real IMU accelerometer/gyro traces on 2 physical Android phones | Before Final Report | High | Medium | **Very High** | Medium | High | **P1 (High)** |
| **RW-06** | Integrate safer-route candidate generation (compare shortest vs safest route) | Strongly Recommended | High | High | **Very High** | **Very High** | **Very High** | **P2 (Medium)** |
| **RW-07** | Ingest all-India NCRB district lookup (expand from 40 TN districts to all 700+ Indian districts) | Strongly Recommended | High | Medium | High | High | High | **P2 (Medium)** |
| **RW-08** | Real Twilio SMS API integration for live emergency broadcast | Optional Enhancement | Medium | Low | Low | **Very High** | High | **P3 (Low)** |
| **RW-09** | Live WebSocket connection between Vite Frontend and Uvicorn Fusion backend | Optional Enhancement | Medium | Medium | Low | High | Medium | **P3 (Low)** |
| **RW-10** | Production Emergency PSAP CAD dispatch integration | Production Roadmap | High | Very High | Low | Low | **Very High** | **P4 (Future)** |

---

## 3. Work Breakdown by Milestone

### Phase A: Required Before Final Project Report Submission
1. **Execute Parameterized Ablation Experiment**:
   - Write and run `scripts/run_fusion_ablation.py` across 500 synthetic scenarios to tabulate exact false-positive and false-negative rates with and without spatial risk, temporal decay, and confidence gating.
2. **Refine Non-TN District Fallback**:
   - Update `district_service.py` so that coordinates outside Tamil Nadu explicitly return `None` rather than falling into the Chennai CMA western heuristic (`Kanchipuram`).
3. **Compile Viva Voce Defense Deck**:
   - Transcribe 30s, 1m, 3m, and 5m answers into the project slide deck.

### Phase B: Required Before Final Committee Live Demo
1. **Interactive Route Safety Breakdown in UI**:
   - Wire the `RouteSafetyProfile` metrics into the frontend `Route & Safety Preview` card so reviewers can see the percentage of major roads vs unclassified roads and data coverage.
2. **Scenario Injection Verification**:
   - Ensure the `DemoScenarioModal` in the frontend triggers all 6 scenarios seamlessly in 60 seconds without server restarts.

### Phase C: Post-Project Production Roadmap (Future Work)
1. **Pan-India Hexagonal Spatial Ingestion**: Run `build_hex_layers.py` across the top 20 metropolitan cities in India.
2. **Wearable BLE Heart-Rate Integration**: Ingest real-time tachycardia / panic heart-rate spikes from smartwatches to augment the fall/audio distress fusion.
3. **Federated Privacy-Preserving On-Device Learning**: Adapt acoustic distress thresholds locally without transmitting private ambient microphone recordings to central cloud servers.
