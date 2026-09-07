'use client';

/**
 * AETHERA v27.0 — Distortion3D
 *
 * Two stacked 3D views for the Distortion Observatory scenario:
 *  • PROJECTIONS — colonial distortion scores as 3D columns (green = fair,
 *    orange = colonial bias).
 *  • STRAIN — the physical-truth manifold recolored as a strain-tensor
 *    style heatmap of legacy-map deviation: red = over-expanded regions
 *    (legacy maps inflate them), blue = under-expanded. Data comes from
 *    /api/distortion/ranking for the selected projection.
 */

import { useEffect, useMemo, useState } from 'react';
import * as THREE from 'three';
import { Scene, ACCENT, heatColor, heatColorHex, ViewportHud } from './Scene';
import { getManifold, fetchDistortionRanking } from '@/lib/useScenario';

interface ScoreRow {
  projection?: string;
  colonial_score?: number;
  note?: string;
  [k: string]: unknown;
}

interface RankRow {
  region?: string;
  area_physical_m2?: number;
  area_legacy_m2?: number;
  relative_error_percent?: number;
  distortion_category?: string;
  [k: string]: unknown;
}

interface Distortion3DProps {
  scores: ScoreRow[];
  selectedProjection: string;
  onRegionClick?: (region: string) => void;
}

const EXTENT = 12;

function fitRegions(
  regions: { name: string; coords: [number, number, number] }[],
): { name: string; x: number; z: number }[] {
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const r of regions) {
    minX = Math.min(minX, r.coords[0]); maxX = Math.max(maxX, r.coords[0]);
    minY = Math.min(minY, r.coords[1]); maxY = Math.max(maxY, r.coords[1]);
  }
  const span = Math.max(maxX - minX, maxY - minY, 1e-6);
  const s = (EXTENT * 2) / span;
  const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
  return regions.map((r) => ({
    name: r.name,
    x: (r.coords[0] - cx) * s,
    z: -(r.coords[1] - cy) * s,
  }));
}

export default function Distortion3D({
  scores,
  selectedProjection,
  onRegionClick,
}: Distortion3DProps) {
  const [mode, setMode] = useState<'projections' | 'strain'>('strain');
  const [manifold, setManifold] = useState<Awaited<ReturnType<typeof getManifold>> | null>(null);
  const [ranking, setRanking] = useState<RankRow[]>([]);
  const [loadingStrain, setLoadingStrain] = useState(false);
  const [hover, setHover] = useState<{
    title: string; lines: string[]; x: number; z: number;
  } | null>(null);

  useEffect(() => {
    let alive = true;
    getManifold().then((m) => { if (alive) setManifold(m); }).catch(() => {});
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    if (mode !== 'strain') return;
    let alive = true;
    setLoadingStrain(true);
    fetchDistortionRanking(selectedProjection, 200)
      .then((rows) => { if (alive) setRanking(rows); })
      .catch(() => { if (alive) setRanking([]); })
      .finally(() => { if (alive) setLoadingStrain(false); });
    return () => { alive = false; };
  }, [mode, selectedProjection]);

  // Strain coloring: relative_error_percent < 0 → over-reported (red),
  // > 0 → under-reported (blue). Saturation at ±200 %.
  const strain = useMemo(() => {
    if (!manifold) return [];
    const byName = new Map<string, RankRow>();
    for (const r of ranking) {
      if (typeof r.region === 'string') byName.set(r.region.toLowerCase(), r);
    }
    const fitted = fitRegions(manifold.regions);
    return fitted.map((f) => {
      const row = byName.get(f.name.toLowerCase());
      const rel = row ? Number(row.relative_error_percent) || 0 : null;
      const t = rel === null ? 0.5 : 0.5 - Math.max(-1, Math.min(1, rel / 200)) * 0.5;
      const color = rel === null ? [0.16, 0.2, 0.26] : heatColorHex(t);
      return { ...f, rel, color: color as [number, number, number], row };
    });
  }, [manifold, ranking]);

  const barData = useMemo(() => {
    const rows = scores.filter((s) => typeof s.colonial_score === 'number');
    const maxAbs = Math.max(0.02, ...rows.map((s) => Math.abs(Number(s.colonial_score))));
    const gap = (EXTENT * 2) / Math.max(1, rows.length + 1);
    return rows.map((s, i) => {
      const v = Number(s.colonial_score);
      return {
        label: String(s.projection ?? `#${i}`),
        note: String(s.note ?? ''),
        x: -EXTENT + gap * (i + 1),
        h: 0.4 + (Math.abs(v) / maxAbs) * 5.6,
        color: v >= 0 ? ACCENT : '#f97322',
      };
    });
  }, [scores]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <Scene camera={[0, EXTENT * 1.2, EXTENT * 1.6]}>
        <gridHelper args={[EXTENT * 2.8, 28, '#0f2436', '#0a1826']} />

        {mode === 'projections' &&
          barData.map((b) => (
            <group key={b.label} position={[b.x, 0, 0]}>
              <mesh
                position={[0, b.h / 2, 0]}
                onPointerOver={(e) => {
                  e.stopPropagation();
                  setHover({ title: b.label, lines: [b.note], x: b.x, z: 0 });
                }}
                onPointerOut={() => setHover(null)}
              >
                <cylinderGeometry args={[0.42, 0.42, b.h, 24]} />
                <meshStandardMaterial
                  color={b.color} emissive={b.color} emissiveIntensity={0.5}
                  roughness={0.35} transparent opacity={0.94}
                />
              </mesh>
              <mesh position={[0, b.h + 0.34, 0]} rotation={[-Math.PI / 2, 0, 0]}>
                <circleGeometry args={[0.18, 20]} />
                <meshBasicMaterial color={b.color} />
              </mesh>
            </group>
          ))}

        {mode === 'strain' &&
          strain.map((s, i) => (
            <mesh
              key={`${s.name}-${i}`}
              position={[s.x, 0.12, s.z]}
              onPointerOver={(e) => {
                e.stopPropagation();
                setHover({
                  title: s.name,
                  lines: s.row
                    ? [
                        `physical: ${fmtArea(Number(s.row.area_physical_m2))}`,
                        `legacy: ${fmtArea(Number(s.row.area_legacy_m2))}`,
                        `deviation: ${s.rel?.toFixed(1)} % (${s.row.distortion_category})`,
                      ]
                    : ['no legacy metric for this projection'],
                  x: s.x, z: s.z,
                });
              }}
              onPointerOut={() => setHover(null)}
              onClick={() => s.row && onRegionClick?.(s.name)}
            >
              <sphereGeometry args={[0.17, 14, 14]} />
              <meshStandardMaterial
                color={new THREE.Color(...s.color)}
                emissive={new THREE.Color(...s.color)}
                emissiveIntensity={0.7}
                roughness={0.4}
              />
            </mesh>
          ))}
      </Scene>

      <ViewportHud
        text={
          mode === 'strain'
            ? `STRAIN FIELD — ${selectedProjection.toUpperCase()} · RED = OVER-EXPANDED · BLUE = UNDER-EXPANDED${loadingStrain ? ' · LOADING' : ''}`
            : 'COLONIAL DISTORTION SCORES — GREEN = FAIR · ORANGE = COLONIAL BIAS'
        }
      />

      {/* mode switch */}
      <div
        style={{
          position: 'absolute', top: 10, right: 12, zIndex: 6, display: 'flex', gap: 6,
        }}
      >
        {(['strain', 'projections'] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            style={{
              background: mode === m ? 'rgba(0,255,136,0.12)' : 'rgba(4,10,16,0.85)',
              border: `1px solid ${mode === m ? ACCENT : '#1c2a38'}`,
              color: mode === m ? ACCENT : '#8b9bab',
              borderRadius: 6, padding: '6px 12px', cursor: 'pointer',
              fontFamily: 'monospace', fontSize: 11,
            }}
          >
            {m === 'strain' ? '🔥 Strain Heatmap' : '📊 Score Columns'}
          </button>
        ))}
      </div>

      {hover && (
        <div
          style={{
            position: 'absolute', bottom: 12, right: 12, zIndex: 6, maxWidth: 340,
            background: 'rgba(4,10,16,0.94)', border: `1px solid ${ACCENT}55`,
            borderRadius: 6, padding: '8px 12px', color: '#e6edf3',
            fontFamily: 'monospace', fontSize: 11, lineHeight: 1.55,
          }}
        >
          <div style={{ color: ACCENT, fontWeight: 700 }}>{hover.title}</div>
          {hover.lines.map((l, i) => (
            <div key={i} style={{ color: '#8b9bab' }}>{l}</div>
          ))}
        </div>
      )}

      {mode === 'strain' && (
        <div
          style={{
            position: 'absolute', top: 10, left: 12, zIndex: 5,
            background: 'rgba(4,10,16,0.8)', border: '1px solid #1c2a38',
            borderRadius: 6, padding: '7px 10px', color: '#5b6b7b',
            fontFamily: 'monospace', fontSize: 10, lineHeight: 1.7,
            pointerEvents: 'none',
          }}
        >
          <div><span style={{ color: 'rgb(56,130,246)' }}>●</span> under-expanded (legacy shrinks)</div>
          <div><span style={{ color: '#f97322' }}>●</span> over-expanded (legacy inflates)</div>
          <div><span style={{ color: '#3d4a58' }}>●</span> no metric</div>
        </div>
      )}
    </div>
  );
}

function fmtArea(v: number): string {
  if (!Number.isFinite(v)) return '—';
  const km2 = v / 1e6;
  return `${km2.toLocaleString(undefined, { maximumFractionDigits: 0 })} km²`;
}
