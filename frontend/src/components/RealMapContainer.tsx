import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { LatLngPoint, RiskLevel } from '../types/streeva';
import { Navigation2, AlertTriangle, RefreshCw, AlertCircle, MapPin } from 'lucide-react';

interface RealMapContainerProps {
  sourceLocation?: LatLngPoint | null;
  destinationLocation?: LatLngPoint | null;
  routePolyline?: LatLngPoint[];
  currentPosition?: LatLngPoint | null;
  deviationState?: 'NORMAL' | 'POSSIBLE_DEVIATION' | 'CONFIRMED_DEVIATION';
  riskLevel?: RiskLevel;
  height?: string | number;
  isLoading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  interactive?: boolean;
}

export const RealMapContainer: React.FC<RealMapContainerProps> = ({
  sourceLocation,
  destinationLocation,
  routePolyline = [],
  currentPosition,
  deviationState = 'NORMAL',
  riskLevel = 'LOW',
  height = '280px',
  isLoading = false,
  error = null,
  onRetry,
  interactive = true
}) => {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);
  const polylineLayerRef = useRef<L.Polyline | null>(null);
  const sourceMarkerRef = useRef<L.CircleMarker | null>(null);
  const destMarkerRef = useRef<L.CircleMarker | null>(null);
  const currentPosMarkerRef = useRef<L.CircleMarker | null>(null);

  const [mapReady, setMapReady] = useState(false);
  const [tileError, setTileError] = useState(false);

  const isDeviated = deviationState === 'CONFIRMED_DEVIATION';
  const isPossibleDeviation = deviationState === 'POSSIBLE_DEVIATION';
  const isEmergency = riskLevel === 'CRITICAL';

  // 1. Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current) return;
    if (mapInstanceRef.current) return; // already initialized

    // Default center (source or tech corridor)
    const initialCenter: [number, number] = sourceLocation
      ? [sourceLocation.lat, sourceLocation.lng]
      : [12.9716, 77.5946];

    const map = L.map(mapContainerRef.current, {
      center: initialCenter,
      zoom: 13,
      zoomControl: false,
      attributionControl: false,
      dragging: interactive,
      touchZoom: interactive,
      scrollWheelZoom: false,
      doubleClickZoom: interactive
    });

    // Clean Tile Provider configuration:
    // OpenStreetMap standard tile server (public, standard, keyless, zero watermarks)
    // Respects optional VITE_MAP_TILE_URL and VITE_MAP_API_KEY if configured in environment
    const envTileUrl = (import.meta as any).env?.VITE_MAP_TILE_URL;
    const envApiKey = (import.meta as any).env?.VITE_MAP_API_KEY;

    let tileUrl = envTileUrl || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
    if (envApiKey && tileUrl.includes('{apiKey}')) {
      tileUrl = tileUrl.replace('{apiKey}', envApiKey);
    }

    const osmTileLayer = L.tileLayer(tileUrl, {
      maxZoom: 19,
      minZoom: 2,
      className: 'streeva-osm-tiles'
    });

    osmTileLayer.on('tileerror', () => {
      setTileError(true);
    });

    osmTileLayer.addTo(map);
    tileLayerRef.current = osmTileLayer;

    mapInstanceRef.current = map;
    setMapReady(true);

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // 2. Render Markers, Polyline, and Viewport Fit whenever props change
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !mapReady) return;

    // A. Update Route Polyline
    if (polylineLayerRef.current) {
      polylineLayerRef.current.remove();
      polylineLayerRef.current = null;
    }

    if (routePolyline && routePolyline.length > 0) {
      const latLngs: [number, number][] = routePolyline.map((p) => [p.lat, p.lng]);

      const polylineColor = isEmergency
        ? '#EF4444'
        : isDeviated
        ? '#F97316'
        : '#6366F1';

      const polyline = L.polyline(latLngs, {
        color: polylineColor,
        weight: 5,
        opacity: 0.95,
        dashArray: isDeviated ? '8, 8' : undefined,
        lineCap: 'round',
        lineJoin: 'round'
      }).addTo(map);

      polylineLayerRef.current = polyline;
    }

    // B. Source Marker
    if (sourceMarkerRef.current) {
      sourceMarkerRef.current.remove();
      sourceMarkerRef.current = null;
    }
    if (sourceLocation) {
      const sourceMarker = L.circleMarker([sourceLocation.lat, sourceLocation.lng], {
        radius: 7,
        color: '#FFFFFF',
        fillColor: '#6366F1',
        fillOpacity: 1.0,
        weight: 2
      }).addTo(map);
      sourceMarkerRef.current = sourceMarker;
    }

    // C. Destination Marker
    if (destMarkerRef.current) {
      destMarkerRef.current.remove();
      destMarkerRef.current = null;
    }
    if (destinationLocation) {
      const destMarker = L.circleMarker([destinationLocation.lat, destinationLocation.lng], {
        radius: 8,
        color: '#FFFFFF',
        fillColor: '#10B981',
        fillOpacity: 1.0,
        weight: 2.5
      }).addTo(map);
      destMarkerRef.current = destMarker;
    }

    // D. Live Current Position Marker
    if (currentPosMarkerRef.current) {
      currentPosMarkerRef.current.remove();
      currentPosMarkerRef.current = null;
    }
    if (currentPosition) {
      const posMarker = L.circleMarker([currentPosition.lat, currentPosition.lng], {
        radius: 9,
        color: '#FFFFFF',
        fillColor: isEmergency ? '#EF4444' : isDeviated ? '#F97316' : '#06B6D4',
        fillOpacity: 1.0,
        weight: 3
      }).addTo(map);
      currentPosMarkerRef.current = posMarker;
    }

    // E. Viewport Fit: Ensure both endpoints and route are fully visible
    try {
      const pointsToFit: [number, number][] = [];
      if (routePolyline && routePolyline.length > 0) {
        routePolyline.forEach((p) => pointsToFit.push([p.lat, p.lng]));
      }
      if (sourceLocation) {
        pointsToFit.push([sourceLocation.lat, sourceLocation.lng]);
      }
      if (destinationLocation) {
        pointsToFit.push([destinationLocation.lat, destinationLocation.lng]);
      }

      if (pointsToFit.length >= 2) {
        const bounds = L.latLngBounds(pointsToFit);
        if (bounds.isValid()) {
          map.fitBounds(bounds, {
            padding: [30, 30],
            maxZoom: 16,
            animate: true
          });
        }
      } else if (pointsToFit.length === 1) {
        map.setView(pointsToFit[0], 13);
      }
    } catch (err) {
      console.warn('fitBounds error:', err);
    }
  }, [mapReady, routePolyline, sourceLocation, destinationLocation, currentPosition, isDeviated, isEmergency]);

  const handleTileRetry = () => {
    setTileError(false);
    if (mapInstanceRef.current && tileLayerRef.current) {
      tileLayerRef.current.redraw();
    }
    if (onRetry) onRetry();
  };

  return (
    <div
      style={{
        width: '100%',
        height: height,
        borderRadius: 'var(--radius-md)',
        backgroundColor: '#07090E',
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
      {/* Real Leaflet Map Container DOM */}
      <div
        ref={mapContainerRef}
        className="streeva-map-tiles"
        style={{
          width: '100%',
          height: '100%',
          zIndex: 1
        }}
      />

      {/* Loading Overlay */}
      {isLoading && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            backgroundColor: 'rgba(7, 9, 14, 0.85)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '10px',
            zIndex: 20
          }}
        >
          <RefreshCw size={24} color="var(--streeva-intel-cyan)" style={{ animation: 'spin 1s linear infinite' }} />
          <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--streeva-text-primary)' }}>
            Calculating safe route...
          </div>
          <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)' }}>
            Fetching turn-by-turn road network geometry
          </div>
        </div>
      )}

      {/* Clean Application-Level Error Overlay (Section 8) */}
      {(error || tileError) && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            backgroundColor: 'rgba(15, 20, 32, 0.92)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
            textAlign: 'center',
            gap: '8px',
            zIndex: 20
          }}
        >
          <AlertCircle size={24} color="var(--safety-high)" />
          <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--streeva-text-primary)' }}>
            {tileError ? 'Map unavailable' : 'Route Calculation Notice'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--streeva-text-muted)', maxWidth: '260px' }}>
            {tileError
              ? 'Unable to load base map tiles. Please check your connection and retry.'
              : error}
          </div>
          <button
            onClick={tileError ? handleTileRetry : onRetry}
            style={{
              marginTop: '6px',
              backgroundColor: 'var(--streeva-surface-card)',
              border: '1px solid var(--streeva-border-subtle)',
              color: 'var(--streeva-intel-cyan)',
              borderRadius: 'var(--radius-sm)',
              padding: '6px 14px',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            Retry
          </button>
        </div>
      )}

      {/* STREEVA HUD Overlays on Map */}
      <div
        style={{
          position: 'absolute',
          top: '10px',
          left: '10px',
          display: 'flex',
          gap: '6px',
          zIndex: 10
        }}
      >
        <div
          style={{
            backgroundColor: 'rgba(11, 14, 23, 0.85)',
            backdropFilter: 'blur(10px)',
            border: '1px solid var(--streeva-border-subtle)',
            borderRadius: 'var(--radius-full)',
            padding: '4px 10px',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '11px',
            color: 'var(--streeva-intel-cyan)',
            fontWeight: 700
          }}
        >
          <Navigation2 size={12} />
          <span>OPENSTREETMAP LIVE</span>
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

      {/* Map Legend / Required Attribution Overlay (Section 7 & 18) */}
      <div
        style={{
          position: 'absolute',
          bottom: '8px',
          right: '8px',
          backgroundColor: 'rgba(7, 9, 14, 0.75)',
          backdropFilter: 'blur(6px)',
          borderRadius: '4px',
          padding: '2px 8px',
          fontSize: '10px',
          color: 'var(--streeva-text-muted)',
          zIndex: 10,
          pointerEvents: 'auto'
        }}
      >
        © <a
          href="https://www.openstreetmap.org/copyright"
          target="_blank"
          rel="noreferrer"
          style={{ color: 'var(--streeva-intel-cyan)', textDecoration: 'none' }}
        >
          OpenStreetMap
        </a> contributors
      </div>
    </div>
  );
};
