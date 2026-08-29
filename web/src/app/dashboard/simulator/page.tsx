"use client";

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import Chart from 'chart.js/auto';
import LLMPalette from '@/components/LLMPalette';
import { apiFetch } from '@/lib/api';

/**
 * AETHERA Simulator (v26.1) — visual front-end for all six simulation
 * scenarios. Every scenario renders a live Chart.js visualization plus
 * stat panels; no text-only output. Works against Railway or the
 * same-origin serverless fallback via apiFetch().
 */

type ScenarioId = 'dynamics' | 'terraformation' | 'projections' | 'physical-truth' | 'alien' | 'ghost';

const SCENARIOS: { id: ScenarioId; label: string; icon: string; blurb: string }[] = [
  { id: 'dynamics', label: 'Celestial', icon: '🪐', blurb: 'Particle trajectory under user-defined force fields' },
  { id: 'terraformation', label: 'Terraform', icon: '🌊', blurb: 'Sea-level rise — area loss per nation' },
  { id: 'projections', label: 'Distortion', icon: '📊', blurb: 'Colonial distortion scores of map projections' },
  { id: 'physical-truth', label: 'Truth Manifold', icon: '🌍', blurb: 'SMACOF-derived world embedding from DEM edges' },
  { id: 'alien', label: 'Alien Geometer', icon: '👽', blurb: 'Intrinsic shape classification from edge lengths' },
  { id: 'ghost', label: 'Ghost Resolver', icon: '🔮', blurb: 'Derive unknown areas from closure constraints' },
];

const FORCES = ['inertial', 'inverse_square', 'uniform'] as const;

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div style={{
      background: '#0d1117', border: '1px solid #1c2a38', borderRadius: '8px',
      padding: '14px 16px', minWidth: '150px',
    }}>
      <div style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: '10px', letterSpacing: '1px', textTransform: 'uppercase' }}>{label}</div>
      <div style={{
        color: accent ? '#00ff88' : '#e6edf3', fontFamily: 'monospace',
        fontSize: '15px', marginTop: '6px', fontWeight: 600, wordBreak: 'break-all',
      }}>{value}</div>
    </div>
  );
}

export default function SimulatorPage() {
  const [scenario, setScenario] = useState<ScenarioId>('dynamics');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const [stats, setStats] = useState<{ label: string; value: string; accent?: boolean }[]>([]);

  // dynamics controls
  const [forceLaw, setForceLaw] = useState<(typeof FORCES)[number]>('inertial');
  const [vx, setVx] = useState(1);
  const [vy, setVy] = useState(0);
  const [tMax, setTMax] = useState(10);
  // terraformation control
  const [seaLevel, setSeaLevel] = useState(10);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const chartRef = useRef<Chart | null>(null);

  const destroyChart = () => { chartRef.current?.destroy(); chartRef.current = null; };

  const makeLineCfg = (labels: number[], datasets: { label: string; data: (number | null)[]; color: string }[]) => ({
    type: 'line' as const,
    data: {
      labels,
      datasets: datasets.map((d) => ({
        label: d.label, data: d.data,
        borderColor: d.color, backgroundColor: `${d.color}1a`,
        borderWidth: 1.5, pointRadius: 0, tension: 0.25, fill: true,
      })),
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: { duration: 250 },
      plugins: { legend: { labels: { color: '#8b9bab', font: { family: 'monospace', size: 10 } } } },
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#5b6b7b', font: { family: 'monospace', size: 9 }, maxTicksLimit: 12 } },
        y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#5b6b7b', font: { family: 'monospace', size: 9 } } },
      },
    },
  });

  const makeBarCfg = (labels: string[], data: number[], colors: string[] | string, horizontal = false) => ({
    type: 'bar' as const,
    data: { labels, datasets: [{ label: '', data, backgroundColor: colors, borderRadius: 3, borderWidth: 0 }] },
    options: {
      indexAxis: horizontal ? ('y' as const) : ('x' as const),
      responsive: true, maintainAspectRatio: false, animation: { duration: 250 },
      plugins: { legend: { display: false } },
      scales: {
        ...(horizontal
          ? { x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#5b6b7b', font: { family: 'monospace', size: 9 } } },
              y: { grid: { display: false }, ticks: { color: '#8b9bab', font: { family: 'monospace', size: 9 } } } }
          : { x: { grid: { display: false }, ticks: { color: '#8b9bab', font: { family: 'monospace', size: 9 }, maxRotation: 45 } },
              y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#5b6b7b', font: { family: 'monospace', size: 9 } } } }),
      },
    },
  });

  const makeScatterCfg = (points: { x: number; y: number; label: string }[]) => ({
    type: 'scatter' as const,
    data: {
      datasets: [{
        label: 'derived positions (km)',
        data: points,
        backgroundColor: '#06b6d4', pointRadius: 3, pointHoverRadius: 5,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: { duration: 250 },
      plugins: {
        legend: { labels: { color: '#8b9bab', font: { family: 'monospace', size: 10 } } },
        tooltip: { callbacks: { label: (c: any) => `${c.raw.label}: (${c.parsed.x.toFixed(0)}, ${c.parsed.y.toFixed(0)})` } },
      },
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#5b6b7b', font: { family: 'monospace', size: 9 } } },
        y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#5b6b7b', font: { family: 'monospace', size: 9 } } },
      },
    },
  });

  const run = useCallback(async (sc: ScenarioId) => {
    setLoading(true); setError(''); setNote(''); setStats([]);
    try {
      let cfg: any = null;

      if (sc === 'dynamics') {
        const j = await (await apiFetch('/api/dynamics/simulate', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            start: [0, 0, 0], initial_velocity: [vx, vy, 0],
            force_law: forceLaw, mu: 1.0, uniform_accel: [0, -0.5, 0],
            dt: 0.01, t_max: tMax,
          }),
        })).json();
        if (j.detail) throw new Error(typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail));
        const traj: number[][] = j.trajectory || [];
        cfg = makeLineCfg(
          traj.map((_, i) => i),
          [
            { label: 'x(t)', data: traj.map((p) => p[0]), color: '#06b6d4' },
            { label: 'y(t)', data: traj.map((p) => p[1]), color: '#00ff88' },
          ],
        );
        setNote(j.note || '');
        setStats([
          { label: 'Trajectory Points', value: String(traj.length), accent: true },
          { label: 'Path Length', value: `${(j.total_path_length ?? 0).toFixed(3)} u` },
          { label: 'Total Time', value: `${(j.total_time ?? 0).toFixed(2)} s` },
          { label: 'Final Position', value: `[${(j.final_position || []).map((n: number) => n.toFixed(2)).join(', ')}]` },
        ]);
      } else if (sc === 'terraformation') {
        const j = await (await apiFetch('/api/terraformation', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sea_level_rise_m: seaLevel }),
        })).json();
        if (j.detail) throw new Error(typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail));
        const cc: any[] = j.coastline_changes || [];
        const worst = [...cc].sort((a, b) => a.area_change_km2 - b.area_change_km2).slice(0, 15);
        cfg = makeBarCfg(
          worst.map((c) => c.nation),
          worst.map((c) => Math.abs(c.area_change_km2)),
          '#06b6d4', true,
        );
        setNote(j.note || '');
        const total = cc.reduce((s, c) => s + Math.min(c.area_change_km2, 0), 0);
        setStats([
          { label: 'Nations Simulated', value: String(cc.length), accent: true },
          { label: 'With Area Loss', value: String(cc.filter((c) => c.area_change_km2 < 0).length), accent: true },
          { label: 'Total Loss', value: `${Math.abs(total).toLocaleString()} km²` },
          { label: 'Sea Level Rise', value: `+${seaLevel} m` },
        ]);
      } else if (sc === 'projections') {
        const j = await (await apiFetch('/api/projections/scores')).json();
        const scores: any[] = j.scores || [];
        cfg = makeBarCfg(
          scores.map((s) => s.projection),
          scores.map((s) => s.colonial_score),
          scores.map((s) => (s.colonial_score >= 0 ? '#00ff88' : '#f97316')),
        );
        setNote('');
        setStats(scores.map((s) => ({
          label: `${s.projection} score`,
          value: s.colonial_score.toFixed(4),
          accent: s.colonial_score >= 0,
        })));
      } else if (sc === 'physical-truth') {
        const j = await (await apiFetch('/api/solve/physical-truth')).json();
        const regions: any[] = j.regions || [];
        cfg = makeScatterCfg(regions.map((r) => ({ x: r.coords[0], y: r.coords[1], label: r.name })));
        setNote(j.note || '');
        setStats([
          { label: 'Nodes (regions)', value: String(j.node_count ?? regions.length), accent: true },
          { label: 'Edges', value: String(j.edge_count ?? '-') },
          { label: 'Convergence Residual', value: (j.convergence_residual ?? j.residual ?? 0).toExponential(4), accent: true },
          { label: 'Solver', value: 'SMACOF (Rust FFI)' },
        ]);
      } else if (sc === 'alien') {
        const j = await (await apiFetch('/api/alien/reconstruct', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            edges: [
              { source: 'A', target: 'B', length: 1.0, source_type: 'topology' },
              { source: 'B', target: 'C', length: 1.0, source_type: 'topology' },
              { source: 'C', target: 'D', length: 1.0, source_type: 'topology' },
              { source: 'D', target: 'A', length: 1.0, source_type: 'topology' },
              { source: 'A', target: 'C', length: 1.4142135623730951, source_type: 'topology' },
              { source: 'B', target: 'D', length: 1.4142135623730951, source_type: 'topology' },
            ],
          }),
        })).json();
        if (j.detail) throw new Error(typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail));
        setNote(j.note || '');
        cfg = makeBarCfg(
          ['Flat', 'Ellipsoidal', 'Potato'],
          [j.shape === 'Flat' ? 1 : 0, j.shape === 'Ellipsoidal' ? 1 : 0, j.shape === 'Potato' ? 1 : 0],
          ['#00ff88', '#1c2a38', '#1c2a38'],
        );
        setStats([
          { label: 'Shape', value: j.shape || '?', accent: true },
          { label: 'Residual', value: (j.residual ?? 0).toExponential(4), accent: true },
          { label: 'Mean Curvature', value: (j.mean_curvature ?? 0).toExponential(4) },
          { label: 'Nodes / Edges', value: `${j.node_count} / ${j.edge_count}` },
        ]);
      } else if (sc === 'ghost') {
        const j = await (await apiFetch('/api/ghost/resolve', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            polygons: [
              { name: 'World', area: 510000000000000 },
              { name: 'Known', area: 400000000000000 },
              { name: 'Unknown', area: null, claimed_area: 50000000000000, neighbours: ['World'] },
            ],
            global_enclosure: 'World',
            global_area: 510000000000000,
          }),
        })).json();
        if (j.detail) throw new Error(typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail));
        const areas = j.resolved_areas || {};
        const names = Object.keys(areas);
        cfg = makeBarCfg(names, names.map((n) => areas[n]), '#06b6d4', true);
        setNote(j.note || '');
        setStats([
          { label: 'Resolved Zones', value: String(names.length), accent: true },
          { label: 'Red Flags', value: String((j.red_flags || []).length), accent: (j.red_flags || []).length > 0 },
          { label: 'Sealed Hash', value: String(j.sealed_hash || '-').slice(0, 18) + '…' },
        ]);
      }

      destroyChart();
      if (cfg && canvasRef.current) {
        chartRef.current = new Chart(canvasRef.current, cfg);
      }
    } catch (e: any) {
      setError(e?.message || 'Simulation request failed');
    } finally {
      setLoading(false);
    }
  }, [forceLaw, vx, vy, tMax, seaLevel]);

  // auto-run on load + on scenario switch
  useEffect(() => { run(scenario); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [scenario]);
  useEffect(() => () => destroyChart(), []);

  const active = SCENARIOS.find((s) => s.id === scenario)!;

  return (
    <div style={{ width: '100%', maxWidth: '1100px', margin: '0 auto', color: '#e6edf3' }}>
      <LLMPalette />
      <header style={{ marginBottom: '20px' }}>
        <h1 style={{ fontSize: '22px', fontWeight: 300, letterSpacing: '2px' }}>🧪 SIMULATOR</h1>
        <p style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: '12px', marginTop: '6px' }}>
          Visual execution of all six AETHERA simulation scenarios — intrinsic geometry only, no coordinates in the engine.
        </p>
      </header>

      {/* scenario tabs */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '16px' }}>
        {SCENARIOS.map((s) => (
          <button key={s.id} onClick={() => setScenario(s.id)} style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            padding: '8px 14px', borderRadius: '6px', cursor: 'pointer',
            background: scenario === s.id ? 'rgba(6,182,212,0.12)' : '#0d1117',
            border: `1px solid ${scenario === s.id ? '#06b6d4' : '#1c2a38'}`,
            color: scenario === s.id ? '#06b6d4' : '#8b9bab',
            fontFamily: 'monospace', fontSize: '12px',
          }}>
            <span>{s.icon}</span>{s.label}
          </button>
        ))}
      </div>
      <p style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: '11px', margin: '0 0 16px' }}>{active.blurb}</p>

      {/* controls */}
      {scenario === 'dynamics' && (
        <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap', alignItems: 'flex-end', marginBottom: '14px' }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontFamily: 'monospace', fontSize: '11px', color: '#8b9bab' }}>
            Force law
            <select value={forceLaw} onChange={(e) => setForceLaw(e.target.value as any)} style={{
              background: '#0d1117', color: '#e6edf3', border: '1px solid #1c2a38',
              borderRadius: '6px', padding: '8px', fontFamily: 'monospace', fontSize: '12px',
            }}>
              {FORCES.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          </label>
          {([['vx', vx, setVx], ['vy', vy, setVy]] as const).map(([label, val, set]) => (
            <label key={label} style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontFamily: 'monospace', fontSize: '11px', color: '#8b9bab' }}>
              {label}
              <input type="number" step="0.1" value={val} onChange={(e) => set(Number(e.target.value))} style={{
                background: '#0d1117', color: '#e6edf3', border: '1px solid #1c2a38',
                borderRadius: '6px', padding: '8px', width: '90px', fontFamily: 'monospace',
              }} />
            </label>
          ))}
          <label style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontFamily: 'monospace', fontSize: '11px', color: '#8b9bab' }}>
            t_max (s)
            <input type="number" step="1" min="1" max="100" value={tMax} onChange={(e) => setTMax(Math.min(100, Math.max(1, Number(e.target.value))))} style={{
              background: '#0d1117', color: '#e6edf3', border: '1px solid #1c2a38',
              borderRadius: '6px', padding: '8px', width: '90px', fontFamily: 'monospace',
            }} />
          </label>
          <button onClick={() => run('dynamics')} disabled={loading} style={{
            background: '#00ff88', color: '#04110a', border: 'none', padding: '10px 22px',
            borderRadius: '6px', fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer',
            fontFamily: 'monospace', fontSize: '12px', opacity: loading ? 0.5 : 1,
          }}>{loading ? 'Running…' : '▶ Run Simulation'}</button>
        </div>
      )}

      {scenario === 'terraformation' && (
        <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap', alignItems: 'flex-end', marginBottom: '14px' }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontFamily: 'monospace', fontSize: '11px', color: '#8b9bab', flex: 1, minWidth: '260px' }}>
            Sea level rise: <span style={{ color: '#00ff88' }}>+{seaLevel} m</span>
            <input type="range" min="0" max="100" step="5" value={seaLevel}
              onChange={(e) => setSeaLevel(Number(e.target.value))}
              onMouseUp={() => run('terraformation')}
              onTouchEnd={() => run('terraformation')}
              style={{ accentColor: '#06b6d4' }} />
          </label>
          <button onClick={() => run('terraformation')} disabled={loading} style={{
            background: '#00ff88', color: '#04110a', border: 'none', padding: '10px 22px',
            borderRadius: '6px', fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer',
            fontFamily: 'monospace', fontSize: '12px', opacity: loading ? 0.5 : 1,
          }}>{loading ? 'Running…' : '▶ Run Simulation'}</button>
        </div>
      )}

      {!['dynamics', 'terraformation'].includes(scenario) && (
        <button onClick={() => run(scenario)} disabled={loading} style={{
          background: '#00ff88', color: '#04110a', border: 'none', padding: '10px 22px',
          borderRadius: '6px', fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer',
          fontFamily: 'monospace', fontSize: '12px', opacity: loading ? 0.5 : 1,
          marginBottom: '14px',
        }}>{loading ? 'Running…' : '▶ Run Simulation'}</button>
      )}

      {error && (
        <div style={{
          background: 'rgba(249,115,22,0.08)', border: '1px solid rgba(249,115,22,0.4)',
          color: '#f97316', borderRadius: '8px', padding: '12px 16px',
          fontFamily: 'monospace', fontSize: '12px', marginBottom: '14px',
        }}>⚠ {error}</div>
      )}

      {/* chart */}
      <div style={{
        background: '#0d1117', border: '1px solid #1c2a38', borderRadius: '10px',
        padding: '18px', height: '420px', position: 'relative', marginBottom: '16px',
      }}>
        {loading && (
          <div style={{
            position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'rgba(0,0,0,0.55)', zIndex: 5, borderRadius: '10px',
            color: '#06b6d4', fontFamily: 'monospace', fontSize: '13px', letterSpacing: '1px',
          }}>deriving…</div>
        )}
        <canvas ref={canvasRef} />
      </div>

      {/* stats */}
      {stats.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '10px' }}>
          {stats.map((s) => <Stat key={s.label} label={s.label} value={s.value} accent={s.accent} />)}
        </div>
      )}

      {note && (
        <p style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: '11px', marginTop: '14px', lineHeight: 1.6 }}>{note}</p>
      )}

      <p style={{ marginTop: '24px' }}>
        <Link href="/dashboard" style={{ color: '#06b6d4', fontFamily: 'monospace', fontSize: '12px', textDecoration: 'none' }}>← back to system overview</Link>
      </p>
    </div>
  );
}
