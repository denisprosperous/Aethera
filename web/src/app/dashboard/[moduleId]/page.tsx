"use client";

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { ChevronLeft, Activity, Clock, Hash, Loader2 } from 'lucide-react';
import { MODULES } from '../../components/ModuleConfig';

interface ModulePageProps {
  params: { moduleId: string };
}

const ModulePage: React.FC<ModulePageProps> = ({ params }) => {
  const router = useRouter();
  const moduleId = params.moduleId;
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [loadTime, setLoadTime] = useState<number>(0);

  const module = MODULES.find(m => m.id === moduleId);
  if (!module) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 300, marginBottom: 'var(--space-lg)' }}>Module not found</h1>
        <button onClick={() => router.push('/')} className="btn-ghost">
          <ChevronLeft size={16} /> Back to Dashboard
        </button>
      </div>
    );
  }

  const Icon = module.icon;

  const runTest = async () => {
    setLoading(true);
    setError('');
    const start = Date.now();
    
    try {
      const endpoints: Record<string, { url: string; body: any }> = {
        ghost: {
          url: '/api/ghost/resolve',
          body: {
            known_areas: [-1, 100, 150, -1],
            adjacency: [[0,1,0,1],[1,0,1,0],[0,1,0,1],[1,0,1,0]],
            global_total: 500,
          },
        },
        geometer: {
          url: '/api/geometer/reconstruct',
          body: {
            distances: [0,10,14.14,10, 10,0,10,14.14, 14.14,10,0,10, 10,14.14,10,0],
            n_points: 4,
            target_dim: 2,
            max_iter: 1000,
          },
        },
        positioning: {
          url: '/api/positioning/calculate',
          body: {
            reference_coords: [[0,0,0],[10,0,0],[0,10,0]],
            distances_to_refs: [[0,10,10],[10,0,10]],
            n_unknowns: 2,
          },
        },
        celestial: {
          url: '/api/celestial/compute',
          body: {
            bodies: [{ position: [0,0,0], velocity: [1,0,0], mass: 1 }],
            time_step: 0.01,
            max_steps: 100,
          },
        },
        extraterrestrial: {
          url: '/api/extraterrestrial/map',
          body: {
            points: Array.from({length: 20}, () => [
              Math.random() * 10,
              Math.random() * 10,
              Math.random() * 5,
            ]),
          },
        },
        distortion: {
          url: '/api/distortion/analyze',
          body: {
            absolute_coords: Array.from({length: 10}, () => [Math.random()*10, Math.random()*10]),
            reference_coords: Array.from({length: 10}, () => [Math.random()*10, Math.random()*10]),
            n_points: 10,
          },
        },
        environmental: {
          url: '/api/environmental/simulate',
          body: {
            vertices: [[0,0],[10,0],[10,10],[0,10]],
            elevations: [0,0,0,0],
            sea_level_change: 0.5,
            original_total_area: 100,
          },
        },
        stellar: {
          url: '/api/stellar/navigate',
          body: {
            quasar_measurements: [
              { quasar_position: [1,0,0], measured_angle: 0.001, uncertainty: 0.0001 },
              { quasar_position: [0,1,0], measured_angle: 0.001, uncertainty: 0.0001 },
              { quasar_position: [0,0,1], measured_angle: 0.001, uncertainty: 0.0001 },
            ],
            n_quasars: 3,
          },
        },
        anomaly: {
          url: '/api/anomaly/detect',
          body: {
            edge_ids: ['edge_A', 'edge_B'],
            lengths: [
              Array.from({length: 50}, (_, i) => 10 + Math.sin(i * 0.3) * 0.01 + (i > 40 ? 0.5 : 0)),
              Array.from({length: 50}, (_, i) => 10 + Math.cos(i * 0.2) * 0.005),
            ],
            timestamps: [
              Array.from({length: 50}, (_, i) => i * 1),
              Array.from({length: 50}, (_, i) => i * 1),
            ],
            threshold_sigma: 2.0,
          },
        },
      };

      const endpoint = endpoints[moduleId];
      if (!endpoint) {
        throw new Error('Unknown module');
      }

      const response = await fetch(endpoint.url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(endpoint.body),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Request failed');
      }

      const data = await response.json();
      setLoadTime(Date.now() - start);
      setResult(data);
    } catch (e: any) {
      setError(e.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden' }}>
      <nav style={{ width: '220px', background: 'var(--bg-surface)', borderRight: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', padding: 'var(--space-lg)' }}>
        <button onClick={() => router.push('/')} className="btn-ghost" style={{ marginBottom: 'var(--space-lg)', display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
          <ChevronLeft size={16} /> Dashboard
        </button>
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {MODULES.map(m => {
            const isActive = m.id === moduleId;
            const MIcon = m.icon;
            return (
              <button
                key={m.id}
                onClick={() => router.push(`/dashboard/${m.id}`)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 'var(--space-sm)',
                  padding: 'var(--space-sm) var(--space-md)',
                  width: '100%', textAlign: 'left',
                  background: isActive ? 'hsla(186,100%,50%,0.1)' : 'transparent',
                  border: 'none', borderRadius: 'var(--radius-sm)',
                  color: isActive ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                  cursor: 'pointer', marginBottom: '2px',
                  fontFamily: 'var(--font-mono)', fontSize: '12px',
                }}
              >
                <MIcon size={14} />
                {m.name}
              </button>
            );
          })}
        </div>
      </nav>

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 'var(--space-2xl)', overflowY: 'auto' }}>
        <header style={{ marginBottom: 'var(--space-xl)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)', marginBottom: 'var(--space-md)' }}>
            <div style={{ padding: 'var(--space-sm)', background: 'var(--bg-app)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
              <Icon size={20} color="var(--accent-cyan)" />
            </div>
            <div>
              <h1 style={{ fontSize: '20px', fontWeight: 400, letterSpacing: '1px' }}>{module.name}</h1>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>{module.description}</p>
            </div>
          </div>
        </header>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="card glass-panel" style={{ marginBottom: 'var(--space-lg)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-md)' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 500, letterSpacing: '1px', textTransform: 'uppercase', color: 'var(--text-muted)' }}>
              Run Test
            </h3>
            <button className="btn-primary" onClick={runTest} disabled={loading} style={{ opacity: loading ? 0.6 : 1 }}>
              {loading ? <><Loader2 size={14} className="animate-spin" /> Computing...</> : 'Execute'}
            </button>
          </div>
          {error && (
            <div style={{ padding: 'var(--space-md)', background: 'hsla(342,100%,50%,0.1)', border: '1px solid var(--accent-crimson)', borderRadius: 'var(--radius-sm)', color: 'var(--accent-crimson)', fontSize: '12px', fontFamily: 'var(--font-mono)' }}>
              {error}
            </div>
          )}
        </motion.div>

        {result && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card glass-panel">
            <div style={{ display: 'flex', gap: 'var(--space-xl)', marginBottom: 'var(--space-md)', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
                <Activity size={14} color="var(--accent-emerald)" />
                <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Status</span>
                <span style={{ fontSize: '12px', color: 'var(--accent-emerald)', fontFamily: 'var(--font-mono)' }}>complete</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
                <Clock size={14} color="var(--accent-amber)" />
                <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Load Time</span>
                <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: loadTime < 1000 ? 'var(--accent-emerald)' : 'var(--accent-amber)' }}>
                  {loadTime}ms
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
                <Hash size={14} color="var(--accent-cyan)" />
                <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Run ID</span>
                <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--text-mono)' }}>
                  {result.solver_run_id || result.run_id || '—'}
                </span>
              </div>
            </div>

            {result.rationale && (
              <div style={{ marginBottom: 'var(--space-md)' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 'var(--space-sm)' }}>Rationale</div>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', lineHeight: 1.6 }}>
                  {result.rationale}
                </p>
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 'var(--space-md)' }}>
              {result.stress !== undefined && (
                <div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px' }}>Stress</div>
                  <div className="tabular-nums" style={{ fontSize: '18px', color: 'var(--text-mono)', fontWeight: 600 }}>
                    {typeof result.stress === 'number' ? result.stress.toExponential(4) : result.stress}
                  </div>
                </div>
              )}
              {result.iterations !== undefined && (
                <div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px' }}>Iterations</div>
                  <div className="tabular-nums" style={{ fontSize: '18px', color: 'var(--text-mono)', fontWeight: 600 }}>{result.iterations}</div>
                </div>
              )}
              {result.converged !== undefined && (
                <div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px' }}>Converged</div>
                  <div style={{ fontSize: '18px', color: result.converged ? 'var(--accent-emerald)' : 'var(--accent-crimson)', fontWeight: 600 }}>
                    {result.converged ? '✓ yes' : '✗ no'}
                  </div>
                </div>
              )}
              {result.error !== undefined && (
                <div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px' }}>Residual</div>
                  <div className="tabular-nums" style={{ fontSize: '18px', color: 'var(--text-mono)', fontWeight: 600 }}>
                    {typeof result.error === 'number' ? result.error.toExponential(4) : result.error}
                  </div>
                </div>
              )}
              {result.projection_distortion_index !== undefined && (
                <div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px' }}>Distortion Index</div>
                  <div className="tabular-nums" style={{ fontSize: '18px', color: 'var(--accent-amber)', fontWeight: 600 }}>
                    {(result.projection_distortion_index * 100).toFixed(4)}%
                  </div>
                </div>
              )}
              {result.geometric_reparations_index !== undefined && (
                <div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px' }}>Reparations Index</div>
                  <div className="tabular-nums" style={{ fontSize: '18px', color: result.geometric_reparations_index < 0 ? 'var(--accent-crimson)' : 'var(--accent-emerald)', fontWeight: 600 }}>
                    {result.geometric_reparations_index.toFixed(4)}
                  </div>
                </div>
              )}
              {result.confidence !== undefined && (
                <div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px' }}>Confidence</div>
                  <div className="tabular-nums" style={{ fontSize: '18px', color: 'var(--accent-cyan)', fontWeight: 600 }}>
                    {(result.confidence * 100).toFixed(1)}%
                  </div>
                </div>
              )}
              {result.area_delta !== undefined && (
                <div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px' }}>Area Change</div>
                  <div className="tabular-nums" style={{ fontSize: '18px', color: result.area_delta < 0 ? 'var(--accent-crimson)' : 'var(--accent-emerald)', fontWeight: 600 }}>
                    {result.area_delta.toFixed(2)} m²
                  </div>
                </div>
              )}
              {result.total_path_length !== undefined && (
                <div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px' }}>Path Length</div>
                  <div className="tabular-nums" style={{ fontSize: '18px', color: 'var(--text-mono)', fontWeight: 600 }}>
                    {result.total_path_length.toFixed(4)}
                  </div>
                </div>
              )}
              {result.dimensionality !== undefined && (
                <div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px' }}>Dimensionality</div>
                  <div className="tabular-nums" style={{ fontSize: '18px', color: 'var(--accent-purple)', fontWeight: 600 }}>
                    {result.dimensionality}D
                  </div>
                </div>
              )}
            </div>

            {result.summary && (
              <div style={{ marginTop: 'var(--space-lg)', padding: 'var(--space-md)', background: 'var(--bg-app)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--text-secondary)' }}>
                {result.summary}
              </div>
            )}

            {result.anomalies && result.anomalies.length > 0 && (
              <div style={{ marginTop: 'var(--space-lg)' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 'var(--space-sm)' }}>Detected Anomalies ({result.anomalies.length})</div>
                {result.anomalies.map((a: any, i: number) => (
                  <div key={i} style={{ padding: 'var(--space-md)', background: 'hsla(38,100%,50%,0.05)', border: '1px solid var(--border-strong)', borderRadius: 'var(--radius-sm)', marginBottom: 'var(--space-sm)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--space-sm)' }}>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--accent-amber)' }}>{a.vertex_id}</span>
                      {a.z_score && <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--text-muted)' }}>z: {a.z_score.toFixed(2)}</span>}
                    </div>
                    {a.explanation && <p style={{ fontSize: '12px', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>{a.explanation}</p>}
                    {a.drift !== undefined && <p style={{ fontSize: '12px', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>Drift: {a.drift.toFixed(4)} m/unit</p>}
                  </div>
                ))}
              </div>
            )}

            {result.strain_tensors && result.strain_tensors.length > 0 && (
              <div style={{ marginTop: 'var(--space-lg)' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 'var(--space-sm)' }}>Strain Tensors</div>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', fontFamily: 'var(--font-mono)' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                        <th style={{ padding: 'var(--space-sm)', textAlign: 'left', color: 'var(--text-muted)' }}>Vertex</th>
                        <th style={{ padding: 'var(--space-sm)', textAlign: 'right', color: 'var(--accent-cyan)' }}>ε_xx</th>
                        <th style={{ padding: 'var(--space-sm)', textAlign: 'right', color: 'var(--accent-cyan)' }}>ε_yy</th>
                        <th style={{ padding: 'var(--space-sm)', textAlign: 'right', color: 'var(--accent-cyan)' }}>ε_xy</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.strain_tensors.slice(0, 20).map((s: any, i: number) => (
                        <tr key={i} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                          <td style={{ padding: 'var(--space-sm)' }}>v{i}</td>
                          <td style={{ padding: 'var(--space-sm)', textAlign: 'right' }}>{s.xx?.toFixed(6)}</td>
                          <td style={{ padding: 'var(--space-sm)', textAlign: 'right' }}>{s.yy?.toFixed(6)}</td>
                          <td style={{ padding: 'var(--space-sm)', textAlign: 'right' }}>{s.xy?.toFixed(6)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </motion.div>
        )}
      </main>
    </div>
  );
};

export default ModulePage;
