'use client';
import { useState, useEffect } from 'react';

export default function AnomalyDetectorPage() {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/anomaly/latest').then(r => r.json()).then(d => {
      setAlerts(d.alerts || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  return (
    <main className="min-h-screen bg-black text-white p-8">
      <h1 className="text-3xl font-bold mb-6">Anomaly Detector</h1>
      <p className="text-white/60 mb-6">Edges that changed &gt;1cm/day (civil-scientific: groundwater, glacial, volcanic).</p>
      {loading ? (
        <p className="text-white/40">Loading...</p>
      ) : alerts.length === 0 ? (
        <p className="text-white/40">No anomalies detected. Ingest time-series edge data to populate.</p>
      ) : (
        <div className="space-y-3">
          {alerts.map((a, i) => (
            <div key={i} className="border border-yellow-500/30 bg-yellow-500/5 rounded p-4">
              <div className="font-semibold text-yellow-400">{a.edge[0]} ↔ {a.edge[1]}</div>
              <div className="text-sm text-white/60 mt-1">{a.note}</div>
              <div className="text-xs font-mono mt-2">Δ = {a.delta_per_day_cm.toFixed(3)} cm/day</div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
