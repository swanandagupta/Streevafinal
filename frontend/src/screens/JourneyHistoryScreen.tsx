import React from 'react';
import { useStreeva } from '../context/StreevaContext';
import { GlassCard } from '../components/GlassCard';
import { PrimaryButton } from '../components/PrimaryButton';
import {
  MapPin,
  Clock,
  ShieldCheck,
  ArrowRight,
  Navigation,
  CheckCircle2,
  Activity,
  AlertTriangle,
  Play
} from 'lucide-react';

export const JourneyHistoryScreen: React.FC = () => {
  const {
    activeJourneyId,
    canonicalRoute,
    snapshot,
    completedJourneys,
    setAppState
  } = useStreeva();

  const formatDuration = (sec: number) => {
    const mins = Math.round(sec / 60);
    return mins > 60 ? `${Math.floor(mins / 60)}h ${mins % 60}m` : `${mins} min`;
  };

  const formatDistance = (m: number) => {
    return `${(m / 1000).toFixed(1)} km`;
  };

  return (
    <div className="streeva-screen-content" style={{ paddingBottom: '100px' }}>
      {/* Header */}
      <div style={{ marginBottom: '16px' }}>
        <h2 style={{ fontSize: '20px', fontWeight: 800, color: 'var(--streeva-text-primary)' }}>
          Journeys
        </h2>
        <p style={{ fontSize: '12px', color: 'var(--streeva-text-muted)' }}>
          Monitored travel corridors, active tracking & arrival audit
        </p>
      </div>

      {/* Active Journey Banner (if one is currently running) */}
      {activeJourneyId && (
        <GlassCard
          borderGlow="low"
          style={{
            padding: '16px',
            marginBottom: '20px',
            backgroundColor: 'rgba(16, 185, 129, 0.08)',
            border: '1px solid var(--safety-low-border)'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: 'var(--safety-low)',
                  boxShadow: '0 0 8px var(--safety-low)'
                }}
              />
              <span style={{ fontSize: '12px', fontWeight: 800, color: 'var(--safety-low)', letterSpacing: '0.04em' }}>
                ACTIVE JOURNEY IN PROGRESS
              </span>
            </div>
            <span style={{ fontSize: '11px', color: 'var(--streeva-text-muted)' }}>
              {snapshot?.progress_percent || 0}% Complete
            </span>
          </div>

          <div style={{ marginBottom: '12px' }}>
            <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--streeva-text-primary)' }}>
              {canonicalRoute?.destination?.name || 'Selected Destination'}
            </div>
            <div style={{ fontSize: '12px', color: 'var(--streeva-text-secondary)', marginTop: '2px' }}>
              From: {canonicalRoute?.source?.name || 'Starting Point'}
            </div>
          </div>

          <PrimaryButton
            variant="primary"
            size="sm"
            icon={<Play size={14} />}
            onClick={() => setAppState('active_journey')}
          >
            Resume Active Journey
          </PrimaryButton>
        </GlassCard>
      )}

      {/* Section Title */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--streeva-text-secondary)', letterSpacing: '0.04em' }}>
          JOURNEY HISTORY ({completedJourneys.length})
        </span>
        <span style={{ fontSize: '11px', color: 'var(--safety-low)', fontWeight: 600 }}>
        </span>
      </div>

      {/* Dynamic Completed Journeys List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {completedJourneys.map((item) => (
          <GlassCard
            key={item.journey_id}
            onClick={() => setAppState('journey_summary')}
            style={{ padding: '16px', cursor: 'pointer', transition: 'all var(--transition-fast)' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div
                  style={{
                    width: '36px',
                    height: '36px',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: 'var(--safety-low-surface)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}
                >
                  <Navigation size={18} color="var(--safety-low)" />
                </div>
                <div>
                  <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--streeva-text-primary)' }}>
                    {item.destination_name}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)', marginTop: '2px' }}>
                    {item.completed_at} • From {item.source_name}
                  </div>
                </div>
              </div>

              <span
                style={{
                  fontSize: '10px',
                  fontWeight: 800,
                  color: 'var(--safety-low)',
                  backgroundColor: 'var(--safety-low-surface)',
                  padding: '3px 8px',
                  borderRadius: 'var(--radius-full)'
                }}
              >
                {item.end_reason === 'USER_CANCELLED' ? 'ENDED' : 'SAFE ARRIVAL'}
              </span>
            </div>

            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginTop: '12px',
                paddingTop: '10px',
                borderTop: '1px solid var(--streeva-border-subtle)',
                fontSize: '12px',
                color: 'var(--streeva-text-secondary)'
              }}
            >
              <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                <span>{formatDuration(item.duration_s)}</span>
                <span>•</span>
                <span>{formatDistance(item.distance_m)}</span>
                <span>•</span>
                <span style={{ color: item.adherence_percent != null ? 'var(--safety-low)' : 'var(--streeva-text-muted)' }}>
                  {item.adherence_percent != null ? `${item.adherence_percent.toFixed(1)}% Adherence` : '— (Not enough data)'}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--streeva-intel-cyan)' }}>
                <span style={{ fontSize: '11px', fontWeight: 600 }}>Summary</span>
                <ArrowRight size={14} />
              </div>
            </div>
          </GlassCard>
        ))}
      </div>
    </div>
  );
};
