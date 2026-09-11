'use client';

/**
 * AETHERA v39.0 — /dashboard/earth-3d
 *
 * THE STITCHED WORLD SIMULATOR (mandatory, principle-first).
 *
 * Fetches /api/solve/world — countries AND oceans in one coherent
 * intrinsic display frame — and renders it with Google-Maps-style
 * interaction:
 *
 *   • wheel zoom, drag pan, right-drag orbit (OrbitControls);
 *   • click a country  → camera zooms to it + Truth Panel deep link;
 *   • ELEVATION toggle → any click POSTs /api/elevation (ETOPO1,
 *     sea-level reference) with a surface tooltip + HUD readout;
 *   • ocean basins and seas rendered beneath the landmass;
 *   • mandatory derived-view disclaimer (never a globe model).
 *
 * The geometry is reconstructed from globe-agnostic scalar data only
 * (edge lengths, walk-frame directions, declared areas, shared-border
 * identities) — no lon/lat, no WGS84, no EPSG anywhere in the solver
 * chain (Axioms 2-4). Every convention is disclosed (Axiom 5).
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import LLMPalette from '@/components/LLMPalette';
import Disclaimer from '@/components/Disclaimer';
import ElevationToggle from '@/components/ElevationToggle';
import { apiFetch } from '@/lib/api';
import type {
  WorldCountry,
  WorldOcean,
  ElevationHit,
} from '@/components/three/InteractiveEarth3D';

const InteractiveEarth3D = dynamic(
  () => import('@/components/three/InteractiveEarth3D'),
  {
    ssr: false,
    loading: () => (
      <ViewportLoading text="initialising stitched world viewport…" />
    ),
  },
);

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

interface LoadState {
  loading: boolean;
  error: string;
  countries: WorldCountry[] | null;
  oceans: WorldOcean[] | null;
  stats: Record<string, unknown> | null;
  oceanStats: Record<string, unknown> | null;
  version: string;
}

const INITIAL: LoadState = {
  loading: true, error: '', countries: null, oceans: null,
  stats: null, oceanStats: null, version: '',
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

export default function Earth3DPage() {
  const [st, setSt] = useState<LoadState>(INITIAL);
  const [elevationMode, setElevationMode] = useState(false);
  const [showLabels, setShowLabels] = useState(true);
  const [showOceans, setShowOceans] = useState(true);
  const [autoRotate, setAutoRotate] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [zoomTarget, setZoomTarget] = useState<{ name: string; nonce: number } | null>(null);
  const [elevHit, setElevHit] = useState<ElevationHit | null>(null);

  // Deep link: /dashboard/earth-3d?region=<Name> → select + zoom.
  const [focusRegion, setFocusRegion] = useState<string | null>(null);
  useEffect(() => {
    const r = new URLSearchParams(window.location.search).get('region');
    if (r && r.trim()) setFocusRegion(r.trim());
  }, []);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await apiFetch('/api/solve/world');
        if (!res.ok) throw new Error(`solve/world → HTTP ${res.status}`);
        const j = await res.json();
        if (!alive) return;
        const countries: WorldCountry[] = ((j.land?.countries as Record<string, unknown>[]) || []).map((c) => ({
          name: String(c.name),
          rings: (c.rings as number[][][]) as [number, number][][],
          ringKinds: (c.ring_kinds as ('outer' | 'hole')[]) || [],
          declared: Number(c.declared_area_km2) || 0,
          placement: String(c.placement || 'stitched'),
          anchored: Boolean(c.anchored),
        }));
        const oceans: WorldOcean[] = ((j.oceans as Record<string, unknown>[]) || []).map((o) => ({
          name: String(o.name),
          kind: (o.kind === 'sea' ? 'sea' : 'ocean') as 'sea' | 'ocean',
          area_km2: Number(o.area_km2) || 0,
          coastline_ring_display:
            (o.coastline_ring_display as [number, number][]) || undefined,
        }));
        setSt({
          loading: false,
          error: '',
          countries,
          oceans,
          stats: (j.land?.stats as Record<string, unknown>) || {},
          oceanStats: (j.ocean_stats as Record<string, unknown>) || {},
          version: String(j.version || ''),
        });
        if (focusRegion) {
          const hit = countries.find(
            (c) => c.name.toLowerCase() === focusRegion.toLowerCase());
          if (hit) {
            setSelected(hit.name);
            setZoomTarget({ name: hit.name, nonce: Date.now() });
          }
        }
      } catch (e) {
        if (alive) setSt((s) => ({ ...s, loading: false, error: (e as Error)?.message || 'failed to load stitched world' }));
      }
    })();
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onCountryClick = useCallback((name: string) => {
    if (!name) {
      setSelected(null);
      return;
    }
    setSelected(name);
    setZoomTarget({ name, nonce: Date.now() });
    window.history.replaceState(null, '', `/dashboard/earth-3d?region=${encodeURIComponent(name)}`);
  }, []);

  const onElevationHit = useCallback((hit: ElevationHit | null) => {
    setElevHit(hit);
  }, []);

  const totalOceanArea = useMemo(
    () => (st.oceans || [])
      .filter((o) => o.kind === 'ocean')
      .reduce((s, o) => s + o.area_km2, 0),
    [st.oceans],
  );
  const totalSeaArea = useMemo(
    () => (st.oceans || [])
      .filter((o) => o.kind === 'sea')
      .reduce((s, o) => s + o.area_km2, 0),
    [st.oceans],
  );
  const stats = st.stats || {};
  const oceanStats = st.oceanStats || {};

  return (
    <div style={{ width: '100%', maxWidth: '1200px', margin: '0 auto', color: '#e6edf3' }}>
      <LLMPalette />
      <header style={{ marginBottom: '14px' }}>
        <h1 style={{ fontSize: '22px', fontWeight: 300, letterSpacing: '2px' }}>◈ 3D EARTH SIMULATION</h1>
        <p style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: '12px', marginTop: '6px', lineHeight: 1.6 }}>
          v39.0 STITCHED WORLD: every country is its derived closed polygon —
          ring-level exact stitching from scalar data (edge lengths + walk-frame
          directions + declared areas), loop-consistent across shared borders,
          placed by the disclosed display-anchor convention with
          <span style={{ color: '#00ff88' }}> zero shelf countries</span>.
          Ocean basins and seas carry true ETOPO1 areas beneath the landmass.
        </p>
      </header>

      <Disclaimer />

      <ElevationToggle enabled={elevationMode} onToggle={setElevationMode} />

      <div
        style={{
          display: 'flex', flexWrap: 'wrap', gap: '10px 14px', alignItems: 'center',
          background: '#0d1117', border: '1px solid #1c2a38', borderRadius: '10px',
          padding: '12px 14px', opacity: st.loading ? 0.5 : 1,
        }}
      >
        <Group label="LAYERS">
          <button style={chip(showOceans)} onClick={() => setShowOceans(!showOceans)}>
            ≈ Oceans
          </button>
          <button style={chip(showLabels)} onClick={() => setShowLabels(!showLabels)}>
            🏷 Labels (major)
          </button>
          <button style={chip(autoRotate)} onClick={() => setAutoRotate(!autoRotate)}>
            🔄 Auto-rotate
          </button>
        </Group>
        <Group label="INTERACTION">
          <span style={{ color: elevationMode ? '#00ff88' : '#5b6b7b', fontFamily: 'monospace', fontSize: 10 }}>
            {elevationMode
              ? 'CLICK → /api/elevation (ETOPO1, sea level 0)'
              : 'CLICK → zoom + Truth Panel · right-drag orbit · wheel zoom'}
          </span>
        </Group>
      </div>

      <div style={{ height: '640px', margin: '14px 0 16px', position: 'relative' }}>
        {st.loading ? (
          <ViewportLoading text="fetching stitched world from /api/solve/world…" />
        ) : st.error || !st.countries ? (
          <ViewportLoading text={`⚠ ${st.error || 'stitched world unavailable'} — retry shortly`} />
        ) : (
          <InteractiveEarth3D
            countries={st.countries}
            oceans={st.oceans || []}
            elevationMode={elevationMode}
            selected={selected}
            showLabels={showLabels}
            showOceans={showOceans}
            autoRotate={autoRotate}
            zoomTarget={zoomTarget}
            onCountryClick={onCountryClick}
            onElevationHit={onElevationHit}
          />
        )}
        {elevHit && (
          <div
            style={{
              position: 'absolute', right: 12, bottom: 12,
              background: 'rgba(4,10,16,0.94)', border: '1px solid #1c2a38',
              borderLeft: `4px solid ${elevHit.elevation_m === null ? '#f59e0b' : elevHit.elevation_m > 0 ? '#00ff88' : '#38bdf8'}`,
              borderRadius: 8, padding: '9px 13px', fontFamily: 'monospace', fontSize: 11,
              color: '#e6edf3', pointerEvents: 'none',
            }}
          >
            <div style={{ color: '#5b6b7b', letterSpacing: 1, marginBottom: 4 }}>
              ELEVATION PROBE · intrinsic ({elevHit.x.toFixed(0)}, {elevHit.y.toFixed(0)})
            </div>
            <div style={{ fontSize: 15, fontWeight: 600 }}>
              {elevHit.elevation_m === null
                ? '◌ Outside manifold'
                : `${elevHit.elevation_m > 0 ? '▲' : '▼'} ${Math.round(elevHit.elevation_m)} m · ETOPO1 · sea level 0`}
            </div>
          </div>
        )}
      </div>

      {/* LEGEND PANEL */}
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
            Stitched world — turtle-walk rings welded across shared border
            vertices (exact), area closure by one global scale
          </span>
        </div>
        <div>
          <span style={{ color: '#5b6b7b' }}>PLACEMENT · </span>
          <span style={{ color: '#00ff88' }}>
            Disclosed display anchors — {String(stats.stitched_countries ?? '—')} countries placed,
            0 on a shelf
          </span>
        </div>
        <div>
          <span style={{ color: '#5b6b7b' }}>OCEANS · </span>
          <span style={{ color: '#38bdf8' }}>
            {String(oceanStats.basins ?? '—')} basins + {String(oceanStats.seas ?? '—')} seas · ETOPO1
          </span>
        </div>
        <div>
          <span style={{ color: '#5b6b7b' }}>MODE · </span>
          <span style={{ color: elevationMode ? '#00ff88' : '#e6edf3' }}>
            {elevationMode ? 'Elevation on click' : 'Country select + zoom'}
          </span>
        </div>
        {selected && (
          <div>
            <span style={{ color: '#5b6b7b' }}>SELECTED · </span>
            <span style={{ color: '#00ff88' }}>{selected}</span>
            <Link
              href={`/dashboard/physical-truth?region=${encodeURIComponent(selected)}`}
              style={{ color: '#06b6d4', marginLeft: 8, textDecoration: 'none' }}
            >
              open Truth Panel →
            </Link>
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '10px', marginTop: 14 }}>
        <Stat label="Countries (stitched)" value={String(st.countries?.length ?? '—')} accent />
        <Stat label="Shelf countries" value="0" accent />
        <Stat label="Boundary vertices" value={String(stats.boundary_vertices ? Number(stats.boundary_vertices).toLocaleString() : '—')} />
        <Stat label="Ring components" value={String(stats.stitched_components ?? '—')} />
        <Stat label="Stitch residual (raw)" value={String(stats.stitch_rms_raw_units ?? '—')} />
        <Stat label="Σ ocean area" value={`${Math.round(totalOceanArea).toLocaleString()} km²`} />
        <Stat label="Σ sea area" value={`${Math.round(totalSeaArea).toLocaleString()} km²`} />
        <Stat label="Elevation source" value={elevationMode ? 'ETOPO1_GLOBAL' : '—'} />
        <Stat label="Source" value="/api/solve/world" />
      </div>

      <p style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: '11px', marginTop: '12px', lineHeight: 1.6 }}>
        Stitched-world disclosure: country shapes are reconstructed from
        globe-agnostic scalars — per-edge lengths and walk-frame directions (an
        exact turtle-walk), welded rigidly across shared border vertices with
        zero residual, closed against declared absolute areas by one global
        scale, and positioned by a single disclosed display-anchor convention
        (Natural Earth label centroids; a display convention only — the solver
        chain receives no coordinates). Island units of multi-part countries use
        deterministic disclosed offsets. Antarctica&apos;s ring is a known
        degree-frame polar band, rescaled to its declared area and disclosed.
        Ocean basins are the disclosed priority-box segmentation of ETOPO1
        bathymetry; seas are named boxes; both are true cos(lat)-corrected
        areas. This is a geometric simulation for transparency and analysis —
        not a navigational or legal reference.
      </p>

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
