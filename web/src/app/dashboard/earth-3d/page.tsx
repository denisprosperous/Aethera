'use client';

/**
 * AETHERA v30.1 — /dashboard/earth-3d
 *
 * THE 3D EARTH SIMULATION (mandatory, principle-first).
 *
 * The platform fetches the solved intrinsic manifold from
 * /api/solve/physical-truth (vertices, intrinsic edge graph, absolute
 * areas) and renders it as a 3D object. The shape on screen is a derived
 * extrinsic embedding — never a pre-seeded globe. Flat stays flat, curved
 * stays curved, exactly as the data decides (Axiom 2 · Intrinsic
 * Emergence, Axiom 3 · Extrinsic Agnosticism, Axiom 4 · Zero Bias).
 *
 * v33.0: every region renders as a CLOSED COUNTRY TERRITORY — the
 * nearest-vertex dual of the intrinsic point set (see lib/geometry.ts) —
 * with crisp borders, heatmap fills and polygon-centred labels. Seed
 * markers are an explicit toggle, off by default.
 *
 * v36.0: derived country boundaries (turtle-walk reconstruction from
 * globe-agnostic scalars) render as the default geometry layer.
 *
 * v37.1: GOOGLE-MAPS-STYLE INTERACTIVITY — InteractiveEarth3D (left-drag
 * pan, right-drag orbit/tilt, middle/scroll zoom, double-click reset,
 * zoom meter) plus ELEVATION-ON-CLICK: with the toggle ON, clicking any
 * point samples the ETOPO1 height above sea level (a per-vertex physical
 * scalar) via POST /api/elevation. No lon/lat, no WGS84, no EPSG.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import LLMPalette from '@/components/LLMPalette';
import Disclaimer from '@/components/Disclaimer';
import ElevationToggle, { type ElevationResult } from '@/components/ElevationToggle';
import { apiFetch } from '@/lib/api';
import type {
  EarthSimulation3DData,
  TerritoryRenderStats,
  BoundaryCountry,
} from '@/components/three/EarthSimulation3D';

const EarthSimulation3D = dynamic(() => import('@/components/three/EarthSimulation3D'), {
  ssr: false,
  loading: () => <ViewportLoading text="initialising WebGL viewport…" />,
});

const InteractiveEarth3D = dynamic(() => import('@/components/three/InteractiveEarth3D'), {
  ssr: false,
  loading: () => <ViewportLoading text="initialising interactive manifold…" />,
});

function ViewportLoading({ text }: { text: string }) {
  return (
    <div
      style={{
        height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: '#00ff88', fontFamily: 'monospace', fontSize: 12,
        background: '#040a10', border: '1px solid #1c2a38', borderRadius: '10px',
      }}
    >
      ◌ {text}
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div style={{ background: '#0d1117', border: '1px solid #1c2a38', borderRadius: '8px', padding: '13px 15px' }}>
      <div style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: '10px', letterSpacing: '1px', textTransform: 'uppercase' }}>
        {label}
      </div>
      <div style={{ color: accent ? '#00ff88' : '#e6edf3', fontFamily: 'monospace', fontSize: '15px', marginTop: '6px', fontWeight: 600, wordBreak: 'break-all' }}>
        {value}
      </div>
    </div>
  );
}

type Mode = 'intrinsic' | 'area-preserving';
type Heatmap = 'none' | 'area' | 'deviation';
type GeometryMode = 'boundary' | 'dual';

interface ControlState {
  mode: Mode;
  heatmap: Heatmap;
  showLabels: boolean;
  labelDensity: 'all' | 'major' | 'none';
  showTerritory: boolean;
  showNodes: boolean;
  autoRotate: boolean;
  viewPreset: 'orbit' | 'planar';
  geometryMode: GeometryMode;
}

const INITIAL_CONTROLS: ControlState = {
  mode: 'intrinsic',
  heatmap: 'area',
  showLabels: true,
  labelDensity: 'all',
  showTerritory: true,
  showNodes: false, // v33.0: countries are the rendering; seeds are opt-in
  autoRotate: false,
  viewPreset: 'orbit',
  geometryMode: 'boundary', // v36.0: derived country boundaries by default
};

const chip = (active: boolean) => ({
  background: active ? 'rgba(0,255,136,0.12)' : '#0d1117',
  border: `1px solid ${active ? '#00ff88' : '#1c2a38'}`,
  color: active ? '#00ff88' : '#8b9bab',
  borderRadius: '6px',
  padding: '7px 13px',
  cursor: 'pointer',
  fontFamily: 'monospace',
  fontSize: '11px',
} as React.CSSProperties);

function Group({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: 9, letterSpacing: 2 }}>{label}</span>
      {children}
    </div>
  );
}

interface LoadState {
  loading: boolean;
  error: string;
  data: EarthSimulation3DData | null;
  boundary: BoundaryCountry[] | null;
  boundaryStats: { countries: number; vertices: number; anchored: number; shelf: number } | null;
  residual: number;
  nodeCount: number;
  edgeCount: number;
}

export default function Earth3DPage() {
  const [controls, setControls] = useState<ControlState>(INITIAL_CONTROLS);
  const [st, setSt] = useState<LoadState>({
    loading: true, error: '', data: null, boundary: null, boundaryStats: null,
    residual: 0, nodeCount: 0, edgeCount: 0,
  });
  const router = useRouter();

  // v33.0: territory stats reported by the 3D component (transparency).
  const [renderStats, setRenderStats] = useState<TerritoryRenderStats | null>(null);
  const onRenderStats = useCallback((s: TerritoryRenderStats) => setRenderStats(s), []);

  // v37.1: elevation-on-click state (toggle lives top-right of the viewport).
  const [elevationOn, setElevationOn] = useState(false);
  const [elevation, setElevation] = useState<ElevationResult | null>(null);

  // v32.0 deep link: /dashboard/earth-3d?region=<Name> focuses that region.
  const [focusRegion, setFocusRegion] = useState<string | null>(null);
  useEffect(() => {
    const r = new URLSearchParams(window.location.search).get('region');
    if (r && r.trim()) setFocusRegion(r.trim());
  }, []);

  // Resolve the deep-link region case-insensitively against loaded data.
  const resolvedFocus = useMemo<string | null>(() => {
    if (!focusRegion || !st.data) return null;
    const needle = focusRegion.toLowerCase();
    const hit = (st.data.regions || []).find((r) => r.name.toLowerCase() === needle);
    return hit ? hit.name : null;
  }, [focusRegion, st.data]);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await apiFetch('/api/solve/physical-truth');
        if (!res.ok) throw new Error(`physical-truth → HTTP ${res.status}`);
        const j = await res.json();
        const rawRegions = j.regions as Record<string, unknown>[];
        // Legacy deviation metrics for the deviation heatmap (best effort).
        const deviationByName: Record<string, number> = {};
        try {
          // v32.1: the ranking endpoint caps limit at 200 (le=200) — a 300
          // request 422s and silently emptied the deviation heatmap.
          const dr = await apiFetch('/api/distortion/ranking?projection=Mercator&limit=200');
          if (dr.ok) {
            const dj = await dr.json();
            for (const row of (dj.ranking as Record<string, unknown>[]) || []) {
              const name = String(row.region ?? '');
              const rel = Number(row.relative_error_percent);
              if (name && Number.isFinite(rel)) deviationByName[name] = rel;
            }
          }
        } catch { /* deviation overlay is optional */ }
        const data: EarthSimulation3DData = {
          vertices: (j.vertices as number[][]) ||
            rawRegions.map((r) => (r.coords as number[]) || [0, 0, 0]),
          edges: (j.edges as number[][]) || [],
          regions: rawRegions.map((r) => ({
            name: String(r.name),
            area: Number(r.area_km2) || 0,
            deviation: deviationByName[String(r.name)] ?? null,
          })),
        };

        // v36.0: derived country boundary geometry (best-effort layer —
        // the dual view remains as fallback).
        let boundary: BoundaryCountry[] | null = null;
        let boundaryStats: LoadState['boundaryStats'] = null;
        try {
          const bres = await apiFetch('/api/boundaries/intrinsic');
          if (bres.ok) {
            const bj = await bres.json();
            boundary = ((bj.countries as Record<string, unknown>[]) || []).map((c) => ({
              name: String(c.name),
              rings: ((c.rings as number[][][]) || []) as [number, number][][],
              ringKinds: (c.ring_kinds as ('outer' | 'hole')[]) || [],
              area: Number(c.declared_area_km2) || 0,
              renderedArea: Number(c.rendered_area_km2) || undefined,
              deviation: deviationByName[String(c.name)] ?? null,
              anchored: Boolean(c.anchored),
            }));
            const bs = (bj.stats as Record<string, unknown>) || {};
            boundaryStats = {
              countries: Number(bs.countries) || (boundary ? boundary.length : 0),
              vertices: Number(bs.boundary_vertices) || 0,
              anchored: Number(bs.anchored_countries) || 0,
              shelf: Number(bs.shelf_countries) || 0,
            };
          }
        } catch { /* boundary layer is optional */ }
        if (!alive) return;
        setSt({
          loading: false, error: '', data,
          boundary,
          boundaryStats,
          residual: Number(j.residual) || 0,
          nodeCount: Number(j.node_count) || rawRegions.length,
          edgeCount: Number(j.edge_count) || (j.edges as unknown[])?.length || 0,
        });
      } catch (e) {
        if (alive) setSt((s) => ({ ...s, loading: false, error: (e as Error)?.message || 'failed to load manifold' }));
      }
    })();
    return () => { alive = false; };
  }, []);

  const onChange = useCallback(
    (patch: Partial<ControlState>) => setControls((c) => ({ ...c, ...patch })),
    [],
  );

  const totalArea = useMemo(
    () => (st.data?.regions || []).reduce((s, r) => s + (r.area || 0), 0),
    [st.data],
  );
  const deviationHits = useMemo(
    () => (st.data?.regions || []).filter((r) => r.deviation !== null).length,
    [st.data],
  );

  return (
    <div style={{ width: '100%', maxWidth: '1200px', margin: '0 auto', color: '#e6edf3' }}>
      <LLMPalette />
      <header style={{ marginBottom: '14px' }}>
        <h1 style={{ fontSize: '22px', fontWeight: 300, letterSpacing: '2px' }}>◈ 3D EARTH SIMULATION</h1>
        <p style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: '12px', marginTop: '6px', lineHeight: 1.6 }}>
          v37.1: GOOGLE-MAPS-STYLE INTERACTIVE MANIFOLD — left-drag pan · right-drag orbit/tilt · middle-drag or
          scroll zoom · double-click reset. With ELEVATION ON (top-right), clicking any point samples the ETOPO1
          height above sea level stored as a per-vertex physical scalar. Every country renders as its DERIVED
          BOUNDARY — a closed polygon reconstructed from globe-agnostic scalar data (edge lengths + walk-frame
          directions, stitched across shared borders, closed against declared absolute areas). No pre-seeded
          shape, no lon/lat, no WGS84, no EPSG. The intrinsic dual view (v33) remains available as a layer.
        </p>
      </header>

      <Disclaimer />

      {/* v32.0 deep-link focus banner */}
      {focusRegion && (
        <div
          style={{
            display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
            background: '#0d1117', border: '1px solid #1c2a38',
            borderLeft: `4px solid ${resolvedFocus ? '#00ff88' : '#f59e0b'}`,
            borderRadius: '8px', padding: '9px 14px', margin: '10px 0 0',
            fontFamily: 'monospace', fontSize: 11,
          }}
        >
          <span style={{ color: '#5b6b7b', letterSpacing: 1 }}>DEEP LINK · ?region=</span>
          <span style={{ color: resolvedFocus ? '#00ff88' : '#f59e0b', fontWeight: 600 }}>
            {focusRegion}
          </span>
          {resolvedFocus ? (
            <>
              <span style={{ color: '#5b6b7b' }}>
                focused on the Intrinsic Manifold — ringed in the viewport
              </span>
              <Link
                href={`/dashboard/physical-truth?region=${encodeURIComponent(resolvedFocus)}`}
                style={{ color: '#06b6d4', textDecoration: 'none' }}
              >
                open Truth Panel →
              </Link>
            </>
          ) : (
            <span style={{ color: '#5b6b7b' }}>
              {st.loading ? 'resolving against manifold…' : 'no matching region in the solved manifold'}
            </span>
          )}
          <button
            style={{ ...chip(false), padding: '4px 10px', marginLeft: 'auto' }}
            onClick={() => setFocusRegion(null)}
          >
            ✕ clear focus
          </button>
        </div>
      )}

      <div
        style={{
          display: 'flex', flexWrap: 'wrap', gap: '10px 14px', alignItems: 'center',
          background: '#0d1117', border: '1px solid #1c2a38', borderRadius: '10px',
          padding: '12px 14px', opacity: st.loading ? 0.5 : 1,
        }}
      >
        <Group label="GEOMETRY">
          <button style={chip(controls.geometryMode === 'boundary')} onClick={() => onChange({ geometryMode: 'boundary' })}>
            ◙ Boundaries (v36)
          </button>
          <button style={chip(controls.geometryMode === 'dual')} onClick={() => onChange({ geometryMode: 'dual' })}>
            ⬡ Intrinsic Dual (v33)
          </button>
        </Group>
        <Group label="MODE">
          <button style={chip(controls.mode === 'intrinsic')} onClick={() => onChange({ mode: 'intrinsic' })}>
            🧬 Intrinsic (solver output)
          </button>
          <button style={chip(controls.mode === 'area-preserving')} onClick={() => onChange({ mode: 'area-preserving' })}>
            ⚖ Area-Preserving
          </button>
        </Group>
        <Group label="HEATMAP">
          <button style={chip(controls.heatmap === 'area')} onClick={() => onChange({ heatmap: 'area' })}>
            🌡 True Area
          </button>
          <button style={chip(controls.heatmap === 'deviation')} onClick={() => onChange({ heatmap: 'deviation' })}>
            📕 Deviation from Legacy
          </button>
          <button style={chip(controls.heatmap === 'none')} onClick={() => onChange({ heatmap: 'none' })}>
            ◻ None
          </button>
        </Group>
        <Group label="VIEW">
          <button style={chip(controls.viewPreset === 'orbit')} onClick={() => onChange({ viewPreset: 'orbit' })}>
            🛰 3D Orbit
          </button>
          <button style={chip(controls.viewPreset === 'planar')} onClick={() => onChange({ viewPreset: 'planar' })}>
            🗺 2D Planar
          </button>
        </Group>
        <Group label="LAYERS">
          <button style={chip(controls.showLabels && controls.labelDensity === 'all')} onClick={() => onChange({ showLabels: true, labelDensity: 'all' })}>
            🏷 Labels·All
          </button>
          <button style={chip(controls.showLabels && controls.labelDensity === 'major')} onClick={() => onChange({ showLabels: true, labelDensity: 'major' })}>
            🏷 Labels·Major
          </button>
          <button style={chip(!controls.showLabels)} onClick={() => onChange({ showLabels: false })}>
            🏷 Off
          </button>
          <button style={chip(controls.showNodes)} onClick={() => onChange({ showNodes: !controls.showNodes })}>
            ◉ Seed Points
          </button>
          <button style={chip(controls.autoRotate)} onClick={() => onChange({ autoRotate: !controls.autoRotate })}>
            🔄 Auto-rotate
          </button>
        </Group>
      </div>

      <div style={{ height: '580px', margin: '14px 0 16px', position: 'relative' }}>
        {st.loading ? (
          <ViewportLoading text="fetching intrinsic manifold from /api/solve/physical-truth…" />
        ) : st.error || !st.data ? (
          <ViewportLoading text={`⚠ ${st.error || 'manifold unavailable'} — retry shortly`} />
        ) : controls.geometryMode === 'boundary' && st.boundary ? (
          <>
            <InteractiveEarth3D
              data={st.data}
              boundaryData={st.boundary}
              heatmap={controls.heatmap}
              showLabels={controls.showLabels}
              labelDensity={controls.showLabels ? controls.labelDensity : 'none'}
              selectedRegion={resolvedFocus}
              autoRotate={controls.autoRotate}
              viewPreset={controls.viewPreset}
              elevationEnabled={elevationOn}
              onElevationUpdate={setElevation}
              onRenderStats={onRenderStats}
              onRegionClick={(region) =>
                router.push(`/dashboard/physical-truth?region=${encodeURIComponent(region)}`)
              }
              hudSuffix={`RESIDUAL ${st.residual.toExponential(3)}`}
            />
            <ElevationToggle
              enabled={elevationOn}
              onToggle={(next) => { setElevationOn(next); if (!next) setElevation(null); }}
              elevation={elevation}
            />
          </>
        ) : (
          <EarthSimulation3D
            data={st.data}
            boundaryData={st.boundary}
            geometryMode={controls.geometryMode === 'boundary' && st.boundary ? 'boundary' : 'dual'}
            mode={controls.mode}
            heatmap={controls.heatmap}
            showLabels={controls.showLabels}
            showHull={controls.showTerritory}
            showNodes={controls.showNodes}
            onRenderStats={onRenderStats}
            autoRotate={controls.autoRotate}
            viewPreset={controls.viewPreset}
            selectedRegion={resolvedFocus}
            labelDensity={controls.showLabels ? controls.labelDensity : 'none'}
            onRegionClick={(region) =>
              router.push(`/dashboard/physical-truth?region=${encodeURIComponent(region)}`)
            }
            hudSuffix={`RESIDUAL ${st.residual.toExponential(3)}`}
          />
        )}
      </div>

      {/* LEGEND PANEL — mandatory per v30.1 */}
      <div
        style={{
          display: 'flex', flexWrap: 'wrap', gap: 18, alignItems: 'center',
          background: '#0d1117', border: '1px solid #1c2a38', borderLeft: '4px solid #06b6d4',
          borderRadius: '10px', padding: '12px 16px', fontFamily: 'monospace', fontSize: 11,
        }}
      >
        <div>
          <span style={{ color: '#5b6b7b' }}>GEOMETRY · </span>
          <span style={{ color: '#00ff88' }}>
            {controls.geometryMode === 'boundary'
              ? 'Derived country boundaries — turtle-walk reconstruction from scalar lengths + directions, stitched across shared borders'
              : 'Intrinsic dual — area-weighted capture cells of the intrinsic point set'}
          </span>
        </div>
        <div>
          <span style={{ color: '#5b6b7b' }}>MODE · </span>
          <span style={{ color: '#00ff88' }}>
            {controls.mode === 'intrinsic'
              ? 'Intrinsic — solver coordinates + unweighted dual, as produced'
              : 'Area-Preserving — dual re-derived from declared areas, coordinates untouched'}
          </span>
        </div>
        <div>
          <span style={{ color: '#5b6b7b' }}>REGIONS RENDERED · </span>
          <span style={{ color: '#e6edf3' }}>{st.data?.regions.length ?? 0}</span>
        </div>
        <div>
          <span style={{ color: '#5b6b7b' }}>SOLVER RESIDUAL (STRESS-1) · </span>
          <span style={{ color: '#e6edf3' }}>{st.residual.toExponential(4)}</span>
        </div>
        <div>
          <span style={{ color: '#5b6b7b' }}>LABELS · </span>
          <span style={{ color: '#e6edf3' }}>
            {controls.showLabels
              ? controls.labelDensity === 'all' ? 'All regions (area-scaled)' : 'Major regions (top 24)'
              : 'Off'}
          </span>
        </div>
        <div>
          <span style={{ color: '#5b6b7b' }}>HEATMAP · </span>
          <span style={{ color: '#e6edf3' }}>
            {controls.heatmap === 'none' ? 'None' : controls.heatmap === 'area' ? 'True Area (log)' : `Legacy Deviation (${deviationHits} metrics)`}
          </span>
        </div>
        <div>
          <span style={{ color: '#5b6b7b' }}>TERRITORIES · </span>
          <span style={{ color: '#e6edf3' }}>
            {renderStats
              ? `${renderStats.cells} closed polygons · ${renderStats.borderSegments} ${controls.geometryMode === 'boundary' ? 'boundary rings' : 'border edges'}`
              : 'computing…'}
          </span>
        </div>
        <div>
          <span style={{ color: '#5b6b7b' }}>RENDERED↔DECLARED AREA r · </span>
          <span style={{ color: renderStats?.areaCorrelation != null ? '#00ff88' : '#e6edf3' }}>
            {renderStats?.areaCorrelation != null
              ? renderStats.areaCorrelation.toFixed(3)
              : '—'}
          </span>
        </div>
        {controls.heatmap === 'area' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ color: '#5b6b7b' }}>SCALE · </span>
            <span style={{ color: '#5b6b7b' }}>small</span>
            <span style={{
              width: 90, height: 8, borderRadius: 4,
              background: 'linear-gradient(90deg, rgb(13,48,36), rgb(0,255,136))', display: 'inline-block',
            }} />
            <span style={{ color: '#5b6b7b' }}>large</span>
          </div>
        )}
        {controls.heatmap === 'deviation' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ color: '#5b6b7b' }}>SCALE · </span>
            <span style={{ color: '#3b82f6' }}>■ shrunk</span>
            <span style={{ color: '#5b6b7b' }}>■ neutral</span>
            <span style={{ color: '#ff3b3b' }}>inflated ■</span>
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '10px', marginTop: 14 }}>
        <Stat label="Countries (territories)" value={String(st.nodeCount)} accent />
        <Stat label="Boundary Countries (v36)" value={String(st.boundaryStats?.countries ?? '—')} accent />
        <Stat label="Boundary Vertices" value={st.boundaryStats ? st.boundaryStats.vertices.toLocaleString() : '—'} />
        <Stat label="Intrinsic Edges" value={String(st.edgeCount)} />
        <Stat label="Convergence Residual" value={st.residual.toExponential(4)} accent />
        <Stat label="Σ True Area" value={`${totalArea.toLocaleString()} km²`} />
        <Stat label="Deviation Metrics" value={String(deviationHits)} />
        <Stat label="Source" value={controls.geometryMode === 'boundary' ? '/api/boundaries/intrinsic' : '/api/solve/physical-truth'} />
      </div>

      {controls.geometryMode === 'boundary' && (
        <p style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: '11px', marginTop: '12px', lineHeight: 1.6 }}>
          Boundary geometry disclosure: every country polygon is reconstructed from
          globe-agnostic scalar data only — per-edge lengths and walk-frame directions
          (an exact turtle-walk), stitched rigidly across shared border vertices,
          rotated/translated onto the platform&apos;s own Physical Truth intrinsic layout,
          and closed against declared absolute areas by one global scale. No lon/lat,
          no WGS84, no EPSG enters the pipeline. Countries with no scalar anchor to the
          layout are placed on a deterministic shelf and disclosed in the stats. This is
          a geometric simulation for transparency and analysis — not a navigational or
          legal boundary reference.
        </p>
      )}

      {elevationOn && (
        <p style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: '11px', marginTop: '12px', lineHeight: 1.6 }}>
          Elevation disclosure: with the toggle ON, clicking any point of the manifold samples the height above
          sea level from the ETOPO1 global DEM (1 arc-minute, NGDC/NOAA), ingested as a per-vertex physical
          SCALAR at the boundary vertices. The sample is resolved by nearest intrinsic vertex (~1 arc-minute
          ground resolution) and is a terrain/bathymetry estimate — not a survey-grade altitude, geoid model or
          navigation aid. The DEM&apos;s own coordinates were discarded at ingestion; only the scalar survives.
        </p>
      )}

      {controls.mode === 'area-preserving' && (
        <p style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: '11px', marginTop: '12px', lineHeight: 1.6 }}>
          Area-Preserving mode re-derives the territory boundaries from the declared
          absolute scalar areas (km²): every country&apos;s capture boundary moves so its
          rendered cell area approaches its Physical Truth value. The intrinsic
          coordinates themselves are never modified — the same solver output is
          rendered in both modes; only the dual&apos;s boundary placement changes,
          recomputed deterministically in the browser. The residual gap is disclosed
          by the RENDERED↔DECLARED AREA correlation above.
        </p>
      )}

      <p style={{ marginTop: '22px', display: 'flex', gap: '18px', flexWrap: 'wrap' }}>
        <Link href="/dashboard" style={{ color: '#06b6d4', fontFamily: 'monospace', fontSize: '12px', textDecoration: 'none' }}>
          ← back to system overview
        </Link>
        <Link href="/dashboard/truth" style={{ color: '#06b6d4', fontFamily: 'monospace', fontSize: '12px', textDecoration: 'none' }}>
          ⚖️ truth portal →
        </Link>
      </p>
    </div>
  );
}
