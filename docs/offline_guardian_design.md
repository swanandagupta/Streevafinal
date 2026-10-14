# STREEVA — PHASE 5: OFFLINE GUARDIAN & CONNECTIVITY RESILIENCE
## Architectural Specification and Design Document

---

### 1. Architectural Overview & Boundary

Phase 5 implements the **Offline Guardian Resilience Layer** around the frozen STREEVA safety pipeline. It guarantees journey continuity, persistent state tracking, deterministic event sequencing, local safety monitoring, and offline emergency management when cellular data or cloud services become unavailable or degraded.

#### Hard Architectural Boundary
```
                    ┌─────────────────────────────────────────┐
                    │            OFFLINE GUARDIAN             │
                    │                                         │
                    │  - Connectivity State Machine           │
                    │  - Active Journey Local Cache           │
                    │  - Durable Event Buffer (SQLite)        │
                    │  - Monotonic Sequence Ordering          │
                    │  - SMS Fallback Boundary                │
                    │  - Reconnection & Reconciliation        │
                    └────────────────────┬────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       FROZEN CORE PIPELINE (Phases 1–4)                      │
│                                                                             │
│  Phase 1: Edge AI Detectors (Route Deviation, Stop, Fall, Audio Distress)   │
│       ↓                                                                     │
│  Phase 2: Guardian Journey Context (Progress, ETA, In-Memory Tracking)      │
│       ↓                                                                     │
│  Phase 3: Contextual Risk Fusion 2.0 & Decision Engine                      │
│       ↓                                                                     │
│  Phase 4: Emergency Response Orchestrator & Evidence Ledger                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Zero Redundancy Principle:**
- Phase 5 does **NOT** create a second risk engine (`No OfflineRiskEngine`).
- Phase 5 does **NOT** create duplicate Phase 1 detectors or retrained models.
- Phase 5 does **NOT** duplicate `GuardianMonitor` or `EmergencyResponseOrchestrator`.
- Phase 5 sits around the existing components, feeding local telemetry directly to them and handling durable buffering, SMS fallback, and reconciliation.

---

### 2. Connectivity State Machine

The network connectivity lifecycle is managed by `ConnectivityManager`, provider-independent and decoupled from traveler safety risk.

```
       ┌────────────────────────┐
       │         ONLINE         │
       └──────────┬─────────────┘
                  │          ▲
      Weak signal │          │ Sync Succeeded
                  ▼          │
       ┌────────────────────────┐
       │        DEGRADED        │
       └──────────┬─────────────┘
                  │          ▲
     Carrier Loss │          │
                  ▼          │
       ┌────────────────────────┐
       │        OFFLINE         │
       └──────────┬─────────────┘
                  │
      Signal Seen │
                  ▼
       ┌────────────────────────┐
       │      RECONNECTING      │
       └──────────┬─────────────┘
                  │
                  ├────────────────────────► ONLINE (All events synced)
                  └────────────────────────► DEGRADED (Partial sync failure)
```

#### Valid Transitions & Semantics
- `ONLINE -> DEGRADED`: High latency (> 1500ms) or low signal strength; network remains tentatively available.
- `ONLINE -> OFFLINE`: Direct carrier loss / tunnel entry.
- `DEGRADED -> ONLINE`: Network quality restored.
- `DEGRADED -> OFFLINE`: Complete signal loss.
- `OFFLINE -> RECONNECTING`: Connectivity handshake initiated; reconciliation begins.
- `RECONNECTING -> ONLINE`: All buffered events successfully synchronized.
- `RECONNECTING -> DEGRADED`: Synchronization partially succeeded; failed events remain queued for retry.
- `RECONNECTING -> OFFLINE`: Connection failed during synchronization handshake.

Invalid transitions (e.g. `OFFLINE -> DEGRADED` directly) are explicitly rejected by raising `InvalidConnectivityTransitionError`.

---

### 3. Separation of Connectivity from Safety Risk

Connectivity state is a data-quality / transport property, **never evidence of physical danger or safety**.

| Connectivity State | Sensor Telemetry | Computed Risk Level | Operational Decision Tier |
|:---|:---|:---|:---|
| **ONLINE** | Normal on-route motion | `LOW` | `MONITOR` |
| **OFFLINE** | Normal on-route motion | `LOW` | `MONITOR` (local tracking continues) |
| **OFFLINE** | Off-route + stationary | `HIGH` | `ELEVATED_MONITORING` |
| **OFFLINE** | Fall impact + audio distress | `CRITICAL` | `AUTONOMOUS_RESPONSE_REQUIRED` |
| **OFFLINE** | Gaps in all sensor streams | `UNKNOWN` | `DEGRADED_MONITORING` |

**Crucial Invariant:**
- `OFFLINE` $\ne$ `HIGH RISK` or `CRITICAL RISK`
- `OFFLINE` $\ne$ `LOW RISK`
- `Missing Telemetry` $\ne$ `LOW RISK` (it maps to `UNKNOWN` $\rightarrow$ `DEGRADED_MONITORING`)

---

### 4. Active Journey Local Cache & Location Quality

When a journey starts, `ActiveJourneyCache` locally caches:
- `journey_id`, `journey_state`
- `source_lat`, `source_lng`, `dest_lat`, `dest_lng`
- `expected_route`: Established route polyline from start
- `route_progress_percent`, `remaining_distance_m`
- `eta`, `eta_source`: Freshness tracking
- `last_trusted_lat`, `last_trusted_lng`, `location_accuracy`
- `telemetry_quality`: `VALID`, `STALE`, `UNAVAILABLE`
- `active_sensor_policy`, `latest_risk_score`, `latest_decision_tier`, `active_incident_id`

#### Zero Coordinate Fabrication Policy
- If GPS fixes cease for more than `offline_location_stale_seconds` (default 45.0s), `telemetry_quality` transitions to `STALE`.
- If no GPS fix has ever been received, `telemetry_quality` remains `UNAVAILABLE`.
- The system **never** synthesizes `(0.0, 0.0)` or fake interpolated points.
- If the expected route is missing, route deviation detection remains unavailable without fabricating route geometry.

---

### 5. Durable Local Event Buffer & Monotonic Sequencing

All lifecycle, sensor, risk, and emergency events occurring while offline are appended to `LocalEventBuffer` backed by SQLite (`offline_buffered_events` table).

#### Monotonic Sequence Ordering
- Each event is assigned an integer `sequence_number` that strictly increases monotonically (`1, 2, 3...`).
- Counter initialization reads the highest existing sequence number from SQLite, ensuring restarts never reset or duplicate sequence numbers.
- Deduplication: Ingesting an identical `event_id` is an idempotent no-op.

#### Event Types Supported
- `TELEMETRY`: Raw GPS / inertial / audio metadata.
- `GUARDIAN_SNAPSHOT`: Consolidated snapshot frame.
- `RISK_ASSESSMENT`: Fused risk score and level.
- `DECISION`: Prescribed decision tier and hysteresis state.
- `ROUTE_DEVIATION`, `UNEXPECTED_STOP`, `FALL`, `AUDIO_DISTRESS`: Direct detector events.
- `EMERGENCY_INCIDENT`: Incident creation records.
- `EMERGENCY_STATE_CHANGE`: Transition audit trail.
- `NOTIFICATION_ATTEMPT`: Dispatch attempts with status.
- `SENSOR_POLICY`, `EVIDENCE_METADATA`.

---

### 6. Offline Emergency Response & SMS Fallback

When Phase 3 outputs `DecisionTier.AUTONOMOUS_RESPONSE_REQUIRED` while offline:
1. **Passes to Phase 4:** Invokes `EmergencyResponseOrchestrator.handle_autonomous_decision()`.
2. **Local Countdown:** Countdown ticks down locally using device time (`advance_emergency_countdown`). It does not poll or wait for server confirmation.
3. **User Cancellation:** If the user confirms a false alarm during countdown, the incident transitions to `CANCELLED`, and **zero** notifications are marked delivered.
4. **Countdown Expiry & SMS Fallback:**
   - When countdown reaches 0.0s, the incident transitions to `RESPONSE_AUTHORIZED`.
   - In offline mode, the orchestrator invokes the abstract `ISMSFallbackProvider`.
   - If SMS succeeds: records `SMSDeliveryStatus.SENT`, updates delivery results, marks incident `NOTIFIED`.
   - If SMS fails or is unavailable: records `SMSDeliveryStatus.FAILED` or `UNAVAILABLE`, records explicit delivery failure in the incident, and marks incident `FAILED`. **Never invents success.**
5. **Incident Continuity:** The exact same `incident_id` is preserved across offline execution, device restarts, and cloud reconnection.

---

### 7. Reconnection & Reconciliation Service

Reconnection is orchestrated via `IReconciliationService` (`MockReconciliationService` in Phase 5):
1. State transitions to `RECONNECTING`.
2. Pending buffered events are queried in strict sequence number order (`ORDER BY sequence_number ASC`).
3. Each event transitions: `PENDING -> SYNCING -> SYNCED`.
4. Partial Synchronization Failure:
   - Events that encounter transmission errors transition to `FAILED` and have `retry_count` incremented.
   - Successful events become `SYNCED`.
   - Failed events remain in the buffer for future retry passes.
   - Connectivity transitions to `DEGRADED` rather than `ONLINE`.
5. Reconnection transitions to `ONLINE` only when 0 failed events remain.

#### Conflict Handling Rule
When local and remote state conflict (e.g. Local = `RESPONSE_AUTHORIZED`, Remote = `NOTIFIED`):
- **Deterministic Priority:** Safety-critical forward progress wins:
  `RESOLVED` > `RESPONSE_AUTHORIZED` > `NOTIFIED` > `COUNTDOWN` > `VERIFYING` > `TRIGGERED` > `CANCELLED`.
- Full transition audit trail is preserved in the emergency history.

---

### 8. Persistence & Restart Recovery

All safety-critical offline artifacts are persisted in SQLite:
- `CachedJourneyDB` in table `cached_journeys`.
- `OfflineEventDB` in table `offline_buffered_events`.
- `ConnectivityHistoryDB` in table `connectivity_history`.
- `IncidentDB` and `IncidentHistoryDB` in `emergency_incidents`.

**Mandatory Restart Test:**
A process shutdown and restart was verified: `OfflineGuardian.restore_from_persistence()` restores the active journey, last known coordinates, active incident reference, and resumes the monotonic sequence counter seamlessly.

---

### 9. Safety Invariants Verification (16/16 Passed)

1. **Invariant 1:** `OFFLINE` never automatically implies `HIGH` or `CRITICAL` risk.
2. **Invariant 2:** `OFFLINE` never automatically implies `LOW` risk.
3. **Invariant 3:** `UNKNOWN/DEGRADED` telemetry retains Phase 3 semantics (maps to `UNKNOWN` risk and `DEGRADED_MONITORING`).
4. **Invariant 4:** Phase 5 never creates a second risk engine.
5. **Invariant 5:** Phase 5 never creates duplicate Phase 1 detectors.
6. **Invariant 6:** Phase 5 never creates a second Emergency Response Orchestrator.
7. **Invariant 7:** Offline autonomous response uses the same Phase 4 incident lifecycle.
8. **Invariant 8:** The same emergency incident ID survives offline/online transitions and restarts.
9. **Invariant 9:** No unavailable communication channel is ever represented as delivered.
10. **Invariant 10:** No unavailable location results in fabricated coordinates.
11. **Invariant 11:** Stale location is explicitly marked `STALE`.
12. **Invariant 12:** Buffered events are never silently discarded.
13. **Invariant 13:** Buffered events reconcile deterministically in sequence order.
14. **Invariant 14:** Duplicate events do not produce duplicate emergency actions.
15. **Invariant 15:** Offline countdown does not depend on network availability.
16. **Invariant 16:** Phase 1–4 behavior remains green and unchanged.

---

### 10. Implemented Now vs Future Production Integrations

| Capability | Implemented in Phase 5 (Now) | Future Production Integrations |
|:---|:---|:---|
| **Connectivity State Machine** | Complete (ONLINE, DEGRADED, OFFLINE, RECONNECTING) | Android NetworkCapabilities / iOS NWPathMonitor |
| **Active Journey Caching** | Complete SQLite + in-memory cache | Mobile Room / CoreData persistence |
| **Event Buffering & Ordering** | Complete monotonic sequence numbering in SQLite | Persistent local write-ahead log on device |
| **Local Pipeline Execution** | Complete in-memory execution of Phase 1–4 modules | On-device ONNX / TFLite runtime |
| **Offline Countdown & Cancel** | Complete local timer & cancellation | Mobile UI countdown modal with tactile buzz |
| **SMS Fallback Abstraction** | Complete `ISMSFallbackProvider` + `MockSMSFallbackProvider` | Real cellular AT modem / Twilio GSM gateway |
| **Reconnection & Reconciliation**| Complete `IReconciliationService` + `MockReconciliationService` | Production Firebase / WebSocket sync backend |
| **Public Dispatch Integration** | Complete simulated dispatch abstraction | Real 112 / 911 PSAP public emergency integration |

> [!IMPORTANT]
> Phase 5 implements the full architectural resilience contracts and deterministic mock providers. **No real SMS, cellular carrier, or external emergency service calls were initiated.**
