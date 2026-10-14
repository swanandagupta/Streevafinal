import React, { useState, useEffect } from 'react';
import { useStreeva } from '../context/StreevaContext';
import { GlassCard } from '../components/GlassCard';
import { PrimaryButton } from '../components/PrimaryButton';
import { RealMapContainer } from '../components/RealMapContainer';
import { routingService } from '../services/routingService';
import { CanonicalLocation } from '../types/streeva';
import {
  MapPin,
  ArrowLeft,
  Shield,
  Clock,
  Compass,
  Search,
  Crosshair,
  Loader2,
  AlertCircle,
  CheckCircle,
  ArrowUpDown,
  Navigation
} from 'lucide-react';

export const JourneySetupScreen: React.FC = () => {
  const {
    selectedSource,
    selectedDestination,
    setStartLocation,
    setDestinationLocation,
    useCurrentLocationForStart,
    canonicalRoute,
    routeStatus,
    routeError,
    calculateCanonicalRoute,
    locationState,
    areaSafetyScore,
    setAppState
  } = useStreeva();

  // Search queries & state
  const [fromQuery, setFromQuery] = useState(selectedSource?.display_name || '');
  const [toQuery, setToQuery] = useState(selectedDestination?.display_name || '');

  const [fromResults, setFromResults] = useState<CanonicalLocation[]>([]);
  const [toResults, setToResults] = useState<CanonicalLocation[]>([]);

  const [isSearchingFrom, setIsSearchingFrom] = useState(false);
  const [isSearchingTo, setIsSearchingTo] = useState(false);

  const [gpsLoading, setGpsLoading] = useState(false);
  const [gpsError, setGpsError] = useState<string | null>(null);

  // Sync initial search query strings when context values change
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
    // Don't search if query matches currently selected display name
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
    // Don't search if query matches currently selected display name
    if (selectedDestination && toQuery === selectedDestination.display_name) {
      setToResults([]);
      return;
    }

    const timer = setTimeout(async () => {
      setIsSearchingTo(true);
      const results = await routingService.searchLocations(toQuery);
      setToResults(results);
      setIsSearchingTo(false);
    }, 400);

    return () => clearTimeout(timer);
  }, [toQuery, selectedDestination]);

  // Handle selecting a FROM location
  const handleSelectFrom = (loc: CanonicalLocation) => {
    setStartLocation(loc);
    setFromQuery(loc.display_name);
    setFromResults([]);
    setGpsError(null);
  };

  // Handle selecting a TO destination
  const handleSelectTo = (loc: CanonicalLocation) => {
    setDestinationLocation(loc);
    setToQuery(loc.display_name);
    setToResults([]);
  };

  // Handle "Use Current Location" option for FROM
  const handleUseCurrentLocation = async () => {
    setGpsLoading(true);
    setGpsError(null);
    try {
      await useCurrentLocationForStart();
    } catch (err: any) {
      setGpsError(err.message || 'Could not acquire GPS location');
    } finally {
      setGpsLoading(false);
    }
  };

  // Swap From and To locations
  const handleSwapLocations = () => {
    if (!selectedSource && !selectedDestination) return;
    const oldSource = selectedSource;
    const oldDest = selectedDestination;
    setStartLocation(oldDest);
    setDestinationLocation(oldSource);
  };

  const handleRetry = () => {
    if (selectedSource && selectedDestination) {
      calculateCanonicalRoute(selectedSource, selectedDestination);
    }
  };

  const formatDistance = (meters?: number) => {
    if (!meters) return '--';
    if (meters >= 1000) {
      return `${(meters / 1000).toFixed(1)} km`;
    }
    return `${Math.round(meters)} m`;
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '--';
    const mins = Math.round(seconds / 60);
    if (mins >= 60) {
      const hrs = Math.floor(mins / 60);
      const remMins = mins % 60;
      return `${hrs}h ${remMins}m`;
    }
    return `${mins} min`;
  };

  const isFromGps = selectedSource?.source === 'GPS_CURRENT_LOCATION';

  return (
    <div className="streeva-screen-content">
      {/* Top Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
        <button
          onClick={() => setAppState('home')}
          style={{
            background: 'var(--streeva-surface-card)',
            border: '1px solid var(--streeva-border-subtle)',
            borderRadius: 'var(--radius-sm)',
            width: '36px',
            height: '36px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--streeva-text-primary)',
            cursor: 'pointer'
          }}
        >
          <ArrowLeft size={18} />
        </button>
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: 800, color: 'var(--streeva-text-primary)' }}>
            Plan Protected Journey
          </h2>
          <p style={{ fontSize: '12px', color: 'var(--streeva-text-muted)' }}>
            Independent Start & Destination Selection
          </p>
        </div>
      </div>

      {/* Dual Location Input Card (Section 1 & 2) */}
      <GlassCard style={{ padding: '16px', marginBottom: '16px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', position: 'relative' }}>
          
          {/* FROM FIELD */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--streeva-intel-cyan)', letterSpacing: '0.04em' }}>
                FROM (STARTING POINT)
              </span>
              {/* Use Current Location convenience button */}
              <button
                type="button"
                onClick={handleUseCurrentLocation}
                disabled={gpsLoading}
                style={{
                  background: isFromGps ? 'var(--streeva-brand-glow)' : 'none',
                  border: '1px solid var(--streeva-border-subtle)',
                  borderRadius: 'var(--radius-full)',
                  padding: '3px 8px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: '11px',
                  color: isFromGps ? 'var(--streeva-intel-cyan)' : 'var(--streeva-text-secondary)',
                  cursor: 'pointer'
                }}
              >
                {gpsLoading ? (
                  <Loader2 size={12} className="spin" />
                ) : (
                  <Crosshair size={12} color="var(--streeva-intel-cyan)" />
                )}
                <span>{isFromGps ? 'Using GPS' : 'Use Current Location'}</span>
              </button>
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                backgroundColor: 'var(--streeva-bg-deep)',
                border: '1px solid var(--streeva-border-subtle)',
                borderRadius: 'var(--radius-md)',
                padding: '8px 12px'
              }}
            >
              <div
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: 'var(--streeva-brand-primary)',
                  flexShrink: 0
                }}
              />
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
              {isSearchingFrom && <Loader2 size={14} className="spin" color="var(--streeva-intel-cyan)" />}
            </div>

            {/* GPS Error indicator */}
            {gpsError && (
              <div style={{ fontSize: '11px', color: 'var(--safety-medium)', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <AlertCircle size={12} />
                <span>{gpsError}</span>
              </div>
            )}

            {/* Resolved FROM Subtext */}
            {selectedSource && (
              <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)', marginTop: '4px', paddingLeft: '4px' }}>
                {selectedSource.source === 'GPS_CURRENT_LOCATION' ? (
                  <span style={{ color: 'var(--streeva-intel-cyan)' }}>
                    Using device GPS (±{Math.round(selectedSource.accuracy_m || 5)}m) • {selectedSource.latitude.toFixed(4)}, {selectedSource.longitude.toFixed(4)}
                  </span>
                ) : (
                  <span>Resolved: {selectedSource.latitude.toFixed(4)}, {selectedSource.longitude.toFixed(4)}</span>
                )}
              </div>
            )}

            {/* FROM Search Results Dropdown */}
            {fromResults.length > 0 && (
              <div
                style={{
                  backgroundColor: 'var(--streeva-surface-card)',
                  border: '1px solid var(--streeva-border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  overflow: 'hidden',
                  marginTop: '6px',
                  maxHeight: '160px',
                  overflowY: 'auto',
                  zIndex: 30
                }}
              >
                {fromResults.map((item, idx) => (
                  <div
                    key={idx}
                    onClick={() => handleSelectFrom(item)}
                    style={{
                      padding: '8px 12px',
                      borderBottom: idx === fromResults.length - 1 ? 'none' : '1px solid var(--streeva-border-subtle)',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      fontSize: '12px',
                      color: 'var(--streeva-text-primary)'
                    }}
                  >
                    <MapPin size={13} color="var(--streeva-brand-primary)" style={{ flexShrink: 0 }} />
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {item.display_name}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Swap Button */}
          <div style={{ display: 'flex', justifyContent: 'center', margin: '-4px 0' }}>
            <button
              type="button"
              onClick={handleSwapLocations}
              title="Swap From and To"
              style={{
                background: 'var(--streeva-surface-card)',
                border: '1px solid var(--streeva-border-subtle)',
                borderRadius: '50%',
                width: '28px',
                height: '28px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--streeva-intel-cyan)',
                cursor: 'pointer'
              }}
            >
              <ArrowUpDown size={14} />
            </button>
          </div>

          {/* TO FIELD */}
          <div>
            <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--safety-low)', letterSpacing: '0.04em', display: 'block', marginBottom: '6px' }}>
              TO (DESTINATION)
            </span>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                backgroundColor: 'var(--streeva-bg-deep)',
                border: '1px solid var(--streeva-border-subtle)',
                borderRadius: 'var(--radius-md)',
                padding: '8px 12px'
              }}
            >
              <MapPin size={14} color="var(--safety-low)" style={{ flexShrink: 0 }} />
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
              {isSearchingTo && <Loader2 size={14} className="spin" color="var(--safety-low)" />}
            </div>

            {/* Resolved TO Subtext */}
            {selectedDestination && (
              <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)', marginTop: '4px', paddingLeft: '4px' }}>
                Resolved: {selectedDestination.latitude.toFixed(4)}, {selectedDestination.longitude.toFixed(4)}
              </div>
            )}

            {/* TO Search Results Dropdown */}
            {toResults.length > 0 && (
              <div
                style={{
                  backgroundColor: 'var(--streeva-surface-card)',
                  border: '1px solid var(--streeva-border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  overflow: 'hidden',
                  marginTop: '6px',
                  maxHeight: '160px',
                  overflowY: 'auto',
                  zIndex: 30
                }}
              >
                {toResults.map((item, idx) => (
                  <div
                    key={idx}
                    onClick={() => handleSelectTo(item)}
                    style={{
                      padding: '8px 12px',
                      borderBottom: idx === toResults.length - 1 ? 'none' : '1px solid var(--streeva-border-subtle)',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      fontSize: '12px',
                      color: 'var(--streeva-text-primary)'
                    }}
                  >
                    <MapPin size={13} color="var(--safety-low)" style={{ flexShrink: 0 }} />
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {item.display_name}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </GlassCard>

      {/* Real Map Presentation (Section 5, 8, 14, 18, 19) */}
      <div style={{ marginBottom: '16px' }}>
        <RealMapContainer
          sourceLocation={
            selectedSource
              ? { lat: selectedSource.latitude, lng: selectedSource.longitude }
              : canonicalRoute?.source || null
          }
          destinationLocation={
            selectedDestination
              ? { lat: selectedDestination.latitude, lng: selectedDestination.longitude }
              : canonicalRoute?.destination || null
          }
          routePolyline={canonicalRoute?.polyline || []}
          isLoading={routeStatus === 'CALCULATING'}
          error={routeError}
          onRetry={handleRetry}
          height="250px"
        />
      </div>

      {/* Real Calculated Route Metrics Card (Section 5) */}
      {canonicalRoute && routeStatus === 'READY' && (
        <div style={{ marginBottom: '16px' }}>
          <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--streeva-text-secondary)', marginBottom: '8px' }}>
            ROUTE TELEMETRY (CANONICAL OSRM)
          </div>

          <GlassCard borderGlow="brand" style={{ padding: '14px 16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Compass size={18} color="var(--streeva-intel-cyan)" />
                <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--streeva-text-primary)' }}>
                  {canonicalRoute.is_demo ? 'Geodesic Safe Corridor' : 'Road Network Corridor'}
                </span>
              </div>
              <span style={{ fontSize: '11px', color: 'var(--streeva-intel-cyan)', fontWeight: 700 }}>
                {canonicalRoute.polyline.length} Waypoints
              </span>
            </div>

            <div style={{ display: 'flex', gap: '16px', marginTop: '10px', fontSize: '13px', color: 'var(--streeva-text-muted)' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Clock size={14} color="var(--streeva-intel-cyan)" />
                <strong style={{ color: 'var(--streeva-text-primary)' }}>
                  {formatDuration(canonicalRoute.duration_s)}
                </strong>
              </span>
              <span>•</span>
              <span>
                <strong style={{ color: 'var(--streeva-text-primary)' }}>
                  {formatDistance(canonicalRoute.distance_m)}
                </strong>
              </span>
              <span>•</span>
              <span style={{ color: 'var(--safety-low)' }}>
                OpenStreetMap
              </span>
            </div>
          </GlassCard>
        </div>
      )}

      {/* Geographic Coverage & Safety Data Audit Card (Sections 5, 6, 7, 8, 22) */}
      {canonicalRoute && routeStatus === 'READY' && (() => {
        // Sample up to 20 coordinates along canonical route polyline
        const poly = canonicalRoute.polyline;
        const numSamples = Math.min(poly.length, 20);
        let inBoundsCount = 0;
        if (numSamples > 0) {
          const step = poly.length / numSamples;
          for (let i = 0; i < numSamples; i++) {
            const pt = poly[Math.min(Math.floor(i * step), poly.length - 1)];
            // Precomputed H3 index bounds: Chennai Metropolitan Area
            if (pt.lat >= 12.74 && pt.lat <= 13.23 && pt.lng >= 80.00 && pt.lng <= 80.33) {
              inBoundsCount++;
            }
          }
        }
        const safetyCoveragePercent = Math.round((inBoundsCount / Math.max(numSamples, 1)) * 100);
        const isFullCoverage = safetyCoveragePercent >= 90;
        const isPartialCoverage = safetyCoveragePercent > 0 && safetyCoveragePercent < 90;

        return (
          <GlassCard
            borderGlow={isFullCoverage ? 'low' : isPartialCoverage ? 'medium' : 'brand'}
            style={{ padding: '16px', marginBottom: '20px' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Shield size={18} color={isFullCoverage ? 'var(--safety-low)' : isPartialCoverage ? 'var(--safety-medium)' : 'var(--streeva-intel-cyan)'} />
                <span style={{ fontSize: '13px', fontWeight: 800, color: 'var(--streeva-text-primary)' }}>
                  SAFETY DATA COVERAGE AUDIT
                </span>
              </div>
              <span
                style={{
                  fontSize: '10px',
                  fontWeight: 800,
                  padding: '3px 8px',
                  borderRadius: 'var(--radius-full)',
                  backgroundColor: isFullCoverage ? 'var(--safety-low-surface)' : isPartialCoverage ? 'var(--safety-medium-surface)' : 'rgba(139, 92, 246, 0.15)',
                  color: isFullCoverage ? 'var(--safety-low)' : isPartialCoverage ? 'var(--safety-medium)' : '#A78BFA',
                  border: `1px solid ${isFullCoverage ? 'var(--safety-low-border)' : isPartialCoverage ? 'var(--safety-medium-border)' : 'rgba(139, 92, 246, 0.3)'}`
                }}
              >
                {isFullCoverage ? 'FULL COVERAGE' : isPartialCoverage ? 'PARTIAL COVERAGE' : 'LIMITED / DEGRADED'}
              </span>
            </div>

            {/* Route Coverage Bar */}
            <div style={{ marginBottom: '10px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '4px' }}>
                <span style={{ color: 'var(--streeva-text-secondary)' }}>Route Corridor (OSRM Road Network)</span>
                <span style={{ color: 'var(--safety-low)', fontWeight: 700 }}>100% Routable</span>
              </div>
              <div style={{ width: '100%', height: '6px', backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: '3px', overflow: 'hidden' }}>
                <div style={{ width: '100%', height: '100%', backgroundColor: 'var(--safety-low)', borderRadius: '3px' }} />
              </div>
            </div>

            {/* Safety Intelligence Coverage Bar */}
            <div style={{ marginBottom: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '4px' }}>
                <span style={{ color: 'var(--streeva-text-secondary)' }}>Spatial Risk Data (H3 & Crime Dataset)</span>
                <span style={{ color: isFullCoverage ? 'var(--safety-low)' : isPartialCoverage ? 'var(--safety-medium)' : '#A78BFA', fontWeight: 700 }}>
                  {safetyCoveragePercent}% Covered
                </span>
              </div>
              <div style={{ width: '100%', height: '6px', backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: '3px', overflow: 'hidden' }}>
                <div
                  style={{
                    width: `${safetyCoveragePercent}%`,
                    height: '100%',
                    backgroundColor: isFullCoverage ? 'var(--safety-low)' : isPartialCoverage ? 'var(--safety-medium)' : '#A78BFA',
                    borderRadius: '3px'
                  }}
                />
              </div>
            </div>

            {/* Honest Architectural Context */}
            <p style={{ fontSize: '11px', color: 'var(--streeva-text-muted)', lineHeight: 1.4 }}>
              {isFullCoverage
                ? 'Hyperlocal H3 risk index, emergency services, and NCRB crime baselines are fully available along this corridor.'
                : isPartialCoverage
                ? `Route extends beyond regional Chennai H3 dataset. Only ${safetyCoveragePercent}% of corridor has precomputed spatial crime priors; remaining distance protected via live edge inertial sensors and cross-track deviation.`
                : 'Destination lies outside the local Chennai H3 crime feature dataset. STREEVA will route successfully and actively monitor GPS cross-track deviation, unexpected stops, and motion anomalies, but spatial crime priors are unavailable (UNKNOWN ≠ LOW).'}
            </p>
          </GlassCard>
        );
      })()}

      {/* Proceed to Pre-Journey Check */}
      <PrimaryButton
        variant="primary"
        size="lg"
        disabled={!canonicalRoute || routeStatus !== 'READY'}
        icon={<Shield size={18} />}
        onClick={() => setAppState('pre_journey_check')}
      >
        Proceed to Safety Check
      </PrimaryButton>
    </div>
  );
};
