'use client';

/**
 * AETHERA v27.0 — Simulator3DControls
 *
 * Left rail of the 3D-first simulator: scenario selector, live parameter
 * controls (sliders fire debounced real-time updates), data uploaders for
 * the Alien Geometer (CSV edge list) and Ghost Resolver (JSON adjacency),
 * and the sealed stats readout.
 */

import { useRef } from 'react';
import {
  SCENARIO_META,
  type ScenarioId,
  type ScenarioParams,
} from '@/lib/useScenario';
import { ALIEN_SAMPLES, FORCES, GHOST_PAYLOAD, PROJECTION_TYPES } from '@/lib/samples';

interface Simulator3DControlsProps {
  scenario: ScenarioId;
  params: ScenarioParams;
  loading: boolean;
  onScenario: (id: ScenarioId) => void;
  onParams: (patch: Partial<ScenarioParams>) => void;
  onRun: () => void;
  error: string;
}

const labelStyle: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 5,
  fontFamily: 'monospace', fontSize: 10, color: '#8b9bab',
  letterSpacing: '1px',
};

const inputStyle: React.CSSProperties = {
  background: '#040a10', color: '#e6edf3', border: '1px solid #1c2a38',
  borderRadius: 6, padding: '7px 9px', fontFamily: 'monospace', fontSize: 12,
};

function Slider({
  label, value, min, max, step, onChange, unit,
}: {
  label: string; value: number; min: number; max: number; step: number;
  onChange: (v: number) => void; unit?: string;
}) {
  return (
    <label style={labelStyle}>
      {label.toUpperCase()} <span style={{ color: '#00ff88' }}>{value}{unit || ''}</span>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{ accentColor: '#00ff88', cursor: 'pointer', width: '100%' }}
      />
    </label>
  );
}

function parseAlienCsv(text: string): { source: string; target: string; length: number; source_type: string }[] {
  const lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  const edges: { source: string; target: string; length: number; source_type: string }[] = [];
  for (const line of lines) {
    const cols = line.split(/[,;\t]/).map((c) => c.trim());
    if (cols.length < 3) continue;
    if (/source/i.test(cols[0]) && /target/i.test(cols[1])) continue; // header
    const length = Number(cols[2]);
    if (!cols[0] || !cols[1] || !Number.isFinite(length)) continue;
    edges.push({ source: cols[0], target: cols[1], length, source_type: 'topology' });
  }
  return edges;
}

export default function Simulator3DControls({
  scenario,
  params,
  loading,
  onScenario,
  onParams,
  onRun,
  error,
}: Simulator3DControlsProps) {
  const alienFileRef = useRef<HTMLInputElement>(null);
  const ghostFileRef = useRef<HTMLInputElement>(null);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, minWidth: 0 }}>
      {/* scenario selector */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {Object.entries(SCENARIO_META).map(([id, meta]) => (
          <button
            key={id}
            onClick={() => onScenario(id as ScenarioId)}
            style={{
              display: 'flex', alignItems: 'center', gap: 9, textAlign: 'left',
              background: scenario === id ? 'rgba(0,255,136,0.10)' : '#0d1117',
              border: `1px solid ${scenario === id ? '#00ff88' : '#1c2a38'}`,
              color: scenario === id ? '#00ff88' : '#8b9bab',
              borderRadius: 7, padding: '9px 12px', cursor: 'pointer',
              fontFamily: 'monospace', fontSize: 12,
            }}
          >
            <span style={{ fontSize: 15 }}>{meta.icon}</span>
            <span>
              <span style={{ display: 'block', fontWeight: 600 }}>{meta.label}</span>
              <span style={{ display: 'block', fontSize: 10, color: '#5b6b7b', marginTop: 2 }}>
                {meta.blurb}
              </span>
            </span>
          </button>
        ))}
      </div>

      {/* parameters */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: 10, letterSpacing: '2px' }}>
          PARAMETERS
        </div>

        {scenario === 'dynamics' && (
          <>
            <label style={labelStyle}>
              FORCE LAW
              <select
                value={params.forceLaw}
                onChange={(e) => onParams({ forceLaw: e.target.value as ScenarioParams['forceLaw'] })}
                style={inputStyle}
              >
                {FORCES.map((f) => <option key={f} value={f}>{f}</option>)}
              </select>
            </label>
            <Slider label="velocity vx" value={params.vx} min={-3} max={3} step={0.1} onChange={(v) => onParams({ vx: v })} />
            <Slider label="velocity vy" value={params.vy} min={-3} max={3} step={0.1} onChange={(v) => onParams({ vy: v })} />
            <Slider label="velocity vz" value={params.vz} min={-3} max={3} step={0.1} onChange={(v) => onParams({ vz: v })} />
            <Slider label="μ (mass parameter)" value={params.mu} min={0.1} max={10} step={0.1} onChange={(v) => onParams({ mu: v })} />
            <Slider label="Δt" value={params.dt} min={0.001} max={0.2} step={0.001} onChange={(v) => onParams({ dt: v })} />
            <Slider label="t max" value={params.tMax} min={1} max={60} step={1} onChange={(v) => onParams({ tMax: v })} unit=" s" />
          </>
        )}

        {scenario === 'terraformation' && (
          <Slider label="sea level rise" value={params.seaLevel} min={0} max={100} step={1} onChange={(v) => onParams({ seaLevel: v })} unit=" m" />
        )}

        {scenario === 'projections' && (
          <label style={labelStyle}>
            LEGACY PROJECTION
            <select
              value={params.projection}
              onChange={(e) => onParams({ projection: e.target.value as ScenarioParams['projection'] })}
              style={inputStyle}
            >
              {PROJECTION_TYPES.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </label>
        )}

        {scenario === 'physical-truth' && (
          <div style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: 11, lineHeight: 1.7, background: '#0d1117', border: '1px solid #1c2a38', borderRadius: 7, padding: '10px 12px' }}>
            No parameters — the manifold solves itself from the ingested
            area-derived edge graph. Zero bias: nothing is assumed, everything
            is derived.
          </div>
        )}

        {scenario === 'alien' && (
          <>
            <label style={labelStyle}>
              SAMPLE GRAPH
              <select
                value={params.alienSample}
                onChange={(e) => onParams({ alienSample: e.target.value })}
                style={inputStyle}
              >
                {ALIEN_SAMPLES.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
                {params.alienSample === 'custom' && <option value="custom">Uploaded CSV</option>}
              </select>
            </label>
            <input
              ref={alienFileRef} type="file" accept=".csv,text/csv" style={{ display: 'none' }}
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                const edges = parseAlienCsv(await file.text());
                if (edges.length >= 3) {
                  onParams({ alienSample: 'custom', alienCustomEdges: edges });
                }
                e.target.value = '';
              }}
            />
            <button onClick={() => alienFileRef.current?.click()} style={{ ...inputStyle, cursor: 'pointer', textAlign: 'left' }}>
              📄 Upload point-cloud edges (CSV: source, target, length)
            </button>
            {params.alienSample === 'custom' && params.alienCustomEdges && (
              <div style={{ color: '#00ff88', fontFamily: 'monospace', fontSize: 10 }}>
                {params.alienCustomEdges.length} edges loaded
              </div>
            )}
          </>
        )}

        {scenario === 'ghost' && (
          <>
            <div style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: 11, lineHeight: 1.7, background: '#0d1117', border: '1px solid #1c2a38', borderRadius: 7, padding: '10px 12px' }}>
              Default problem: derive an unknown region from enclosure closure
              against the global total. Upload your own adjacency JSON to
              investigate other ghosts.
            </div>
            <input
              ref={ghostFileRef} type="file" accept=".json,application/json" style={{ display: 'none' }}
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                try {
                  const j = JSON.parse(await file.text());
                  onParams({ ghostCustom: j });
                } catch { /* invalid JSON — ignore */ }
                e.target.value = '';
              }}
            />
            <button onClick={() => ghostFileRef.current?.click()} style={{ ...inputStyle, cursor: 'pointer', textAlign: 'left' }}>
              📄 Upload adjacency (JSON: polygons, global_enclosure, global_area)
            </button>
            {params.ghostCustom ? (
              <button onClick={() => onParams({ ghostCustom: null })} style={{ ...inputStyle, cursor: 'pointer', textAlign: 'left', color: '#f97316' }}>
                ✕ clear custom problem — back to default
              </button>
            ) : (
              <div style={{ color: '#00ff88', fontFamily: 'monospace', fontSize: 10 }}>
                default: {GHOST_PAYLOAD.polygons.length} polygons, enclosure {GHOST_PAYLOAD.global_enclosure}
              </div>
            )}
          </>
        )}
      </div>

      <button
        onClick={onRun}
        disabled={loading}
        style={{
          background: '#00ff88', color: '#04110a', border: 'none', padding: '11px 20px',
          borderRadius: 7, fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer',
          fontFamily: 'monospace', fontSize: 12, opacity: loading ? 0.5 : 1,
        }}
      >
        {loading ? 'deriving…' : '▶ Run Simulation'}
      </button>

      {error && (
        <div style={{
          background: 'rgba(249,115,22,0.08)', border: '1px solid rgba(249,115,22,0.4)',
          color: '#f97316', borderRadius: 7, padding: '10px 12px',
          fontFamily: 'monospace', fontSize: 11,
        }}>
          ⚠ {error}
        </div>
      )}
    </div>
  );
}
