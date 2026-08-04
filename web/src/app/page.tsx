'use client';
import { useMemo, useState } from 'react';
import StrainTensorView from '@/components/StrainTensorView';
import { CONTINENT_POLYGONS } from '@/lib/polygons';
import { allScores, PROJECTIONS } from '@/lib/projections';

export default function Home() {
  const [projection, setProjection] = useState('Mercator');
  const scores = useMemo(() => allScores(CONTINENT_POLYGONS), []);

  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      {/* Hero Section */}
      <header className="border-b border-white/5 px-8 py-12">
        <div className="max-w-6xl mx-auto">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center">
              <span className="text-xl font-bold text-white">Æ</span>
            </div>
            <span className="text-sm font-mono text-cyan-400 tracking-wider">AETHERA</span>
          </div>
          <h1 className="text-5xl font-bold tracking-tight mb-4">
            Projection Distortion Atlas
          </h1>
          <p className="text-lg text-slate-400 max-w-2xl leading-relaxed">
            Explore how map projections reshape our understanding of the world.
            Compare physical truth against cartographic convention — see the geometry
            that maps hide, explained clearly and visually.
          </p>
          <div className="flex gap-3 mt-6">
            <a href="/dashboard" className="px-5 py-2.5 bg-cyan-500 text-white rounded-lg font-semibold hover:bg-cyan-400 transition">
              Explore Dashboards →
            </a>
            <a href="/dashboard/distortion-observatory" className="px-5 py-2.5 bg-white/5 text-slate-200 rounded-lg font-semibold hover:bg-white/10 transition border border-white/10">
              Distortion Observatory
            </a>
          </div>
        </div>
      </header>

      {/* Projection Selector + Map */}
      <section className="px-8 py-8">
        <div className="max-w-6xl mx-auto">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-xl font-semibold text-slate-200">Interactive Strain Map</h2>
              <p className="text-sm text-slate-500 mt-1">
                Red = inflated by the projection · Blue = deflated · White = accurate
              </p>
            </div>
            <div className="flex gap-2">
              {Object.keys(PROJECTIONS).map((name) => (
                <button key={name} onClick={() => setProjection(name)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                    projection === name
                      ? 'bg-cyan-500 text-white shadow-lg shadow-cyan-500/25'
                      : 'bg-white/5 text-slate-400 hover:bg-white/10 hover:text-slate-200 border border-white/10'
                  }`}>
                  {name}
                </button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-8 h-[420px] rounded-2xl bg-slate-950/50 border border-white/5 overflow-hidden">
              <StrainTensorView polygons={CONTINENT_POLYGONS} projection={projection} />
            </div>
            <div className="col-span-4 space-y-4">
              <div className="bg-slate-950/50 rounded-2xl border border-white/5 p-5">
                <h3 className="text-sm font-semibold text-slate-300 mb-3">Distortion Scores</h3>
                {scores.map((s) => (
                  <div key={s.projection} onClick={() => setProjection(s.projection)}
                    className={`p-3 rounded-lg cursor-pointer transition mb-2 ${
                      projection === s.projection ? 'bg-cyan-500/10 border border-cyan-500/30' : 'hover:bg-white/5'
                    }`}>
                    <div className="flex justify-between items-baseline">
                      <span className="text-sm font-medium text-slate-200">{s.projection}</span>
                      <span className={`font-mono text-sm ${s.colonialDistortionScore > 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                        {s.colonialDistortionScore > 0 ? '+' : ''}{s.colonialDistortionScore.toFixed(3)}
                      </span>
                    </div>
                    <div className="w-full bg-white/5 rounded h-1.5 mt-2">
                      <div className={`h-1.5 rounded ${s.colonialDistortionScore > 0 ? 'bg-rose-500' : 'bg-blue-500'}`}
                        style={{ width: `${Math.min(Math.abs(s.colonialDistortionScore) * 100, 100)}%` }} />
                    </div>
                  </div>
                ))}
              </div>
              <div className="bg-cyan-500/5 rounded-2xl border border-cyan-500/20 p-4">
                <p className="text-xs text-slate-400 leading-relaxed">
                  <strong className="text-cyan-300">How to read this:</strong> Each region is coloured
                  by how much its area changes under the selected projection. Mercator inflates
                  polar regions dramatically; equatorial regions stay closer to true size.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Module Overview */}
      <section className="px-8 py-12 border-t border-white/5">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-xl font-semibold text-slate-200 mb-6">Platform Modules</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { name: 'Ghost Resolver', desc: 'Derive unknown areas from topological closure', href: '/dashboard/ghost-resolver', icon: '🔮' },
              { name: 'Distortion Observatory', desc: 'Interactive manifold + deviation ranking', href: '/dashboard/distortion-observatory', icon: '📊' },
              { name: 'Terraformation', desc: 'Simulate sea-level rise impact', href: '/dashboard/terraformer', icon: '🌊' },
              { name: 'Anomaly Detector', desc: 'Detect edge changes in real time', href: '/dashboard/anomaly-detector', icon: '⚡' },
            ].map((m) => (
              <a key={m.name} href={m.href}
                className="bg-slate-950/50 rounded-2xl border border-white/5 p-5 hover:border-cyan-500/30 transition group">
                <div className="text-2xl mb-3">{m.icon}</div>
                <h3 className="font-semibold text-slate-200 group-hover:text-cyan-300 transition">{m.name}</h3>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">{m.desc}</p>
              </a>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="px-8 py-8 border-t border-white/5">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <p className="text-xs text-slate-600">
            AETHERA v10.12 — Geometric substrate. No hardcoded areas, no projections assumed.
          </p>
          <div className="flex gap-4 text-xs text-slate-600">
            <span>Neon DB</span><span>·</span><span>Vercel</span><span>·</span><span>Rust FFI</span><span>·</span><span>Z.ai GLM-5.2</span>
          </div>
        </div>
      </footer>
    </main>
  );
}
