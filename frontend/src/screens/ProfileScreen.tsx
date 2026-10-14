import React, { useState } from 'react';
import { useStreeva } from '../context/StreevaContext';
import { GlassCard } from '../components/GlassCard';
import { PrimaryButton } from '../components/PrimaryButton';
import {
  User,
  Users,
  Shield,
  Phone,
  Plus,
  Trash2,
  Lock,
  Eye,
  Info,
  LogOut,
  MapPin,
  Radio,
  Mic,
  Bell,
  Sliders,
  Check,
  Edit2
} from 'lucide-react';

export const ProfileScreen: React.FC = () => {
  const {
    user,
    updateUserPhone,
    safetyPreferences,
    updateSafetyPreferences,
    contacts,
    addContact,
    removeContact,
    toggleContact,
    logout
  } = useStreeva();

  const [showAddContact, setShowAddContact] = useState(false);
  const [newContactName, setNewContactName] = useState('');
  const [newContactPhone, setNewContactPhone] = useState('');
  const [newContactRelation, setNewContactRelation] = useState('Friend');
  const [contactError, setContactError] = useState('');

  // User account phone editing
  const [isEditingPhone, setIsEditingPhone] = useState(false);
  const [userPhoneInput, setUserPhoneInput] = useState(user?.phone || '+91 98765 00000');
  const [phoneSaveSuccess, setPhoneSaveSuccess] = useState(false);

  const handleSaveUserPhone = () => {
    if (!userPhoneInput.trim() || userPhoneInput.trim().length < 8) return;
    updateUserPhone(userPhoneInput.trim());
    setIsEditingPhone(false);
    setPhoneSaveSuccess(true);
    setTimeout(() => setPhoneSaveSuccess(false), 2000);
  };

  const handleCreateContact = (e: React.FormEvent) => {
    e.preventDefault();
    const cleanName = newContactName.trim();
    const cleanPhone = newContactPhone.trim();

    if (!cleanName) {
      setContactError('Contact name is required.');
      return;
    }
    if (!cleanPhone || cleanPhone.length < 8) {
      setContactError('Please enter a valid phone number (+91 XXXXX XXXXX).');
      return;
    }
    // Prevent duplicate contact numbers
    if (contacts.some((c) => c.phone_number.replace(/\s+/g, '') === cleanPhone.replace(/\s+/g, ''))) {
      setContactError('A contact with this phone number already exists.');
      return;
    }

    setContactError('');
    addContact({
      name: cleanName,
      phone_number: cleanPhone,
      relationship: newContactRelation,
      priority: contacts.length + 1,
      active: true,
      channel: 'SMS_AND_CALL'
    });
    setNewContactName('');
    setNewContactPhone('');
    setShowAddContact(false);
  };

  return (
    <div className="streeva-screen-content" style={{ paddingBottom: '100px' }}>
      {/* Profile Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '16px' }}>
        <div
          style={{
            width: '56px',
            height: '56px',
            borderRadius: '50%',
            background: 'var(--streeva-brand-gradient)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '20px',
            fontWeight: 800,
            color: '#FFFFFF',
            boxShadow: '0 0 15px var(--streeva-brand-glow)'
          }}
        >
          {user?.name?.[0] || 'P'}
        </div>
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: 800, color: 'var(--streeva-text-primary)' }}>
            {user?.name || 'Priya Sharma'}
          </h2>
          <div style={{ fontSize: '12px', color: 'var(--streeva-text-muted)' }}>
            {user?.email || 'priya.sharma@streeva.safe'}
          </div>
        </div>
      </div>

      {/* User Account Phone Number Card (Critical Distinction: User ID/Auth Phone vs Emergency Recipient) */}
      <GlassCard style={{ padding: '14px', marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Phone size={14} color="var(--streeva-intel-cyan)" />
              <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--streeva-text-primary)' }}>
                Your Phone Number (Account Identity)
              </span>
            </div>
            <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)', marginTop: '2px' }}>
              Used to identify and secure your STREEVA account. This is <strong style={{ color: 'var(--safety-medium)' }}>NOT</strong> an emergency recipient.
            </div>
          </div>
          {!isEditingPhone ? (
            <button
              onClick={() => setIsEditingPhone(true)}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--streeva-intel-cyan)',
                fontSize: '11px',
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                cursor: 'pointer'
              }}
            >
              <Edit2 size={12} /> Edit
            </button>
          ) : (
            <button
              onClick={handleSaveUserPhone}
              style={{
                background: 'var(--streeva-brand-primary)',
                border: 'none',
                borderRadius: 'var(--radius-xs)',
                color: '#FFFFFF',
                fontSize: '11px',
                fontWeight: 700,
                padding: '4px 8px',
                cursor: 'pointer'
              }}
            >
              Save
            </button>
          )}
        </div>

        <div style={{ marginTop: '10px' }}>
          {!isEditingPhone ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--streeva-text-primary)', letterSpacing: '0.04em' }}>
                {user?.phone || '+91 98765 00000'}
              </div>
              {phoneSaveSuccess && (
                <span style={{ fontSize: '11px', color: 'var(--safety-low)', fontWeight: 600 }}>
                  ✓ Saved
                </span>
              )}
            </div>
          ) : (
            <input
              type="text"
              value={userPhoneInput}
              onChange={(e) => setUserPhoneInput(e.target.value)}
              placeholder="+91 XXXXX XXXXX"
              style={{
                width: '100%',
                background: 'var(--streeva-bg-deep)',
                border: '1px solid var(--streeva-brand-primary)',
                borderRadius: 'var(--radius-sm)',
                padding: '8px 12px',
                color: '#FFFFFF',
                fontSize: '13px',
                outline: 'none'
              }}
            />
          )}
        </div>
      </GlassCard>

      {/* Emergency Contacts Section */}
      <div style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Users size={16} color="var(--streeva-intel-cyan)" />
            <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--streeva-text-secondary)' }}>
              EMERGENCY CONTACTS ({contacts.filter(c => c.active).length} Active)
            </span>
          </div>
          <button
            onClick={() => {
              setShowAddContact(!showAddContact);
              setContactError('');
            }}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--streeva-intel-cyan)',
              fontSize: '12px',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}
          >
            <Plus size={14} /> Add
          </button>
        </div>

        <p style={{ fontSize: '11px', color: 'var(--streeva-text-muted)', marginBottom: '10px' }}>
          These contacts receive simulated emergency alerts and live GPS tracking when STREEVA initiates response.
        </p>

        {/* Add Contact Modal / Form */}
        {showAddContact && (
          <GlassCard borderGlow="brand" style={{ padding: '14px', marginBottom: '12px' }}>
            <form onSubmit={handleCreateContact} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {contactError && (
                <div style={{ fontSize: '11px', color: 'var(--safety-critical)', fontWeight: 600 }}>
                  ⚠ {contactError}
                </div>
              )}
              <input
                type="text"
                placeholder="Contact Name (e.g., Mother, Partner)"
                value={newContactName}
                onChange={(e) => setNewContactName(e.target.value)}
                style={{
                  background: 'var(--streeva-bg-deep)',
                  border: '1px solid var(--streeva-border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '8px 12px',
                  color: '#FFFFFF',
                  fontSize: '13px',
                  outline: 'none'
                }}
              />
              <input
                type="text"
                placeholder="Phone (+91 XXXXX XXXXX)"
                value={newContactPhone}
                onChange={(e) => setNewContactPhone(e.target.value)}
                style={{
                  background: 'var(--streeva-bg-deep)',
                  border: '1px solid var(--streeva-border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '8px 12px',
                  color: '#FFFFFF',
                  fontSize: '13px',
                  outline: 'none'
                }}
              />
              <div style={{ display: 'flex', gap: '8px' }}>
                <PrimaryButton variant="primary" size="sm" fullWidth={true}>
                  Save Emergency Contact
                </PrimaryButton>
                <PrimaryButton
                  variant="ghost"
                  size="sm"
                  fullWidth={false}
                  onClick={() => setShowAddContact(false)}
                >
                  Cancel
                </PrimaryButton>
              </div>
            </form>
          </GlassCard>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {contacts.map((c, index) => (
            <GlassCard key={c.id} style={{ padding: '12px 14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--streeva-text-primary)' }}>
                      {c.name}
                    </span>
                    <span style={{ fontSize: '10px', color: 'var(--streeva-intel-cyan)', fontWeight: 600 }}>
                      [{index === 0 ? 'PRIMARY' : 'SECONDARY'}]
                    </span>
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--streeva-text-muted)', marginTop: '2px' }}>
                    {c.relationship} • {c.phone_number}
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <input
                    type="checkbox"
                    checked={c.active}
                    onChange={() => toggleContact(c.id)}
                    style={{ accentColor: 'var(--safety-low)', width: '16px', height: '16px' }}
                  />
                  {contacts.length > 1 && (
                    <button
                      onClick={() => removeContact(c.id)}
                      style={{ background: 'none', border: 'none', color: 'var(--streeva-text-muted)', cursor: 'pointer' }}
                    >
                      <Trash2 size={15} />
                    </button>
                  )}
                </div>
              </div>
            </GlassCard>
          ))}
        </div>
      </div>

      {/* Authoritative Safety Preferences Section (Moved from deprecated Guardian page) */}
      <div style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px' }}>
          <Sliders size={16} color="var(--streeva-intel-cyan)" />
          <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--streeva-text-secondary)' }}>
            SAFETY PREFERENCES
          </span>
        </div>
        <GlassCard style={{ padding: '16px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Automatic Guardian Mode Toggle */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--streeva-text-primary)' }}>
                  Automatic Guardian Mode
                </div>
                <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)', marginTop: '2px' }}>
                  Engages protection upon detecting transit.
                </div>
              </div>
              <input
                type="checkbox"
                checked={safetyPreferences.autoGuardian}
                onChange={(e) => updateSafetyPreferences({ autoGuardian: e.target.checked })}
                style={{ width: '18px', height: '18px', accentColor: 'var(--streeva-brand-primary)', cursor: 'pointer' }}
              />
            </div>

            {/* Acoustic Distress Detection Toggle */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--streeva-text-primary)' }}>
                  Acoustic Distress Detection
                </div>
                <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)', marginTop: '2px' }}>
                  On-device vocal distress classifier.
                </div>
              </div>
              <input
                type="checkbox"
                checked={safetyPreferences.audioAnalysis}
                onChange={(e) => updateSafetyPreferences({ audioAnalysis: e.target.checked })}
                style={{ width: '18px', height: '18px', accentColor: 'var(--streeva-brand-primary)', cursor: 'pointer' }}
              />
            </div>

            {/* Emergency Countdown Window */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--streeva-text-primary)' }}>
                  Emergency Countdown
                </div>
                <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)', marginTop: '2px' }}>
                  Seconds before autonomous response.
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <select
                  value={safetyPreferences.countdownDuration}
                  onChange={(e) => updateSafetyPreferences({ countdownDuration: Number(e.target.value) })}
                  style={{
                    backgroundColor: 'var(--streeva-bg-deep)',
                    color: 'var(--streeva-intel-cyan)',
                    border: '1px solid var(--streeva-border-subtle)',
                    borderRadius: 'var(--radius-xs)',
                    padding: '4px 8px',
                    fontSize: '12px',
                    fontWeight: 700,
                    outline: 'none',
                    cursor: 'pointer'
                  }}
                >
                  <option value={10}>10s</option>
                  <option value={15}>15s (Default)</option>
                  <option value={20}>20s</option>
                  <option value={30}>30s</option>
                </select>
              </div>
            </div>
          </div>
        </GlassCard>
      </div>

      {/* Permission Center (Section 11.AC) */}
      <div style={{ marginBottom: '20px' }}>
        <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--streeva-text-secondary)', marginBottom: '10px' }}>
          PERMISSION CENTER
        </div>
        <GlassCard style={{ padding: '14px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <MapPin size={16} color="var(--safety-low)" />
                <div>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--streeva-text-primary)' }}>
                    High-Precision GPS
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)' }}>
                    Needed for cross-track route deviation detection
                  </div>
                </div>
              </div>
              <span style={{ fontSize: '11px', color: 'var(--safety-low)', fontWeight: 700 }}>Active</span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Radio size={16} color="var(--safety-low)" />
                <div>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--streeva-text-primary)' }}>
                    Motion & Gyroscope Sensors
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)' }}>
                    Detects physical impact, falls, and unexpected stops
                  </div>
                </div>
              </div>
              <span style={{ fontSize: '11px', color: 'var(--safety-low)', fontWeight: 700 }}>Active</span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Mic size={16} color="var(--safety-low)" />
                <div>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--streeva-text-primary)' }}>
                    Distress Audio Analysis
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)' }}>
                    On-device model flags scream vocalizations (zero recording saved)
                  </div>
                </div>
              </div>
              <span style={{ fontSize: '11px', color: 'var(--safety-low)', fontWeight: 700 }}>Active</span>
            </div>
          </div>
        </GlassCard>
      </div>

      {/* Privacy & Trust Guarantee */}
      <GlassCard style={{ padding: '14px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <Lock size={16} color="var(--streeva-intel-cyan)" />
          <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--streeva-text-primary)' }}>
            STREEVA Privacy Architecture
          </span>
        </div>
        <p style={{ fontSize: '11px', color: 'var(--streeva-text-muted)', lineHeight: 1.4 }}>
          Telemetry is processed locally using on-device neural models. Audio raw waves are never uploaded or stored.
          Emergency contacts only receive non-technical status coordinates when an emergency is explicitly triggered.
        </p>
      </GlassCard>

      {/* Logout Action */}
      <PrimaryButton
        variant="secondary"
        size="md"
        icon={<LogOut size={16} />}
        onClick={logout}
      >
        Sign Out
      </PrimaryButton>
    </div>
  );
};
