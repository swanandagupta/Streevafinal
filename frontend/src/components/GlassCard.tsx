import React from 'react';

interface GlassCardProps {
  children: React.ReactNode;
  style?: React.CSSProperties;
  className?: string;
  onClick?: () => void;
  borderGlow?: 'none' | 'brand' | 'low' | 'medium' | 'high' | 'critical';
}

export const GlassCard: React.FC<GlassCardProps> = ({
  children,
  style,
  className = '',
  onClick,
  borderGlow = 'none'
}) => {
  const getGlowStyle = () => {
    switch (borderGlow) {
      case 'brand':
        return {
          borderColor: 'var(--streeva-border-active)',
          boxShadow: '0 4px 20px var(--streeva-brand-glow), inset 0 1px 0 rgba(99, 102, 241, 0.25)'
        };
      case 'low':
        return {
          borderColor: 'var(--safety-low-border)',
          boxShadow: '0 4px 20px var(--safety-low-glow), inset 0 1px 0 rgba(16, 185, 129, 0.25), inset 0 0 16px rgba(16, 185, 129, 0.04)'
        };
      case 'medium':
        return {
          borderColor: 'var(--safety-medium-border)',
          boxShadow: '0 4px 20px var(--safety-medium-glow), inset 0 1px 0 rgba(245, 158, 11, 0.25)'
        };
      case 'high':
        return {
          borderColor: 'var(--safety-high-border)',
          boxShadow: '0 4px 24px var(--safety-high-glow), inset 0 1px 0 rgba(249, 115, 22, 0.3)'
        };
      case 'critical':
        return {
          borderColor: 'var(--safety-critical-border)',
          boxShadow: '0 4px 30px var(--safety-critical-glow), inset 0 1px 0 rgba(239, 68, 68, 0.35)'
        };
      default:
        return {
          borderColor: 'var(--streeva-border-subtle)',
          boxShadow: '0 4px 16px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.05)'
        };
    }
  };

  return (
    <div
      onClick={onClick}
      className={`streeva-glass ${className}`}
      style={{
        padding: '16px',
        position: 'relative',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'all var(--transition-smooth)',
        ...getGlowStyle(),
        ...style
      }}
    >
      {children}
    </div>
  );
};
