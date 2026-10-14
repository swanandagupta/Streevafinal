# STREEVA Phase 6: Screen & State Behavior Matrix

| SCREEN | BACKEND STATE | UI STATE | USER ACTION | API CALLED | RESULT | ERROR HANDLING | OFFLINE BEHAVIOR |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Splash** | Idle / Server running | Splash intro, glowing 3D Guardian Core | View splash | None | Auto-routes to Onboarding after 2.4s | Graceful fallback orb if WebGL missing | Local bundle loads instantly |
| **Onboarding** | Uninitialized | 4-step interactive guided carousel | Tap Next / Skip | None | Advances step $\to$ Routes to Home | None | Functions completely offline |
| **Auth** | Unauthenticated | Login / Register / Forgot Password | Enter email & password or tap Demo | Local auth state | Sets user in context $\to$ Routes to Home | Displays inline error banner | Local guest/demo access available |
| **Home** | Idle / Ready | Hero 3D Guardian Core, readiness checks | Tap Destination / Plan Journey | None | Routes to Journey Setup | Prompts contact setup if circle empty | Cached contacts & offline status shown |
| **Journey Setup** | Ready | Corridor selection, Route preview map | Select Corridor $\to$ Tap Proceed | None | Previews distance & ETA $\to$ Routes to Check | None | Cached safe corridor polyline used |
| **Pre-Journey Check** | Starting | 6-point telemetry readiness checklist | Tap "START JOURNEY" | `POST /guardian/journey/start` | Backend starts journey $\to$ Routes to Active | Retries connection or enters offline mode | Caches journey locally via Phase 5 |
| **Active Journey** | `IN_PROGRESS` (LOW risk) | Live Map, Route Progress bar, Guardian Watching | Travel along corridor | `POST /guardian/journey/update` | Updates position, ETA, and progress | Retains last known trusted GPS position | Continues local progression; buffers state |
| **Route Deviation** | `CONFIRMED_DEVIATION` | High Risk badge, Amber/Red dashed polyline, Deviation Card | Tap "Return to route" or "New route" | `POST /guardian/journey/update` | Hysteresis resets when back on route | Logs warning in activity feed | Deviation tracked in local event buffer |
| **Unexpected Stop** | `CONFIRMED_STOP` | Medium Risk badge, Stop alert card | Tap "I'm Okay" | None (or check-in) | Resets stop state; restores LOW risk | None | Local timer checks duration |
| **Emergency Countdown** | `CONFIRMATION_COUNTDOWN` | Full-screen focused crimson modal, 15s timer, "I'M SAFE" | Tap "I'M SAFE" or wait | `POST /emergency/{id}/cancel` | If cancelled: restores normal journey | Displays cancel failure alert | Local countdown continues offline |
| **Emergency Active** | `RESPONSE_AUTHORIZED` | Active emergency banner, checklist, SMS preview | Tap "Simulate Ack" or "Resolve" | `POST /emergency/{id}/acknowledge` | Incident marked RESOLVED | Fallback to SMS if cellular degraded | Local SMS fallback dispatched per Phase 5 |
| **Journey Summary** | `ARRIVED` | Safe arrival celebration, metrics, audit timeline | Tap "Return to Home" | None | Returns to Home screen | None | Saved to local journey history |
| **Journey History** | History query | Past monitored routes & summaries | Tap trip card | None | Displays detailed Journey Summary | Shows empty state if no trips | Reads from local storage / SQLite |
| **Guardian Page** | Active / Idle | Telemetry health cards, policy controls | Toggle auto-mode or sensors | `POST /contextual-safety/evaluate` | Adjusts adaptive sensor policies | Reverts toggle if policy invalid | Displays offline monitoring indicator |
| **Activity** | Log feed | Chronological alerts & notifications | Scroll activity feed | None | Displays audit events with risk colors | Shows empty placeholder | Appends offline buffer sync events |
| **Profile** | User profile | Emergency contacts, permission center | Add / Remove contact | Local / backend profile | Contact updated in emergency circle | Validates phone numbers | Locally persistent in client state |
