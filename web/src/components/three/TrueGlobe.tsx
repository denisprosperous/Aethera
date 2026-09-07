'use client';

/**
 * AETHERA v27.0 — TrueGlobe
 *
 * The globe WITHOUT assumptions. There is no pre-seeded sphere anywhere in
 * this component: the rendered object is the solved Physical Truth
 * intrinsic manifold (140 regions, area-derived edge lengths, SMACOF
 * embedding). Vertices = intrinsic coordinates, faces = Delaunay
 * triangulation of those points, colors = area truth or legacy-map
 * deviation. If the data said curved, it would render curved — today the
 * data says planar (z ≈ 0), so it renders planar. That IS the honest
 * "globe" of this platform.
 *
 * Interactions: orbit / zoom / pan / fly (OrbitControls), hover → Physical
 * Truth tooltip, click → module page, camera presets (3D orbit ↔ 2D
 * planar), heatmap modes (true area ↔ legacy deviation), labels.
 */

import { useEffect, useMemo, useState } from 'react';
import { ACCENT } from './Scene';
import Manifold3D, { type ManifoldRegion } from './Manifold3D';
import { getManifold, fetchDistortionRanking } from '@/lib/useScenario';

export interface TrueGlobeState {
  loading: boolean;
  error: string;
  regions: ManifoldRegion[];
  nodeCount: number;
  edgeCount: number;
  residual: number;
  ranking: Record<string, unknown>[];
}

export type GlobeHeatMode = 'area' | 'legacy' | 'plain';

/** Legacy-deviation heat: rel% < 0 → over-expanded → red; > 0 → blue. */
function legacyHeat(rel: number | null): number | null {
  if (rel === null || !Number.isFinite(rel)) return null;
  return 0.5 - Math.max(-1, Math.min(1, rel / 200)) * 0.5;
}

export function useTrueGlobe(projection: string): TrueGlobeState {
  const [state, setState] = useState<TrueGlobeState>({
    loading: true,
    error: '',
    regions: [],
    nodeCount: 0,
    edgeCount: 0,
    residual: 0,
    ranking: [],
  });

  useEffect(() => {
    let alive = true;
    setState((s) => ({ ...s, loading: true, error: '' }));
    (async () => {
      try {
        const m = await getManifold();
        const ranking = await fetchDistortionRanking(projection, 200).catch(() => []);
        if (!alive) return;
        setState({
          loading: false,
          error: '',
          regions: m.regions,
          nodeCount: m.nodeCount,
          edgeCount: m.edgeCount,
          residual: m.residual,
          ranking,
        });
      } catch (e) {
        if (alive) {
          setState((s) => ({
            ...s,
            loading: false,
            error: (e as Error)?.message || 'failed to load manifold',
          }));
        }
      }
    })();
    return () => {
      alive = false;
    };
  }, [projection]);

  return state;
}

interface TrueGlobeProps {
  globe: TrueGlobeState;
  heatMode: GlobeHeatMode;
  showLabels: boolean;
  showMesh: boolean;
  autoRotate: boolean;
  viewPreset: 'orbit' | 'planar';
  onRegionClick?: (region: string) => void;
}

export default function TrueGlobe({
  globe,
  heatMode,
  showLabels,
  showMesh,
  autoRotate,
  viewPreset,
  onRegionClick,
}: TrueGlobeProps) {
  const heatValues = useMemo(() => {
    if (heatMode !== 'legacy') return null;
    const byName = new Map<string, number>();
    for (const r of globe.ranking) {
      const name = String(r.region ?? '');
      const rel = Number(r.relative_error_percent);
      const t = legacyHeat(Number.isFinite(rel) ? rel : null);
      if (name && t !== null) byName.set(name, t);
    }
    return Object.fromEntries(byName);
  }, [globe.ranking, heatMode]);

  const labels = useMemo(() => {
    if (!showLabels) return null;
    const top = [...globe.regions]
      .sort((a, b) => (b.area_km2 || 0) - (a.area_km2 || 0))
      .slice(0, 10);
    return Object.fromEntries(top.map((r) => [r.name, r.name]));
  }, [globe.regions, showLabels]);

  const hud =
    heatMode === 'legacy'
      ? `TRUE GLOBE — LEGACY DEVIATION (${'Mercator-style ranking'}) · RED = INFLATED BY LEGACY MAPS · BLUE = SHRUNK · ${globe.ranking.length} METRICS`
      : `TRUE GLOBE — ${globe.nodeCount} REGIONS · ${globe.edgeCount} EDGES · EMERGENT SHAPE (NO SPHERE ASSUMED)`;

  if (globe.loading) {
    return (
      <ViewportFrame>
        <div
          style={{
            width: '100%', height: '100%', display: 'flex', alignItems: 'center',
            justifyContent: 'center', color: ACCENT, fontFamily: 'monospace',
            fontSize: 12, flexDirection: 'column', gap: 10,
          }}
        >
          <div style={{ fontSize: 30 }}>🌍</div>
          <div>solving the Physical Truth manifold…</div>
          <div style={{ color: '#5b6b7b', fontSize: 10 }}>
            area-derived edge lengths → SMACOF → intrinsic coordinates
          </div>
        </div>
      </ViewportFrame>
    );
  }

  if (globe.error || globe.regions.length < 3) {
    return (
      <ViewportFrame>
        <div
          style={{
            width: '100%', height: '100%', display: 'flex', alignItems: 'center',
            justifyContent: 'center', color: '#f97316', fontFamily: 'monospace',
            fontSize: 12, flexDirection: 'column', gap: 8,
          }}
        >
          <div>⚠ manifold unavailable</div>
          <div style={{ color: '#5b6b7b', maxWidth: 420, textAlign: 'center' }}>
            {globe.error || 'not enough regions'} — the backend may be restarting;
            retry shortly.
          </div>
        </div>
      </ViewportFrame>
    );
  }

  return (
    <ViewportFrame>
      <Manifold3D
        regions={globe.regions}
        edgeCount={globe.edgeCount}
        residual={globe.residual}
        heatValues={heatValues}
        labels={labels}
        showMesh={heatMode !== 'plain' && showMesh}
        viewPreset={viewPreset}
        autoRotate={autoRotate}
        hud={hud}
        onRegionClick={onRegionClick}
      />
    </ViewportFrame>
  );
}

function ViewportFrame({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        position: 'relative', width: '100%', height: '100%',
        background: '#040a10', border: '1px solid #1c2a38',
        borderRadius: '10px', overflow: 'hidden',
      }}
    >
      {children}
    </div>
  );
}
