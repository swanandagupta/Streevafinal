import React, { useState } from 'react';
import { AlertOctagon } from 'lucide-react';

interface SOSButtonProps {
  onTriggerSOS: () => void;
  size?: 'sm' | 'md' | 'lg';
  compact?: boolean;
}

export const SOSButton: React.FC<SOSButtonProps> = ({
  onTriggerSOS,
  size = 'md',
  compact = false
}) => {
  const [isPressing, setIsPressing] = useState(false);

  const handleClick = () => {
    // Immediate activation of Manual SOS
    onTriggerSOS();
  };

  const getDimensions = () => {
    if (compact) {
      return { width: '46px', height: '46px', fontSize: '12px', iconSize: 20 };
    }
    switch (size) {
      case 'sm':
        return { width: '56px', height: '56px', fontSize: '13px', iconSize: 22 };
      case 'md':
        return { width: '68px', height: '68px', fontSize: '15px', iconSize: 26 };
      case 'lg':
        return { width: '84px', height: '84px', fontSize: '18px', iconSize: 32 };
    }
  };

  const dims = getDimensions();

  return (
    <button
      onClick={handleClick}
      onMouseDown={() => setIsPressing(true)}
      onMouseUp={() => setIsPressing(false)}
      onTouchStart={() => setIsPressing(true)}
      onTouchEnd={() => setIsPressing(false)}
      aria-label="Emergency SOS — Hold or press to trigger emergency response"
      style={{
        width: dims.width,
        height: dims.height,
        borderRadius: '50%',
        background: 'radial-gradient(circle at 35% 35%, #EF4444 0%, #991B1B 90%)',
        border: '2px solid rgba(255, 255, 255, 0.4)',
        boxShadow: isPressing
          ? '0 0 45px rgba(239, 68, 68, 0.95), inset 0 0 15px rgba(0, 0, 0, 0.5)'
          : '0 0 25px rgba(239, 68, 68, 0.65), 0 6px 16px rgba(0, 0, 0, 0.5)',
        color: '#FFFFFF',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: compact ? '0' : '2px',
        fontWeight: 800,
        fontFamily: 'var(--font-sans)',
        letterSpacing: '0.06em',
        cursor: 'pointer',
        transform: isPressing ? 'scale(0.92)' : 'scale(1)',
        transition: 'all 120ms cubic-bezier(0.4, 0, 0.2, 1)',
        zIndex: 100,
        userSelect: 'none',
        outline: 'none'
      }}
    >
      <AlertOctagon size={dims.iconSize} color="#FFFFFF" strokeWidth={2.5} />
      {!compact && <span style={{ fontSize: dims.fontSize }}>SOS</span>}
    </button>
  );
};
