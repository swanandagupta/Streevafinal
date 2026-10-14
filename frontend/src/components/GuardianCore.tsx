import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { RiskLevel } from '../types/streeva';

interface GuardianCoreProps {
  riskLevel?: RiskLevel;
  size?: number; // width & height in px
  showLabel?: boolean;
  interactive?: boolean;
}

export const GuardianCore: React.FC<GuardianCoreProps> = ({
  riskLevel = 'LOW',
  size = 180,
  showLabel = false,
  interactive = false
}) => {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const [hasWebGL, setHasWebGL] = useState(true);

  // Color mapping based on STREEVA Safety Spectrum
  const getColorHex = (level: RiskLevel): number => {
    switch (level) {
      case 'LOW':
        return 0x10b981; // Mint / Teal
      case 'MEDIUM':
        return 0xf59e0b; // Amber
      case 'HIGH':
        return 0xf97316; // Coral / Orange
      case 'CRITICAL':
        return 0xef4444; // Crimson
      case 'UNKNOWN':
        return 0x8b5cf6; // Desaturated Violet
      case 'DEGRADED':
        return 0x6b7280; // Muted Charcoal / Grey
      default:
        return 0x10b981;
    }
  };

  const getSpeedMultiplier = (level: RiskLevel): number => {
    switch (level) {
      case 'LOW':
        return 0.65; // Serene, gentle, continuously aware
      case 'MEDIUM':
        return 1.2;
      case 'HIGH':
        return 1.8;
      case 'CRITICAL':
        return 3.0;
      case 'UNKNOWN':
      case 'DEGRADED':
        return 0.45;
      default:
        return 0.7;
    }
  };

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    // Check WebGL availability
    try {
      const canvas = document.createElement('canvas');
      const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
      if (!gl) {
        setHasWebGL(false);
        return;
      }
    } catch {
      setHasWebGL(false);
      return;
    }

    // Three.js Scene Setup
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
    // Optimized camera distance so the wireframe and inner core appear full and detailed
    camera.position.z = 4.85;

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(size, size);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.domElement.style.display = 'block';
    renderer.domElement.style.pointerEvents = 'none';
    container.appendChild(renderer.domElement);

    const group = new THREE.Group();
    scene.add(group);

    const colorHex = getColorHex(riskLevel);
    const primaryColor = new THREE.Color(colorHex);

    // 1. Inner Core: Luminous Icosahedron
    const coreGeometry = new THREE.IcosahedronGeometry(0.92, 2);
    const coreMaterial = new THREE.MeshStandardMaterial({
      color: primaryColor,
      emissive: primaryColor,
      emissiveIntensity: riskLevel === 'CRITICAL' ? 0.9 : 0.55,
      roughness: 0.15,
      metalness: 0.85,
      wireframe: riskLevel === 'UNKNOWN' || riskLevel === 'DEGRADED'
    });
    const coreMesh = new THREE.Mesh(coreGeometry, coreMaterial);
    group.add(coreMesh);

    // 2. Middle Wireframe Lattice Cage (exact geometric mesh from splash)
    const cageGeometry = new THREE.IcosahedronGeometry(1.24, 1);
    const cageMaterial = new THREE.MeshBasicMaterial({
      color: primaryColor,
      wireframe: true,
      transparent: true,
      opacity: riskLevel === 'DEGRADED' ? 0.25 : 0.65
    });
    const cageMesh = new THREE.Mesh(cageGeometry, cageMaterial);
    group.add(cageMesh);

    // 3. Orbital Ring (Scaled so it glides smoothly without edge clipping)
    const ringGeometry = new THREE.TorusGeometry(1.48, 0.025, 16, 100);
    const ringMaterial = new THREE.MeshBasicMaterial({
      color: primaryColor,
      transparent: true,
      opacity: riskLevel === 'CRITICAL' ? 0.9 : 0.55
    });
    const ringMesh = new THREE.Mesh(ringGeometry, ringMaterial);
    ringMesh.rotation.x = Math.PI / 3;
    group.add(ringMesh);

    // 4. Secondary Counter-Orbital Ring (for HIGH & CRITICAL states)
    let ringMesh2: THREE.Mesh | null = null;
    if (riskLevel === 'HIGH' || riskLevel === 'CRITICAL') {
      const ringGeometry2 = new THREE.TorusGeometry(1.62, 0.02, 16, 100);
      ringMesh2 = new THREE.Mesh(ringGeometry2, ringMaterial);
      ringMesh2.rotation.x = -Math.PI / 4;
      ringMesh2.rotation.y = Math.PI / 4;
      group.add(ringMesh2);
    }

    // Ambient & Point Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.65);
    scene.add(ambientLight);

    const pointLight = new THREE.PointLight(colorHex, 2.8, 10);
    pointLight.position.set(1.5, 2.5, 3.5);
    scene.add(pointLight);

    // Animation Loop
    let animationFrameId: number;
    let clock = new THREE.Clock();

    const speed = getSpeedMultiplier(riskLevel);

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      const elapsedTime = clock.getElapsedTime() * speed;

      // Gentle, smooth, continuous rotations
      coreMesh.rotation.x = elapsedTime * 0.2;
      coreMesh.rotation.y = elapsedTime * 0.32;

      cageMesh.rotation.x = -elapsedTime * 0.15;
      cageMesh.rotation.y = -elapsedTime * 0.24;

      ringMesh.rotation.z = elapsedTime * 0.35;
      if (ringMesh2) {
        ringMesh2.rotation.z = -elapsedTime * 0.5;
      }

      // Subtle, alive breathing oscillation
      let scale = 1.0;
      if (riskLevel === 'CRITICAL') {
        // Rapid focused emergency pulse
        scale = 1.0 + Math.sin(elapsedTime * 5.5) * 0.1;
      } else if (riskLevel === 'LOW') {
        // Calm, deep, subtle meditative breath
        scale = 1.0 + Math.sin(elapsedTime * 1.3) * 0.045;
      } else if (riskLevel === 'MEDIUM') {
        scale = 1.0 + Math.sin(elapsedTime * 2.0) * 0.06;
      } else if (riskLevel === 'HIGH') {
        scale = 1.0 + Math.sin(elapsedTime * 3.2) * 0.08;
      } else {
        // Muted drift
        scale = 0.96 + Math.sin(elapsedTime * 0.8) * 0.03;
      }

      coreMesh.scale.set(scale, scale, scale);
      renderer.render(scene, camera);
    };

    animate();

    return () => {
      cancelAnimationFrame(animationFrameId);
      renderer.dispose();
      coreGeometry.dispose();
      coreMaterial.dispose();
      cageGeometry.dispose();
      cageMaterial.dispose();
      ringGeometry.dispose();
      ringMaterial.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [riskLevel, size]);

  const getStatusLabel = (level: RiskLevel): string => {
    switch (level) {
      case 'LOW':
        return 'Guardian Watching • Low Risk';
      case 'MEDIUM':
        return 'Guardian Alert • Unusual Activity';
      case 'HIGH':
        return 'Elevated Monitoring • Multiple Signals';
      case 'CRITICAL':
        return 'EMERGENCY FOCUS • Action Required';
      case 'UNKNOWN':
        return 'Telemetry Incomplete';
      case 'DEGRADED':
        return 'Limited Data • Operating Local';
      default:
        return 'Active';
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
      <div
        ref={mountRef}
        style={{
          width: size,
          height: size,
          position: 'relative',
          cursor: interactive ? 'pointer' : 'default',
          pointerEvents: interactive ? 'auto' : 'none',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          filter: `drop-shadow(0 0 ${Math.max(8, Math.round(size * 0.1))}px ${
            riskLevel === 'CRITICAL'
              ? 'rgba(239, 68, 68, 0.5)'
              : riskLevel === 'LOW'
              ? 'rgba(16, 185, 129, 0.4)'
              : riskLevel === 'HIGH'
              ? 'rgba(249, 115, 22, 0.4)'
              : 'rgba(245, 158, 11, 0.4)'
          })`,
          transition: 'filter var(--transition-normal)'
        }}
      >
        {!hasWebGL && (
          // Graceful CSS Fallback Orb
          <div
            style={{
              width: size * 0.7,
              height: size * 0.7,
              borderRadius: '50%',
              background: `radial-gradient(circle, ${
                riskLevel === 'CRITICAL'
                  ? '#EF4444'
                  : riskLevel === 'LOW'
                  ? '#10B981'
                  : riskLevel === 'MEDIUM'
                  ? '#F59E0B'
                  : riskLevel === 'HIGH'
                  ? '#F97316'
                  : '#8B5CF6'
              } 0%, rgba(11, 14, 23, 0.4) 70%)`,
              boxShadow: `0 0 35px ${
                riskLevel === 'CRITICAL' ? 'rgba(239, 68, 68, 0.6)' : 'rgba(99, 102, 241, 0.4)'
              }`,
              animation: riskLevel === 'CRITICAL' ? 'pulse-critical 1s infinite' : 'pulse-calm 3s infinite'
            }}
          />
        )}
      </div>

      {showLabel && (
        <div
          style={{
            marginTop: 8,
            fontSize: 12,
            fontWeight: 600,
            letterSpacing: '0.05em',
            textTransform: 'uppercase',
            color:
              riskLevel === 'CRITICAL'
                ? '#EF4444'
                : riskLevel === 'LOW'
                ? '#10B981'
                : riskLevel === 'MEDIUM'
                ? '#F59E0B'
                : riskLevel === 'HIGH'
                ? '#F97316'
                : '#94A3B8'
          }}
        >
          {getStatusLabel(riskLevel)}
        </div>
      )}
    </div>
  );
};
