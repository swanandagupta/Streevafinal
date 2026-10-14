/**
 * STREEVA Centralized API Client
 * Strictly calls backend contracts on fusion-service.
 * Provides fallback mock behavior for offline testing and standalone demo mode.
 */

import {
  GuardianSnapshot,
  EmergencyIncident,
  ContextualSafetyResponse,
  OfflineStatus,
  ConnectivityState
} from '../types/streeva';

const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8001';

class StreevaApiClient {
  private baseUrl: string;
  private isSimulatedMode: boolean = false;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  public setBaseUrl(url: string) {
    this.baseUrl = url;
  }

  public setSimulatedMode(enabled: boolean) {
    this.isSimulatedMode = enabled;
  }

  public getBaseUrl(): string {
    return this.baseUrl;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...(options.headers || {})
        }
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API error ${response.status}: ${errorText || response.statusText}`);
      }

      return await response.json();
    } catch (err: any) {
      // Re-throw with descriptive context
      throw new Error(`STREEVA Backend Connection Failed [${endpoint}]: ${err.message}`);
    }
  }

  // --- Journey APIs (Phase 2) ---
  public async startJourney(params: {
    journey_id: string;
    source_lat: number;
    source_lng: number;
    destination_lat: number;
    destination_lng: number;
    expected_route: { lat: number; lng: number }[];
    expected_duration_s?: number;
    external_eta?: string;
  }): Promise<GuardianSnapshot> {
    return this.request<GuardianSnapshot>('/guardian/journey/start', {
      method: 'POST',
      body: JSON.stringify(params)
    });
  }

  public async updateTelemetry(params: {
    journey_id: string;
    timestamp?: string;
    current_position: { lat: number; lng: number };
    gps_accuracy?: number;
    speed_mps?: number;
    accel_x?: number;
    accel_y?: number;
    accel_z?: number;
    gyro_x?: number;
    gyro_y?: number;
    gyro_z?: number;
    audio_distress_detected?: boolean;
    audio_confidence?: number;
  }): Promise<GuardianSnapshot> {
    return this.request<GuardianSnapshot>('/guardian/journey/update', {
      method: 'POST',
      body: JSON.stringify(params)
    });
  }

  public async endJourney(params: {
    journey_id: string;
    reason?: string;
    current_position?: { lat: number; lng: number };
  }): Promise<GuardianSnapshot> {
    return this.request<GuardianSnapshot>('/guardian/journey/end', {
      method: 'POST',
      body: JSON.stringify(params)
    });
  }

  public async getSnapshot(journeyId: string): Promise<GuardianSnapshot> {
    return this.request<GuardianSnapshot>(`/guardian/journey/${journeyId}`, {
      method: 'GET'
    });
  }

  // --- Contextual Safety APIs (Phase 3) ---
  public async evaluateContextualSafety(params: {
    snapshot: GuardianSnapshot;
    area_risk_score: number;
    area_risk_confidence?: number;
    motion_anomaly_score?: number;
    battery?: { level: number; is_charging: boolean };
    network?: { state: string };
  }): Promise<ContextualSafetyResponse> {
    return this.request<ContextualSafetyResponse>('/contextual-safety/evaluate', {
      method: 'POST',
      body: JSON.stringify(params)
    });
  }

  // --- Emergency APIs (Phase 4) ---
  public async triggerManualSOS(params: {
    journey_id: string;
    latitude?: number;
    longitude?: number;
    accuracy?: number;
    reason?: string;
  }): Promise<EmergencyIncident> {
    return this.request<EmergencyIncident>('/emergency/trigger', {
      method: 'POST',
      body: JSON.stringify(params)
    });
  }

  public async triggerAutonomousEmergency(params: {
    journey_id: string;
    decision_tier: string;
    risk_score: number;
    risk_level: string;
    dominant_factor: string;
    active_factors: string[];
  }): Promise<EmergencyIncident> {
    return this.request<EmergencyIncident>('/emergency/autonomous', {
      method: 'POST',
      body: JSON.stringify(params)
    });
  }

  public async getEmergencyIncident(incidentId: string): Promise<EmergencyIncident> {
    return this.request<EmergencyIncident>(`/emergency/${incidentId}`, {
      method: 'GET'
    });
  }

  public async cancelEmergency(incidentId: string, reason: string = 'User confirmed safe'): Promise<EmergencyIncident> {
    return this.request<EmergencyIncident>(`/emergency/${incidentId}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ reason })
    });
  }

  public async acknowledgeEmergency(
    incidentId: string,
    contactId: string,
    acknowledgedBy: string,
    notes?: string
  ): Promise<EmergencyIncident> {
    return this.request<EmergencyIncident>(`/emergency/${incidentId}/acknowledge`, {
      method: 'POST',
      body: JSON.stringify({
        contact_id: contactId,
        acknowledged_by: acknowledgedBy,
        notes: notes || 'Contact acknowledged alert via STREEVA client'
      })
    });
  }

  public async advanceEmergencyCountdown(incidentId: string, elapsedSeconds: number = 5): Promise<EmergencyIncident> {
    return this.request<EmergencyIncident>(`/emergency/${incidentId}/advance`, {
      method: 'POST',
      body: JSON.stringify({ elapsed_seconds: elapsedSeconds })
    });
  }

  // --- Offline APIs (Phase 5) ---
  public async getOfflineStatus(): Promise<OfflineStatus> {
    return this.request<OfflineStatus>('/offline/status', {
      method: 'GET'
    });
  }

  public async setConnectivity(state: ConnectivityState, reason?: string): Promise<any> {
    return this.request<any>('/offline/connectivity', {
      method: 'POST',
      body: JSON.stringify({ state, reason })
    });
  }

  public async reconcileOffline(): Promise<any> {
    return this.request<any>('/offline/reconcile', {
      method: 'POST',
      body: JSON.stringify({ simulate_partial_failure: false })
    });
  }
}

export const api = new StreevaApiClient();
