import React from 'react';

interface PrimaryButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'success';
  size?: 'sm' | 'md' | 'lg';
  fullWidth?: boolean;
  disabled?: boolean;
  loading?: boolean;
  icon?: React.ReactNode;
  style?: React.CSSProperties;
}

export const PrimaryButton: React.FC<PrimaryButtonProps> = ({
  children,
  onClick,
  variant = 'primary',
  size = 'md',
  fullWidth = true,
  disabled = false,
  loading = false,
  icon,
  style
}) => {
  const getVariantStyles = () => {
    switch (variant) {
      case 'primary':
        return {
          background: 'var(--streeva-brand-gradient)',
          color: '#ffffff',
          boxShadow: '0 4px 15px var(--streeva-brand-glow)',
          border: 'none'
        };
      case 'secondary':
        return {
          background: 'var(--streeva-surface-card)',
          color: 'var(--streeva-text-primary)',
          border: '1px solid var(--streeva-border-subtle)',
          boxShadow: 'var(--shadow-sm)'
        };
      case 'danger':
        return {
          background: 'linear-gradient(135deg, #EF4444 0%, #B91C1C 100%)',
          color: '#ffffff',
          boxShadow: '0 4px 20px var(--safety-critical-glow)',
          border: 'none'
        };
      case 'success':
        return {
          background: 'linear-gradient(135deg, #10B981 0%, #047857 100%)',
          color: '#ffffff',
          boxShadow: '0 4px 15px var(--safety-low-glow)',
          border: 'none'
        };
      case 'ghost':
        return {
          background: 'transparent',
          color: 'var(--streeva-text-secondary)',
          border: '1px solid transparent'
        };
    }
  };

  const getSizeStyles = () => {
    switch (size) {
      case 'sm':
        return { padding: '8px 14px', fontSize: '13px', borderRadius: 'var(--radius-sm)' };
      case 'md':
        return { padding: '12px 20px', fontSize: '15px', borderRadius: 'var(--radius-md)' };
      case 'lg':
        return { padding: '16px 24px', fontSize: '16px', borderRadius: 'var(--radius-md)' };
    }
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      style={{
        width: fullWidth ? '100%' : 'auto',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '10px',
        fontWeight: 600,
        fontFamily: 'var(--font-sans)',
        cursor: disabled || loading ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.45 : 1,
        transition: 'all var(--transition-smooth)',
        outline: 'none',
        ...getVariantStyles(),
        ...getSizeStyles(),
        ...style
      }}
    >
      {loading ? (
        <span
          style={{
            width: 18,
            height: 18,
            border: '2px solid rgba(255,255,255,0.3)',
            borderTopColor: '#ffffff',
            borderRadius: '50%',
            animation: 'spin 0.8s linear infinite'
          }}
        />
      ) : (
        <>
          {icon && <span style={{ display: 'flex' }}>{icon}</span>}
          <span>{children}</span>
        </>
      )}
    </button>
  );
};
