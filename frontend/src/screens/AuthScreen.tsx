import React, { useState } from 'react';
import { useStreeva } from '../context/StreevaContext';
import { PrimaryButton } from '../components/PrimaryButton';
import { GlassCard } from '../components/GlassCard';
import { Shield, Lock, Mail, User, Phone, AlertCircle } from 'lucide-react';

export const AuthScreen: React.FC = () => {
  const { login } = useStreeva();
  const [mode, setMode] = useState<'login' | 'register' | 'forgot'>('login');
  const [email, setEmail] = useState('priya.sharma@streeva.safe');
  const [password, setPassword] = useState('••••••••••••');
  const [name, setName] = useState('Priya Sharma');
  const [phone, setPhone] = useState('+91 98765 00000');
  const [error, setError] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) {
      setError('Please enter a valid email address.');
      return;
    }
    if (mode === 'register' && (!phone || phone.length < 8)) {
      setError('Please enter your account phone number (+91 XXXXX XXXXX).');
      return;
    }
    setError('');
    login(email, name, phone);
  };

  const handleDemoSignIn = () => {
    login('traveler.demo@streeva.safe', 'Priya Sharma (Demo)', '+91 98765 00000');
  };

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        padding: '24px 20px',
        backgroundColor: 'var(--streeva-bg-midnight)',
        overflowY: 'auto'
      }}
    >
      {/* Brand Logo & Heading */}
      <div style={{ textAlign: 'center', marginBottom: '28px' }}>
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '56px',
            height: '56px',
            borderRadius: 'var(--radius-lg)',
            background: 'var(--streeva-brand-gradient)',
            boxShadow: '0 0 25px var(--streeva-brand-glow)',
            marginBottom: '16px'
          }}
        >
          <Shield size={28} color="#FFFFFF" />
        </div>
        <h1 style={{ fontSize: '24px', fontWeight: 800, color: 'var(--streeva-text-primary)' }}>
          {mode === 'login' ? 'Welcome to STREEVA' : mode === 'register' ? 'Create Account' : 'Reset Password'}
        </h1>
        <p style={{ fontSize: '13px', color: 'var(--streeva-text-muted)', marginTop: '4px' }}>
          {mode === 'login'
            ? 'Sign in to access your intelligent protective layer'
            : mode === 'register'
            ? 'Set up your verified traveler profile'
            : 'Enter your email to receive recovery instructions'}
        </p>
      </div>

      {/* Explicit Architecture Limitation Notice (Section 4) */}
      <div
        style={{
          backgroundColor: 'rgba(99, 102, 241, 0.1)',
          border: '1px solid var(--streeva-border-subtle)',
          borderRadius: 'var(--radius-sm)',
          padding: '10px 14px',
          marginBottom: '20px',
          fontSize: '11px',
          color: 'var(--streeva-intel-cyan)',
          lineHeight: 1.4,
          textAlign: 'center'
        }}
      >
        <strong>DEVELOPMENT & DEMO AUTHENTICATION</strong>
        <div style={{ color: 'var(--streeva-text-secondary)', marginTop: '2px' }}>
          Local session storage active for Phase 6 evaluation. Production JWT Auth server integration in roadmap.
        </div>
      </div>

      {error && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            backgroundColor: 'var(--safety-critical-surface)',
            border: '1px solid var(--safety-critical-border)',
            borderRadius: 'var(--radius-sm)',
            padding: '10px 14px',
            marginBottom: '16px',
            fontSize: '12px',
            color: 'var(--safety-critical)'
          }}
        >
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* Form Card */}
      <GlassCard style={{ padding: '20px', marginBottom: '20px' }}>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {mode === 'register' && (
            <>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--streeva-text-secondary)', marginBottom: '6px' }}>
                  Full Name
                </label>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    backgroundColor: 'var(--streeva-bg-deep)',
                    border: '1px solid var(--streeva-border-subtle)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '10px 14px'
                  }}
                >
                  <User size={16} color="var(--streeva-text-muted)" />
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Your Name"
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--streeva-text-primary)',
                      fontSize: '14px',
                      width: '100%',
                      outline: 'none'
                    }}
                  />
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--streeva-text-secondary)', marginBottom: '2px' }}>
                  Your Phone Number
                </label>
                <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)', marginBottom: '6px' }}>
                  Used to identify your STREEVA account. This is <strong style={{ color: 'var(--safety-medium)' }}>NOT</strong> an emergency contact.
                </div>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    backgroundColor: 'var(--streeva-bg-deep)',
                    border: '1px solid var(--streeva-border-subtle)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '10px 14px'
                  }}
                >
                  <Phone size={16} color="var(--streeva-text-muted)" />
                  <input
                    type="text"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+91 XXXXX XXXXX"
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--streeva-text-primary)',
                      fontSize: '14px',
                      width: '100%',
                      outline: 'none'
                    }}
                  />
                </div>
              </div>
            </>
          )}

          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--streeva-text-secondary)', marginBottom: '6px' }}>
              Email Address
            </label>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                backgroundColor: 'var(--streeva-bg-deep)',
                border: '1px solid var(--streeva-border-subtle)',
                borderRadius: 'var(--radius-sm)',
                padding: '10px 14px'
              }}
            >
              <Mail size={16} color="var(--streeva-text-muted)" />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@domain.com"
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--streeva-text-primary)',
                  fontSize: '14px',
                  width: '100%',
                  outline: 'none'
                }}
              />
            </div>
          </div>

          {mode !== 'forgot' && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--streeva-text-secondary)' }}>
                  Password
                </label>
                {mode === 'login' && (
                  <button
                    type="button"
                    onClick={() => setMode('forgot')}
                    style={{ background: 'none', border: 'none', fontSize: '12px', color: 'var(--streeva-intel-cyan)', cursor: 'pointer' }}
                  >
                    Forgot?
                  </button>
                )}
              </div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  backgroundColor: 'var(--streeva-bg-deep)',
                  border: '1px solid var(--streeva-border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '10px 14px'
                }}
              >
                <Lock size={16} color="var(--streeva-text-muted)" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Password"
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--streeva-text-primary)',
                    fontSize: '14px',
                    width: '100%',
                    outline: 'none'
                  }}
                />
              </div>
            </div>
          )}

          <PrimaryButton variant="primary" size="md" fullWidth={true} style={{ marginTop: '8px' }}>
            {mode === 'login' ? 'Sign In' : mode === 'register' ? 'Create Account' : 'Send Reset Link'}
          </PrimaryButton>
        </form>
      </GlassCard>

      {/* Quick Demo Access & Mode Toggles */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', textAlign: 'center' }}>
        <PrimaryButton variant="secondary" size="sm" onClick={handleDemoSignIn} fullWidth={true}>
          Quick Demo Login (BTech Review Mode)
        </PrimaryButton>

        <div style={{ fontSize: '13px', color: 'var(--streeva-text-muted)' }}>
          {mode === 'login' ? (
            <>
              Don't have an account?{' '}
              <button
                onClick={() => setMode('register')}
                style={{ background: 'none', border: 'none', color: 'var(--streeva-brand-primary)', fontWeight: 600, cursor: 'pointer' }}
              >
                Sign Up
              </button>
            </>
          ) : (
            <>
              Already have an account?{' '}
              <button
                onClick={() => setMode('login')}
                style={{ background: 'none', border: 'none', color: 'var(--streeva-brand-primary)', fontWeight: 600, cursor: 'pointer' }}
              >
                Sign In
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
