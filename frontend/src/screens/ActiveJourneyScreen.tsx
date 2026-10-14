import React, { useState } from 'react';
import { useStreeva } from '../context/StreevaContext';
import { RealMapContainer } from '../components/RealMapContainer';
import { RouteProgress } from '../components/RouteProgress';
import { RiskBadge } from '../components/RiskBadge';
import { GlassCard } from '../components/GlassCard';
import {
  Shield,
  Radio,
  AlertTriangle,
  CheckCircle,
  Share2,
  WifiOff,
  RefreshCw,
  Sliders,
  AlertCircle
} from 'lucide-react';

export const ActiveJourneyScreen: React.FC = () => {
  const {
    snapshot,
    canonicalRoute,
    riskLevel,
    riskScore,
    sensorPolicy,
    connectivity,
    endJourney,
    isEndingJourney,
    endJourneyError,
    simulateRouteDeviation,
    simulateUnexpectedStop,
    clearAnomalies,
    triggerAutonomousEmergency,
    setConnectivity,
    reconcileOffline
  } = useStreeva();

  const [showDevControls, setShowDevControls] = useState(false);

  const deviationState = snapshot?.route_deviation_state || 'NORMAL';
  const stopState = snapshot?.unexpected_stop_state || 'MOVING';

  const isOffline = connectivity === 'OFFLINE';
  const isReconnecting = connectivity === 'RECONNECTING';

  const getPolicyIntensity = () => {
    if (!sensorPolicy) return 'Normal';
    switch (sensorPolicy.profile) {
      case 'LOW_POWER':
        return 'Conserving';
      case 'BALANCED':
        return 'Normal';
      case 'ELEVATED':
        return 'Active Vigilance';
      case 'CRITICAL_MAX':
        return 'Intensive';
      default:
        return 'Normal';
    }
  };

  const sourceName = canonicalRoute?.source?.name || 'Starting Point';
  const destName = canonicalRoute?.destination?.name || 'Destination';

  return (
    <div className="streeva-screen-content" style={{ paddingBottom: '100px' }}>
      {/* Offline / Reconnecting Status Banner */}
      {isOffline && (
        <div
          style={{
            backgroundColor: 'var(--safety-medium-surface)',
            border: '1px solid var(--safety-medium-border)',
            borderRadius: 'var(--radius-sm)',
            padding: '10px 14px',
            marginBottom: '12px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <WifiOff size={16} color="var(--safety-medium)" />
            <div style={{ fontSize: '12px', color: 'var(--streeva-text-primary)' }}>
              <strong>Offline Guardian Active</strong> — Local monitoring enabled
            </div>
          </div>
          <button
            onClick={() => reconcileOffline()}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--streeva-intel-cyan)',
              fontSize: '11px',
              fontWeight: 700,
              cursor: 'pointer'
            }}
          >
            Recheck
          </button>
        </div>
      )}

      {isReconnecting && (
        <div
          style={{
            backgroundColor: 'var(--streeva-surface-elevated)',
            border: '1px solid var(--streeva-intel-cyan)',
            borderRadius: 'var(--radius-sm)',
            padding: '10px 14px',
            marginBottom: '12px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            color: 'var(--streeva-intel-cyan)'
          }}
        >
          <RefreshCw size={16} className="spin" />
          <div style={{ fontSize: '12px', fontWeight: 600 }}>
            RECONNECTING... Synchronizing journey telemetry
          </div>
        </div>
      )}

      {/* Top HUD Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div
            style={{
              width: '10px',
              height: '10px',
              borderRadius: '50%',
              backgroundColor: 'var(--safety-low)',
              boxShadow: '0 0 8px var(--safety-low)'
            }}
          />
          <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--streeva-text-primary)', letterSpacing: '0.04em' }}>
            GUARDIAN ACTIVE
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <RiskBadge level={riskLevel} size="sm" showScore={riskScore} />
          <button
            onClick={() => setShowDevControls(!showDevControls)}
            style={{
              background: 'var(--streeva-surface-card)',
              border: '1px solid var(--streeva-border-subtle)',
              borderRadius: 'var(--radius-sm)',
              padding: '5px 8px',
              color: 'var(--streeva-text-muted)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center'
            }}
            title="Toggle Demo Controls"
          >
            <Sliders size={14} />
          </button>
        </div>
      </div>

      {/* Primary Real Map View (Leaflet OpenStreetMap) */}
      <div style={{ marginBottom: '14px' }}>
        <RealMapContainer
          sourceLocation={canonicalRoute?.source}
          destinationLocation={canonicalRoute?.destination}
          routePolyline={canonicalRoute?.polyline || []}
          currentPosition={snapshot?.current_location || canonicalRoute?.source || null}
          deviationState={deviationState}
          riskLevel={riskLevel}
          height="240px"
        />
      </div>

      {/* Route Progress HUD (ETA + Distance + Track) */}
      <div style={{ marginBottom: '14px' }}>
        <RouteProgress
          progressPercent={snapshot?.progress_percent || 0}
          distanceRemainingM={snapshot?.distance_remaining_m || canonicalRoute?.distance_m || 0}
          etaSeconds={snapshot?.estimated_eta_seconds || canonicalRoute?.duration_s || 0}
          sourceName={sourceName}
          destinationName={destName}
        />
      </div>

      {/* Anomaly Alerts (Route Deviation / Unexpected Stop) */}
      {deviationState === 'CONFIRMED_DEVIATION' && (
        <GlassCard borderGlow="high" style={{ padding: '14px', marginBottom: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
            <AlertTriangle size={20} color="var(--safety-high)" />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--safety-high)' }}>
                ROUTE DEVIATION DETECTED
              </div>
              <p style={{ fontSize: '12px', color: 'var(--streeva-text-secondary)', marginTop: '2px' }}>
                You are currently outside your planned safe corridor.
              </p>
              <div style={{ display: 'flex', gap: '8px', marginTop: '10px' }}>
                <button
                  onClick={clearAnomalies}
                  style={{
                    backgroundColor: 'var(--streeva-surface-card)',
                    border: '1px solid var(--streeva-border-subtle)',
                    color: 'var(--streeva-text-primary)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '6px 12px',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer'
                  }}
                >
                  I'm going somewhere else
                </button>
                <button
                  onClick={clearAnomalies}
                  style={{
                    backgroundColor: 'var(--safety-low-surface)',
                    border: '1px solid var(--safety-low-border)',
                    color: 'var(--safety-low)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '6px 12px',
                    fontSize: '12px',
                    fontWeight: 700,
                    cursor: 'pointer'
                  }}
                >
                  Returning to route
                </button>
              </div>
            </div>
          </div>
        </GlassCard>
      )}

      {stopState === 'CONFIRMED_STOP' && (
        <GlassCard borderGlow="medium" style={{ padding: '14px', marginBottom: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
            <Radio size={20} color="var(--safety-medium)" />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--safety-medium)' }}>
                UNEXPECTED STOP
              </div>
              <p style={{ fontSize: '12px', color: 'var(--streeva-text-secondary)', marginTop: '2px' }}>
                Movement stationary away from expected stops.
              </p>
              <div style={{ marginTop: '10px' }}>
                <button
                  onClick={clearAnomalies}
                  style={{
                    backgroundColor: 'var(--safety-low-surface)',
                    border: '1px solid var(--safety-low-border)',
                    color: 'var(--safety-low)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '6px 14px',
                    fontSize: '12px',
                    fontWeight: 700,
                    cursor: 'pointer'
                  }}
                >
                  I'm Okay
                </button>
              </div>
            </div>
          </div>
        </GlassCard>
      )}

      {/* Adaptive Monitoring Intensity Card */}
      <GlassCard style={{ padding: '14px', marginBottom: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Shield size={16} color="var(--streeva-intel-cyan)" />
            <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--streeva-text-primary)' }}>
              Guardian Monitoring
            </span>
          </div>
          <span
            style={{
              fontSize: '12px',
              fontWeight: 700,
              color: riskLevel === 'HIGH' ? 'var(--safety-high)' : 'var(--streeva-intel-cyan)'
            }}
          >
            {getPolicyIntensity()}
          </span>
        </div>

        {/* Intensity Meter */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '10px' }}>
          <div
            style={{
              flex: 1,
              height: '4px',
              borderRadius: '2px',
              backgroundColor: 'var(--safety-low)',
              boxShadow: '0 0 6px var(--safety-low)'
            }}
          />
          <div
            style={{
              flex: 1,
              height: '4px',
              borderRadius: '2px',
              backgroundColor:
                riskLevel === 'MEDIUM' || riskLevel === 'HIGH' ? 'var(--safety-medium)' : 'rgba(255,255,255,0.1)',
              boxShadow: riskLevel === 'MEDIUM' || riskLevel === 'HIGH' ? '0 0 6px var(--safety-medium)' : 'none'
            }}
          />
          <div
            style={{
              flex: 1,
              height: '4px',
              borderRadius: '2px',
              backgroundColor: riskLevel === 'HIGH' ? 'var(--safety-high)' : 'rgba(255,255,255,0.1)',
              boxShadow: riskLevel === 'HIGH' ? '0 0 6px var(--safety-high)' : 'none'
            }}
          />
        </div>

        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: '10px',
            color: 'var(--streeva-text-muted)',
            marginTop: '4px'
          }}
        >
          <span>Normal</span>
          <span>Active</span>
          <span>Intensive</span>
        </div>
      </GlassCard>

      {/* Failure State Notice (Section 13: "Couldn't end the journey" with "Retry") */}
      {endJourneyError && (
        <GlassCard borderGlow="critical" style={{ padding: '12px 14px', marginBottom: '14px', backgroundColor: 'var(--safety-critical-surface)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <AlertTriangle size={18} color="var(--safety-critical)" />
              <div>
                <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--safety-critical)' }}>
                  Couldn't end the journey
                </div>
                <div style={{ fontSize: '11px', color: 'var(--streeva-text-secondary)' }}>
                  {endJourneyError}
                </div>
              </div>
            </div>
            <button
              onClick={() => endJourney('ARRIVED_SAFELY')}
              style={{
                backgroundColor: 'var(--streeva-surface-card)',
                border: '1px solid var(--safety-critical-border)',
                borderRadius: 'var(--radius-sm)',
                padding: '6px 12px',
                color: 'var(--streeva-text-primary)',
                fontSize: '12px',
                fontWeight: 700,
                cursor: 'pointer'
              }}
            >
              Retry
            </button>
          </div>
        </GlassCard>
      )}

      {/* Journey Actions Row (Section 10: User selects End Journey or Arrived Safely) */}
      <div style={{ display: 'flex', gap: '10px', marginBottom: '20px' }}>
        <button
          onClick={() => endJourney('USER_CANCELLED')}
          disabled={isEndingJourney}
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            backgroundColor: 'var(--streeva-surface-card)',
            border: '1px solid var(--streeva-border-subtle)',
            borderRadius: 'var(--radius-md)',
            padding: '12px',
            color: 'var(--streeva-text-secondary)',
            fontSize: '13px',
            fontWeight: 600,
            cursor: 'pointer'
          }}
        >
          {isEndingJourney ? (
            <RefreshCw size={16} className="spin" />
          ) : (
            <AlertCircle size={16} color="var(--streeva-text-muted)" />
          )}
          <span>End Journey</span>
        </button>

        <button
          onClick={() => endJourney('ARRIVED_SAFELY')}
          disabled={isEndingJourney}
          style={{
            flex: 1.2,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            backgroundColor: 'var(--streeva-surface-card)',
            border: '1px solid var(--safety-low-border)',
            borderRadius: 'var(--radius-md)',
            padding: '12px',
            color: 'var(--safety-low)',
            fontSize: '13px',
            fontWeight: 700,
            cursor: 'pointer'
          }}
        >
          {isEndingJourney ? (
            <RefreshCw size={16} className="spin" />
          ) : (
            <CheckCircle size={16} />
          )}
          <span>Arrived Safely</span>
        </button>
      </div>

      {/* Interactive Reviewer / Demonstration Controls Drawer */}
      {showDevControls && (
        <GlassCard borderGlow="brand" style={{ padding: '14px', marginBottom: '16px' }}>
          <div
            style={{
              fontSize: '12px',
              fontWeight: 800,
              color: 'var(--streeva-brand-primary)',
              marginBottom: '8px',
              letterSpacing: '0.04em'
            }}
          >
            DEMO SCENARIO INJECTOR (PHASE 1-5 AUDIT)
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px' }}>
            <button
              onClick={simulateRouteDeviation}
              style={{
                padding: '8px',
                fontSize: '11px',
                fontWeight: 600,
                borderRadius: '6px',
                border: '1px solid var(--safety-high-border)',
                background: 'var(--safety-high-surface)',
                color: 'var(--safety-high)',
                cursor: 'pointer'
              }}
            >
              Simulate Deviation
            </button>
            <button
              onClick={simulateUnexpectedStop}
              style={{
                padding: '8px',
                fontSize: '11px',
                fontWeight: 600,
                borderRadius: '6px',
                border: '1px solid var(--safety-medium-border)',
                background: 'var(--safety-medium-surface)',
                color: 'var(--safety-medium)',
                cursor: 'pointer'
              }}
            >
              Simulate Stop
            </button>
            <button
              onClick={() => setConnectivity(isOffline ? 'ONLINE' : 'OFFLINE')}
              style={{
                padding: '8px',
                fontSize: '11px',
                fontWeight: 600,
                borderRadius: '6px',
                border: '1px solid var(--streeva-border-subtle)',
                background: 'var(--streeva-bg-deep)',
                color: 'var(--streeva-text-secondary)',
                cursor: 'pointer'
              }}
            >
              Toggle Offline Mode
            </button>
            <button
              onClick={triggerAutonomousEmergency}
              style={{
                padding: '8px',
                fontSize: '11px',
                fontWeight: 700,
                borderRadius: '6px',
                border: '1px solid var(--safety-critical-border)',
                background: 'var(--safety-critical-surface)',
                color: 'var(--safety-critical)',
                cursor: 'pointer'
              }}
            >
              Trigger Auto SOS
            </button>
          </div>
        </GlassCard>
      )}
    </div>
  );
};
