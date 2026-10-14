import React from 'react';
import { Home, Navigation, Shield, Bell, User } from 'lucide-react';
import { SOSButton } from './SOSButton';

export type NavTab = 'HOME' | 'JOURNEYS' | 'ACTIVITY' | 'PROFILE';

interface BottomNavigationProps {
  activeTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  onTriggerSOS: () => void;
  showSOS?: boolean;
}

export const BottomNavigation: React.FC<BottomNavigationProps> = ({
  activeTab,
  onSelectTab,
  onTriggerSOS,
  showSOS = true
}) => {
  const navItems: { id: NavTab; label: string; icon: React.ReactNode }[] = [
    { id: 'HOME', label: 'Home', icon: <Home size={20} /> },
    { id: 'JOURNEYS', label: 'Journeys', icon: <Navigation size={20} /> },
    { id: 'ACTIVITY', label: 'Activity', icon: <Bell size={20} /> },
    { id: 'PROFILE', label: 'Profile', icon: <User size={20} /> }
  ];

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        height: '76px',
        backgroundColor: 'rgba(11, 14, 23, 0.92)',
        backdropFilter: 'blur(20px) saturate(180%)',
        borderTop: '1px solid var(--streeva-border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-around',
        padding: '0 8px 12px 8px',
        zIndex: 90
      }}
    >
      {navItems.map((item) => {
        const isActive = activeTab === item.id;
        return (
          <button
            key={item.id}
            role="tab"
            aria-selected={isActive}
            aria-label={item.label}
            onClick={() => onSelectTab(item.id)}
            style={{
              background: 'none',
              border: 'none',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '4px',
              color: isActive ? 'var(--streeva-intel-cyan)' : 'var(--streeva-text-muted)',
              cursor: 'pointer',
              padding: '6px 12px',
              minWidth: '48px',
              minHeight: '48px',
              borderRadius: 'var(--radius-sm)',
              transition: 'all var(--transition-fast)',
              position: 'relative'
            }}
          >
            {item.icon}
            <span
              style={{
                fontSize: '11px',
                fontWeight: isActive ? 700 : 500,
                letterSpacing: '0.02em'
              }}
            >
              {item.label}
            </span>

            {isActive && (
              <span
                style={{
                  position: 'absolute',
                  bottom: '0px',
                  width: '16px',
                  height: '3px',
                  borderRadius: '2px',
                  backgroundColor: 'var(--streeva-intel-cyan)',
                  boxShadow: '0 0 8px var(--streeva-intel-cyan)'
                }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
};
