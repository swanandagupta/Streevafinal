# STREEVA — Comprehensive Competitor Evidence Matrix & Analysis

**Document Status**: Rigorous Academic & Technical Market Audit  
**Date**: September 2026  
**Subject**: Competitive Landscape, Overlap Analysis, and Architectural Differentiation of STREEVA

---

## 1. Executive Summary

Existing personal safety systems on the market specialize in one or two functional layers:
1. **Manual SOS / Physical Panic Triggers** (bSafe, Noonlight, 112 India, Himmat Plus, Life360)
2. **Social Location Sharing & Geofencing** (Life360, Apple Find My, Google Maps Location Sharing)
3. **Crowdsourced / Reported Crime Maps** (WalkSafe UK, Citizen)
4. **Corporate Travel Risk Intelligence** (Safeture, International SOS)
5. **Acoustic / Crash Telematics** (Noonlight Crash, Apple Crash/Fall, bSafe Voice)

**What is Absent from the Market:**  
No surveyed competitor system integrates **environmental spatial priors (crime + isolation + POI + emergency infrastructure)**, **planned canonical route geometry**, **real-time edge behavioral anomalies (route deviation, unexpected stops, falls, acoustic distress)**, into a **continuous, stateful, confidence-weighted, time-decayed risk fusion engine** that adaptively controls sensor monitoring and orchestrates an autonomous emergency pipeline with **offline edge continuity**.

---

## 2. Competitor Evidence Matrix

### Legend
* **✓**: Implemented & publicly verified in official documentation / application
* **△**: Partial, adjacent, or restricted capability (e.g., enterprise only, vehicular only)
* **—**: Feature absent / not provided
* **?**: Insufficient public documentation to verify

| Competitor | Core Purpose | Women-First? | Manual SOS | Auto Detection | Live GPS | Journey Sharing | Route Deviation | Unexpected Stop | Fall Detection | Audio Distress | Spatial Risk | Crime Data | Road Class / Width | Route Safety Score | Temporal Fusion | Confidence Reasoning | Adaptive Sensors | Auto Escalation | Trusted Contacts | PSAP Dispatch | Offline Ops | Verifiable Evidence |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **bSafe** | Personal safety & live streaming | ✓ | ✓ | △ (Voice) | ✓ | ✓ (Follow Me) | — | — | — | △ (Phrase) | — | — | — | — | — | — | — | — | ✓ | — | — | ✓ (Cloud Video) |
| **Noonlight** | Personal safety & 911 dispatch | — | ✓ (Hold/Release) | △ (Crash) | ✓ | ✓ | — | — | — | — | — | — | — | — | — | — | — | △ (Timer/Crash) | ✓ | ✓ (US 911) | — | — |
| **WalkSafe** | UK route planning & crime map | ✓ | ✓ | — | ✓ | ✓ (HomeSafe) | — | — | — | — | ✓ (UK Police) | ✓ (Police.uk) | — | △ (Static map) | — | — | — | — | ✓ | — | — | — |
| **Life360** | Family location & telematics | — | ✓ | △ (Crash) | ✓ | ✓ (Circles) | — | — | — | — | — | — | — | — | — | — | — | △ (Crash only) | ✓ | △ (Third-party) | — | — |
| **Safeture** | Enterprise travel risk management | — | ✓ | — | ✓ | ✓ | — | — | — | — | ✓ (Global alerts) | △ (Country/City) | — | — | — | — | — | — | ✓ | ✓ (Ops Center) | — | — |
| **Himmat Plus** | Delhi Police women's emergency app | ✓ | ✓ (Shake/Button) | — | ✓ | — | — | — | — | — | — | — | — | — | — | — | — | — | ✓ | ✓ (Delhi Police) | — | ✓ (Audio/Video) |
| **112 India** | Pan-India Emergency Response (ERSS) | — | ✓ (3-click/Panic) | — | ✓ | ✓ (Trip Track) | — | — | — | — | — | — | — | — | — | — | — | — | ✓ | ✓ (State PSAP) | — | — |
| **SafarSafe** | AI safe routing for women (India) | ✓ | ✓ | — | ✓ | ✓ | — | — | — | — | △ (Route score) | △ (City priors) | — | ✓ (Planned route) | — | — | — | — | ✓ | — | — | — |
| **StillSafe** | Check-in & wellness safety timers | — | ✓ | — | ✓ | ✓ | — | — | — | — | — | — | — | — | — | — | — | △ (Timer expiry) | ✓ | — | — | — |
| **Citizen** | Hyperlocal crime & safety alerts | — | ✓ (SafeWalk) | — | ✓ | ✓ | — | — | — | — | ✓ (911 police radio) | ✓ (Live scanner) | — | — | — | — | — | — | ✓ | △ (Paid agent) | — | — |
| **STREEVA** | **AI Journey Guardian & Fusion Engine** | **✓** | **✓** | **✓ (Multimodal)** | **✓** | **✓** | **✓ (Corridor)** | **✓ (Kinematic)** | **✓ (IMU 3-axis)** | **✓ (TFLite CNN)** | **✓ (H3/OSM/POI)** | **✓ (NCRB IPC)** | **✓ (OSM hierarchy)** | **✓ (Segment-level)** | **✓ (Decay & Boosts)** | **✓ (Telemetry QA)** | **✓ (Stateful Tiers)** | **✓ (Hysteresis)** | **✓** | **△ (Abstracted Mock)** | **✓ (Durable SQLite)** | **✓ (SHA-256 Chain)** |

---

## 3. Detailed Competitor Profiles & Evidence Verification

### 3.1 bSafe (Mobile Software AS)
* **Official Source**: [getbsafe.com](https://getbsafe.com), Google Play Store, Apple App Store
* **Core Mechanisms**:
  - Voice activation trigger: listens for a specific key phrase (e.g. "bSafe") to initiate an alarm without touching the handset.
  - Live audio/video streaming directly to chosen guardians.
  - "Follow Me" live GPS tracking with timed check-in alarms.
  - "Fake Call" simulator to excuse users from awkward or uncomfortable situations.
* **Architectural Limitations Relative to STREEVA**:
  - **Zero Environmental Context**: Completely agnostic of whether the user is on a well-lit arterial avenue or an isolated rural dead-end.
  - **Zero Journey Context**: Does not evaluate route deviations, unexpected vehicle stops, or progress delays.
  - **Reactive Only**: Does not fuse multiple weak distress cues (e.g. high area risk + sudden unexpected stop + quiet voice distress).
  - **Cloud Dependency**: Requires active cellular data for video streaming; does not operate autonomous offline monitoring.

### 3.2 Noonlight (Noonlight, Inc. / SafeTrek)
* **Official Source**: [noonlight.com](https://noonlight.com), US Patent US9852605B2 ("System and method for personal safety")
* **Core Mechanisms**:
  - "Hold Until Safe" dead-man's switch: User holds finger on an onscreen button; releasing without entering a 4-digit PIN within 10 seconds dispatches 911.
  - Certified 24/7 UL-compliant emergency dispatch center integration in the United States.
  - Automatic vehicular crash detection via smartphone accelerometer/gyroscope/GPS.
* **Architectural Limitations Relative to STREEVA**:
  - **Static High-Stress Assumption**: Holding a button for 30 minutes while walking is ergonomically impractical and causes fatigue.
  - **No Pedestrian Anomaly Detection**: Does not detect route deviations, unusual walking stops, or acoustic distress.
  - **Geographic Lock**: Operational exclusively within the United States due to PSAP (911) integration dependencies.
  - **No Pre-Journey Risk Modeling**: Does not compute environmental risk profiles or inspect road hierarchy.

### 3.3 WalkSafe UK (WalkSafe Ltd)
* **Official Source**: [walksafe.io](https://walksafe.io), UK Police Partnerships (West Mercia, Kent, Cumberland)
* **Core Mechanisms**:
  - Map overlay of verified Police.uk historical crime categories (knife crime, sexual assault, mugging).
  - "Safe Spaces" directory: accredited commercial venues (bars, shops with *Ask for Angela* certification) where travelers can take refuge.
  - "HomeSafe" journey sharing with ETA notifications upon delay.
* **Architectural Limitations Relative to STREEVA**:
  - **Passive Information Display**: Displays crime pins on a map but does NOT compute an algorithmic risk score for individual road segments.
  - **No Real-Time Anomaly Engine**: Does not monitor real-time accelerometer, gyroscope, or microphone telemetry.
  - **No Autonomous Edge Decisioning**: Relies entirely on the user looking at the map or guardians reacting to missed timers.

### 3.4 112 India / ERSS (Ministry of Home Affairs, Govt. of India)
* **Official Source**: [112.gov.in](https://112.gov.in), Emergency Response Support System (ERSS)
* **Core Mechanisms**:
  - Single unified national emergency helpline integration across all 36 Indian States and Union Territories.
  - "Panic" button, hardware power-button trigger (3 rapid presses), and "SHOUT" volunteer alert feature.
  - Live CAD (Computer-Aided Dispatch) to state police control rooms.
* **Architectural Limitations Relative to STREEVA**:
  - **Strictly Reactive SOS**: System has zero autonomous detection capability; emergency response is initialized only AFTER the user manually triggers a panic alert.
  - **Zero Spatial or Environmental Intelligence**: Does not ingest NCRB baselines, OpenStreetMap road topology, or POI density.
  - **Zero Multimodal Sensing**: Does not process motion telemetry, route deviation, or acoustic signals.

### 3.5 SafarSafe (Research / Early-Stage Startup, India)
* **Official Source**: Public reporting, Mid-Day India (2024–2025)
* **Core Mechanisms**:
  - AI-driven safe route selection focused on women travelers in Indian cities.
  - Uses historical incident data and urban factors to suggest alternative walking/transit paths.
* **Architectural Limitations Relative to STREEVA**:
  - **Pre-Journey Only**: Focuses on suggesting the route before departure, but lacks a real-time active edge guardian loop monitoring the user during transit.
  - **No Sensor Fusion**: Lacks IMU fall/impact detection, TFLite acoustic distress detection, or unexpected stop state machines.

---

## 4. What STREEVA Explicitly Shares with Existing Products (Non-Novel Baselines)

To maintain rigorous academic honesty, STREEVA does **NOT** claim novelty for standard consumer safety features:

1. **Manual SOS Button**: Standard industry baseline since 2010 (bSafe, 112 India, Noonlight).
2. **Real-Time GPS Location Sharing**: Standard utility provided by Life360, Apple Find My, and Google Maps.
3. **Emergency Contact Notifications**: Standard SMS/Push pattern implemented across dozens of applications.
4. **Destination Arrival Detection**: Standard geofencing pattern (radius $\le 50\text{m}$) present in WalkSafe and Life360.
5. **Historical Crime Map Display**: Implemented by WalkSafe (UK Police data) and Citizen (US police scanners).
6. **Hardware Sensor Ingestion**: Vehicular crash and fall detection using accelerometers exist in Noonlight and Apple Watch.

Acknowledging these overlaps strengthens STREEVA's defensibility by demonstrating mastery of baseline mechanisms while focusing academic novelty strictly on what competitors cannot do.

---

## 5. Architectural Novelty: What Genuinely Differentiates STREEVA

STREEVA's differentiation lies in **Cross-Layer Unified Autonomous Reasoning**:

```
Competitor Model:
[Manual Panic Trigger] ───────────────────────────► [Dispatch / Notify]
         OR
[Single Crash Sensor]  ───────────────────────────► [Dispatch / Notify]

STREEVA System Architecture:
┌─────────────────────────┐     ┌────────────────────────┐
│  Spatial Intelligence   │     │  Edge Sensor Signals   │
│  (NCRB, OSM, POI, Pop)  │     │  (IMU, Audio, GPS, RD) │
└────────────┬────────────┘     └───────────┬────────────┘
             │                              │
             └──────────────┬───────────────┘
                            ▼
           ┌─────────────────────────────────┐
           │   Contextual Risk Fusion 2.0    │
           │   - Dynamic Renormalization     │
           │   - Temporal Half-Life Decay    │
           │   - Cross-Modal Boosts          │
           │   - Confidence Gating           │
           └────────────────┬────────────────┘
                            ▼
           ┌─────────────────────────────────┐
           │      Stateful Decision Engine   │
           │      (Debounced Hysteresis)     │
           └────────────────┬────────────────┘
                            ▼
           ┌─────────────────────────────────┐
           │   Adaptive Monitoring Engine    │
           │   (Low Power ◄──► High Rigor)   │
           └────────────────┬────────────────┘
                            ▼
           ┌─────────────────────────────────┐
           │  Autonomous Escalation Engine   │
           │  (Countdown ──► SHA-256 Audit)  │
           └────────────────┬────────────────┘
                            ▼
           ┌─────────────────────────────────┐
           │ Offline Continuity & Sync Store │
           │ (Durable SQLite Monotonic Log)  │
           └─────────────────────────────────┘
```

### The 6 Core Structural Differentiators:
1. **Priors + Real-Time Telemetry Coupling**: An unexpected 3-minute stop on a brightly lit commercial avenue triggers low concern; the exact same stop on an isolated, unlit road in a high-crime district triggers elevated monitoring and interaction boosts (+10.0 pts).
2. **Cross-Modal Physical/Acoustic Confirmation**: Automatic bypass of confirmation delays occurs *only* when an acute physical impact (Fall) is temporally correlated ($|\Delta t| \le 15\text{s}$) with an acoustic distress vocalization (TFLite CNN, $p \ge 0.60$).
3. **Adaptive Sensor Management**: The sampling frequency of power-hungry sensors (IMU, Audio, High-Frequency GPS) is modulated dynamically based on real-time fused risk ($0 \text{ to } 100$), conserving battery during safe segments and maximizing resolution during hazardous corridors.
4. **Data-Quality & Uncertainty Reasoning**: If GPS accuracy degrades to $\pm 80\text{m}$, detector confidence scales down dynamically to prevent false alarms. If all telemetry drops, the system flags `UNKNOWN / DEGRADED`, enforcing the principle: **"Absence of evidence of danger is NOT evidence of safety."**
5. **Autonomous Verification with Graceful Cancellation**: Emergency escalation does not depend on the user frantically pressing buttons while incapacitated; high-risk composite states automatically initiate a local verification countdown with loud audio/haptic cues and verifiable audit logging.
6. **Offline Edge Resilience**: Full monitoring, local anomaly detection, local countdown, and monotonic event buffering continue seamlessly without network connectivity, reconciling deterministically upon reconnection.
