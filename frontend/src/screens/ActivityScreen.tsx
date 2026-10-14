import React from 'react';
import { useStreeva } from '../context/StreevaContext';
import { GlassCard } from '../components/GlassCard';
import {
  Bell,
  AlertTriangle,
  CheckCircle2,
  AlertOctagon,
  Wifi,
  Navigation
} from 'lucide-react';

export const ActivityScreen: React.FC = () => {
  const { notifications } = useStreeva();

  const getIcon = (type: string) => {
    switch (type) {
      case 'CRITICAL':
        return <AlertOctagon size={18} color="var(--safety-critical)" />;
      case 'ALERT':
        return <AlertTriangle size={18} color="var(--safety-high)" />;
      case 'RESTORE':
        return <CheckCircle2 size={18} color="var(--safety-low)" />;
      default:
        return <Navigation size={18} color="var(--streeva-intel-cyan)" />;
    }
  };

  return (
    <div className="streeva-screen-content" style={{ paddingBottom: '100px' }}>
      {/* Header */}
      <div style={{ marginBottom: '16px' }}>
        <h2 style={{ fontSize: '20px', fontWeight: 800, color: 'var(--streeva-text-primary)' }}>
          Activity & Safety Feed
        </h2>
        <p style={{ fontSize: '12px', color: 'var(--streeva-text-muted)' }}>
          Audit trail of journey and protection events
        </p>
      </div>

      {notifications.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--streeva-text-muted)' }}>
          <Bell size={32} style={{ opacity: 0.3, marginBottom: '8px' }} />
          <div style={{ fontSize: '14px' }}>No recent activity</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {notifications.map((item) => (
            <GlassCard
              key={item.id}
              borderGlow={item.type === 'CRITICAL' ? 'critical' : item.type === 'ALERT' ? 'high' : 'none'}
              style={{ padding: '14px' }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                <div style={{ marginTop: '2px' }}>{getIcon(item.type)}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                    <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--streeva-text-primary)' }}>
                      {item.title}
                    </div>
                    <span style={{ fontSize: '11px', color: 'var(--streeva-text-muted)' }}>
                      {item.timestamp}
                    </span>
                  </div>
                  <p style={{ fontSize: '12px', color: 'var(--streeva-text-secondary)', marginTop: '4px', lineHeight: 1.4 }}>
                    {item.message}
                  </p>
                </div>
              </div>
            </GlassCard>
          ))}
        </div>
      )}
    </div>
  );
};
