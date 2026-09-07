'use client';

/**
 * AETHERA v27.0 — /dashboard/globe
 *
 * The True-Area Globe page. Renders the emergent Physical Truth manifold
 * as an interactive 3D object — no pre-seeded sphere, no projection, no
 * lon/lat. Regions are clickable (→ module page), hoverable (Physical
 * Truth tooltip), and colorable by true area or legacy-map deviation.
 */

import { useCallback, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import LLMPalette from '@/components/LLMPalette';
import GlobeControls, { type GlobeControlState } from '@/components/ui/GlobeControls';
import { useTrueGlobe } from '@/components/three/TrueGlobe';

const TrueGlobe = dynamic(() => import('@/components/three/TrueGlobe'), {
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

const INITIAL_CONTROLS: GlobeControlState = {
  heatMode: 'area',
  showLabels: true,
  showMesh: true,
  autoRotate: false,
  viewPreset: 'orbit',
  projection: 'Mercator',
};

export default function GlobePage() {
  const [controls, setControls] = useState<GlobeControlState>(INITIAL_CONTROLS);
  const globe = useTrueGlobe(controls.projection);
  const router = useRouter();

  const onChange = useCallback(
    (patch: Partial<GlobeControlState>) => setControls((c) => ({ ...c, ...patch })),
    [],
  );

  const topOver = useMemo(() => {
    const rows = globe.ranking
      .filter((r) => Number(r.relative_error_percent) < 0)
      .sort((a, b) => Number(a.relative_error_percent) - Number(b.relative_error_percent));
    return rows[0] || null;
  }, [globe.ranking]);

  const topUnder = useMemo(() => {
    const rows = globe.ranking
      .filter((r) => Number(r.relative_error_percent) > 0)
      .sort((a, b) => Number(b.relative_error_percent) - Number(a.relative_error_percent));
    return rows[0] || null;
  }, [globe.ranking]);

  const totalArea = useMemo(
    () => globe.regions.reduce((s, r) => s + (r.area_km2 || 0), 0),
    [globe.regions],
  );

  return (
    <div style={{ width: '100%', maxWidth: '1200px', margin: '0 auto', color: '#e6edf3' }}>
      <LLMPalette />
      <header style={{ marginBottom: '18px' }}>
        <h1 style={{ fontSize: '22px', fontWeight: 300, letterSpacing: '2px' }}>🌍 TRUE-AREA GLOBE</h1>
        <p style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: '12px', marginTop: '6px', lineHeight: 1.6 }}>
          The globe without assumptions — shape emerges purely from absolute scalar data
          (areas and edge lengths). No sphere is ever assumed; today the solved manifold is
          planar (z ≈ 0), so it renders planar. Every region keeps its true area. Hover a
          node for its Physical Truth, click to open its module page.
        </p>
      </header>

      <GlobeControls state={controls} onChange={onChange} disabled={globe.loading} />

      <div style={{ height: '580px', margin: '14px 0 16px' }}>
        <TrueGlobe
          globe={globe}
          heatMode={controls.heatMode}
          showLabels={controls.showLabels}
          showMesh={controls.showMesh}
          autoRotate={controls.autoRotate}
          viewPreset={controls.viewPreset}
          onRegionClick={(region) =>
            router.push(`/dashboard/physical-truth?region=${encodeURIComponent(region)}`)
          }
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '10px' }}>
        <Stat label="Regions (nodes)" value={String(globe.nodeCount || globe.regions.length)} accent />
        <Stat label="Mesh Edges" value={String(globe.edgeCount)} />
        <Stat label="Convergence Residual" value={(globe.residual || 0).toExponential(4)} accent />
        <Stat label="Σ True Area" value={`${totalArea.toLocaleString()} km²`} />
        <Stat
          label="Most Inflated (legacy)"
          value={topOver ? `${topOver.region} (${Number(topOver.relative_error_percent).toFixed(0)} %)` : '—'}
        />
        <Stat
          label="Most Shrunk (legacy)"
          value={topUnder ? `${topUnder.region} (+${Number(topUnder.relative_error_percent).toFixed(0)} %)` : '—'}
        />
      </div>

      {controls.heatMode === 'legacy' && (
        <p style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: '11px', marginTop: '12px', lineHeight: 1.6 }}>
          Legacy deviation = (legacy area − physical area) relative to the physical truth, as
          recorded against the selected legacy projection. Red nodes were INFLATED by the
          legacy map; blue nodes were SHRUNK. Regions without a recorded metric stay neutral.
        </p>
      )}

      <p style={{ marginTop: '22px', display: 'flex', gap: '18px' }}>
        <Link href="/dashboard" style={{ color: '#06b6d4', fontFamily: 'monospace', fontSize: '12px', textDecoration: 'none' }}>
          ← back to system overview
        </Link>
        <Link href="/dashboard/simulator3d" style={{ color: '#06b6d4', fontFamily: 'monospace', fontSize: '12px', textDecoration: 'none' }}>
          🧊 3D simulator →
        </Link>
      </p>
    </div>
  );
}
