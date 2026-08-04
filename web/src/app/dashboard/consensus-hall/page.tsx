'use client';
import { useState, useEffect } from 'react';

export default function ConsensusHallPage() {
  const [scores, setScores] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/projections/scores').then(r => r.json()).then(d => {
      setScores(d.scores || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  return (
    <main className="min-h-screen bg-black text-white p-8">
      <h1 className="text-3xl font-bold mb-6">Consensus Hall of Shame</h1>
      <p className="text-white/60 mb-6">Colonial Distortion Scores for scholarly map projections.</p>
      {loading ? (
        <p className="text-white/40">Loading scores...</p>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {scores.map(s => (
            <div key={s.projection} className="border border-white/10 rounded p-4">
              <div className="flex justify-between items-baseline mb-2">
                <h3 className="font-semibold">{s.projection}</h3>
                <span className={`font-mono ${s.colonial_score > 0 ? 'text-red-400' : 'text-blue-400'}`}>
                  {s.colonial_score > 0 ? '+' : ''}{s.colonial_score.toFixed(3)}
                </span>
              </div>
              <p className="text-xs text-white/50">{s.note}</p>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
