import React from 'react';

interface RouteProgressProps {
  progressPercent: number; // 0 - 100
  distanceRemainingM: number;
  etaSeconds: number;
  sourceName?: string;
  destinationName?: string;
}

export const RouteProgress: React.FC<RouteProgressProps> = ({
  progressPercent = 0,
  distanceRemainingM,
  etaSeconds,
  sourceName = 'Current Location',
  destinationName = 'Destination'
}) => {
  const validProgress = isNaN(progressPercent) ? 0 : progressPercent;
  const clampedProgress = Math.min(Math.max(validProgress, 0), 100);

  const formatDistance = (meters: number) => {
    const validM = Math.max(0, isNaN(meters) ? 0 : meters);
    if (validM >= 1000) {
      return `${(validM / 1000).toFixed(1)} km`;
    }
    return `${Math.round(validM)} m`;
  };

  const formatETA = (seconds: number) => {
    const validSecs = Math.max(0, isNaN(seconds) ? 0 : seconds);
    const mins = Math.round(validSecs / 60);
    if (mins >= 60) {
      const hrs = Math.floor(mins / 60);
      const remMins = mins % 60;
      return `${hrs}h ${remMins}m`;
    }
    return `${mins} min`;
  };

  return (
    <div
      style={{
        width: '100%',
        backgroundColor: 'var(--streeva-surface-card)',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--streeva-border-subtle)',
        padding: '16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px'
      }}
    >
      {/* Metrics Row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <div>
          <span style={{ fontSize: '26px', fontWeight: 800, color: 'var(--streeva-text-primary)' }}>
            {formatETA(etaSeconds)}
          </span>
          <span style={{ fontSize: '13px', color: 'var(--streeva-text-muted)', marginLeft: '6px' }}>
            remaining
          </span>
        </div>
        <div style={{ textAlign: 'right' }}>
          <span style={{ fontSize: '15px', fontWeight: 700, color: 'var(--streeva-intel-cyan)' }}>
            {formatDistance(distanceRemainingM)}
          </span>
          <span style={{ fontSize: '12px', color: 'var(--streeva-text-muted)', marginLeft: '4px' }}>
            ({Math.round(clampedProgress)}%)
          </span>
        </div>
      </div>

      {/* Progress Track Line */}
      <div style={{ position: 'relative', margin: '18px 10px 10px 10px' }}>
        {/* Background track */}
        <div
          style={{
            width: '100%',
            height: '6px',
            backgroundColor: 'rgba(255, 255, 255, 0.08)',
            borderRadius: '3px',
            position: 'relative'
          }}
        >
          {/* Filled active track */}
          <div
            style={{
              width: `${clampedProgress}%`,
              height: '100%',
              background: 'linear-gradient(90deg, #6366F1 0%, #06B6D4 100%)',
              borderRadius: '3px',
              transition: 'width 400ms ease-out',
              boxShadow: '0 0 10px rgba(6, 182, 212, 0.5)'
            }}
          />
        </div>

        {/* Start Point */}
        <span
          style={{
            position: 'absolute',
            left: '0%',
            top: '50%',
            transform: 'translate(-50%, -50%)',
            width: '12px',
            height: '12px',
            borderRadius: '50%',
            backgroundColor: 'var(--streeva-brand-primary)',
            border: '2px solid var(--streeva-bg-midnight)',
            boxShadow: '0 0 8px var(--streeva-brand-primary)'
          }}
        />

        {/* Destination Point */}
        <span
          style={{
            position: 'absolute',
            right: '0%',
            top: '50%',
            transform: 'translate(50%, -50%)',
            width: '12px',
            height: '12px',
            borderRadius: '50%',
            backgroundColor: 'var(--safety-low)',
            border: '2px solid var(--streeva-bg-midnight)',
            boxShadow: '0 0 8px var(--safety-low)'
          }}
        />

        {/* Current Position Pin / Indicator */}
        <div
          style={{
            position: 'absolute',
            left: `${clampedProgress}%`,
            top: '50%',
            transform: 'translate(-50%, -50%)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            transition: 'left 400ms ease-out'
          }}
        >
          <div
            style={{
              width: '16px',
              height: '16px',
              borderRadius: '50%',
              backgroundColor: '#FFFFFF',
              border: '3px solid var(--streeva-intel-cyan)',
              boxShadow: '0 0 12px var(--streeva-intel-cyan)'
            }}
          />
          <span
            style={{
              fontSize: '9px',
              fontWeight: 800,
              color: 'var(--streeva-intel-cyan)',
              position: 'absolute',
              top: '-18px',
              letterSpacing: '0.04em'
            }}
          >
            YOU
          </span>
        </div>
      </div>

      {/* Origin & Destination Labels */}
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--streeva-text-muted)' }}>
        <span style={{ maxWidth: '45%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {sourceName}
        </span>
        <span style={{ maxWidth: '45%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', textAlign: 'right' }}>
          {destinationName}
        </span>
      </div>
    </div>
  );
};
