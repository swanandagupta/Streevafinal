import React from 'react';
import { useStreeva } from '../context/StreevaContext';
import { GlassCard } from '../components/GlassCard';
import { PrimaryButton } from '../components/PrimaryButton';
import { CheckCircle2, ShieldCheck, Clock, MapPin, Award, ArrowRight } from 'lucide-react';

export const JourneySummaryScreen: React.FC = () => {
  const { lastCompletedSummary, returnHomeFromSummary } = useStreeva();

  const formatDistance = (meters?: number) => {
    if (!meters) return '0 m';
    if (meters >= 1000) {
      return `${(meters / 1000).toFixed(1)} km`;
    }
    return `${Math.round(meters)} m`;
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds || seconds <= 0) return '0s';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const mins = Math.round(seconds / 60);
    if (mins >= 60) {
      const hrs = Math.floor(mins / 60);
      const remMins = mins % 60;
      return `${hrs}h ${remMins}m`;
    }
    return `${mins} min`;
  };

  const isCancelled = lastCompletedSummary?.end_reason === 'USER_CANCELLED';
  const sourceName = lastCompletedSummary?.source_name || 'Origin';
  const destinationName = lastCompletedSummary?.destination_name || 'Destination';
  const hasAdherence = lastCompletedSummary?.adherence_percent !== null && lastCompletedSummary?.adherence_percent !== undefined;
  const adherenceDisplay = hasAdherence ? `${lastCompletedSummary!.adherence_percent!.toFixed(1)}%` : '—';

  return (
    <div className="streeva-screen-content">
      {/* Top Visual */}
      <div style={{ textAlign: 'center', margin: '20px 0' }}>
        <div
          style={{
            width: '72px',
            height: '72px',
            borderRadius: '50%',
            backgroundColor: isCancelled ? 'var(--safety-medium-surface)' : 'var(--safety-low-surface)',
            border: `2px solid ${isCancelled ? 'var(--safety-medium)' : 'var(--safety-low)'}`,
            boxShadow: `0 0 25px ${isCancelled ? 'var(--safety-medium-glow)' : 'var(--safety-low-glow)'}`,
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: '16px'
          }}
        >
          <CheckCircle2 size={36} color={isCancelled ? 'var(--safety-medium)' : 'var(--safety-low)'} />
        </div>
        <h1 style={{ fontSize: '24px', fontWeight: 800, color: 'var(--streeva-text-primary)' }}>
          {isCancelled ? 'Journey Ended' : 'Journey Complete'}
        </h1>
        <p style={{ fontSize: '13px', color: isCancelled ? 'var(--safety-medium)' : 'var(--safety-low)', fontWeight: 600, marginTop: '4px' }}>
          {isCancelled ? 'Journey concluded per traveler request.' : 'You arrived safely at your destination.'}
        </p>
      </div>

      {/* Primary Metrics Grid (Populated dynamically from finalized journey) */}
      <GlassCard style={{ padding: '16px', marginBottom: '16px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', textAlign: 'center' }}>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)', textTransform: 'uppercase' }}>Duration</div>
            <div style={{ fontSize: '18px', fontWeight: 800, color: 'var(--streeva-text-primary)', marginTop: '4px' }}>
              {formatDuration(lastCompletedSummary?.duration_s)}
            </div>
          </div>
          <div style={{ borderLeft: '1px solid var(--streeva-border-subtle)', borderRight: '1px solid var(--streeva-border-subtle)' }}>
            <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)', textTransform: 'uppercase' }}>Distance</div>
            <div style={{ fontSize: '18px', fontWeight: 800, color: 'var(--streeva-intel-cyan)', marginTop: '4px' }}>
              {formatDistance(lastCompletedSummary?.distance_m)}
            </div>
          </div>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)', textTransform: 'uppercase' }}>Adherence</div>
            <div style={{ fontSize: '18px', fontWeight: 800, color: hasAdherence ? 'var(--safety-low)' : 'var(--streeva-text-muted)', marginTop: '4px' }}>
              {adherenceDisplay}
            </div>
            {!hasAdherence && (
              <div style={{ fontSize: '9px', color: 'var(--streeva-text-muted)', marginTop: '2px', letterSpacing: '-0.2px' }}>
                Not enough data
              </div>
            )}
          </div>
        </div>
      </GlassCard>

      {/* Safety Timeline (Real endpoints) */}
      <GlassCard style={{ padding: '16px', marginBottom: '24px' }}>
        <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--streeva-text-secondary)', marginBottom: '12px' }}>
          GUARDIAN AUDIT SUMMARY
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--streeva-brand-primary)', marginTop: '5px' }} />
            <div>
              <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--streeva-text-primary)' }}>Departed Origin</div>
              <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)' }}>{sourceName} • Guardian monitoring active</div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: hasAdherence ? 'var(--safety-low)' : 'var(--streeva-text-muted)', marginTop: '5px' }} />
            <div>
              <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--streeva-text-primary)' }}>Route Corridor Adherence</div>
              <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)' }}>
                {hasAdherence 
                  ? `${lastCompletedSummary!.adherence_percent!.toFixed(1)}% conformance with planned corridor`
                  : 'Insufficient valid movement observations to evaluate corridor adherence'}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: isCancelled ? 'var(--safety-medium)' : 'var(--safety-low)', marginTop: '5px' }} />
            <div>
              <div style={{ fontSize: '13px', fontWeight: 600, color: isCancelled ? 'var(--safety-medium)' : 'var(--safety-low)' }}>
                {isCancelled ? 'Journey Ended' : 'Arrived at Destination'}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)' }}>
                {destinationName} • Completed at {lastCompletedSummary?.completed_at || 'Just now'}
              </div>
            </div>
          </div>
        </div>
      </GlassCard>

      {/* Return to Home CTA (Section 10 & 12: Completely clears active journey context and returns Home) */}
      <PrimaryButton variant="primary" size="lg" onClick={returnHomeFromSummary}>
        Return to Home
      </PrimaryButton>
    </div>
  );
};
