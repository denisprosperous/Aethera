'use client';

/**
 * AETHERA v27.0 — Alien3D
 *
 * Reconstruction view for the Alien Geometer scenario. The point cloud is
 * the 3D SMACOF embedding of the exact edge-length graph that was fed to
 * /api/alien/reconstruct (solved by /api/solve/manifold?embedding=3d) —
 * the shape classification (Flat / Ellipsoidal / Potato) still comes from
 * the backend; nothing here assumes dimensionality in advance.
 */

import { useMemo, useState } from 'react';
import * as THREE from 'three';
import { Line } from '@react-three/drei';
import { Scene, ACCENT, ViewportHud } from './Scene';

interface Alien3DProps {
  shape: string;
  embedding?: string;
  meanCurvature?: number;
  residual?: number;
  /** node → [x,y,z] from the 3D manifold solve. */
  coords: Record<string, number[]> | null;
  edges: { source: string; target: string }[];
  onRegionClick?: (region: string) => void;
}

const EXTENT = 7;

const SHAPE_COLOR: Record<string, string> = {
  Flat: ACCENT,
  Ellipsoidal: '#06b6d4',
  Potato: '#f97322',
};

export default function Alien3D({
  shape,
  embedding,
  meanCurvature,
  residual,
  coords,
  edges,
  onRegionClick,
}: Alien3DProps) {
  const [hover, setHover] = useState<string | null>(null);

  const model = useMemo(() => {
    if (!coords || Object.keys(coords).length < 3) return null;
    const names = Object.keys(coords);
    let minX = Infinity, minY = Infinity, minZ = Infinity;
    let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
    for (const n of names) {
      const [x, y, z] = coords[n];
      minX = Math.min(minX, x); maxX = Math.max(maxX, x);
      minY = Math.min(minY, y); maxY = Math.max(maxY, y);
      minZ = Math.min(minZ, z); maxZ = Math.max(maxZ, z);
    }
    const span = Math.max(maxX - minX, maxY - minY, maxZ - minZ, 1e-6);
    const s = (EXTENT * 2) / span;
    const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2, cz = (minZ + maxZ) / 2;
    const pos: Record<string, [number, number, number]> = {};
    for (const n of names) {
      const [x, y, z] = coords[n];
      pos[n] = [(x - cx) * s, (y - cy) * s, (z - cz) * s];
    }
    const degree = new Map<string, number>();
    for (const e of edges) {
      degree.set(e.source, (degree.get(e.source) || 0) + 1);
      degree.set(e.target, (degree.get(e.target) || 0) + 1);
    }
    const maxDeg = Math.max(1, ...degree.values());
    const linePts: [number, number, number][] = [];
    for (const e of edges) {
      if (!pos[e.source] || !pos[e.target]) continue;
      linePts.push(pos[e.source], pos[e.target]);
    }
    return { names, pos, degree, maxDeg, linePts };
  }, [coords, edges]);

  if (!model) {
    return (
      <div
        style={{
          width: '100%', height: '100%', display: 'flex', alignItems: 'center',
          justifyContent: 'center', color: '#5b6b7b', fontFamily: 'monospace',
          fontSize: 12, flexDirection: 'column', gap: 8,
        }}
      >
        <div style={{ fontSize: 30 }}>👽</div>
        <div>3D embedding unavailable — the solver refused this graph.</div>
      </div>
    );
  }

  const color = SHAPE_COLOR[shape] || ACCENT;

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <Scene camera={[EXTENT * 1.2, EXTENT * 1.0, EXTENT * 1.5]}>
        <gridHelper args={[EXTENT * 2.6, 20, '#0f2436', '#0a1826']} />
        <Line
          points={model.linePts}
          color={color}
          lineWidth={1.7}
          transparent
          opacity={0.9}
        />
        {model.names.map((n) => {
          const deg = model.degree.get(n) || 0;
          const r = 0.22 + (deg / model.maxDeg) * 0.22;
          return (
            <mesh
              key={n}
              position={model.pos[n]}
              onPointerOver={(e) => { e.stopPropagation(); setHover(n); }}
              onPointerOut={() => setHover(null)}
              onClick={() => onRegionClick?.(n)}
            >
              <sphereGeometry args={[r, 18, 18]} />
              <meshStandardMaterial
                color={color} emissive={color} emissiveIntensity={0.65} roughness={0.35}
              />
            </mesh>
          );
        })}
      </Scene>

      <ViewportHud
        text={`ALIEN GEOMETER — CLASSIFICATION: ${(shape || '?').toUpperCase()} · EMBEDDING: ${(embedding || '3d').toUpperCase()} · ⟨κ⟩ ${(meanCurvature ?? 0).toExponential(3)} · AUTO-DIMENSIONALITY`}
      />

      {hover && (
        <div
          style={{
            position: 'absolute', bottom: 12, right: 12, zIndex: 6,
            background: 'rgba(4,10,16,0.94)', border: `1px solid ${ACCENT}55`,
            borderRadius: 6, padding: '8px 12px', color: '#e6edf3',
            fontFamily: 'monospace', fontSize: 11, lineHeight: 1.55,
          }}
        >
          <div style={{ color: ACCENT, fontWeight: 700 }}>node {hover}</div>
          <div style={{ color: '#8b9bab' }}>degree {model.degree.get(hover) || 0}</div>
          <div style={{ color: '#5b6b7b' }}>residual {(residual ?? 0).toExponential(4)}</div>
        </div>
      )}

      <div
        style={{
          position: 'absolute', top: 10, left: 12, zIndex: 5,
          background: 'rgba(4,10,16,0.8)', border: `1px solid ${color}44`,
          borderRadius: 6, padding: '8px 12px', color: '#e6edf3',
          fontFamily: 'monospace', fontSize: 11, pointerEvents: 'none',
        }}
      >
        <span style={{ color }}>■</span> intrinsic classification: <b>{shape || '?'}</b>
        <span style={{ color: '#5b6b7b' }}> — from edge lengths alone</span>
      </div>
    </div>
  );
}
