import React, { useState } from 'react';
import { GuardianCore } from '../components/GuardianCore';
import { PrimaryButton } from '../components/PrimaryButton';
import { Shield, Navigation, Activity, Mic, Users, ArrowRight, ArrowLeft } from 'lucide-react';

interface OnboardingScreenProps {
  onComplete: () => void;
}

export const OnboardingScreen: React.FC<OnboardingScreenProps> = ({ onComplete }) => {
  const [step, setStep] = useState<number>(0);

  const steps = [
    {
      title: 'Travel freely. Stay intelligently protected.',
      subtitle: 'An autonomous protective layer around your everyday commutes and late-night journeys.',
      risk: 'LOW' as const,
      graphic: null
    },
    {
      title: 'STREEVA understands your journey.',
      subtitle: 'Real-time GPS, inertial motion, distress audio, and area intelligence combine to monitor your safety.',
      risk: 'MEDIUM' as const,
      graphic: 'multimodal'
    },
    {
      title: 'When something feels wrong, STREEVA adapts.',
      subtitle: 'Adaptive monitoring escalates vigilance seamlessly from normal travel to immediate emergency response.',
      risk: 'HIGH' as const,
      graphic: 'escalation'
    },
    {
      title: 'Your emergency contacts stay connected.',
      subtitle: 'Autonomous verification, live location sharing, and multi-tier escalation when you need it most.',
      risk: 'LOW' as const,
      graphic: 'contacts'
    }
  ];

  const currentStep = steps[step];

  const handleNext = () => {
    if (step < steps.length - 1) {
      setStep(step + 1);
    } else {
      onComplete();
    }
  };

  const handlePrev = () => {
    if (step > 0) {
      setStep(step - 1);
    }
  };

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        padding: '24px 20px',
        backgroundColor: 'var(--streeva-bg-midnight)',
        overflowY: 'auto'
      }}
    >
      {/* Header with Step Dots & Skip */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '12px' }}>
        <div style={{ display: 'flex', gap: '8px' }}>
          {steps.map((_, i) => (
            <span
              key={i}
              style={{
                width: i === step ? '24px' : '8px',
                height: '8px',
                borderRadius: '4px',
                backgroundColor: i === step ? 'var(--streeva-intel-cyan)' : 'var(--streeva-border-subtle)',
                transition: 'all 300ms ease'
              }}
            />
          ))}
        </div>

        <button
          onClick={onComplete}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--streeva-text-muted)',
            fontSize: '13px',
            fontWeight: 600,
            cursor: 'pointer'
          }}
        >
          Skip
        </button>
      </div>

      {/* Hero Visual Area */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', margin: '20px 0' }}>
        <GuardianCore riskLevel={currentStep.risk} size={170} />

        {currentStep.graphic === 'multimodal' && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(4, 1fr)',
              gap: '10px',
              marginTop: '20px',
              width: '100%',
              maxWidth: '320px'
            }}
          >
            {[
              { icon: <Navigation size={18} />, label: 'GPS' },
              { icon: <Activity size={18} />, label: 'Motion' },
              { icon: <Mic size={18} />, label: 'Audio' },
              { icon: <Shield size={18} />, label: 'Context' }
            ].map((s, i) => (
              <div
                key={i}
                style={{
                  backgroundColor: 'var(--streeva-surface-card)',
                  border: '1px solid var(--streeva-border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '10px 4px',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '4px',
                  color: 'var(--streeva-intel-cyan)'
                }}
              >
                {s.icon}
                <span style={{ fontSize: '11px', color: 'var(--streeva-text-secondary)' }}>{s.label}</span>
              </div>
            ))}
          </div>
        )}

        {currentStep.graphic === 'escalation' && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              marginTop: '20px',
              fontSize: '11px',
              fontWeight: 700
            }}
          >
            <span style={{ color: 'var(--safety-low)', background: 'var(--safety-low-surface)', padding: '4px 8px', borderRadius: '4px' }}>NORMAL</span>
            <span style={{ color: 'var(--streeva-text-muted)' }}>→</span>
            <span style={{ color: 'var(--safety-medium)', background: 'var(--safety-medium-surface)', padding: '4px 8px', borderRadius: '4px' }}>UNUSUAL</span>
            <span style={{ color: 'var(--streeva-text-muted)' }}>→</span>
            <span style={{ color: 'var(--safety-high)', background: 'var(--safety-high-surface)', padding: '4px 8px', borderRadius: '4px' }}>ELEVATED</span>
            <span style={{ color: 'var(--streeva-text-muted)' }}>→</span>
            <span style={{ color: 'var(--safety-critical)', background: 'var(--safety-critical-surface)', padding: '4px 8px', borderRadius: '4px' }}>SOS</span>
          </div>
        )}

        {currentStep.graphic === 'contacts' && (
          <div
            style={{
              backgroundColor: 'var(--streeva-surface-card)',
              border: '1px solid var(--streeva-border-subtle)',
              borderRadius: 'var(--radius-md)',
              padding: '12px 16px',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              marginTop: '20px',
              width: '100%',
              maxWidth: '300px'
            }}
          >
            <Users size={24} color="var(--safety-low)" />
            <div style={{ textAlign: 'left' }}>
              <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--streeva-text-primary)' }}>Verified Circle</div>
              <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)' }}>2 emergency contacts ready</div>
            </div>
          </div>
        )}
      </div>

      {/* Copy Content */}
      <div style={{ textAlign: 'center', marginBottom: '24px' }}>
        <h2
          style={{
            fontSize: '22px',
            fontWeight: 800,
            color: 'var(--streeva-text-primary)',
            lineHeight: 1.3,
            marginBottom: '10px'
          }}
        >
          {currentStep.title}
        </h2>
        <p style={{ fontSize: '14px', color: 'var(--streeva-text-secondary)', lineHeight: 1.5, padding: '0 8px' }}>
          {currentStep.subtitle}
        </p>
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: '12px' }}>
        {step > 0 && (
          <PrimaryButton variant="secondary" size="md" onClick={handlePrev} fullWidth={false} style={{ flex: '0 0 54px' }}>
            <ArrowLeft size={18} />
          </PrimaryButton>
        )}
        <PrimaryButton variant="primary" size="md" onClick={handleNext} fullWidth={true}>
          <span>{step === steps.length - 1 ? 'Set up STREEVA' : 'Continue'}</span>
          <ArrowRight size={18} />
        </PrimaryButton>
      </div>
    </div>
  );
};
