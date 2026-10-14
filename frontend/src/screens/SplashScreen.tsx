import React, { useEffect } from 'react';
import { GuardianCore } from '../components/GuardianCore';
import { Shield } from 'lucide-react';

interface SplashScreenProps {
  onFinish: () => void;
}

export const SplashScreen: React.FC<SplashScreenProps> = ({ onFinish }) => {
  useEffect(() => {
    const timer = setTimeout(() => {
      onFinish();
    }, 2400);
    return () => clearTimeout(timer);
  }, [onFinish]);

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'var(--streeva-bg-deep)',
        position: 'relative',
        padding: '24px',
        textAlign: 'center'
      }}
    >
      <div style={{ marginBottom: '24px' }}>
        <GuardianCore riskLevel="LOW" size={200} />
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
        <Shield size={24} color="var(--streeva-brand-primary)" />
        <h1
          style={{
            fontSize: '32px',
            fontWeight: 800,
            letterSpacing: '0.12em',
            color: '#FFFFFF'
          }}
        >
          STREEVA
        </h1>
      </div>

      <p
        style={{
          fontSize: '14px',
          color: 'var(--streeva-intel-cyan)',
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          fontWeight: 600,
          marginBottom: '32px'
        }}
      >
        Intelligent Journey Safety
      </p>

      {/* Subtle loader */}
      <div
        style={{
          position: 'absolute',
          bottom: '40px',
          display: 'flex',
          gap: '6px'
        }}
      >
        <span
          style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            backgroundColor: 'var(--streeva-brand-primary)',
            animation: 'pulse-calm 1.5s infinite'
          }}
        />
        <span
          style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            backgroundColor: 'var(--streeva-intel-cyan)',
            animation: 'pulse-calm 1.5s infinite 0.2s'
          }}
        />
        <span
          style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            backgroundColor: 'var(--safety-low)',
            animation: 'pulse-calm 1.5s infinite 0.4s'
          }}
        />
      </div>
    </div>
  );
};
