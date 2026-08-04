'use client';
import { useState, useEffect } from 'react';

export default function GhostResolverPage() {
  const [regions, setRegions] = useState<any[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch('/api/datasets').then(r => r.json()).then(d => setRegions(d.regions || [])).catch(() => setRegions([]));
  }, []);

  const resolve = async () => {
    setLoading(true);
    // Simplified: resolve Antarctica with a synthetic global area.
    const res = await fetch('/api/ghost/resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        polygons: [
          { name: 'World', area: 510_000_000 },
          { name: 'Known', area: 400_000_000 },
          { name: 'Unknown', area: null, claimed_area: 50_000_000, neighbours: ['World'] },
        ],
        global_enclosure: 'World',
        global_area: 510_000_000,
      }),
    }).then(r => r.json()).catch(() => null);
    setResult(res);
    setLoading(false);
  };

  return (
    <main className="min-h-screen bg-black text-white p-8">
      <h1 className="text-3xl font-bold mb-6">Ghost Resolver</h1>
      <p className="text-white/60 mb-6">Topological residual closure for censored/unknown polygon areas.</p>
      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-1 border border-white/10 rounded p-4">
          <h2 className="text-sm uppercase text-white/40 mb-3">Regions</h2>
          {regions.length === 0 ? (
            <p className="text-white/40 text-sm">No regions ingested yet.</p>
          ) : (
            regions.map(r => (
              <button key={r.region} onClick={() => setSelected(r.region)}
                className={`block w-full text-left px-3 py-2 rounded text-sm mb-1 ${
                  selected === r.region ? 'bg-cyan-500 text-black' : 'bg-white/5 hover:bg-white/10'
                }`}>
                {r.region} ({r.status})
              </button>
            ))
          )}
        </div>
        <div className="col-span-2 border border-white/10 rounded p-4">
          <button onClick={resolve} disabled={loading}
            className="px-4 py-2 bg-cyan-500 text-black rounded font-semibold mb-4">
            {loading ? 'Resolving...' : 'Resolve Synthetic Example'}
          </button>
          {result && (
            <div>
              <h3 className="text-sm uppercase text-white/40 mb-2">Resolved Areas</h3>
              <pre className="text-xs bg-white/5 p-3 rounded overflow-auto">
                {JSON.stringify(result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
