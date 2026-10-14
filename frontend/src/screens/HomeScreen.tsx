import React, { useState, useEffect } from 'react';
import { useStreeva } from '../context/StreevaContext';
import { GuardianCore } from '../components/GuardianCore';
import { GlassCard } from '../components/GlassCard';
import { PrimaryButton } from '../components/PrimaryButton';
import { RiskBadge } from '../components/RiskBadge';
import { routingService, RouteSearchResult } from '../services/routingService';
import { CanonicalLocation } from '../types/streeva';
import {
  MapPin,
  Search,
  Navigation,
  Radio,
  Users,
  Wifi,
  Loader2,
  Compass,
  Crosshair,
  ArrowRight,
  Clock,
  ShieldCheck,
  History
} from 'lucide-react';

export const HomeScreen: React.FC = () => {
  const {
    user,
    riskLevel,
    connectivity,
    contacts,
    locationState,
    sensorPolicy,
    selectedSource,
    selectedDestination,
    setStartLocation,
    setDestinationLocation,
    useCurrentLocationForStart,
    calculateCanonicalRoute,
    completedJourneys,
    selectDestination,
    setAppState
  } = useStreeva();

  // Search queries & autocomplete
  const [fromQuery, setFromQuery] = useState(selectedSource?.display_name || '');
  const [toQuery, setToQuery] = useState(selectedDestination?.display_name || '');

  const [fromResults, setFromResults] = useState<CanonicalLocation[]>([]);
  const [toResults, setToResults] = useState<RouteSearchResult[]>([]);

  const [isSearchingFrom, setIsSearchingFrom] = useState(false);
  const [isSearchingTo, setIsSearchingTo] = useState(false);
  const [isGpsLoading, setIsGpsLoading] = useState(false);
  const [isCalculating, setIsCalculating] = useState(false);

  // Sync inputs with selected source & destination
  useEffect(() => {
    if (selectedSource) {
      setFromQuery(selectedSource.display_name);
    }
  }, [selectedSource]);

  useEffect(() => {
    if (selectedDestination) {
      setToQuery(selectedDestination.display_name);
    }
  }, [selectedDestination]);

  // Debounced search for FROM location
  useEffect(() => {
    if (!fromQuery || fromQuery.trim().length < 2) {
      setFromResults([]);
      setIsSearchingFrom(false);
      return;
    }
    if (selectedSource && fromQuery === selectedSource.display_name) {
      setFromResults([]);
      return;
    }

    const timer = setTimeout(async () => {
      setIsSearchingFrom(true);
      const results = await routingService.searchLocations(fromQuery);
      setFromResults(results);
      setIsSearchingFrom(false);
    }, 400);

    return () => clearTimeout(timer);
  }, [fromQuery, selectedSource]);

  // Debounced search for TO destination
  useEffect(() => {
    if (!toQuery || toQuery.trim().length < 2) {
      setToResults([]);
      setIsSearchingTo(false);
      return;
    }
    if (selectedDestination && toQuery === selectedDestination.display_name) {
      setToResults([]);
      return;
    }

    const timer = setTimeout(async () => {
      setIsSearchingTo(true);
      const results = await routingService.searchDestinations(toQuery);
      setToResults(results);
      setIsSearchingTo(false);
    }, 400);

    return () => clearTimeout(timer);
  }, [toQuery, selectedDestination]);

  const handleSelectFrom = (loc: CanonicalLocation) => {
    setStartLocation(loc);
    setFromQuery(loc.display_name);
    setFromResults([]);
  };

  const handleSelectTo = (result: RouteSearchResult) => {
    const shortName = result.display_name.split(',')[0].trim();
    const destLoc: CanonicalLocation = {
      display_name: shortName,
      latitude: result.lat,
      longitude: result.lng,
      source: 'USER_INPUT'
    };
    setDestinationLocation(destLoc);
    setToQuery(shortName);
    setToResults([]);
  };

  const handleUseCurrentLocation = async () => {
    setIsGpsLoading(true);
    try {
      await useCurrentLocationForStart();
    } catch {
      // Handled in context
    } finally {
      setIsGpsLoading(false);
    }
  };

  const handleCalculateRoute = async () => {
    setIsCalculating(true);
    try {
      let src = selectedSource;
      if (!src) {
        try {
          src = routingService.resolveCurrentLocation(locationState);
          setStartLocation(src);
        } catch {
          src = {
            display_name: 'Current Location (Device GPS)',
            latitude: locationState.coords?.lat || 12.9716,
            longitude: locationState.coords?.lng || 77.5946,
            source: 'GPS_CURRENT_LOCATION'
          };
          setStartLocation(src);
        }
      }

      let dest = selectedDestination;
      if (!dest && toQuery.trim()) {
        const searched = await routingService.searchLocations(toQuery.trim());
        if (searched.length > 0) {
          dest = searched[0];
          setDestinationLocation(dest);
        }
      }

      if (src && dest) {
        await calculateCanonicalRoute(src, dest);
        setAppState('journey_setup');
      } else if (dest) {
        setAppState('journey_setup');
      }
    } finally {
      setIsCalculating(false);
    }
  };

  // Dynamic GPS Status calculation
  const getGpsStatus = () => {
    if (locationState.status === 'DENIED' || locationState.status === 'UNAVAILABLE') {
      return { title: 'GPS', value: 'Unavailable', isAlert: true };
    }
    if (locationState.status === 'ACQUIRING') {
      return { title: 'GPS', value: 'Acquiring...', isAlert: false };
    }
    const isStale =
      locationState.timestamp &&
      Date.now() - new Date(locationState.timestamp).getTime() > 60000;
    if (isStale) {
      return { title: 'GPS', value: 'Stale', isAlert: true };
    }
    if (locationState.status === 'ACQUIRED' && locationState.accuracy_m != null) {
      const acc = Math.round(locationState.accuracy_m);
      if (acc > 150) {
        return { title: 'GPS', value: `±${acc}m · Limited`, isAlert: true };
      }
      return { title: 'GPS Lock', value: `±${acc}m`, isAlert: false };
    }
    if (locationState.coords) {
      const acc = locationState.accuracy_m ? Math.round(locationState.accuracy_m) : 105;
      return { title: 'GPS Lock', value: `±${acc}m`, isAlert: false };
    }
    return { title: 'GPS', value: 'Standby', isAlert: false };
  };

  // Dynamic Sensor Status calculation
  const getSensorStatus = () => {
    if (!sensorPolicy) {
      return { title: 'Sensors', value: 'Standby' };
    }
    if (sensorPolicy.battery_saver_applied) {
      return { title: 'Sensors', value: 'Limited' };
    }
    if (sensorPolicy.profile === 'ELEVATED' || sensorPolicy.profile === 'CRITICAL_MAX') {
      return { title: 'Sensors', value: 'Active' };
    }
    if (sensorPolicy.profile === 'LOW_POWER') {
      return { title: 'Sensors', value: 'Standby' };
    }
    return { title: 'Sensors', value: 'Calibrated' };
  };

  const gpsStatus = getGpsStatus();
  const sensorStatus = getSensorStatus();
  const activeContacts = contacts.filter((c) => c.active);
  const contactsLabel =
    activeContacts.length === 0
      ? '0 Contacts'
      : activeContacts.length === 1
      ? '1 Contact'
      : `${activeContacts.length} Contacts`;

  return (
    <div className="streeva-screen-content">
      {/* Top Greeting & Status Pill */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div>
          <span style={{ fontSize: '12px', color: 'var(--streeva-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Protective Layer
          </span>
          <h2 style={{ fontSize: '20px', fontWeight: 800, color: 'var(--streeva-text-primary)' }}>
            Hello, {user?.name?.split(' ')[0] || 'Traveler'}
          </h2>
        </div>
        <RiskBadge level={riskLevel} size="sm" />
      </div>

      {/* Redesigned Guardian Awareness Card: Left-Aligned Core + Title + 2x2 Grid */}
      <GlassCard
        borderGlow={riskLevel === 'LOW' ? 'low' : 'brand'}
        style={{
          padding: '16px',
          marginBottom: '20px'
        }}
      >
        {/* Top Unit: Guardian Core on Left, Guardian Ready vertically centered on Right */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ flexShrink: 0 }}>
            <GuardianCore riskLevel={riskLevel} size={96} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <div
              style={{
                fontSize: '22px',
                fontWeight: 800,
                color: 'var(--streeva-text-primary)',
                lineHeight: 1.15,
                letterSpacing: '-0.02em'
              }}
            >
              Guardian
            </div>
            <div
              style={{
                fontSize: '22px',
                fontWeight: 800,
                color: activeContacts.length === 0 ? 'var(--safety-medium)' : 'var(--safety-low)',
                lineHeight: 1.15,
                letterSpacing: '-0.02em'
              }}
            >
              {activeContacts.length === 0 ? 'Ready (Limited)' : 'Ready'}
            </div>
            {activeContacts.length === 0 && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  marginTop: '4px',
                  fontSize: '11px',
                  color: 'var(--safety-medium)'
                }}
              >
                <span>Emergency contacts not configured</span>
                <button
                  onClick={() => setAppState('profile')}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--streeva-intel-cyan)',
                    fontSize: '11px',
                    fontWeight: 700,
                    textDecoration: 'underline',
                    cursor: 'pointer',
                    padding: 0
                  }}
                >
                  Add
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Separator Line */}
        <div
          style={{
            width: '100%',
            height: '1px',
            backgroundColor: 'var(--streeva-border-subtle)',
            margin: '14px 0 12px 0'
          }}
        />

        {/* 2 × 2 Dynamic Information Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '8px',
            width: '100%'
          }}
        >
          {/* Row 1, Col 1: GPS Status */}
          <div
            style={{
              backgroundColor: 'rgba(255, 255, 255, 0.02)',
              border: '1px solid var(--streeva-border-subtle)',
              borderRadius: 'var(--radius-sm)',
              padding: '8px 10px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            <MapPin
              size={16}
              color={gpsStatus.isAlert ? 'var(--safety-medium)' : 'var(--safety-low)'}
              style={{ flexShrink: 0 }}
            />
            <div style={{ minWidth: 0, overflow: 'hidden' }}>
              <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--streeva-text-secondary)', whiteSpace: 'nowrap' }}>
                {gpsStatus.title}
              </div>
              <div
                style={{
                  fontSize: '12px',
                  fontWeight: 700,
                  color: gpsStatus.isAlert ? 'var(--safety-medium)' : 'var(--safety-low)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis'
                }}
              >
                {gpsStatus.value}
              </div>
            </div>
          </div>

          {/* Row 1, Col 2: Sensors Status */}
          <div
            style={{
              backgroundColor: 'rgba(255, 255, 255, 0.02)',
              border: '1px solid var(--streeva-border-subtle)',
              borderRadius: 'var(--radius-sm)',
              padding: '8px 10px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            <Radio size={16} color="var(--safety-low)" style={{ flexShrink: 0 }} />
            <div style={{ minWidth: 0, overflow: 'hidden' }}>
              <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--streeva-text-secondary)', whiteSpace: 'nowrap' }}>
                {sensorStatus.title}
              </div>
              <div
                style={{
                  fontSize: '12px',
                  fontWeight: 700,
                  color: 'var(--safety-low)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis'
                }}
              >
                {sensorStatus.value}
              </div>
            </div>
          </div>

          {/* Row 2, Col 1: Connection Status */}
          <div
            style={{
              backgroundColor: 'rgba(255, 255, 255, 0.02)',
              border: '1px solid var(--streeva-border-subtle)',
              borderRadius: 'var(--radius-sm)',
              padding: '8px 10px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            <Wifi
              size={16}
              color={connectivity === 'OFFLINE' || connectivity === 'DEGRADED' ? 'var(--safety-medium)' : 'var(--safety-low)'}
              style={{ flexShrink: 0 }}
            />
            <div style={{ minWidth: 0, overflow: 'hidden' }}>
              <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--streeva-text-secondary)', whiteSpace: 'nowrap' }}>
                Connection
              </div>
              <div
                style={{
                  fontSize: '12px',
                  fontWeight: 700,
                  color:
                    connectivity === 'OFFLINE' || connectivity === 'DEGRADED'
                      ? 'var(--safety-medium)'
                      : 'var(--safety-low)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis'
                }}
              >
                {connectivity}
              </div>
            </div>
          </div>

          {/* Row 2, Col 2: Emergency Contacts Status */}
          <div
            style={{
              backgroundColor: 'rgba(255, 255, 255, 0.02)',
              border: '1px solid var(--streeva-border-subtle)',
              borderRadius: 'var(--radius-sm)',
              padding: '8px 10px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            <Users
              size={16}
              color={activeContacts.length === 0 ? 'var(--safety-medium)' : 'var(--safety-low)'}
              style={{ flexShrink: 0 }}
            />
            <div style={{ minWidth: 0, overflow: 'hidden' }}>
              <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--streeva-text-secondary)', whiteSpace: 'nowrap' }}>
                Emergency
              </div>
              <div
                style={{
                  fontSize: '12px',
                  fontWeight: 700,
                  color: activeContacts.length === 0 ? 'var(--safety-medium)' : 'var(--safety-low)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis'
                }}
              >
                {contactsLabel}
              </div>
            </div>
          </div>
        </div>
      </GlassCard>

      {/* Primary Journey Planning Center (Sections 6 & 7: Start Location + Destination) */}
      <GlassCard style={{ padding: '16px', marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--streeva-intel-cyan)', letterSpacing: '0.04em' }}>
            PLAN A SAFE JOURNEY
          </span>
          <button
            onClick={handleUseCurrentLocation}
            disabled={isGpsLoading}
            style={{
              background: 'none',
              border: 'none',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              color: 'var(--streeva-brand-primary)',
              fontSize: '11px',
              fontWeight: 700,
              cursor: 'pointer'
            }}
          >
            {isGpsLoading ? <Loader2 size={12} className="spin" /> : <Crosshair size={12} />}
            Use Current Location
          </button>
        </div>

        {/* FROM Location Search Input */}
        <div style={{ marginBottom: '12px', position: 'relative' }}>
          <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)', marginBottom: '4px', fontWeight: 600 }}>
            FROM (STARTING POINT)
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              backgroundColor: 'var(--streeva-bg-deep)',
              border: '1px solid var(--streeva-border-subtle)',
              borderRadius: 'var(--radius-sm)',
              padding: '9px 12px'
            }}
          >
            <MapPin size={16} color="var(--safety-low)" style={{ flexShrink: 0 }} />
            <input
              type="text"
              value={fromQuery}
              onChange={(e) => setFromQuery(e.target.value)}
              placeholder="Search starting location..."
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--streeva-text-primary)',
                fontSize: '13px',
                width: '100%',
                outline: 'none'
              }}
            />
            {isSearchingFrom && <Loader2 size={14} color="var(--streeva-intel-cyan)" className="spin" />}
          </div>

          {/* Autocomplete Dropdown for FROM */}
          {fromResults.length > 0 && (
            <div
              style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                right: 0,
                zIndex: 30,
                backgroundColor: 'var(--streeva-surface-card)',
                border: '1px solid var(--streeva-border-subtle)',
                borderRadius: 'var(--radius-sm)',
                marginTop: '4px',
                maxHeight: '160px',
                overflowY: 'auto',
                boxShadow: '0 8px 24px rgba(0,0,0,0.5)'
              }}
            >
              {fromResults.map((res, i) => (
                <div
                  key={i}
                  onClick={() => handleSelectFrom(res)}
                  style={{
                    padding: '8px 12px',
                    borderBottom: i === fromResults.length - 1 ? 'none' : '1px solid var(--streeva-border-subtle)',
                    cursor: 'pointer',
                    fontSize: '12px',
                    color: 'var(--streeva-text-primary)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap'
                  }}
                >
                  {res.display_name}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* TO Destination Search Input */}
        <div style={{ marginBottom: '16px', position: 'relative' }}>
          <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)', marginBottom: '4px', fontWeight: 600 }}>
            TO (DESTINATION)
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              backgroundColor: 'var(--streeva-bg-deep)',
              border: '1px solid var(--streeva-border-subtle)',
              borderRadius: 'var(--radius-sm)',
              padding: '9px 12px'
            }}
          >
            <Search size={16} color="var(--streeva-intel-cyan)" style={{ flexShrink: 0 }} />
            <input
              type="text"
              value={toQuery}
              onChange={(e) => setToQuery(e.target.value)}
              placeholder="Search destination..."
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--streeva-text-primary)',
                fontSize: '13px',
                width: '100%',
                outline: 'none'
              }}
            />
            {isSearchingTo && <Loader2 size={14} color="var(--streeva-intel-cyan)" className="spin" />}
          </div>

          {/* Autocomplete Dropdown for TO */}
          {toResults.length > 0 && (
            <div
              style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                right: 0,
                zIndex: 30,
                backgroundColor: 'var(--streeva-surface-card)',
                border: '1px solid var(--streeva-border-subtle)',
                borderRadius: 'var(--radius-sm)',
                marginTop: '4px',
                maxHeight: '160px',
                overflowY: 'auto',
                boxShadow: '0 8px 24px rgba(0,0,0,0.5)'
              }}
            >
              {toResults.map((res, i) => (
                <div
                  key={res.place_id || i}
                  onClick={() => handleSelectTo(res)}
                  style={{
                    padding: '8px 12px',
                    borderBottom: i === toResults.length - 1 ? 'none' : '1px solid var(--streeva-border-subtle)',
                    cursor: 'pointer',
                    fontSize: '12px',
                    color: 'var(--streeva-text-primary)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap'
                  }}
                >
                  {res.display_name}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Calculate Safe Route Button */}
        <PrimaryButton
          variant="primary"
          size="md"
          icon={<Navigation size={18} />}
          loading={isCalculating}
          disabled={!toQuery.trim()}
          onClick={handleCalculateRoute}
        >
          Calculate Safe Route
        </PrimaryButton>
      </GlassCard>

      {/* Suggested Live Safe Corridors (OpenStreetMap Geocoded) */}
      <div style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
          <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--streeva-text-secondary)' }}>
            QUICK DESTINATIONS
          </span>
          <Compass size={14} color="var(--streeva-text-muted)" />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {[
            { name: 'Koramangala, Bengaluru', lat: 12.9352, lng: 77.6245 },
            { name: 'Indiranagar, Bengaluru', lat: 12.9784, lng: 77.6408 },
            { name: 'Whitefield, Bengaluru', lat: 12.9698, lng: 77.7500 }
          ].map((place, idx) => (
            <div
              key={idx}
              onClick={() => selectDestination(place)}
              style={{
                backgroundColor: 'var(--streeva-surface-card)',
                border: '1px solid var(--streeva-border-subtle)',
                borderRadius: 'var(--radius-md)',
                padding: '12px 16px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                cursor: 'pointer',
                transition: 'all var(--transition-fast)'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div
                  style={{
                    width: '36px',
                    height: '36px',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: 'rgba(99, 102, 241, 0.1)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}
                >
                  <MapPin size={18} color="var(--streeva-brand-primary)" />
                </div>
                <div>
                  <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--streeva-text-primary)' }}>
                    {place.name}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)' }}>
                    {place.lat.toFixed(4)}, {place.lng.toFixed(4)}
                  </div>
                </div>
              </div>
              <Navigation size={16} color="var(--streeva-intel-cyan)" />
            </div>
          ))}
        </div>
      </div>

      {/* Recent Journeys Card (Section 6) */}
      {completedJourneys.length > 0 && (
        <div style={{ marginBottom: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--streeva-text-secondary)' }}>
              RECENT JOURNEYS
            </span>
            <button
              onClick={() => setAppState('journey_history')}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--streeva-intel-cyan)',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              View All
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {completedJourneys.slice(0, 2).map((j) => (
              <div
                key={j.journey_id}
                onClick={() => setAppState('journey_history')}
                style={{
                  backgroundColor: 'var(--streeva-surface-card)',
                  border: '1px solid var(--streeva-border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  padding: '12px 14px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  cursor: 'pointer'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <History size={16} color="var(--streeva-intel-cyan)" />
                  <div>
                    <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--streeva-text-primary)' }}>
                      {j.destination_name}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)' }}>
                      {j.completed_at} • {(j.distance_m / 1000).toFixed(1)} km
                    </div>
                  </div>
                </div>
                <ArrowRight size={14} color="var(--streeva-text-muted)" />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
