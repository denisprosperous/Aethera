'use client';

/**
 * AETHERA v27.0 — /dashboard/simulator3d
 *
 * The unified 3D-first simulation experience. Left rail: scenario selector
 * + live parameters. Right: Three.js viewport + sealed stats panel.
 * Parameter changes update the viewport in real time (debounced 400 ms);
 * ▶ Run forces an immediate re-run.
 *
 * Layout:
 *  ┌─────────────┬───────────────────────────────┐
 *  │ Scenario    │ 3D Viewport                   │
 *  │ Parameters  │ [Three.js Canvas]             │
 *  │ [Run]       │ Stats Panel                   │
 *  └─────────────┴───────────────────────────────┘
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { useRouter } from 'next/navigation';
import LLMPalette from '@/components/LLMPalette';
import Simulator3DControls from '@/components/Simulator3DControls';
import {
  DEFAULT_PARAMS,
  runScenario,
  SCENARIO_META,
  type ScenarioId,
  type ScenarioParams,
  type StatItem,
} from '@/lib/useScenario';

const ScenarioViewport = dynamic(
  () => import('@/components/three/ScenarioViewport'),
  { ssr: false },
);

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div style={{ background: '#0d1117', border: '1px solid #1c2a38', borderRadius: '8px', padding: '13px 15px' }}>
      <div style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: '10px', letterSpacing: '1px', textTransform: 'uppercase' }}>
        {label}
      </div>
      <div style={{ color: accent ? '#00ff88' : '#e6edf3', fontFamily: 'monospace', fontSize: '15px', marginTop: '6px', fontWeight: 600, wordBreak: 'break-all' }}>
        {value}
      </div>
    </div>
  );
}

const DEBOUNCE_MS = 400;

export default function Simulator3DPage() {
  const [scenario, setScenario] = useState<ScenarioId>('dynamics');
  const [params, setParams] = useState<ScenarioParams>(DEFAULT_PARAMS);
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [stats, setStats] = useState<StatItem[]>([]);
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const runToken = useRef(0);
  const router = useRouter();

  const onParams = useCallback(
    (patch: Partial<ScenarioParams>) => setParams((p) => ({ ...p, ...patch })),
    [],
  );

  const execute = useCallback(
    async (sc: ScenarioId, p: ScenarioParams) => {
      const token = ++runToken.current;
      setLoading(true);
      setError('');
      try {
        const result = await runScenario(sc, p);
        if (token !== runToken.current) return; // superseded by a newer run
        setData(result.data);
        setStats(result.stats);
        setNote(result.note);
      } catch (e) {
        if (token !== runToken.current) return;
        setError((e as Error)?.message || 'Simulation request failed');
      } finally {
        if (token === runToken.current) setLoading(false);
      }
    },
    [],
  );

  // Auto-load on mount + real-time (debounced) re-run on any change.
  useEffect(() => {
    const t = setTimeout(() => execute(scenario, params), DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [scenario, params, execute]);

  return (
    <div style={{ width: '100%', maxWidth: '1280px', margin: '0 auto', color: '#e6edf3' }}>
      <LLMPalette />
      <header style={{ marginBottom: '18px' }}>
        <h1 style={{ fontSize: '22px', fontWeight: 300, letterSpacing: '2px' }}>🧊 SIMULATOR (3D)</h1>
        <p style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: '12px', marginTop: '6px' }}>
          All six AETHERA scenarios as interactive 3D scenes — rotate, zoom, pan, fly.
          Parameters update the viewport in real time. Intrinsic geometry only.
        </p>
      </header>

      <div
        style={{
          display: 'grid', gridTemplateColumns: 'minmax(240px, 300px) 1fr',
          gap: '16px', alignItems: 'start',
        }}
        className="simulator3d-grid"
      >
        {/* left rail */}
        <div style={{ background: '#0d1117', border: '1px solid #1c2a38', borderRadius: '10px', padding: '14px' }}>
          <Simulator3DControls
            scenario={scenario}
            params={params}
            loading={loading}
            error={error}
            onScenario={setScenario}
            onParams={onParams}
            onRun={() => execute(scenario, params)}
          />
        </div>

        {/* right: viewport + stats */}
        <div style={{ minWidth: 0 }}>
          <div style={{ position: 'relative', height: '560px', background: '#040a10', border: '1px solid #1c2a38', borderRadius: '10px', overflow: 'hidden' }}>
            {loading && (
              <div style={{
                position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: 'rgba(0,0,0,0.45)', zIndex: 9, color: '#06b6d4',
                fontFamily: 'monospace', fontSize: 13, letterSpacing: 1,
              }}>
                deriving…
              </div>
            )}
            <ScenarioViewport
              scenario={scenario}
              data={data}
              params={{
                seaLevel: params.seaLevel,
                forceLaw: params.forceLaw,
                dt: params.dt,
                tMax: params.tMax,
                projection: params.projection,
              }}
              onRegionClick={(region) =>
                router.push(`/dashboard/physical-truth?region=${encodeURIComponent(region)}`)
              }
            />
          </div>

          <p style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: '11px', margin: '10px 2px 14px' }}>
            {SCENARIO_META[scenario].icon} {SCENARIO_META[scenario].blurb}
          </p>

          {stats.length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '10px' }}>
              {stats.map((s) => <Stat key={s.label} label={s.label} value={s.value} accent={s.accent} />)}
            </div>
          )}

          {note && (
            <p style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: '11px', marginTop: '12px', lineHeight: 1.6 }}>
              {note}
            </p>
          )}
        </div>
      </div>

      <style>{`
        @media (max-width: 860px) {
          .simulator3d-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>

      <p style={{ marginTop: '24px', display: 'flex', gap: '18px' }}>
        <Link href="/dashboard" style={{ color: '#06b6d4', fontFamily: 'monospace', fontSize: '12px', textDecoration: 'none' }}>
          ← back to system overview
        </Link>
        <Link href="/dashboard/simulator" style={{ color: '#06b6d4', fontFamily: 'monospace', fontSize: '12px', textDecoration: 'none' }}>
          🧪 classic simulator →
        </Link>
        <Link href="/dashboard/globe" style={{ color: '#06b6d4', fontFamily: 'monospace', fontSize: '12px', textDecoration: 'none' }}>
          🌍 true-area globe →
        </Link>
      </p>
    </div>
  );
}
