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
 * Features: intrinsic ↔ area-preserving modes, heatmap toggles (none /
 * true area / legacy deviation), OrbitControls, hover tooltips, click →
 * region module page, legend panel with live solver stats, and the
 * mandatory prominent disclaimer.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import LLMPalette from '@/components/LLMPalette';
import Disclaimer from '@/components/Disclaimer';
import { apiFetch } from '@/lib/api';
import type { EarthSimulation3DData } from '@/components/three/EarthSimulation3D';

const EarthSimulation3D = dynamic(() => import('@/components/three/EarthSimulation3D'), {
  ssr: false,
  loading: () => <GlobeLoading text="initialising WebGL viewport…" />,
});

function GlobeLoading({ text }: { text: string }) {
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

interface ControlState {
  mode: Mode;
  heatmap: Heatmap;
  showLabels: boolean;
  showHull: boolean;
  autoRotate: boolean;
  viewPreset: 'orbit' | 'planar';
}

const INITIAL_CONTROLS: ControlState = {
  mode: 'intrinsic',
  heatmap: 'area',
  showLabels: true,
  showHull: true,
  autoRotate: false,
  viewPreset: 'orbit',
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
  residual: number;
  nodeCount: number;
  edgeCount: number;
}

export default function Earth3DPage() {
  const [controls, setControls] = useState<ControlState>(INITIAL_CONTROLS);
  const [st, setSt] = useState<LoadState>({
    loading: true, error: '', data: null,
    residual: 0, nodeCount: 0, edgeCount: 0,
  });
  const router = useRouter();

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
          const dr = await apiFetch('/api/distortion/ranking?projection=Mercator&limit=300');
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
        if (!alive) return;
        setSt({
          loading: false, error: '', data,
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
        <h1 style={{ fontSize: '22px', fontWeight: 300, letterSpacing: '2px' }}>🌍 3D EARTH SIMULATION</h1>
        <p style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: '12px', marginTop: '6px', lineHeight: 1.6 }}>
          The platform fetches the solved intrinsic manifold and renders it in 3D.
          Vertices = intrinsic coordinates · edges = the solver&apos;s intrinsic edge graph ·
          colors = absolute scalar data. No sphere, no lon/lat, no WGS84 — the shape
          is whatever the data says it is.
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
          <button style={chip(controls.showLabels)} onClick={() => onChange({ showLabels: !controls.showLabels })}>
            🏷 Labels
          </button>
          <button style={chip(controls.showHull)} onClick={() => onChange({ showHull: !controls.showHull })}>
            🕸 Hull
          </button>
          <button style={chip(controls.autoRotate)} onClick={() => onChange({ autoRotate: !controls.autoRotate })}>
            🔄 Auto-rotate
          </button>
        </Group>
      </div>

      <div style={{ height: '580px', margin: '14px 0 16px' }}>
        {st.loading ? (
          <GlobeLoading text="fetching intrinsic manifold from /api/solve/physical-truth…" />
        ) : st.error || !st.data ? (
          <GlobeLoading text={`⚠ ${st.error || 'manifold unavailable'} — retry shortly`} />
        ) : (
          <EarthSimulation3D
            data={st.data}
            mode={controls.mode}
            heatmap={controls.heatmap}
            showLabels={controls.showLabels}
            showHull={controls.showHull}
            autoRotate={controls.autoRotate}
            viewPreset={controls.viewPreset}
            selectedRegion={resolvedFocus}
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
          <span style={{ color: '#5b6b7b' }}>MODE · </span>
          <span style={{ color: '#00ff88' }}>
            {controls.mode === 'intrinsic'
              ? 'Intrinsic — solver coordinates, untouched'
              : 'Area-Preserving — post-hoc equal-area relaxation'}
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
          <span style={{ color: '#5b6b7b' }}>HEATMAP · </span>
          <span style={{ color: '#e6edf3' }}>
            {controls.heatmap === 'none' ? 'None' : controls.heatmap === 'area' ? 'True Area (log)' : `Legacy Deviation (${deviationHits} metrics)`}
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
        <Stat label="Regions (nodes)" value={String(st.nodeCount)} accent />
        <Stat label="Intrinsic Edges" value={String(st.edgeCount)} />
        <Stat label="Convergence Residual" value={st.residual.toExponential(4)} accent />
        <Stat label="Σ True Area" value={`${totalArea.toLocaleString()} km²`} />
        <Stat label="Deviation Metrics" value={String(deviationHits)} />
        <Stat label="Source" value="/api/solve/physical-truth" />
      </div>

      {controls.mode === 'area-preserving' && (
        <p style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: '11px', marginTop: '12px', lineHeight: 1.6 }}>
          Area-Preserving mode applies a post-hoc equal-area relaxation to the rendered
          embedding: each region&apos;s rendered footprint is iteratively driven toward its
          absolute scalar area (km²). The intrinsic solve itself is never modified — the
          transform is a purely visual derivation, recomputed deterministically in the browser.
        </p>
      )}

      <p style={{ marginTop: '22px', display: 'flex', gap: '18px', flexWrap: 'wrap' }}>
        <Link href="/dashboard" style={{ color: '#06b6d4', fontFamily: 'monospace', fontSize: '12px', textDecoration: 'none' }}>
          ← back to system overview
        </Link>
        <Link href="/dashboard/globe" style={{ color: '#06b6d4', fontFamily: 'monospace', fontSize: '12px', textDecoration: 'none' }}>
          🌍 true-area globe →
        </Link>
        <Link href="/dashboard/truth" style={{ color: '#06b6d4', fontFamily: 'monospace', fontSize: '12px', textDecoration: 'none' }}>
          ⚖️ truth portal →
        </Link>
      </p>
    </div>
  );
}
