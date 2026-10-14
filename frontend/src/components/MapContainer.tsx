import React from 'react';
import { LatLngPoint, RiskLevel } from '../types/streeva';
import { MapPin, Navigation2, AlertTriangle } from 'lucide-react';

interface MapContainerProps {
  currentLocation?: LatLngPoint | null;
  routePolyline?: LatLngPoint[];
  destination?: LatLngPoint | null;
  deviationState?: 'NORMAL' | 'POSSIBLE_DEVIATION' | 'CONFIRMED_DEVIATION';
  riskLevel?: RiskLevel;
  height?: string | number;
  interactive?: boolean;
}

export const MapContainer: React.FC<MapContainerProps> = ({
  currentLocation = { lat: 12.9716, lng: 77.5946 }, // default Bengaluru sample
  routePolyline = [
    { lat: 12.9716, lng: 77.5946 },
    { lat: 12.9750, lng: 77.6000 },
    { lat: 12.9800, lng: 77.6100 },
    { lat: 12.9850, lng: 77.6200 }
  ],
  destination = { lat: 12.9850, lng: 77.6200 },
  deviationState = 'NORMAL',
  riskLevel = 'LOW',
  height = '260px'
}) => {
  // Convert lat/lng coordinates to SVG viewbox coordinates (500x300)
  const coords = routePolyline && routePolyline.length > 0 ? routePolyline : [currentLocation || { lat: 12.9716, lng: 77.5946 }];
  const lats = coords.map((p) => p.lat);
  const lngs = coords.map((p) => p.lng);

  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs);
  const maxLng = Math.max(...lngs);

  const latSpan = maxLat - minLat || 0.01;
  const lngSpan = maxLng - minLng || 0.01;

  const toSvgX = (lng: number) => {
    const norm = (lng - minLng) / lngSpan;
    return 40 + norm * 420;
  };

  const toSvgY = (lat: number) => {
    const norm = (maxLat - lat) / latSpan;
    return 40 + norm * 220;
  };

  const polylinePoints = coords.map((p) => `${toSvgX(p.lng)},${toSvgY(p.lat)}`).join(' ');

  const currX = currentLocation ? toSvgX(currentLocation.lng) : 250;
  const currY = currentLocation ? toSvgY(currentLocation.lat) : 150;

  const destX = destination ? toSvgX(destination.lng) : 460;
  const destY = destination ? toSvgY(destination.lat) : 50;

  const isDeviated = deviationState === 'CONFIRMED_DEVIATION';
  const isPossibleDeviation = deviationState === 'POSSIBLE_DEVIATION';
  const isEmergency = riskLevel === 'CRITICAL';

  return (
    <div
      style={{
        width: '100%',
        height: height,
        borderRadius: 'var(--radius-md)',
        backgroundColor: '#0A0D15',
        backgroundImage: `
          radial-gradient(#1E293B 1px, transparent 1px),
          radial-gradient(#111827 1px, #0A0D15 1px)
        `,
        backgroundSize: '24px 24px',
        border: `1px solid ${
          isEmergency
            ? 'var(--safety-critical-border)'
            : isDeviated
            ? 'var(--safety-high-border)'
            : 'var(--streeva-border-subtle)'
        }`,
        position: 'relative',
        overflow: 'hidden',
        boxShadow: isEmergency ? '0 0 25px var(--safety-critical-glow)' : 'var(--shadow-md)'
      }}
    >
      {/* Interactive / Presentation SVG Canvas */}
      <svg
        viewBox="0 0 500 300"
        style={{ width: '100%', height: '100%', display: 'block' }}
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          {/* Neon Glow filters */}
          <filter id="route-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* City Street Grid Abstraction */}
        <path
          d="M0 80 H500 M0 160 H500 M0 240 H500 M120 0 V300 M260 0 V300 M400 0 V300"
          stroke="#151C2C"
          strokeWidth="2"
        />

        {/* Expected Route Polyline */}
        <polyline
          points={polylinePoints}
          fill="none"
          stroke={isDeviated ? '#F97316' : '#6366F1'}
          strokeWidth="5"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeDasharray={isDeviated ? '8 6' : 'none'}
          filter="url(#route-glow)"
          opacity="0.9"
        />

        {/* Deviation Vector from Route if Deviated */}
        {isDeviated && (
          <line
            x1={currX - 30}
            y1={currY - 20}
            x2={currX}
            y2={currY}
            stroke="#EF4444"
            strokeWidth="2"
            strokeDasharray="4 4"
          />
        )}

        {/* Destination Marker */}
        <g transform={`translate(${destX}, ${destY})`}>
          <circle r="14" fill="#10B981" fillOpacity="0.25" />
          <circle r="6" fill="#10B981" />
        </g>

        {/* Current Position Marker with Radar Ping */}
        <g transform={`translate(${currX}, ${currY})`}>
          <circle
            r="20"
            fill={isEmergency ? '#EF4444' : isDeviated ? '#F97316' : '#06B6D4'}
            fillOpacity="0.2"
          />
          <circle
            r="9"
            fill={isEmergency ? '#EF4444' : isDeviated ? '#F97316' : '#06B6D4'}
            stroke="#FFFFFF"
            strokeWidth="2.5"
          />
        </g>
      </svg>

      {/* Map Badges / Overlays */}
      <div
        style={{
          position: 'absolute',
          top: '12px',
          left: '12px',
          display: 'flex',
          gap: '8px',
          zIndex: 10
        }}
      >
        <div
          style={{
            backgroundColor: 'rgba(15, 20, 32, 0.85)',
            backdropFilter: 'blur(8px)',
            border: '1px solid var(--streeva-border-subtle)',
            borderRadius: 'var(--radius-full)',
            padding: '4px 10px',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '11px',
            color: 'var(--streeva-intel-cyan)',
            fontWeight: 600
          }}
        >
          <Navigation2 size={12} />
          <span>GPS LIVE</span>
        </div>

        {(isDeviated || isPossibleDeviation) && (
          <div
            style={{
              backgroundColor: isDeviated ? 'rgba(239, 68, 68, 0.9)' : 'rgba(245, 158, 11, 0.9)',
              borderRadius: 'var(--radius-full)',
              padding: '4px 10px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '11px',
              color: '#FFFFFF',
              fontWeight: 700
            }}
          >
            <AlertTriangle size={12} />
            <span>{isDeviated ? 'ROUTE DEVIATED' : 'CHECKING ROUTE'}</span>
          </div>
        )}
      </div>

      {/* Destination label overlay */}
      <div
        style={{
          position: 'absolute',
          bottom: '10px',
          right: '12px',
          backgroundColor: 'rgba(15, 20, 32, 0.85)',
          backdropFilter: 'blur(8px)',
          border: '1px solid var(--streeva-border-subtle)',
          borderRadius: 'var(--radius-sm)',
          padding: '4px 8px',
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          fontSize: '11px',
          color: 'var(--streeva-text-primary)'
        }}
      >
        <MapPin size={12} color="var(--safety-low)" />
        <span>Destination</span>
      </div>
    </div>
  );
};
