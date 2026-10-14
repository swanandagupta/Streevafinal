# STREEVA Phase 6: Mobile Application & Experience Architecture

## 1. Architectural Overview
STREEVA Phase 6 provides the user-facing mobile client layer designed strictly as a consumer of the frozen Phase 0–5 safety core. It provides a modern, dark atmospheric mobile-first experience that feels like a serious, intelligent personal protective layer.

### Hard Architectural Rule
- The mobile application is a client of the STREEVA backend (`fusion-service`).
- It **never** recalculates risk independently, evaluates route deviation or unexpected stops, runs edge fall/distress models in JavaScript, or duplicates backend state machines.
- All safety assessments, guardian snapshots, emergency events, and offline buffer summaries originate from backend contracts.

---

## 2. Technology Stack Selection & Rationale
| Component | Technology | Rationale |
| :--- | :--- | :--- |
| **Framework** | React 18 + Vite | Lightning-fast HMR and production bundle generation, clean modular component architecture, zero bloat, mobile viewport simulation. |
| **Styling** | Vanilla CSS Design Tokens | Strict control over atmospheric dark aesthetics, luminous glows, glassmorphism, responsive viewports, and zero framework overhead. |
| **Signature 3D Element** | Three.js + WebGL Canvas | Renders the reactive 3D STREEVA Guardian Core with hardware-accelerated shaders and automatic CSS/Canvas glow fallback. |
| **Map Presentation** | Leaflet + OpenStreetMap (CartoDB Dark Matter) | Real dark-themed road network tiles, live GPS marker, destination marker, OSRM road polyline, and automatic viewport fitting (`fitBounds`). |
| **Routing Provider** | OpenStreetMap OSRM API | Canonical turn-by-turn road network geometry, distance calculation, and duration estimation. |
| **Geocoding Provider** | OpenStreetMap Nominatim API | Live search & geocoding of traveler destinations across world places. |
| **Iconography** | Lucide React | Clean, modern, accessible vector iconography matching safety application standards. |
| **Testing** | Node.js Test Runner (`node:test`) | Native, zero-dependency unit, contract, and integration test execution. |

---

## 3. Visual & Design Token System
- **Backgrounds**: Deep midnight (`#0B0E17`, `#07090E`), blue-charcoal surfaces (`#151B2D`, `#1A2238`), elevated translucent glass (`rgba(22, 29, 47, 0.75)`).
- **Brand & Intelligence**: Electric violet (`#6366F1`, `#7C3AED`), Cyan intelligence indicator (`#06B6D4`).
- **Safety Spectrum Tokens**:
  - `LOW`: Mint / Teal (`#10B981`) — Journey normal.
  - `MEDIUM`: Amber (`#F59E0B`) — Unusual movement / check-in recommended.
  - `HIGH`: Coral / Orange (`#F97316`) — Elevated vigilance / multiple anomaly signals.
  - `CRITICAL`: Controlled Crimson (`#EF4444`) — Emergency countdown & dispatch.
  - `UNKNOWN`: Desaturated Violet (`#8B5CF6`) — Telemetry incomplete (never declared safe).
  - `DEGRADED`: Charcoal Grey (`#6B7280`) — Limited data / local mode.
- **Typography**: Inter sans-serif with tabular numeric figures for ETA, distance, countdowns.

---

## 4. Signature 3D Element: Guardian Core
The Guardian Core visually communicates STREEVA's awareness state in real time:
- **Inner Core**: Luminous rotating icosahedron.
- **Middle Cage**: Wireframe lattice representing spatial tracking.
- **Outer Orbital Rings**: Dynamic rings revolving around the core.
- **State Dynamics**:
  - `LOW`: Calm breathing scale oscillation ($1.0 \pm 0.05$), steady slow rotation.
  - `MEDIUM`: Increased rotation speed, amber pulse.
  - `HIGH`: Dual counter-rotating orbital rings, accelerated rotation.
  - `CRITICAL`: Rapid focused emergency pulse ($6.0\text{ Hz}$), vivid crimson glow.
  - `UNKNOWN / DEGRADED`: Muted wireframe, diffused drift, low opacity.
  - *WebGL Fallback*: Radial gradient CSS orb with pulse animations if WebGL context is lost.

---

## 5. Navigation Architecture
- **5 Primary Destinations**:
  1. `HOME`: Hero Guardian Core, readiness checks, destination quick input, recent safe places.
  2. `JOURNEYS`: Corridor selection, route preview, pre-journey safety verification.
  3. `GUARDIAN`: Sensor health telemetry, awareness state, safety preferences.
  4. `ACTIVITY`: Chronological audit trail of journey events, network states, and alerts.
  5. `PROFILE`: User traveler info, emergency contacts circle, permission center, privacy guarantee.
- **Global SOS Access**: Persistent crimson button on primary screens calling backend `POST /emergency/trigger`.

---

## 6. API Client Mapping
| UI Action | Backend Endpoint | Method | Request Contract | Response Contract |
| :--- | :--- | :--- | :--- | :--- |
| Start Journey | `/guardian/journey/start` | `POST` | `JourneyStartRequest` | `GuardianSnapshot` |
| Ingest Telemetry | `/guardian/journey/update` | `POST` | `JourneyUpdateRequest` | `GuardianSnapshot` |
| Safe Arrival / End | `/guardian/journey/end` | `POST` | `JourneyEndRequest` | `GuardianSnapshot` |
| Context Evaluation | `/contextual-safety/evaluate`| `POST` | `ContextualSafetyRequest` | `ContextualSafetyResponse` |
| Manual SOS | `/emergency/trigger` | `POST` | `ManualSOSTriggerRequest` | `EmergencyIncident` |
| Auto Emergency | `/emergency/autonomous` | `POST` | `AutonomousTriggerRequest` | `EmergencyIncident` |
| Cancel Countdown | `/emergency/{id}/cancel` | `POST` | `CancelEmergencyRequest` | `EmergencyIncident` |
| Acknowledge | `/emergency/{id}/acknowledge`| `POST` | `AcknowledgeEmergencyRequest`| `EmergencyIncident` |
| Offline Status | `/offline/status` | `GET` | None | `OfflineStatusSummary` |
| Reconcile | `/offline/reconcile` | `POST` | `ReconcileRequest` | `ReconciliationSummary` |

---

## 7. Emergency UX & Privacy Standards
- **15-Second Verification Window**: Full-screen focused modal with crimson pulsating Guardian Core, large countdown timer, and unmissable "I'M SAFE" cancellation button.
- **Non-Technical Emergency SMS Payload**:
  - Contact alert includes traveler name, live tracking link, destination, and timestamp.
  - **Zero Raw ML Metrics**: Internal CNN confidence, LightGBM risk scores, and H3 values are strictly forbidden from contact notifications.
- **Escalation Protocol**: Primary contact notified $\to$ waiting for acknowledgement $\to$ secondary contact escalation $\to$ emergency services.

---

## 8. Offline Guardian UX
- Detects network transitions (`ONLINE`, `DEGRADED`, `OFFLINE`, `RECONNECTING`).
- Displays non-panicking amber warning banner: *"Guardian is operating offline — Local monitoring active"*.
- Preserves cached route, buffered sensor events, and local countdown capability.
- Displays synchronization animation during reconciliation.

---

## 9. Verification & Regression Preservation
- Backend regression suite: 153/153 tests in `fusion-service` and 77/77 tests in `area-risk-service` passing (230/230 total).
- Frontend tests: 9/9 safety contract tests and 20/20 integration checkpoints passing.
- Complete deterministic demo scenario passing.
