'use client';

/**
 * AETHERA v27.0 — shared Three.js scene scaffold.
 *
 * Provides the dark-space Canvas, lighting, OrbitControls, an error
 * boundary with a non-WebGL fallback, and small shared helpers used by
 * every 3D scenario view. The visual language matches the platform
 * theme: near-black space, #00ff88 accent, monospace HUD.
 */

import { Component, Suspense, useState, type ReactNode } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Html } from '@react-three/drei';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';

export const ACCENT = '#00ff88';
export const DIM = '#1c2a38';
export const GRID = 'rgba(0,255,136,0.08)';

/**
 * Diverging blue → dark → red scale for legacy-deviation heatmaps.
 * Blue = under-expanded (legacy shrinks), red = over-expanded (legacy
 * inflates). Pure blue↔red — no green in the path, so red always means
 * "inflated" at any magnitude.
 */
export function heatColor(t: number): string {
  const clamped = Math.max(0, Math.min(1, Number.isFinite(t) ? t : 0.5));
  const stops: [number, [number, number, number]][] = [
    [0.0, [56, 130, 246]],   // blue — under-expanded
    [0.25, [6, 182, 212]],   // cyan
    [0.5, [13, 17, 23]],     // dark neutral
    [0.75, [249, 115, 34]],  // orange
    [1.0, [255, 59, 59]],    // red — over-expanded
  ];
  for (let i = 0; i < stops.length - 1; i++) {
    const [t0, c0] = stops[i];
    const [t1, c1] = stops[i + 1];
    if (clamped >= t0 && clamped <= t1) {
      const f = t1 === t0 ? 0 : (clamped - t0) / (t1 - t0);
      const c = c0.map((v, k) => Math.round(v + f * (c1[k] - v)));
      return `rgb(${c[0]},${c[1]},${c[2]})`;
    }
  }
  return ACCENT;
}

/** Single-hue green ramp for true-area heatmaps (small → dark, large → neon). */
export function areaColor(t: number): string {
  const clamped = Math.max(0, Math.min(1, Number.isFinite(t) ? t : 0));
  const c0 = [13, 48, 36];   // deep green-black
  const c1 = [0, 255, 136];  // neon accent
  const c = c0.map((v, k) => Math.round(v + clamped * (c1[k] - v)));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

export function heatColorHex(t: number): [number, number, number] {
  const m = heatColor(t).match(/\d+/g);
  return m
    ? [Number(m[0]) / 255, Number(m[1]) / 255, Number(m[2]) / 255]
    : [0, 1, 0.53];
}

export function areaColorHex(t: number): [number, number, number] {
  const m = areaColor(t).match(/\d+/g);
  return m
    ? [Number(m[0]) / 255, Number(m[1]) / 255, Number(m[2]) / 255]
    : [0, 1, 0.53];
}

/** Simple 3D force-directed layout for small graphs (deterministic). */
export function springLayout3d(
  nodes: string[],
  edges: [string, string][],
  iterations = 120,
  radius = 5,
): Record<string, [number, number, number]> {
  const idx = new Map(nodes.map((n, i) => [n, i]));
  const pos: [number, number, number][] = nodes.map((_, i) => {
    // Deterministic golden-angle spiral seed.
    const ga = i * 2.399963;
    const r = radius * (0.3 + 0.7 * ((i + 1) / (nodes.length + 1)));
    return [r * Math.cos(ga), r * Math.sin(ga * 1.7), r * Math.sin(ga)];
  });
  const k = (radius * 2) / Math.cbrt(nodes.length || 1);
  for (let it = 0; it < iterations; it++) {
    const force: [number, number, number][] = nodes.map(() => [0, 0, 0]);
    // Repulsion
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        let dx = pos[i][0] - pos[j][0];
        let dy = pos[i][1] - pos[j][1];
        let dz = pos[i][2] - pos[j][2];
        let d2 = dx * dx + dy * dy + dz * dz;
        if (d2 < 1e-6) {
          dx = 0.01 * (i + 1); dy = 0.01; dz = 0.01 * (j + 1);
          d2 = dx * dx + dy * dy + dz * dz;
        }
        const f = (k * k) / d2;
        const d = Math.sqrt(d2);
        const ux = (dx / d) * f, uy = (dy / d) * f, uz = (dz / d) * f;
        force[i][0] += ux; force[i][1] += uy; force[i][2] += uz;
        force[j][0] -= ux; force[j][1] -= uy; force[j][2] -= uz;
      }
    }
    // Attraction along edges
    for (const [a, b] of edges) {
      const i = idx.get(a);
      const j = idx.get(b);
      if (i === undefined || j === undefined) continue;
      const dx = pos[j][0] - pos[i][0];
      const dy = pos[j][1] - pos[i][1];
      const dz = pos[j][2] - pos[i][2];
      const d = Math.sqrt(dx * dx + dy * dy + dz * dz) || 1e-6;
      const f = (d * d) / (k * nodes.length);
      const ux = (dx / d) * f, uy = (dy / d) * f, uz = (dz / d) * f;
      force[i][0] += ux; force[i][1] += uy; force[i][2] += uz;
      force[j][0] -= ux; force[j][1] -= uy; force[j][2] -= uz;
    }
    // Integrate with cooling
    const cool = 1 - it / iterations;
    for (let i = 0; i < nodes.length; i++) {
      for (let a = 0; a < 3; a++) {
        const step = Math.max(-0.5, Math.min(0.5, force[i][a] * 0.05)) * cool;
        pos[i][a] += step;
      }
    }
  }
  return Object.fromEntries(nodes.map((n, i) => [n, pos[i]]));
}

/** Floating HTML tooltip attached to a 3D position. */
export function Tip({ children }: { children: ReactNode }) {
  return (
    <Html center distanceFactor={14} zIndexRange={[50, 0]}>
      <div
        style={{
          background: 'rgba(4,10,16,0.94)', border: `1px solid ${ACCENT}55`,
          borderRadius: 6, padding: '7px 11px', color: '#e6edf3',
          fontFamily: 'monospace', fontSize: 11, lineHeight: 1.5,
          pointerEvents: 'none', whiteSpace: 'nowrap', userSelect: 'none',
        }}
      >
        {children}
      </div>
    </Html>
  );
}

class SceneErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  render() {
    if (this.state.error) {
      return (
        <div
          style={{
            width: '100%', height: '100%', display: 'flex',
            flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            color: '#f97322', fontFamily: 'monospace', fontSize: 12, gap: 8, padding: 20,
          }}
        >
          <div>⚠ 3D RENDER FAULT</div>
          <div style={{ color: '#5b6b7b', fontSize: 11, textAlign: 'center', maxWidth: 420 }}>
            {this.state.error.message}. Your browser may not support WebGL —
            switch to the 2D chart view for this scenario.
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

function SceneFallback() {
  return (
    <div
      style={{
        width: '100%', height: '100%', display: 'flex', alignItems: 'center',
        justifyContent: 'center', color: ACCENT, fontFamily: 'monospace', fontSize: 12,
      }}
    >
      ◌ initialising 3D viewport…
    </div>
  );
}

export interface SceneProps {
  children: ReactNode;
  camera?: [number, number, number];
  controlsRef?: React.MutableRefObject<OrbitControlsImpl | null>;
  autoRotate?: boolean;
}

/** Full-bleed dark Canvas with OrbitControls (rotate / zoom / pan / fly). */
export function Scene({ children, camera = [12, 10, 14], controlsRef, autoRotate = false }: SceneProps) {
  return (
    <SceneErrorBoundary>
      <Canvas
        dpr={[1, 2]}
        camera={{ position: camera, fov: 50, near: 0.05, far: 4000 }}
        gl={{ antialias: true, alpha: false }}
        style={{ width: '100%', height: '100%', background: '#040a10' }}
      >
        <color attach="background" args={['#040a10']} />
        <fog attach="fog" args={['#040a10', 60, 260]} />
        <ambientLight intensity={0.55} />
        <directionalLight position={[18, 26, 12]} intensity={1.15} />
        <pointLight position={[-14, -8, -16]} intensity={0.35} color={ACCENT} />
        <Suspense fallback={<SceneFallback />}>{children}</Suspense>
        <OrbitControls
          ref={(r) => { if (controlsRef) controlsRef.current = r; }}
          enableDamping
          dampingFactor={0.08}
          autoRotate={autoRotate}
          autoRotateSpeed={0.7}
          minDistance={0.5}
          maxDistance={600}
        />
      </Canvas>
    </SceneErrorBoundary>
  );
}

/** Shared HUD chip shown above every 3D viewport. */
export function ViewportHud({ text }: { text: string }) {
  const [pos, setPos] = useState<'top' | 'bottom'>('top');
  return (
    <div
      style={{
        position: 'absolute', [pos]: 10, left: 12, zIndex: 5,
        background: 'rgba(4,10,16,0.8)', border: `1px solid ${DIM}`,
        borderRadius: 6, padding: '5px 10px', color: '#5b6b7b',
        fontFamily: 'monospace', fontSize: 10, letterSpacing: 1,
        pointerEvents: 'none',
      } as React.CSSProperties}
      onDoubleClick={() => setPos(pos === 'top' ? 'bottom' : 'top')}
    >
      {text}
    </div>
  );
}
