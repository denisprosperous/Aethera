'use client';
import Link from 'next/link';

export default function DashboardIndex() {
  const dashboards = [
    { href: '/dashboard/ghost-resolver', name: 'Ghost Resolver', desc: 'Topological residual closure for censored areas' },
    { href: '/dashboard/consensus-hall', name: 'Consensus Hall of Shame', desc: 'Projection strain tensor + Colonial Distortion Score' },
    { href: '/dashboard/terraformer', name: 'Terraformation Simulator', desc: 'Sea-level rise and coastline displacement' },
    { href: '/dashboard/anomaly-detector', name: 'Anomaly Detector', desc: 'Edge changes >1cm/day (civil-scientific)' },
  ];
  return (
    <main className="min-h-screen bg-black text-white p-8">
      <h1 className="text-3xl font-bold mb-6">AETHERA Dashboard</h1>
      <div className="grid grid-cols-2 gap-4">
        {dashboards.map(d => (
          <Link key={d.href} href={d.href}
            className="border border-white/10 rounded p-6 hover:border-cyan-500 transition">
            <h2 className="text-xl font-semibold mb-2">{d.name}</h2>
            <p className="text-sm text-white/60">{d.desc}</p>
          </Link>
        ))}
      </div>
    </main>
  );
}
