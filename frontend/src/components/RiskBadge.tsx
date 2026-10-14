import React from 'react';
import { RiskLevel } from '../types/streeva';

interface RiskBadgeProps {
  level: RiskLevel;
  size?: 'sm' | 'md' | 'lg';
  showScore?: number;
}

export const RiskBadge: React.FC<RiskBadgeProps> = ({ level, size = 'md', showScore }) => {
  const getConfig = (lvl: RiskLevel) => {
    switch (lvl) {
      case 'LOW':
        return {
          label: 'LOW RISK',
          color: 'var(--safety-low)',
          bg: 'var(--safety-low-surface)',
          border: 'var(--safety-low-border)',
          dotGlow: '0 0 8px var(--safety-low)'
        };
      case 'MEDIUM':
        return {
          label: 'MEDIUM RISK',
          color: 'var(--safety-medium)',
          bg: 'var(--safety-medium-surface)',
          border: 'var(--safety-medium-border)',
          dotGlow: '0 0 8px var(--safety-medium)'
        };
      case 'HIGH':
        return {
          label: 'HIGH RISK',
          color: 'var(--safety-high)',
          bg: 'var(--safety-high-surface)',
          border: 'var(--safety-high-border)',
          dotGlow: '0 0 10px var(--safety-high)'
        };
      case 'CRITICAL':
        return {
          label: 'CRITICAL',
          color: 'var(--safety-critical)',
          bg: 'var(--safety-critical-surface)',
          border: 'var(--safety-critical-border)',
          dotGlow: '0 0 12px var(--safety-critical)'
        };
      case 'UNKNOWN':
        return {
          label: 'UNKNOWN STATUS',
          color: 'var(--safety-unknown)',
          bg: 'var(--safety-unknown-surface)',
          border: 'var(--safety-unknown-border)',
          dotGlow: '0 0 8px var(--safety-unknown)'
        };
      case 'DEGRADED':
        return {
          label: 'DEGRADED TELEMETRY',
          color: 'var(--safety-degraded)',
          bg: 'var(--safety-degraded-surface)',
          border: 'var(--safety-degraded-border)',
          dotGlow: 'none'
        };
      default:
        return {
          label: 'UNKNOWN',
          color: 'var(--streeva-text-muted)',
          bg: 'var(--streeva-surface-card)',
          border: 'var(--streeva-border-subtle)',
          dotGlow: 'none'
        };
    }
  };

  const config = getConfig(level);
  const sizeStyles = {
    sm: { fontSize: '11px', padding: '3px 8px', dotSize: '6px' },
    md: { fontSize: '12px', padding: '5px 12px', dotSize: '8px' },
    lg: { fontSize: '14px', padding: '7px 16px', dotSize: '10px' }
  }[size];

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        backgroundColor: config.bg,
        border: `1px solid ${config.border}`,
        borderRadius: 'var(--radius-full)',
        color: config.color,
        fontWeight: 700,
        fontSize: sizeStyles.fontSize,
        padding: sizeStyles.padding,
        letterSpacing: '0.04em',
        textTransform: 'uppercase',
        userSelect: 'none'
      }}
    >
      <span
        style={{
          width: sizeStyles.dotSize,
          height: sizeStyles.dotSize,
          borderRadius: '50%',
          backgroundColor: config.color,
          boxShadow: config.dotGlow,
          flexShrink: 0
        }}
      />
      <span>{config.label}</span>
      {typeof showScore === 'number' && (
        <span style={{ opacity: 0.75, marginLeft: '2px', fontWeight: 500 }}>
          ({showScore.toFixed(0)})
        </span>
      )}
    </div>
  );
};
