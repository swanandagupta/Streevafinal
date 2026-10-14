/**
 * @deprecated DEPRECATED AS OF HOME REDESIGN
 * The dedicated Guardian page has been removed from primary navigation.
 * - Guardian Core & 2x2 dynamic status grid are integrated into HomeScreen.
 * - Safety Preferences have moved authoritatively to ProfileScreen.
 * - Backend GuardianMonitor, journey state, and Phase 0-5 logic remain completely active.
 */

import React, { useState } from 'react';
import { useStreeva } from '../context/StreevaContext';
import { GuardianCore } from '../components/GuardianCore';
import { GlassCard } from '../components/GlassCard';
import { RiskBadge } from '../components/RiskBadge';
import {
  Shield,
  Radio,
  Sliders,
  Bell,
  Mic,
  MapPin,
  Wifi,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';

export const GuardianScreen: React.FC = () => {
  const { riskLevel, connectivity, sensorPolicy } = useStreeva();
  const [autoGuardian, setAutoGuardian] = useState(true);
  const [audioAnalysis, setAudioAnalysis] = useState(true);
  const [countdownDuration, setCountdownDuration] = useState(15);

  return (
    <div className="streeva-screen-content" style={{ paddingBottom: '100px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div>
          <h2 style={{ fontSize: '20px', fontWeight: 800, color: 'var(--streeva-text-primary)' }}>
            Guardian Center
          </h2>
          <p style={{ fontSize: '12px', color: 'var(--streeva-text-muted)' }}>
            Awareness state & intelligence policies
          </p>
        </div>
        <RiskBadge level={riskLevel} size="sm" />
      </div>

      {/* Hero Visual Card */}
      <GlassCard
        borderGlow="brand"
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          padding: '24px 16px',
          marginBottom: '20px',
          textAlign: 'center'
        }}
      >
        <GuardianCore riskLevel={riskLevel} size={160} />
        <h3 style={{ fontSize: '18px', fontWeight: 800, color: 'var(--streeva-text-primary)', marginTop: '12px' }}>
          {riskLevel === 'LOW' ? 'Guardian Active & Stable' : 'Adaptive Vigilance Engaged'}
        </h3>
        <p style={{ fontSize: '12px', color: 'var(--streeva-text-secondary)', maxWidth: '280px', marginTop: '4px' }}>
          Multimodal edge models are continuously tracking movement vectors and environmental cues.
        </p>
      </GlassCard>

      {/* Sensor & Intelligence Telemetry Health */}
      <GlassCard style={{ padding: '16px', marginBottom: '20px' }}>
        <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--streeva-intel-cyan)', marginBottom: '12px' }}>
          TELEMETRY HEALTH
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
              <MapPin size={16} color="var(--safety-low)" />
              <span>Location Context</span>
            </div>
            <span style={{ fontSize: '12px', color: 'var(--safety-low)', fontWeight: 600 }}>Active (Fused GPS)</span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
              <Radio size={16} color="var(--safety-low)" />
              <span>Inertial Motion Sensor</span>
            </div>
            <span style={{ fontSize: '12px', color: 'var(--safety-low)', fontWeight: 600 }}>Calibrated</span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
              <Mic size={16} color="var(--safety-low)" />
              <span>Distress Acoustic Filter</span>
            </div>
            <span style={{ fontSize: '12px', color: 'var(--safety-low)', fontWeight: 600 }}>Standby (Edge TFLite)</span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
              <Wifi size={16} color={connectivity === 'OFFLINE' ? 'var(--safety-medium)' : 'var(--safety-low)'} />
              <span>Connectivity Resilience</span>
            </div>
            <span
              style={{
                fontSize: '12px',
                color: connectivity === 'OFFLINE' ? 'var(--safety-medium)' : 'var(--safety-low)',
                fontWeight: 600
              }}
            >
              {connectivity}
            </span>
          </div>
        </div>
      </GlassCard>

      {/* Guardian Policy Controls */}
      <GlassCard style={{ padding: '16px', marginBottom: '20px' }}>
        <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--streeva-text-secondary)', marginBottom: '14px' }}>
          SAFETY PREFERENCES
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--streeva-text-primary)' }}>
                Automatic Guardian Mode
              </div>
              <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)' }}>
                Engages protection upon detecting transit
              </div>
            </div>
            <input
              type="checkbox"
              checked={autoGuardian}
              onChange={(e) => setAutoGuardian(e.target.checked)}
              style={{ width: '18px', height: '18px', accentColor: 'var(--streeva-brand-primary)' }}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--streeva-text-primary)' }}>
                Acoustic Distress Detection
              </div>
              <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)' }}>
                On-device vocal distress classifier
              </div>
            </div>
            <input
              type="checkbox"
              checked={audioAnalysis}
              onChange={(e) => setAudioAnalysis(e.target.checked)}
              style={{ width: '18px', height: '18px', accentColor: 'var(--streeva-brand-primary)' }}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--streeva-text-primary)' }}>
                Emergency Countdown Window
              </div>
              <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)' }}>
                Seconds before autonomous dispatch
              </div>
            </div>
            <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--streeva-intel-cyan)' }}>
              {countdownDuration}s
            </span>
          </div>
        </div>
      </GlassCard>
    </div>
  );
};
