import React, { useState, useEffect } from 'react';
import { useStreeva } from '../context/StreevaContext';
import { GuardianCore } from '../components/GuardianCore';
import { PrimaryButton } from '../components/PrimaryButton';
import { GlassCard } from '../components/GlassCard';
import {
  AlertOctagon,
  CheckCircle2,
  PhoneCall,
  Send,
  ShieldAlert,
  MapPin,
  Clock,
  ExternalLink,
  Users
} from 'lucide-react';

export const EmergencyScreen: React.FC = () => {
  const {
    incident,
    cancelEmergency,
    acknowledgeEmergency,
    contacts,
    user,
    selectedDestination,
    locationState,
    snapshot,
    activeJourneyId,
    safetyPreferences
  } = useStreeva();
  const [secondsRemaining, setSecondsRemaining] = useState<number>(
    safetyPreferences?.countdownDuration || 15
  );
  const [isAuthorized, setIsAuthorized] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'status' | 'message' | 'escalation'>('status');

  // Countdown timer logic
  useEffect(() => {
    if (isAuthorized) return;

    if (secondsRemaining <= 0) {
      setIsAuthorized(true);
      return;
    }

    const timer = setInterval(() => {
      setSecondsRemaining((prev) => prev - 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [secondsRemaining, isAuthorized]);

  const handleCancel = async () => {
    await cancelEmergency('False alarm confirmed by traveler');
  };

  const primaryContact = contacts[0] || {
    name: 'Aanya Sharma',
    phone_number: '+91 98765 43210',
    relationship: 'Mother'
  };

  const secondaryContact = contacts[1] || {
    name: 'Rohan Verma',
    phone_number: '+91 98765 11223',
    relationship: 'Brother'
  };

  const lat = snapshot?.current_location?.lat || locationState?.coords?.lat;
  const lng = snapshot?.current_location?.lng || locationState?.coords?.lng;
  const hasLocation = lat != null && lng != null;
  const locationString = hasLocation ? `${lat.toFixed(4)}, ${lng.toFixed(4)}` : 'Location Unavailable';
  const locationStatusText =
    locationState.status === 'ACQUIRED'
      ? 'Live'
      : locationState.status === 'ACQUIRING'
      ? 'Recent'
      : 'Stale';
  const destName = selectedDestination?.display_name || 'Indiranagar Metro Station';

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        backgroundColor: '#07090E',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        padding: '24px 20px',
        overflowY: 'auto'
      }}
    >
      {/* 1. COUNTDOWN VIEW */}
      {!isAuthorized ? (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            flex: 1,
            textAlign: 'center'
          }}
        >
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              backgroundColor: 'var(--safety-critical-surface)',
              border: '1px solid var(--safety-critical-border)',
              borderRadius: 'var(--radius-full)',
              padding: '6px 14px',
              color: 'var(--safety-critical)',
              fontSize: '12px',
              fontWeight: 800,
              letterSpacing: '0.06em',
              marginBottom: '20px'
            }}
          >
            <AlertOctagon size={16} />
            <span>EMERGENCY RESPONSE COUNTDOWN</span>
          </div>

          <GuardianCore riskLevel="CRITICAL" size={170} />

          {/* Large Countdown Digit */}
          <div
            style={{
              fontSize: '56px',
              fontWeight: 900,
              fontVariantNumeric: 'tabular-nums',
              color: 'var(--safety-critical)',
              marginTop: '16px',
              letterSpacing: '-0.03em',
              textShadow: '0 0 25px var(--safety-critical-glow)'
            }}
          >
            00:{secondsRemaining < 10 ? `0${secondsRemaining}` : secondsRemaining}
          </div>

          <h2 style={{ fontSize: '20px', fontWeight: 800, color: 'var(--streeva-text-primary)', marginTop: '8px' }}>
            Critical Safety Event Detected
          </h2>
          <p
            style={{
              fontSize: '13px',
              color: 'var(--streeva-text-secondary)',
              maxWidth: '300px',
              marginTop: '6px',
              lineHeight: 1.4
            }}
          >
            Autonomous emergency response and location dispatch will begin when the countdown ends.
          </p>

          {/* Prominent, Unmissable Cancel Button */}
          <div style={{ width: '100%', maxWidth: '320px', marginTop: '32px' }}>
            <PrimaryButton
              variant="success"
              size="lg"
              onClick={handleCancel}
              style={{
                height: '60px',
                fontSize: '18px',
                letterSpacing: '0.04em',
                fontWeight: 800
              }}
            >
              I'M SAFE — CANCEL ALERT
            </PrimaryButton>
          </div>
        </div>
      ) : (
        /* 2. EMERGENCY ACTIVE VIEW (Authorized Response) */
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', justifyContent: 'space-between' }}>
          <div>
            {/* Active Header */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                paddingBottom: '14px',
                borderBottom: '1px solid var(--streeva-border-subtle)',
                marginBottom: '16px'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div
                  style={{
                    width: '12px',
                    height: '12px',
                    borderRadius: '50%',
                    backgroundColor: 'var(--safety-critical)',
                    boxShadow: '0 0 12px var(--safety-critical)',
                    animation: 'pulse-critical 1.5s infinite'
                  }}
                />
                <div>
                  <h2 style={{ fontSize: '17px', fontWeight: 800, color: 'var(--safety-critical)' }}>
                    EMERGENCY ACTIVE
                  </h2>
                  <span style={{ fontSize: '11px', color: 'var(--streeva-text-muted)' }}>
                    Incident #{incident?.incident_id?.slice(-8) || 'ST-4892'}
                  </span>
                </div>
              </div>

              <button
                onClick={handleCancel}
                style={{
                  backgroundColor: 'var(--streeva-surface-card)',
                  border: '1px solid var(--streeva-border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  color: 'var(--streeva-text-secondary)',
                  padding: '6px 12px',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                Resolve
              </button>
            </div>

            {/* Simulated Prototype Banner */}
            <div
              style={{
                backgroundColor: 'rgba(99, 102, 241, 0.08)',
                border: '1px solid var(--streeva-border-subtle)',
                borderRadius: 'var(--radius-sm)',
                padding: '6px 10px',
                marginBottom: '12px',
                fontSize: '11px',
                color: 'var(--streeva-intel-cyan)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
              }}
            >
              <span>● MOCK NOTIFICATION PROVIDER ACTIVE</span>
              <span style={{ color: 'var(--streeva-text-muted)' }}>Simulated Dispatch</span>
            </div>

            {/* Navigation Tabs */}
            <div
              style={{
                display: 'flex',
                backgroundColor: 'var(--streeva-surface-card)',
                borderRadius: 'var(--radius-sm)',
                padding: '3px',
                marginBottom: '16px'
              }}
            >
              {(['status', 'message', 'escalation'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  style={{
                    flex: 1,
                    padding: '8px',
                    fontSize: '12px',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    border: 'none',
                    borderRadius: 'var(--radius-sm)',
                    cursor: 'pointer',
                    background: activeTab === tab ? 'var(--streeva-brand-primary)' : 'none',
                    color: activeTab === tab ? '#FFFFFF' : 'var(--streeva-text-muted)'
                  }}
                >
                  {tab}
                </button>
              ))}
            </div>

            {/* Tab: Status Checklist */}
            {activeTab === 'status' && (
              <GlassCard borderGlow="critical" style={{ padding: '16px', marginBottom: '16px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
                      <MapPin size={16} color="var(--safety-low)" />
                      <span>GPS Coordinates ({locationStatusText})</span>
                    </div>
                    <span style={{ fontSize: '11px', color: hasLocation ? 'var(--safety-low)' : 'var(--safety-critical)', fontWeight: 700 }}>
                      {hasLocation ? `✓ ${locationString}` : 'Explicitly Unavailable'}
                    </span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
                      <Users size={16} color="var(--safety-low)" />
                      <span>Primary Contact ({primaryContact.name})</span>
                    </div>
                    <span style={{ fontSize: '11px', color: 'var(--safety-low)', fontWeight: 700 }}>
                      ✓ Simulated: SENT (Mock SMS)
                    </span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
                      <ShieldAlert size={16} color="var(--safety-low)" />
                      <span>Evidence Package</span>
                    </div>
                    <span style={{ fontSize: '11px', color: 'var(--safety-low)', fontWeight: 700 }}>
                      ✓ Encrypted & Sealed
                    </span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
                      <Clock size={16} color="var(--safety-medium)" />
                      <span>Contact Acknowledgement</span>
                    </div>
                    <span style={{ fontSize: '11px', color: 'var(--safety-medium)', fontWeight: 700 }}>
                      {incident?.acknowledgement_status === 'ACKNOWLEDGED' ? '✓ Acknowledged' : 'Waiting...'}
                    </span>
                  </div>
                </div>
              </GlassCard>
            )}

            {/* Tab: Non-Technical Contact Message Payload Preview (Requirement 20 & 23) */}
            {activeTab === 'message' && (
              <GlassCard style={{ padding: '16px', marginBottom: '16px' }}>
                <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--streeva-intel-cyan)', marginBottom: '8px' }}>
                  DISPATCHED EMERGENCY SMS PAYLOAD (MOCK PROVIDER)
                </div>
                <div
                  style={{
                    backgroundColor: 'var(--streeva-bg-deep)',
                    border: '1px solid var(--streeva-border-subtle)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '12px',
                    fontSize: '12px',
                    color: 'var(--streeva-text-secondary)',
                    lineHeight: 1.5,
                    fontFamily: 'var(--font-mono)'
                  }}
                >
                  <p>
                    <strong>STREEVA Emergency Alert</strong>
                  </p>
                  <p style={{ marginTop: '6px' }}>
                    STREEVA has detected a critical safety event during {user?.name || 'Priya'}'s active journey and autonomous emergency response has been initiated.
                  </p>
                  <p style={{ marginTop: '8px' }}>
                    • Current location: {hasLocation ? `https://streeva.safe/track?lat=${lat.toFixed(4)}&lng=${lng.toFixed(4)}` : 'Explicitly unavailable'}<br />
                    • Location status: {locationStatusText}<br />
                    • Destination: {destName}<br />
                    • Journey status: Active<br />
                    • Time: {new Date().toLocaleTimeString()}
                  </p>
                  <p style={{ marginTop: '8px', color: 'var(--safety-medium)' }}>
                    Please try to contact them and take appropriate action.
                  </p>
                </div>
                <div style={{ fontSize: '10px', color: 'var(--streeva-text-muted)', marginTop: '6px' }}>
                  * Notification simulated successfully via MockNotificationProvider. No carrier SMS bill incurred.
                </div>
              </GlassCard>
            )}

            {/* Tab: Multi-tier Escalation Ladder (Section 11.U) */}
            {activeTab === 'escalation' && (
              <GlassCard style={{ padding: '16px', marginBottom: '16px' }}>
                <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--streeva-text-secondary)', marginBottom: '12px' }}>
                  ESCALATION PROTOCOL
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--safety-low)' }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--streeva-text-primary)' }}>
                        Tier 1: Primary Contact ({primaryContact.name})
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--safety-low)' }}>Dispatched via SMS & Automated Voice</div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--safety-medium)' }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--streeva-text-primary)' }}>
                        Tier 2: Secondary Contact ({secondaryContact.name})
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)' }}>
                        Escalates if unacknowledged in 60 seconds
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'rgba(255,255,255,0.2)' }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--streeva-text-muted)' }}>
                        Tier 3: Emergency Services
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)' }}>
                        Ready on verified confirmation
                      </div>
                    </div>
                  </div>
                </div>
              </GlassCard>
            )}
          </div>

          {/* Contact Simulator Action (for BTech evaluation & testing) */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <PrimaryButton
              variant="secondary"
              size="md"
              icon={<CheckCircle2 size={18} color="var(--safety-low)" />}
              onClick={() => acknowledgeEmergency(primaryContact.phone_number)}
            >
              Simulate Contact Acknowledgment
            </PrimaryButton>

            <PrimaryButton variant="danger" size="md" onClick={handleCancel}>
              Resolve & Resume Normal Journey
            </PrimaryButton>
          </div>
        </div>
      )}
    </div>
  );
};
