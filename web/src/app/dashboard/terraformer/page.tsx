'use client';
import { useState } from 'react';

export default function TerraformerPage() {
  const [seaLevel, setSeaLevel] = useState(1);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const simulate = async (val: number) => {
    setSeaLevel(val);
    setLoading(true);
    const res = await fetch('/api/terraformation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sea_level_rise_m: val }),
    }).then(r => r.json()).catch(() => null);
    setResult(res);
    setLoading(false);
  };

  return (
    <main className="min-h-screen bg-black text-white p-8">
      <h1 className="text-3xl font-bold mb-6">Terraformation Simulator</h1>
      <p className="text-white/60 mb-6">Simulate sea-level rise and coastline displacement.</p>
      <div className="mb-6">
        <label className="block text-sm text-white/40 mb-2">Sea level rise: {seaLevel}m</label>
        <input type="range" min="0" max="10" value={seaLevel} onChange={e => simulate(Number(e.target.value))}
          className="w-full" />
      </div>
      {loading && <p className="text-white/40">Simulating...</p>}
      {result && (
        <div>
          <h3 className="text-sm uppercase text-white/40 mb-2">Coastline Changes</h3>
          <table className="w-full text-sm">
            <thead><tr className="text-white/40"><th className="text-left p-2">Nation</th><th className="text-right p-2">Area Change (km²)</th></tr></thead>
            <tbody>
              {result.coastline_changes?.map((c: any) => (
                <tr key={c.nation} className="border-t border-white/10">
                  <td className="p-2">{c.nation}</td>
                  <td className={`text-right p-2 font-mono ${c.area_change_km2 < 0 ? 'text-red-400' : 'text-green-400'}`}>
                    {c.area_change_km2 > 0 ? '+' : ''}{c.area_change_km2.toFixed(0)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
