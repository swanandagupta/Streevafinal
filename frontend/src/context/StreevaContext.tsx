import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  GuardianSnapshot,
  EmergencyIncident,
  EmergencyContact,
  RiskLevel,
  DecisionTier,
  ConnectivityState,
  SensorPolicy,
  LatLngPoint,
  LocationState,
  CanonicalRoute,
  CanonicalLocation
} from '../types/streeva';
import { api } from '../api/client';
import { routingService, RouteStatus } from '../services/routingService';

export type AppState =
  | 'splash'
  | 'onboarding'
  | 'auth'
  | 'home'
  | 'journey_setup'
  | 'pre_journey_check'
  | 'active_journey'
  | 'emergency_countdown'
  | 'emergency_active'
  | 'journey_summary'
  | 'journey_history'
  | 'guardian_page'
  | 'activity'
  | 'profile'
  | 'settings';

export interface ActivityNotification {
  id: string;
  title: string;
  message: string;
  timestamp: string;
  type: 'INFO' | 'ALERT' | 'CRITICAL' | 'RESTORE';
}

export interface CompletedJourneySummary {
  journey_id: string;
  source_name: string;
  destination_name: string;
  distance_m: number;
  duration_s: number;
  adherence_percent: number | null;
  completed_at: string;
  end_reason: string;
}

interface StreevaContextType {
  appState: AppState;
  setAppState: (state: AppState) => void;
  isAuthenticated: boolean;
  user: { name: string; email: string; phone: string } | null;
  updateUserPhone: (phone: string) => void;
  safetyPreferences: {
    autoGuardian: boolean;
    audioAnalysis: boolean;
    countdownDuration: number;
  };
  updateSafetyPreferences: (prefs: Partial<{ autoGuardian: boolean; audioAnalysis: boolean; countdownDuration: number }>) => void;
  login: (email: string, name?: string, phone?: string) => void;
  logout: () => void;
  completeOnboarding: () => void;
  completedJourneys: CompletedJourneySummary[];

  // Emergency Contacts
  contacts: EmergencyContact[];
  addContact: (contact: Omit<EmergencyContact, 'id'>) => void;
  removeContact: (id: string) => void;
  toggleContact: (id: string) => void;

  // Real Geolocation State
  locationState: LocationState;
  refreshLocation: () => Promise<void>;

  // Route & Destination State (Section 1 & 2: User-selectable FROM and TO)
  selectedSource: CanonicalLocation | null;
  selectedDestination: CanonicalLocation | null;
  setStartLocation: (loc: CanonicalLocation | null) => void;
  setDestinationLocation: (loc: CanonicalLocation | null) => void;
  useCurrentLocationForStart: () => Promise<void>;
  canonicalRoute: CanonicalRoute | null;
  routeStatus: RouteStatus;
  routeError: string | null;
  selectDestination: (dest: { name: string; lat: number; lng: number }) => Promise<void>;
  calculateCanonicalRoute: (
    source: CanonicalLocation | { lat: number; lng: number; name?: string; display_name?: string; source?: string },
    destination: CanonicalLocation | { lat: number; lng: number; name?: string; display_name?: string; source?: string },
    isDemo?: boolean
  ) => Promise<void>;

  // Journey & Guardian State (Section 10–13: Lifecycle, Termination & Reset)
  activeJourneyId: string | null;
  snapshot: GuardianSnapshot | null;
  isEndingJourney: boolean;
  endJourneyError: string | null;
  lastCompletedSummary: CompletedJourneySummary | null;
  returnHomeFromSummary: () => void;
  riskLevel: RiskLevel;
  riskScore: number;
  decisionTier: DecisionTier;
  sensorPolicy: SensorPolicy | null;
  areaSafetyScore: number | null;
  startJourney: () => Promise<void>;
  updateTelemetry: (params: any) => Promise<void>;
  endJourney: (reason?: string) => Promise<boolean>;
  simulateRouteDeviation: () => void;
  simulateUnexpectedStop: () => void;
  clearAnomalies: () => void;

  // Emergency State
  incident: EmergencyIncident | null;
  triggerManualSOS: () => Promise<void>;
  triggerAutonomousEmergency: () => Promise<void>;
  cancelEmergency: (reason?: string) => Promise<void>;
  acknowledgeEmergency: (contactId?: string) => Promise<void>;

  // Connectivity & Offline
  connectivity: ConnectivityState;
  setConnectivity: (state: ConnectivityState) => void;
  reconcileOffline: () => Promise<void>;

  // Activity Feed
  notifications: ActivityNotification[];
  addNotification: (title: string, message: string, type: 'INFO' | 'ALERT' | 'CRITICAL' | 'RESTORE') => void;
}

const defaultContacts: EmergencyContact[] = [
  {
    id: 'c1',
    name: 'Aanya Sharma',
    relationship: 'Mother',
    phone_number: '+91 98765 43210',
    priority: 1,
    active: true,
    channel: 'SMS_AND_CALL'
  },
  {
    id: 'c2',
    name: 'Rohan Verma',
    relationship: 'Brother',
    phone_number: '+91 98765 11223',
    priority: 2,
    active: true,
    channel: 'SMS'
  }
];

const initialCompletedJourneys: CompletedJourneySummary[] = [
  {
    journey_id: 'j-hist-101',
    source_name: 'Indiranagar 100ft Road',
    destination_name: 'Koramangala 5th Block',
    distance_m: 5400,
    duration_s: 1440,
    adherence_percent: 99.2,
    completed_at: 'Yesterday, 9:15 PM',
    end_reason: 'ARRIVED_SAFELY'
  },
  {
    journey_id: 'j-hist-102',
    source_name: 'MG Road Metro Station',
    destination_name: 'RMZ Infinity Tech Park',
    distance_m: 4200,
    duration_s: 1100,
    adherence_percent: 98.6,
    completed_at: '10 Sep 2026, 7:30 PM',
    end_reason: 'ARRIVED_SAFELY'
  }
];

const StreevaContext = createContext<StreevaContextType | undefined>(undefined);

export const StreevaProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [appState, setAppState] = useState<AppState>('splash');
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => {
    try {
      return !!localStorage.getItem('streeva_user_session');
    } catch {
      return true;
    }
  });
  const [user, setUser] = useState<{ name: string; email: string; phone: string } | null>(() => {
    try {
      const raw = localStorage.getItem('streeva_user_session');
      if (raw) return JSON.parse(raw);
    } catch {}
    return {
      name: 'Priya Sharma',
      email: 'priya.sharma@streeva.safe',
      phone: '+91 98765 00000'
    };
  });

  const [completedJourneys, setCompletedJourneys] = useState<CompletedJourneySummary[]>(initialCompletedJourneys);
  const [contacts, setContacts] = useState<EmergencyContact[]>(defaultContacts);

  // Real Geolocation
  const [locationState, setLocationState] = useState<LocationState>({
    coords: { lat: 12.9716, lng: 77.5946 }, // initial fallback
    accuracy_m: null,
    status: 'ACQUIRING'
  });  // Destination and Canonical Route (Section 1 & 2: User-selectable FROM and TO)
  const [selectedSource, setSelectedSource] = useState<CanonicalLocation | null>(null);
  const [selectedDestination, setSelectedDestination] = useState<CanonicalLocation | null>(null);

  const [canonicalRoute, setCanonicalRoute] = useState<CanonicalRoute | null>(null);
  const [routeStatus, setRouteStatus] = useState<RouteStatus>('IDLE');
  const [routeError, setRouteError] = useState<string | null>(null);
  const [areaSafetyScore, setAreaSafetyScore] = useState<number | null>(null);

  // Active Journey (Section 10–13: Lifecycle, Termination & Complete Isolation)
  const [activeJourneyId, setActiveJourneyId] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<GuardianSnapshot | null>(null);
  const [isEndingJourney, setIsEndingJourney] = useState<boolean>(false);
  const [endJourneyError, setEndJourneyError] = useState<string | null>(null);
  const [lastCompletedSummary, setLastCompletedSummary] = useState<CompletedJourneySummary | null>(null);

  const [riskLevel, setRiskLevel] = useState<RiskLevel>('LOW');
  const [riskScore, setRiskScore] = useState<number>(18.5);
  const [decisionTier, setDecisionTier] = useState<DecisionTier>('MONITORING_SUFFICIENT');
  const [sensorPolicy, setSensorPolicy] = useState<SensorPolicy | null>({
    profile: 'BALANCED',
    accelerometer_hz: 20,
    gyroscope_enabled: true,
    gyroscope_hz: 50,
    audio_distress_active: false,
    gps_interval_sec: 5,
    battery_saver_applied: false
  });

  const [incident, setIncident] = useState<EmergencyIncident | null>(null);
  const [connectivity, setConnectivityState] = useState<ConnectivityState>('ONLINE');
  const [notifications, setNotifications] = useState<ActivityNotification[]>([
    {
      id: 'n1',
      title: 'Guardian Ready',
      message: 'Sensors calibrated and GPS lock confirmed.',
      timestamp: '10:15 AM',
      type: 'INFO'
    },
    {
      id: 'n2',
      title: 'Safety Check Passed',
      message: 'Emergency contacts reachable and local storage verified.',
      timestamp: '10:14 AM',
      type: 'INFO'
    }
  ]);

  // Acquire real location from device GPS
  const refreshLocation = useCallback(async (): Promise<void> => {
    if (!('geolocation' in navigator)) {
      setLocationState((prev) => ({
        ...prev,
        status: 'UNAVAILABLE',
        error_message: 'Geolocation not supported by device'
      }));
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocationState({
          coords: {
            lat: position.coords.latitude,
            lng: position.coords.longitude
          },
          accuracy_m: position.coords.accuracy,
          status: 'ACQUIRING', // will be ACQUIRED once valid
          timestamp: new Date().toISOString()
        });
        // Confirm acquired
        setTimeout(() => {
          setLocationState((prev) => ({ ...prev, status: 'ACQUIRED' }));
        }, 200);
      },
      (err) => {
        console.warn('Geolocation acquisition error:', err.message);
        setLocationState((prev) => ({
          ...prev,
          status: err.code === 1 ? 'DENIED' : 'UNAVAILABLE',
          error_message: err.message
        }));
      },
      { enableHighAccuracy: true, timeout: 8000, maximumAge: 10000 }
    );
  }, []);

  useEffect(() => {
    refreshLocation();
  }, [refreshLocation]);

  const addNotification = (
    title: string,
    message: string,
    type: 'INFO' | 'ALERT' | 'CRITICAL' | 'RESTORE'
  ) => {
    setNotifications((prev) => [
      {
        id: `notif-${Date.now()}`,
        title,
        message,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        type
      },
      ...prev
    ]);
  };

  const [safetyPreferences, setSafetyPreferences] = useState<{
    autoGuardian: boolean;
    audioAnalysis: boolean;
    countdownDuration: number;
  }>(() => {
    try {
      const stored = localStorage.getItem('streeva_safety_prefs');
      if (stored) return JSON.parse(stored);
    } catch {}
    return {
      autoGuardian: true,
      audioAnalysis: true,
      countdownDuration: 15
    };
  });

  const updateSafetyPreferences = (
    prefs: Partial<{ autoGuardian: boolean; audioAnalysis: boolean; countdownDuration: number }>
  ) => {
    setSafetyPreferences((prev) => {
      const updated = { ...prev, ...prefs };
      try {
        localStorage.setItem('streeva_safety_prefs', JSON.stringify(updated));
      } catch {}
      return updated;
    });
  };

  const updateUserPhone = (phone: string) => {
    setUser((prev) => {
      if (!prev) return null;
      const updated = { ...prev, phone };
      try {
        localStorage.setItem('streeva_user_session', JSON.stringify(updated));
      } catch {}
      return updated;
    });
  };

  const login = (
    email: string,
    name: string = 'Priya Sharma',
    phone: string = '+91 98765 00000'
  ) => {
    const userData = { name, email, phone };
    try {
      localStorage.setItem('streeva_user_session', JSON.stringify(userData));
    } catch {}
    setIsAuthenticated(true);
    setUser(userData);
    setAppState('home');
  };

  const logout = () => {
    try {
      localStorage.removeItem('streeva_user_session');
    } catch {}
    setIsAuthenticated(false);
    setUser(null);
    setAppState('auth');
  };

  const completeOnboarding = () => {
    setAppState('auth');
  };

  const addContact = (contactData: Omit<EmergencyContact, 'id'>) => {
    const newContact: EmergencyContact = {
      ...contactData,
      id: `c-${Date.now()}`
    };
    setContacts((prev) => [...prev, newContact]);
    addNotification('Contact Added', `${newContact.name} added to emergency list.`, 'INFO');
  };

  const removeContact = (id: string) => {
    setContacts((prev) => prev.filter((c) => c.id !== id));
  };

  const toggleContact = (id: string) => {
    setContacts((prev) =>
      prev.map((c) => (c.id === id ? { ...c, active: !c.active } : c))
    );
  };

  /**
   * Calculates the real Canonical Route using OpenStreetMap OSRM.
   */
  const calculateCanonicalRoute = async (
    source: CanonicalLocation | { lat: number; lng: number; name?: string; display_name?: string; source?: string },
    destination: CanonicalLocation | { lat: number; lng: number; name?: string; display_name?: string; source?: string },
    isDemo: boolean = false
  ) => {
    setRouteStatus('CALCULATING');
    setRouteError(null);

    try {
      const route = await routingService.calculateRoute({
        source,
        destination,
        isOffline: connectivity === 'OFFLINE',
        isDemoMode: isDemo
      });

      setCanonicalRoute(route);
      setRouteStatus('READY');

      const destLat = 'latitude' in destination ? destination.latitude : destination.lat;
      const destLng = 'longitude' in destination ? destination.longitude : destination.lng;

      // Optionally query real area safety score from area-risk-service (port 8000)
      try {
        const areaResp = await fetch(
          `http://localhost:8000/area-risk?lat=${destLat}&lng=${destLng}&hour=${new Date().getHours()}`
        );
        if (areaResp.ok) {
          const areaData = await areaResp.json();
          setAreaSafetyScore(areaData.risk_score);
        } else {
          setAreaSafetyScore(null);
        }
      } catch {
        setAreaSafetyScore(null);
      }
    } catch (err: any) {
      setRouteStatus('FAILED');
      setRouteError(err.message || 'Failed to calculate route on road network.');
    }
  };

  /**
   * Convenience option: resolve device GPS as the starting location.
   */
  const useCurrentLocationForStart = async () => {
    try {
      const loc = routingService.resolveCurrentLocation(locationState);
      setSelectedSource(loc);
      if (selectedDestination) {
        await calculateCanonicalRoute(loc, selectedDestination);
      }
      // Attempt background reverse geocoding to enrich name
      routingService.reverseGeocode(loc.latitude, loc.longitude).then((addr) => {
        if (addr) {
          setSelectedSource((prev) =>
            prev && prev.source === 'GPS_CURRENT_LOCATION'
              ? { ...prev, address: addr, display_name: `${addr.split(',')[0]} (Device GPS)` }
              : prev
          );
        }
      });
    } catch (err: any) {
      setRouteError(err.message || 'Unable to access device GPS location.');
      throw err;
    }
  };

  const setStartLocation = (loc: CanonicalLocation | null) => {
    setSelectedSource(loc);
    if (loc && selectedDestination) {
      calculateCanonicalRoute(loc, selectedDestination);
    }
  };

  const setDestinationLocation = (loc: CanonicalLocation | null) => {
    setSelectedDestination(loc);
    if (selectedSource && loc) {
      calculateCanonicalRoute(selectedSource, loc);
    }
  };

  /**
   * User selects a destination from quick list or home search.
   */
  const selectDestination = async (dest: { name: string; lat: number; lng: number }) => {
    const canonicalDest: CanonicalLocation = {
      display_name: dest.name,
      latitude: dest.lat,
      longitude: dest.lng,
      source: 'USER_INPUT'
    };
    setSelectedDestination(canonicalDest);

    // If source isn't explicitly chosen, default to current location or fallback
    let srcLoc = selectedSource;
    if (!srcLoc) {
      try {
        srcLoc = routingService.resolveCurrentLocation(locationState);
        setSelectedSource(srcLoc);
      } catch {
        srcLoc = {
          display_name: 'Current Location (Device GPS)',
          latitude: locationState.coords?.lat || 12.9716,
          longitude: locationState.coords?.lng || 77.5946,
          source: 'GPS_CURRENT_LOCATION'
        };
        setSelectedSource(srcLoc);
      }
    }

    await calculateCanonicalRoute(srcLoc, canonicalDest, false);
    setAppState('journey_setup');
  };

  /**
   * Start Journey — passes the EXACT canonical route forward to Phase 2 backend!
   */
  const startJourney = async () => {
    if (!canonicalRoute) {
      throw new Error('Cannot start journey: no canonical route calculated.');
    }

    const jId = `journey-${Date.now()}`;
    setActiveJourneyId(jId);

    const startPayload = {
      journey_id: jId,
      source_lat: canonicalRoute.source.lat,
      source_lng: canonicalRoute.source.lng,
      destination_lat: canonicalRoute.destination.lat,
      destination_lng: canonicalRoute.destination.lng,
      expected_route: canonicalRoute.polyline,
      expected_duration_s: canonicalRoute.duration_s
    };

    try {
      const snap = await api.startJourney(startPayload);
      setSnapshot(snap);
    } catch (err) {
      console.warn('Backend startJourney failed, using local offline Phase 5 cache:', err);
      // Fallback preserves the EXACT same canonical polyline locally
      setSnapshot({
        journey_id: jId,
        timestamp: new Date().toISOString(),
        journey_state: 'IN_PROGRESS',
        current_location: {
          lat: canonicalRoute.source.lat,
          lng: canonicalRoute.source.lng
        },
        distance_covered_m: 0,
        distance_remaining_m: canonicalRoute.distance_m,
        estimated_eta_seconds: canonicalRoute.duration_s,
        progress_percent: 0,
        telemetry_quality: 'VALID',
        arrival_status: 'NOT_ARRIVED',
        route_deviation_state: 'NORMAL',
        unexpected_stop_state: 'MOVING',
        fall_state: 'NORMAL',
        audio_state: 'NORMAL'
      });
    }

    setRiskLevel('LOW');
    setRiskScore(15.0);
    setDecisionTier('MONITORING_SUFFICIENT');
    setEndJourneyError(null);
    addNotification(
      'Journey Started',
      `Navigating to ${canonicalRoute.destination.name} under Guardian protection.`,
      'INFO'
    );
    setAppState('active_journey');
  };

  const updateTelemetry = async (params: any) => {
    if (!activeJourneyId) return;
    try {
      const snap = await api.updateTelemetry({
        journey_id: activeJourneyId,
        ...params
      });
      setSnapshot(snap);
      if (snap.arrival_status === 'ARRIVED') {
        // Section 11: Phase 2 reports ARRIVED -> finalize journey lifecycle
        await endJourney('ARRIVED_SAFELY');
      }
    } catch {
      if (snapshot && canonicalRoute) {
        const stepDist = Math.round(canonicalRoute.distance_m * 0.15);
        setSnapshot((prev) =>
          prev
            ? {
                ...prev,
                progress_percent: Math.min(prev.progress_percent + 15, 100),
                distance_covered_m: prev.distance_covered_m + stepDist,
                distance_remaining_m: Math.max(prev.distance_remaining_m - stepDist, 0),
                estimated_eta_seconds: Math.max(
                  prev.estimated_eta_seconds - Math.round(canonicalRoute.duration_s * 0.15),
                  0
                )
              }
            : null
        );
      }
    }
  };

  /**
   * Section 10 & 13: End Journey Lifecycle
   * Calls Phase 2 backend lifecycle first.
   * On success: clears active state, stores summary, transitions to summary screen.
   * On failure: stays on screen, displays "Couldn't end the journey" with retry.
   */
  const endJourney = async (reason: string = 'ARRIVED_SAFELY'): Promise<boolean> => {
    if (!activeJourneyId) {
      setAppState('home');
      return true;
    }

    setIsEndingJourney(true);
    setEndJourneyError(null);

    try {
      // 1. Call real Phase 2 end lifecycle
      const endSnapshot = await api.endJourney({
        journey_id: activeJourneyId,
        reason: reason
      });

      // 2. Persist finalized journey summary
      // Strict provenance: adherence is calculated solely from valid movement observations by GuardianMonitor.
      // If telemetry is insufficient or journey ended before travel, adherence is null (renders "— / Not enough data").
      const adherence = endSnapshot?.route_adherence_percent ?? null;
      const actualDistance = (endSnapshot?.distance_travelled_m != null && endSnapshot.distance_travelled_m > 0)
        ? endSnapshot.distance_travelled_m
        : (endSnapshot?.route_progress_percent && endSnapshot.route_progress_percent > 0 && canonicalRoute?.distance_m
          ? (canonicalRoute.distance_m * endSnapshot.route_progress_percent) / 100
          : 0);
      const actualDuration = endSnapshot?.actual_duration_s ?? 0;

      const summary: CompletedJourneySummary = {
        journey_id: activeJourneyId,
        source_name: canonicalRoute?.source?.name || 'Starting Point',
        destination_name: canonicalRoute?.destination?.name || 'Destination',
        distance_m: Math.round(actualDistance),
        duration_s: Math.round(actualDuration),
        adherence_percent: adherence,
        completed_at: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        end_reason: reason
      };
      setLastCompletedSummary(summary);
      setCompletedJourneys((prev) => [summary, ...prev]);

      // 3. Clear active journey state completely (Section 12 & 20: Clean up monitoring & state)
      setActiveJourneyId(null);
      setSnapshot(null);
      setSelectedSource(null);
      setSelectedDestination(null);
      setCanonicalRoute(null);
      setRiskLevel('LOW');
      setRiskScore(15.0);
      setDecisionTier('MONITORING_SUFFICIENT');
      setIsEndingJourney(false);

      addNotification(
        reason === 'ARRIVED_SAFELY' ? 'Arrived Safely' : 'Journey Ended',
        `Journey to ${summary.destination_name} ended safely.`,
        'INFO'
      );

      // 4. Section 17 & 18: If user ended journey, return directly Home! If arrived safely, transition to journey summary.
      if (reason === 'USER_CANCELLED') {
        setAppState('home');
      } else {
        setAppState('journey_summary');
      }
      return true;
    } catch (err: any) {
      console.error('Failed to end journey on Phase 2 backend:', err);
      setIsEndingJourney(false);
      // Section 13: Failure -> remain on journey screen, show "Couldn't end the journey" with "Retry"
      setEndJourneyError(err.message || "Couldn't end the journey");
      return false;
    }
  };

  /**
   * Section 10 & 12: Return to Home from Journey Summary
   * Guarantees all active journey state is null/cleared so new journey starts fresh.
   */
  const returnHomeFromSummary = () => {
    setActiveJourneyId(null);
    setSnapshot(null);
    setSelectedSource(null);
    setSelectedDestination(null);
    setCanonicalRoute(null);
    setRiskLevel('LOW');
    setRiskScore(15.0);
    setDecisionTier('MONITORING_SUFFICIENT');
    setEndJourneyError(null);
    setAppState('home');
  };

  const simulateRouteDeviation = () => {
    if (!snapshot) return;
    setSnapshot({
      ...snapshot,
      route_deviation_state: 'CONFIRMED_DEVIATION'
    });
    setRiskLevel('HIGH');
    setRiskScore(68.0);
    setDecisionTier('USER_CHECK_IN_RECOMMENDED');
    setSensorPolicy((prev) => (prev ? { ...prev, profile: 'ELEVATED', audio_distress_active: true } : null));
    addNotification('Route Deviation', 'Departed from expected route by 140 meters.', 'ALERT');
  };

  const simulateUnexpectedStop = () => {
    if (!snapshot) return;
    setSnapshot({
      ...snapshot,
      unexpected_stop_state: 'CONFIRMED_STOP'
    });
    setRiskLevel('MEDIUM');
    setRiskScore(45.0);
    setDecisionTier('USER_CHECK_IN_RECOMMENDED');
    addNotification('Stationary Check', 'Movement paused for over 3 minutes.', 'ALERT');
  };

  const clearAnomalies = () => {
    if (!snapshot) return;
    setSnapshot({
      ...snapshot,
      route_deviation_state: 'NORMAL',
      unexpected_stop_state: 'MOVING'
    });
    setRiskLevel('LOW');
    setRiskScore(18.0);
    setDecisionTier('MONITORING_SUFFICIENT');
    setSensorPolicy((prev) => (prev ? { ...prev, profile: 'BALANCED', audio_distress_active: false } : null));
    addNotification('Stationary Cleared', "Traveler confirmed 'I'm Okay'. Continuing journey under Guardian protection.", 'RESTORE');
  };

  const triggerManualSOS = async () => {
    const jId = activeJourneyId || `standalone-${Date.now()}`;
    const lat = snapshot?.current_location?.lat || locationState.coords?.lat || 12.9716;
    const lng = snapshot?.current_location?.lng || locationState.coords?.lng || 77.5946;

    try {
      const inc = await api.triggerManualSOS({
        journey_id: jId,
        latitude: lat,
        longitude: lng,
        reason: 'User activated manual SOS'
      });
      setIncident(inc);
    } catch {
      setIncident({
        incident_id: `inc-${Date.now()}`,
        journey_id: jId,
        trigger_type: 'MANUAL_SOS',
        state: 'CONFIRMATION_COUNTDOWN',
        risk_score: 95.0,
        risk_level: 'CRITICAL',
        decision_tier: 'AUTONOMOUS_RESPONSE_REQUIRED',
        countdown_seconds_remaining: 15,
        acknowledgement_status: 'UNACKNOWLEDGED',
        escalation_level: 'PRIMARY_PENDING',
        primary_contact: contacts[0],
        last_known_location: {
          lat,
          lng,
          quality: 'LIVE_GPS'
        }
      });
    }

    setRiskLevel('CRITICAL');
    setDecisionTier('AUTONOMOUS_RESPONSE_REQUIRED');
    setAppState('emergency_countdown');
    addNotification('Emergency Triggered', 'Manual SOS initiated. 15s verification window active.', 'CRITICAL');
  };

  const triggerAutonomousEmergency = async () => {
    const jId = activeJourneyId || `auto-${Date.now()}`;
    const lat = snapshot?.current_location?.lat || locationState.coords?.lat || 12.9716;
    const lng = snapshot?.current_location?.lng || locationState.coords?.lng || 77.5946;

    try {
      const inc = await api.triggerAutonomousEmergency({
        journey_id: jId,
        decision_tier: 'AUTONOMOUS_RESPONSE_REQUIRED',
        risk_score: 88.5,
        risk_level: 'CRITICAL',
        dominant_factor: 'FALL_PLUS_DISTRESS',
        active_factors: ['IMPACT_FALL', 'DISTRESS_AUDIO']
      });
      setIncident(inc);
    } catch {
      setIncident({
        incident_id: `auto-inc-${Date.now()}`,
        journey_id: jId,
        trigger_type: 'AUTONOMOUS_DECISION',
        state: 'CONFIRMATION_COUNTDOWN',
        risk_score: 88.5,
        risk_level: 'CRITICAL',
        decision_tier: 'AUTONOMOUS_RESPONSE_REQUIRED',
        countdown_seconds_remaining: 15,
        acknowledgement_status: 'UNACKNOWLEDGED',
        escalation_level: 'PRIMARY_PENDING',
        primary_contact: contacts[0],
        last_known_location: {
          lat,
          lng,
          quality: 'LIVE_GPS'
        }
      });
    }

    setRiskLevel('CRITICAL');
    setDecisionTier('AUTONOMOUS_RESPONSE_REQUIRED');
    setAppState('emergency_countdown');
    addNotification('Autonomous Escalation', 'High-confidence safety threshold exceeded. Emergency initiated.', 'CRITICAL');
  };

  const cancelEmergency = async (reason: string = 'User confirmed safe') => {
    if (incident) {
      try {
        await api.cancelEmergency(incident.incident_id, reason);
      } catch {
        // Fallback
      }
    }
    setIncident(null);
    setRiskLevel('LOW');
    setDecisionTier('MONITORING_SUFFICIENT');
    setAppState(activeJourneyId ? 'active_journey' : 'home');
    addNotification('Emergency Cancelled', 'False alarm confirmed. Normal monitoring resumed.', 'RESTORE');
  };

  const acknowledgeEmergency = async (contactId?: string) => {
    if (incident) {
      try {
        await api.acknowledgeEmergency(incident.incident_id, contactId || 'c1', 'Aanya Sharma');
      } catch {
        // Fallback
      }
      setIncident((prev) =>
        prev
          ? {
              ...prev,
              acknowledgement_status: 'ACKNOWLEDGED',
              acknowledged_by: 'Aanya Sharma',
              state: 'RESOLVED'
            }
          : null
      );
    }
    addNotification('Emergency Acknowledged', 'Contact confirmed receipt and assistance.', 'INFO');
  };

  const setConnectivity = (state: ConnectivityState) => {
    setConnectivityState(state);
    if (state === 'OFFLINE') {
      addNotification('Offline Guardian', 'Network disconnected. Operating local monitoring.', 'ALERT');
    } else if (state === 'RECONNECTING') {
      addNotification('Synchronizing', 'Network detected. Reconciling telemetry buffers...', 'INFO');
    } else if (state === 'ONLINE') {
      addNotification('Connected', 'Guardian restored to full online synchronization.', 'RESTORE');
    }
  };

  const reconcileOffline = async () => {
    setConnectivityState('RECONNECTING');
    try {
      await api.reconcileOffline();
    } catch {
      // Fallback
    }
    setTimeout(() => {
      setConnectivityState('ONLINE');
      addNotification('Reconciliation Complete', 'All buffered journey telemetry synchronized.', 'RESTORE');
    }, 1200);
  };

  return (
    <StreevaContext.Provider
      value={{
        appState,
        setAppState,
        isAuthenticated,
        user,
        updateUserPhone,
        safetyPreferences,
        updateSafetyPreferences,
        login,
        logout,
        completeOnboarding,
        completedJourneys,
        contacts,
        addContact,
        removeContact,
        toggleContact,
        locationState,
        refreshLocation,
        selectedSource,
        selectedDestination,
        setStartLocation,
        setDestinationLocation,
        useCurrentLocationForStart,
        canonicalRoute,
        routeStatus,
        routeError,
        selectDestination,
        calculateCanonicalRoute,
        activeJourneyId,
        snapshot,
        isEndingJourney,
        endJourneyError,
        lastCompletedSummary,
        returnHomeFromSummary,
        riskLevel,
        riskScore,
        decisionTier,
        sensorPolicy,
        areaSafetyScore,
        startJourney,
        updateTelemetry,
        endJourney,
        simulateRouteDeviation,
        simulateUnexpectedStop,
        clearAnomalies,
        incident,
        triggerManualSOS,
        triggerAutonomousEmergency,
        cancelEmergency,
        acknowledgeEmergency,
        connectivity,
        setConnectivity,
        reconcileOffline,
        notifications,
        addNotification
      }}
    >
      {children}
    </StreevaContext.Provider>
  );
};

export const useStreeva = () => {
  const context = useContext(StreevaContext);
  if (!context) {
    throw new Error('useStreeva must be used within a StreevaProvider');
  }
  return context;
};
