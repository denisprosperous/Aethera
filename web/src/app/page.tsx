'use client';
import { useMemo, useState } from 'react';
import StrainTensorView from '@/components/StrainTensorView';
import { CONTINENT_POLYGONS } from '@/lib/polygons';
import { allScores, PROJECTIONS } from '@/lib/projections';

export default function Home() {
  const [projection, setProjection] = useState('Mercator');
  const scores = useMemo(() => allScores(CONTINENT_POLYGONS), []);

  return (
    <main className="min-h-screen bg-black text-white">
      <header className="border-b border-white/10 px-8 py-6">
        <div className="flex items-baseline justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">AETHERA — Consensus Hall of Shame</h1>
            <p className="text-sm text-white/60 mt-1">
              Strain tensor overlay of scholarly map projections. Pure geometric substrate — no radius, no G, no ephemeris.
            </p>
          </div>
          <div className="text-xs text-white/40 font-mono">v0.2.0 · geometry provider · not a weapons controller</div>
        </div>
      </header>
      <div className="grid grid-cols-12 gap-0">
        <aside className="col-span-2 border-r border-white/10 p-4 space-y-2">
          <h2 className="text-xs uppercase tracking-wider text-white/40 mb-2">Projection</h2>
          {Object.keys(PROJECTIONS).map((name) => (
            <button key={name} onClick={() => setProjection(name)}
              className={`block w-full text-left px-3 py-2 rounded text-sm transition ${
                projection === name ? 'bg-cyan-500 text-black font-semibold' : 'bg-white/5 hover:bg-white/10 text-white/80'
              }`}>{name}</button>
          ))}
        </aside>
        <section className="col-span-7 border-r border-white/10 h-[80vh]">
          <StrainTensorView polygons={CONTINENT_POLYGONS} projection={projection} />
        </section>
        <aside className="col-span-3 p-4 space-y-4 overflow-y-auto h-[80vh]">
          <h2 className="text-xs uppercase tracking-wider text-white/40 mb-2">Colonial Distortion Scores</h2>
          <p className="text-xs text-white/60">Positive = inflates historically colonising nations. Pure geometric scalar.</p>
          <div className="space-y-2">
            {scores.map((s) => (
              <div key={s.projection}
                onClick={() => setProjection(s.projection)}
                className={`p-3 rounded border cursor-pointer transition ${
                  projection === s.projection ? 'border-cyan-500 bg-cyan-500/10' : 'border-white/10 bg-white/5'
                }`}>
                <div className="flex justify-between items-baseline">
                  <div className="font-semibold text-sm">{s.projection}</div>
                  <div className={`font-mono text-xs ${
                    s.colonialDistortionScore > 0 ? 'text-red-400' : 'text-blue-400'
                  }`}>{s.colonialDistortionScore > 0 ? '+' : ''}{s.colonialDistortionScore.toFixed(3)}</div>
                </div>
                <div className="text-xs text-white/50 mt-1">
                  max infl: {s.maxInflation.toFixed(2)} · max defl: {s.maxDeflation.toFixed(2)}
                </div>
              </div>
            ))}
          </div>
        </aside>
      </div>
      <footer className="border-t border-white/10 px-8 py-6 bg-white/[0.02]">
        <h2 className="text-xs uppercase tracking-wider text-white/40 mb-3">AETHERA Substrate — Agents & Modules (v6.0)</h2>
        <div className="grid grid-cols-4 gap-3 text-xs">
          <Card name="Agent 0 — Ghost Resolver" desc="Residual closure, 5% threshold, rationale log" ok />
          <Card name="Agent 2 — Intrinsic Geometer" desc="Weighted SMACOF + curvature" ok />
          <Card name="Agent 6 — ACIF Navigator" desc="Atomic-interferometry + VLBI" ok />
          <Card name="Agent 8 — Alien Geometer" desc="Topology-agnostic shape reconstruction" ok />
          <Card name="Agent 7 — Dynamics (reformed)" desc="Dual-mode: geodesic + user-force-field. No targeting." ok />
          <Card name="Module 5A — Transparency" desc="Range-vs-chord comparator" ok />
          <Card name="Module 5B — Strain Visualizer" desc="Seismic strain (not a predictor)" ok />
          <Card name="Module 5C — Anomaly Daemon" desc="Civil-scientific: groundwater, glacial, volcanic" ok />
          <Card name="Module 5D — Maritime" desc="Chokepoint navigability" ok />
          <Card name="Module 5E — Hall of Shame" desc="Strain tensor overlay (this view)" ok />
          <Card name="Module 5F — Terraformation" desc="Volume-transfer coastline" ok />
          <Card name="Module 5G — Stellar" desc="Deep-space probe VLBI" ok />
        </div>
        <p className="text-xs text-white/40 mt-4">
          AETHERA v6.0 — hardened physics, transparent ethics. The platform is a geometry provider, not a weapons controller.
        </p>
      </footer>
    </main>
  );
}

function Card({ name, desc, ok }: { name: string; desc: string; ok: boolean }) {
  return (
    <div className={`p-3 rounded border ${ok ? 'border-cyan-500/30 bg-cyan-500/5' : 'border-red-500/30 bg-red-500/5'}`}>
      <div className="flex items-center gap-2 mb-1">
        <span className={ok ? 'text-cyan-400' : 'text-red-400'}>{ok ? '✓' : '✗'}</span>
        <span className="font-semibold text-white/90">{name}</span>
      </div>
      <div className="text-white/50 leading-relaxed">{desc}</div>
    </div>
  );
}
