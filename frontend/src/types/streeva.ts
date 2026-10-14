/**
 * STREEVA Client Type Definitions
 * Directly mapping to backend schemas in fusion-service (Phases 1–5).
 * The client NEVER recalculates risk or invents data structures.
 */

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | 'UNKNOWN' | 'DEGRADED';

export type DecisionTier = 
  | 'MONITORING_SUFFICIENT' 
  | 'USER_CHECK_IN_RECOMMENDED' 
  | 'AUTONOMOUS_RESPONSE_REQUIRED';

export type JourneyState = 
  | 'UNINITIALIZED'
  | 'STARTING'
  | 'IN_PROGRESS'
  | 'PAUSED'
  | 'STOPPED'
  | 'ARRIVED'
  | 'CANCELLED';

export type EmergencyState =
  | 'TRIGGERED'
  | 'CONFIRMATION_COUNTDOWN'
  | 'RESPONSE_AUTHORIZED'
  | 'CONTACTS_NOTIFIED'
  | 'RESOLVED'
  | 'CANCELLED';

export type TriggerType = 'MANUAL_SOS' | 'AUTONOMOUS_DECISION';

export type EscalationLevel = 
  | 'PRIMARY_PENDING'
  | 'PRIMARY_NOTIFIED'
  | 'SECONDARY_ESCALATED'
  | 'AUTHORITIES_ALERTED';

export type AcknowledgementStatus = 'UNACKNOWLEDGED' | 'ACKNOWLEDGED' | 'TIMED_OUT';

export type ConnectivityState = 'ONLINE' | 'DEGRADED' | 'OFFLINE' | 'RECONNECTING';

export type SensorProfile = 'LOW_POWER' | 'BALANCED' | 'ELEVATED' | 'CRITICAL_MAX';

export interface LatLngPoint {
  lat: number;
  lng: number;
}

export interface LocationState {
  coords: LatLngPoint | null;
  accuracy_m: number | null;
  status: 'ACQUIRING' | 'ACQUIRED' | 'DENIED' | 'UNAVAILABLE';
  error_message?: string;
  timestamp?: string;
}

export interface CanonicalLocation {
  display_name: string;
  latitude: number;
  longitude: number;
  address?: string;
  source: 'GPS_CURRENT_LOCATION' | 'OSM_NOMINATIM_SEARCH' | 'USER_INPUT';
  accuracy_m?: number | null;
}

export interface CanonicalRoute {
  source: {
    lat: number;
    lng: number;
    name: string;
    display_name?: string;
    source?: string;
  };
  destination: {
    lat: number;
    lng: number;
    name: string;
    display_name?: string;
    source?: string;
  };
  polyline: LatLngPoint[];
  distance_m: number;
  duration_s: number;
  provider: 'OSRM_OPENSTREETMAP' | 'DEMO_FIXTURE';
  is_demo: boolean;
}

export interface EmergencyContact {
  id: string;
  name: string;
  relationship: string;
  phone_number: string;
  priority: number;
  active: boolean;
  channel: string;
}

export interface ContextualSafetyResponse {
  assessment: any;
  decision: DecisionOutput;
  sensor_policy: SensorPolicy;
}

export interface RiskFactor {
  name: string;
  contribution: number;
  confidence: number;
  state: string;
  reason: string;
}

export interface SensorPolicy {
  profile: SensorProfile;
  accelerometer_hz: number;
  gyroscope_enabled: boolean;
  gyroscope_hz: number;
  audio_distress_active: boolean;
  gps_interval_sec: number;
  battery_saver_applied: boolean;
}

export interface DecisionOutput {
  decision_tier: DecisionTier;
  hysteresis_state: string;
  consecutive_observations: number;
  requires_user_check_in: boolean;
  reason: string;
}

export interface GuardianSnapshot {
  journey_id: string;
  timestamp: string;
  journey_state: JourneyState;
  current_location: LatLngPoint | null;
  distance_covered_m: number;
  distance_remaining_m: number;
  estimated_eta_seconds: number;
  progress_percent: number;
  route_progress_percent?: number;
  telemetry_quality: 'VALID' | 'DEGRADED' | 'MISSING' | 'STALE';
  arrival_status: 'NOT_ARRIVED' | 'ARRIVED';
  route_deviation_state: 'NORMAL' | 'POSSIBLE_DEVIATION' | 'CONFIRMED_DEVIATION';
  unexpected_stop_state: 'MOVING' | 'POSSIBLE_STOP' | 'CONFIRMED_STOP';
  fall_state: 'NORMAL' | 'IMPACT_DETECTED' | 'POTENTIAL_FALL' | 'CONFIRMED_FALL';
  audio_state: 'NORMAL' | 'DISTRESS_DETECTED' | 'CONFIRMED_DISTRESS';
  route_adherence_percent?: number | null;
  distance_travelled_m?: number;
  actual_duration_s?: number;
  valid_observations_count?: number;
}

export interface NotificationDeliveryResult {
  contact_id: string;
  channel: string;
  status: 'PENDING' | 'SENT' | 'DELIVERED' | 'FAILED' | 'ACKNOWLEDGED';
  timestamp: string;
  error_message?: string;
}

export interface EmergencyIncident {
  incident_id: string;
  journey_id: string;
  trigger_type: TriggerType;
  state: EmergencyState;
  risk_score: number;
  risk_level: RiskLevel;
  decision_tier: DecisionTier;
  countdown_seconds_remaining?: number;
  countdown_started_at?: string;
  response_authorized_at?: string;
  resolved_at?: string;
  cancelled_at?: string;
  acknowledgement_status: AcknowledgementStatus;
  acknowledged_by?: string;
  escalation_level: EscalationLevel;
  primary_contact?: EmergencyContact;
  delivery_results?: NotificationDeliveryResult[];
  last_known_location?: {
    lat: number;
    lng: number;
    accuracy?: number;
    quality?: 'LIVE_GPS' | 'CACHED_RECENT' | 'STALE' | 'UNAVAILABLE';
    timestamp?: string;
  };
}

export interface OfflineStatus {
  connectivity_state: ConnectivityState;
  local_monitoring_active: boolean;
  cached_journey_id?: string;
  buffered_events_count: number;
  last_reconciled_at?: string;
}
