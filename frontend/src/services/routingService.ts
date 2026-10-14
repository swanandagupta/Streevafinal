/**
 * STREEVA Routing & Geocoding Service
 * Uses OpenStreetMap (OSRM for routing, Nominatim for geocoding).
 * Provides the single Canonical Route Object consumed by both the Frontend Map and Phase 2 backend.
 */

import type { LatLngPoint, CanonicalLocation, LocationState } from '../types/streeva.ts';

export interface RouteSearchResult {
  display_name: string;
  lat: number;
  lng: number;
  place_id?: number | string;
}

export interface CanonicalRoute {
  source: {
    lat: number;
    lng: number;
    name: string;
    display_name?: string;
    source?: string;
  };
  destination: {
    lat: number;
    lng: number;
    name: string;
    display_name?: string;
    source?: string;
  };
  polyline: LatLngPoint[];
  distance_m: number;
  duration_s: number;
  provider: 'OSRM_OPENSTREETMAP' | 'DEMO_FIXTURE';
  is_demo: boolean;
}

export type RouteStatus = 'IDLE' | 'CALCULATING' | 'READY' | 'FAILED' | 'OFFLINE';

class RoutingService {
  private osrmBaseUrl = 'https://router.project-osrm.org/route/v1/driving';
  private nominatimBaseUrl = 'https://nominatim.openstreetmap.org/search';
  private nominatimReverseUrl = 'https://nominatim.openstreetmap.org/reverse';

  /**
   * Searches OpenStreetMap Nominatim for locations (used for both FROM and TO).
   * Resolves to canonical location objects with coordinates, display name, and source.
   */
  public async searchLocations(query: string): Promise<CanonicalLocation[]> {
    if (!query || query.trim().length < 2) return [];

    try {
      const url = `${this.nominatimBaseUrl}?format=json&q=${encodeURIComponent(query)}&limit=5&addressdetails=1`;
      const response = await fetch(url, {
        headers: {
          'Accept': 'application/json',
          'User-Agent': 'STREEVA-Safety-App/1.0'
        }
      });

      if (!response.ok) {
        throw new Error(`Nominatim geocoding error: ${response.statusText}`);
      }

      const data = await response.json();
      return data.map((item: any) => ({
        display_name: item.display_name,
        latitude: parseFloat(item.lat),
        longitude: parseFloat(item.lon),
        address: item.display_name,
        source: 'OSM_NOMINATIM_SEARCH' as const
      }));
    } catch (err) {
      console.warn('Nominatim geocoding search failed:', err);
      return [];
    }
  }

  /**
   * Backward-compatible alias for destination search.
   */
  public async searchDestinations(query: string): Promise<RouteSearchResult[]> {
    const locations = await this.searchLocations(query);
    return locations.map((loc) => ({
      display_name: loc.display_name,
      lat: loc.latitude,
      lng: loc.longitude
    }));
  }

  /**
   * Reverse geocodes coordinates to a human-readable place name using OpenStreetMap.
   */
  public async reverseGeocode(lat: number, lng: number): Promise<string | null> {
    try {
      const url = `${this.nominatimReverseUrl}?format=json&lat=${lat}&lon=${lng}`;
      const response = await fetch(url, {
        headers: {
          'Accept': 'application/json',
          'User-Agent': 'STREEVA-Safety-App/1.0'
        }
      });
      if (!response.ok) return null;
      const data = await response.json();
      return data.display_name || null;
    } catch {
      return null;
    }
  }

  /**
   * Validates and resolves the real device GPS into a CanonicalLocation object.
   * Handles: permission denied, unavailable, acquiring/loading, invalid 0,0 coords.
   */
  public resolveCurrentLocation(locationState: LocationState): CanonicalLocation {
    if (locationState.status === 'DENIED') {
      throw new Error('GPS permission denied. Please enable location permissions or search for a starting location.');
    }
    if (locationState.status === 'UNAVAILABLE') {
      throw new Error('Device location is unavailable. Please check your GPS signal or enter a starting location.');
    }
    if (locationState.status === 'ACQUIRING' && !locationState.coords) {
      throw new Error('Acquiring device GPS... Please wait a moment or search manually.');
    }
    if (!locationState.coords) {
      throw new Error('No GPS coordinates acquired.');
    }

    const { lat, lng } = locationState.coords;
    if (lat === 0 && lng === 0) {
      throw new Error('Invalid GPS coordinates (0, 0 received).');
    }

    const accuracyText = locationState.accuracy_m
      ? ` (±${Math.round(locationState.accuracy_m)}m)`
      : '';

    return {
      display_name: `Current Location${accuracyText}`,
      latitude: lat,
      longitude: lng,
      source: 'GPS_CURRENT_LOCATION',
      accuracy_m: locationState.accuracy_m
    };
  }

  /**
   * Calculates a real road network route using OpenStreetMap OSRM.
   * Returns the single Canonical Route Object with real polyline, distance, and duration.
   */
  public async calculateRoute(params: {
    source: CanonicalLocation | { lat: number; lng: number; name?: string; display_name?: string; source?: string };
    destination: CanonicalLocation | { lat: number; lng: number; name?: string; display_name?: string; source?: string };
    isOffline?: boolean;
    isDemoMode?: boolean;
  }): Promise<CanonicalRoute> {
    const { source, destination, isOffline, isDemoMode } = params;

    const srcLat = 'latitude' in source ? source.latitude : source.lat;
    const srcLng = 'longitude' in source ? source.longitude : source.lng;
    const srcName = ('display_name' in source && source.display_name ? source.display_name : ('name' in source && source.name ? source.name : `${srcLat.toFixed(4)}, ${srcLng.toFixed(4)}`));
    const srcSource = 'source' in source && source.source ? source.source : 'USER_INPUT';

    const destLat = 'latitude' in destination ? destination.latitude : destination.lat;
    const destLng = 'longitude' in destination ? destination.longitude : destination.lng;
    const destName = ('display_name' in destination && destination.display_name ? destination.display_name : ('name' in destination && destination.name ? destination.name : `${destLat.toFixed(4)}, ${destLng.toFixed(4)}`));
    const destSource = 'source' in destination && destination.source ? destination.source : 'USER_INPUT';

    if (srcLat === 0 && srcLng === 0) {
      throw new Error('INVALID_COORDINATES: Source coordinates cannot be 0, 0.');
    }
    if (destLat === 0 && destLng === 0) {
      throw new Error('INVALID_COORDINATES: Destination coordinates cannot be 0, 0.');
    }

    if (isOffline) {
      throw new Error('OFFLINE_NO_ROUTE: Cannot calculate online route while offline.');
    }

    if (isDemoMode) {
      return this.getDemoFixtureRoute(
        { lat: srcLat, lng: srcLng, name: srcName, source: srcSource },
        { lat: destLat, lng: destLng, name: destName, source: destSource }
      );
    }

    try {
      const coordinates = `${srcLng},${srcLat};${destLng},${destLat}`;
      const url = `${this.osrmBaseUrl}/${coordinates}?overview=full&geometries=geojson`;

      const response = await fetch(url, {
        headers: {
          'Accept': 'application/json',
          'User-Agent': 'STREEVA-Safety-App/1.0'
        }
      });

      if (!response.ok) {
        throw new Error(`OSRM routing HTTP error ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      if (!data.routes || data.routes.length === 0) {
        throw new Error('OSRM_NO_ROUTE: No road network route found between these coordinates.');
      }

      const primaryRoute = data.routes[0];
      // OSRM returns coordinates as [lng, lat]
      const polylinePoints: LatLngPoint[] = primaryRoute.geometry.coordinates.map((coord: [number, number]) => ({
        lat: coord[1],
        lng: coord[0]
      }));

      return {
        source: {
          lat: srcLat,
          lng: srcLng,
          name: srcName,
          display_name: srcName,
          source: srcSource
        },
        destination: {
          lat: destLat,
          lng: destLng,
          name: destName,
          display_name: destName,
          source: destSource
        },
        polyline: polylinePoints,
        distance_m: Math.round(primaryRoute.distance),
        duration_s: Math.round(primaryRoute.duration),
        provider: 'OSRM_OPENSTREETMAP',
        is_demo: false
      };
    } catch (err: any) {
      console.warn('Live OSRM routing failed, evaluating fallback:', err.message);
      // If live network routing failed (e.g. test environment or network timeout), generate geodesic corridor
      return this.getDemoFixtureRoute(
        { lat: srcLat, lng: srcLng, name: srcName, source: srcSource },
        { lat: destLat, lng: destLng, name: destName, source: destSource }
      );
    }
  }

  /**
   * Deterministic geodesic fixture route for offline/test environments (explicitly labelled).
   * Dynamically calculates true Haversine distance and waypoints between ANY two coordinates.
   */
  public getDemoFixtureRoute(
    source: { lat: number; lng: number; name?: string; source?: string },
    destination: { lat: number; lng: number; name?: string; source?: string }
  ): CanonicalRoute {
    const latSpan = destination.lat - source.lat;
    const lngSpan = destination.lng - source.lng;

    // Generate 12 deterministic corridor waypoints following the vector
    const polyline: LatLngPoint[] = [];
    for (let i = 0; i <= 12; i++) {
      const frac = i / 12;
      const curve = Math.sin(frac * Math.PI) * 0.002;
      polyline.push({
        lat: Number((source.lat + latSpan * frac + curve).toFixed(6)),
        lng: Number((source.lng + lngSpan * frac - curve).toFixed(6))
      });
    }

    // Haversine approximation for distance
    const R = 6371000;
    const dLat = (destination.lat - source.lat) * (Math.PI / 180);
    const dLng = (destination.lng - source.lng) * (Math.PI / 180);
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(source.lat * (Math.PI / 180)) *
        Math.cos(destination.lat * (Math.PI / 180)) *
        Math.sin(dLng / 2) *
        Math.sin(dLng / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    const distM = Math.max(Math.round(R * c * 1.25), 100); // 1.25 road winding factor, minimum 100m
    const durS = Math.max(Math.round(distM / 1.3), 60); // 1.3 m/s urban pace, minimum 60s

    const srcName = source.name || `${source.lat.toFixed(4)}, ${source.lng.toFixed(4)}`;
    const destName = destination.name || `${destination.lat.toFixed(4)}, ${destination.lng.toFixed(4)}`;

    return {
      source: {
        lat: source.lat,
        lng: source.lng,
        name: srcName,
        display_name: srcName,
        source: source.source || 'USER_INPUT'
      },
      destination: {
        lat: destination.lat,
        lng: destination.lng,
        name: destName,
        display_name: destName,
        source: destination.source || 'USER_INPUT'
      },
      polyline,
      distance_m: distM,
      duration_s: durS,
      provider: 'DEMO_FIXTURE',
      is_demo: true
    };
  }
}

export const routingService = new RoutingService();
