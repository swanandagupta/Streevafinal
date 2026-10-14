import React, { useState } from 'react';
import { useStreeva } from '../context/StreevaContext';
import { GlassCard } from '../components/GlassCard';
import { PrimaryButton } from '../components/PrimaryButton';
import { GuardianCore } from '../components/GuardianCore';
import {
  CheckCircle2,
  Battery,
  MapPin,
  Wifi,
  Radio,
  Users,
  Route,
  ArrowLeft,
  Navigation
} from 'lucide-react';

export const PreJourneyCheckScreen: React.FC = () => {
  const { setAppState, startJourney, connectivity, contacts, locationState, canonicalRoute } = useStreeva();
  const [isStarting, setIsStarting] = useState(false);

  const accuracyText = locationState.accuracy_m
    ? `±${Math.round(locationState.accuracy_m)}m (Locked)`
    : locationState.status === 'ACQUIRED'
    ? 'High Precision'
    : 'Default Centroid';

  const checks = [
    { label: 'GPS Coordinates', status: accuracyText, icon: <MapPin size={16} /> },
    { label: 'Device Battery', status: 'Sufficient (>20%)', icon: <Battery size={16} /> },
    { label: 'Network Connection', status: connectivity, icon: <Wifi size={16} /> },
    { label: 'Edge Motion Sensors', status: 'Calibrated', icon: <Radio size={16} /> },
    { label: 'Emergency Circle', status: `${contacts.filter((c) => c.active).length} Contacts Active`, icon: <Users size={16} /> },
    {
      label: 'Canonical Safe Route',
      status: canonicalRoute ? `${canonicalRoute.polyline.length} Waypoints Verified` : 'Missing',
      icon: <Route size={16} />
    }
  ];

  const handleStart = async () => {
    setIsStarting(true);
    await startJourney();
  };

  return (
    <div className="streeva-screen-content">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
        <button
          onClick={() => setAppState('journey_setup')}
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
            Pre-Journey Safety Check
          </h2>
          <p style={{ fontSize: '12px', color: 'var(--streeva-text-muted)' }}>
            Verifying Guardian telemetry & route readiness
          </p>
        </div>
      </div>

      {/* Hero Visual */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', margin: '16px 0' }}>
        <GuardianCore riskLevel="LOW" size={140} />
        <div style={{ marginTop: '8px', fontSize: '16px', fontWeight: 700, color: 'var(--safety-low)' }}>
          Guardian is Ready
        </div>
        <div style={{ fontSize: '12px', color: 'var(--streeva-text-muted)', marginTop: '2px' }}>
          Destination: {canonicalRoute?.destination?.name || 'Selected Destination'}
        </div>
      </div>

      {/* Safety Checks Checklist */}
      <GlassCard style={{ padding: '16px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {checks.map((item, idx) => (
            <div
              key={idx}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                paddingBottom: idx === checks.length - 1 ? 0 : '10px',
                borderBottom: idx === checks.length - 1 ? 'none' : '1px solid var(--streeva-border-subtle)'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ color: 'var(--streeva-intel-cyan)' }}>{item.icon}</span>
                <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--streeva-text-primary)' }}>
                  {item.label}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ fontSize: '12px', color: 'var(--streeva-text-muted)' }}>{item.status}</span>
                <CheckCircle2 size={16} color="var(--safety-low)" />
              </div>
            </div>
          ))}
        </div>
      </GlassCard>

      {/* Start Button */}
      <PrimaryButton
        variant="primary"
        size="lg"
        loading={isStarting}
        disabled={!canonicalRoute}
        icon={<Navigation size={18} />}
        onClick={handleStart}
      >
        START JOURNEY
      </PrimaryButton>
    </div>
  );
};
