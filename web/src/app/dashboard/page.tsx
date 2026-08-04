'use client';
import Link from 'next/link';

export default function DashboardIndex() {
  const dashboards = [
    { href: '/dashboard/distortion-observatory', name: 'Distortion Observatory', desc: 'Interactive manifold viewer with real-time distortion metrics and data-guided shape reconstruction', icon: '📊', tag: 'Featured' },
    { href: '/dashboard/ghost-resolver', name: 'Ghost Resolver', desc: 'Derive unknown polygon areas using topological residual closure and global area constraints', icon: '🔮' },
    { href: '/dashboard/consensus-hall', name: 'Projection Comparison', desc: 'Compare how different map projections distort area across continents', icon: '🗺️' },
    { href: '/dashboard/terraformer', name: 'Terraformation Simulator', desc: 'Simulate sea-level rise and visualize coastline displacement', icon: '🌊' },
    { href: '/dashboard/anomaly-detector', name: 'Anomaly Detector', desc: 'Monitor edge-length changes for groundwater, glacial, and volcanic activity', icon: '⚡' },
  ];
  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100 p-8">
      <div className="max-w-5xl mx-auto">
        <div className="mb-8">
          <h1 className="text-4xl font-bold mb-2">Dashboard</h1>
          <p className="text-slate-400">Select a module to explore geometric truth.</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {dashboards.map(d => (
            <Link key={d.href} href={d.href}
              className="group bg-slate-950/50 rounded-2xl border border-white/5 p-6 hover:border-cyan-500/30 transition">
              <div className="flex items-start justify-between">
                <div className="text-3xl mb-3">{d.icon}</div>
                {d.tag && <span className="text-xs px-2 py-0.5 bg-cyan-500/20 text-cyan-300 rounded-full">{d.tag}</span>}
              </div>
              <h2 className="text-lg font-semibold text-slate-100 group-hover:text-cyan-300 transition mb-2">{d.name}</h2>
              <p className="text-sm text-slate-500 leading-relaxed">{d.desc}</p>
            </Link>
          ))}
        </div>
        <div className="mt-8 text-center">
          <Link href="/" className="text-sm text-slate-500 hover:text-cyan-400 transition">← Back to Atlas</Link>
        </div>
      </div>
    </main>
  );
}
