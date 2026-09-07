'use client';

/**
 * AETHERA v27.0 — Terraformer3D
 *
 * Sea-level-rise scenario in 3D, rendered WITHOUT a globe: every nation is
 * a prism anchored at its Physical Truth intrinsic manifold position (the
 * emergent flat embedding — no spherical assumption, no projection).
 * Prism height encodes |area change|; color encodes loss (red) vs gain
 * (green). Nations missing from the manifold are placed on an outer
 * spiral ring so nothing is hidden.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';
import { Scene, ACCENT, Tip, ViewportHud } from './Scene';
import { getManifold } from '@/lib/useScenario';

interface CoastlineChange {
  nation?: string;
  region?: string;
  area_change_km2?: number;
  before?: number;
  after?: number;
  note?: string;
  [k: string]: unknown;
}

interface Terraformer3DProps {
  coastlineChanges: CoastlineChange[];
  seaLevel: number;
  onRegionClick?: (region: string) => void;
}

const EXTENT = 13;
const SPIRAL_R0 = EXTENT * 1.18;

function norm(s: string): string {
  return s.toLowerCase().replace(/[^a-z]/g, '');
}

function Prism({
  pos,
  targetH,
  color,
  onOver,
  onOut,
  onClick,
}: {
  pos: [number, number, number];
  targetH: number;
  color: string;
  onOver: () => void;
  onOut: () => void;
  onClick: () => void;
}) {
  const mesh = useRef<THREE.Mesh>(null);
  const hRef = useRef(0.02);

  useFrame((_, delta) => {
    if (!mesh.current) return;
    // Ease height toward target → real-time slider feedback.
    hRef.current += (targetH - hRef.current) * Math.min(1, delta * 6);
    const h = Math.max(0.02, hRef.current);
    mesh.current.scale.y = h / 0.06; // base geometry height 0.06
    mesh.current.position.y = pos[1] + h / 2;
  });

  return (
    <mesh
      ref={mesh}
      position={[pos[0], pos[1] + 0.01, pos[2]]}
      onPointerOver={(e) => { e.stopPropagation(); onOver(); }}
      onPointerOut={onOut}
      onClick={(e) => { e.stopPropagation(); onClick(); }}
    >
      <boxGeometry args={[0.42, 0.06, 0.42]} />
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={0.45}
        transparent
        opacity={0.92}
        roughness={0.4}
      />
    </mesh>
  );
}

export default function Terraformer3D({
  coastlineChanges,
  seaLevel,
  onRegionClick,
}: Terraformer3DProps) {
  const [manifold, setManifold] = useState<Awaited<ReturnType<typeof getManifold>> | null>(null);
  const [hover, setHover] = useState<{
    name: string; change: number; before: number; after: number; pct: string;
  } | null>(null);

  useEffect(() => {
    let alive = true;
    getManifold()
      .then((m) => { if (alive) setManifold(m); })
      .catch(() => { /* stay null → spiral-only layout */ });
    return () => { alive = false; };
  }, []);

  const nations = useMemo(() => {
    const rows = coastlineChanges.filter(
      (c) => typeof c.area_change_km2 === 'number' && Number.isFinite(c.area_change_km2 as number),
    );
    const maxAbs = Math.max(1e-9, ...rows.map((c) => Math.abs(Number(c.area_change_km2))));
    const coordMap = new Map<string, [number, number, number]>();
    if (manifold) {
      for (const r of manifold.regions) coordMap.set(norm(r.name), [r.coords[0], r.coords[1], r.coords[2]]);
    }
    // Manifold fit: reuse raw coords (SMACOF output already ~[-2500..2500]) → scale to extent.
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const [x, y] of coordMap.values()) {
      minX = Math.min(minX, x); maxX = Math.max(maxX, x);
      minY = Math.min(minY, y); maxY = Math.max(maxY, y);
    }
    const span = Math.max(maxX - minX, maxY - minY, 1e-6);
    const s = (EXTENT * 2) / span;
    const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;

    let spiralIdx = 0;
    return rows.map((c) => {
      const name = String(c.nation ?? c.region ?? '?');
      const change = Number(c.area_change_km2);
      const key = norm(name);
      let pos: [number, number, number] | null = null;
      const c0 = coordMap.get(key);
      if (c0) {
        pos = [(c0[0] - cx) * s, 0, -(c0[1] - cy) * s];
      } else {
        // Unmatched nation → outer golden-angle spiral ring.
        const ga = spiralIdx++ * 2.399963;
        const r = SPIRAL_R0 + (spiralIdx % 7) * 0.55;
        pos = [r * Math.cos(ga), 0, r * Math.sin(ga)];
      }
      const frac = Math.abs(change) / maxAbs;
      const h = 0.12 + frac * 3.4;
      const color = change < 0
        ? `rgb(${Math.round(160 + 95 * frac)},${Math.round(83 - 60 * frac)},${Math.round(34 - 20 * frac)})`
        : ACCENT;
      return { name, change, before: Number(c.before) || 0, after: Number(c.after) || 0, pos, h, color };
    });
  }, [coastlineChanges, manifold]);

  const lost = nations.filter((n) => n.change < 0).length;

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <Scene camera={[0, EXTENT * 1.35, EXTENT * 1.5]}>
        {/* Reference plane grid — neutral, not a globe */}
        <gridHelper args={[EXTENT * 2.9, 30, '#0f2436', '#0a1826']} />
        {nations.map((n, i) => (
          <Prism
            key={`${n.name}-${i}`}
            pos={n.pos}
            targetH={n.h}
            color={n.color}
            onOver={() =>
              setHover({
                name: n.name,
                change: n.change,
                before: n.before,
                after: n.after,
                pct: n.before > 0 ? `${((n.change / n.before) * 100).toFixed(2)}%` : '—',
              })
            }
            onOut={() => setHover(null)}
            onClick={() => onRegionClick?.(n.name)}
          />
        ))}
      </Scene>

      <ViewportHud text={`TERRAFORMER — SEA LEVEL +${seaLevel} M · ${nations.length} NATIONS · ${lost} LOSING AREA · NO GLOBE, EMERGENT MANIFOLD`} />

      {hover && (
        <div
          style={{
            position: 'absolute', bottom: 12, right: 12, zIndex: 6,
            background: 'rgba(4,10,16,0.94)', border: `1px solid ${ACCENT}55`,
            borderRadius: 6, padding: '8px 12px', color: '#e6edf3',
            fontFamily: 'monospace', fontSize: 11, lineHeight: 1.55,
          }}
        >
          <div style={{ color: ACCENT, fontWeight: 700 }}>{hover.name}</div>
          <div>{Math.abs(hover.change).toLocaleString()} km² {hover.change < 0 ? 'LOST' : 'GAINED'}</div>
          <div style={{ color: '#5b6b7b' }}>
            {hover.before.toLocaleString()} → {hover.after.toLocaleString()} km² ({hover.pct})
          </div>
        </div>
      )}

      <div
        style={{
          position: 'absolute', top: 10, right: 12, zIndex: 5,
          display: 'flex', flexDirection: 'column', gap: 4,
          background: 'rgba(4,10,16,0.8)', border: '1px solid #1c2a38',
          borderRadius: 6, padding: '7px 10px', color: '#5b6b7b',
          fontFamily: 'monospace', fontSize: 10, pointerEvents: 'none',
        }}
      >
        <span><span style={{ color: '#f97322' }}>■</span> area loss</span>
        <span><span style={{ color: ACCENT }}>■</span> area gain</span>
        <span>height ∝ |Δ area|</span>
      </div>
    </div>
  );
}
