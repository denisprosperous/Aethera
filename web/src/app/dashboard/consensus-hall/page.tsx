'use client';

/**
 * AETHERA v34.0 — /dashboard/consensus-hall
 *
 * THE CONSENSUS HALL OF SHAME.
 *
 * Legacy cartographic projections are measured artifacts here: the page
 * ranks regions by how much each scholarly projection inflates or shrinks
 * them relative to the platform's computed physical areas, and computes a
 * fully disclosed group-inflation score between two EDITABLE region
 * groups.
 *
 * Honesty rails:
 *  • The grouping is an INPUT, not a fact — presets are editable and the
 *    exact matched regions are always shown next to the score.
 *  • The score is pure arithmetic on stored legacy-vs-physical metrics.
 *  • The platform itself never adopts a legacy projection as a frame.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { apiFetch } from '@/lib/api';

interface StrainRow {
  region: string;
  area_physical_m2: number;
  area_legacy_m2: number;
  relative_error_percent: number;
}

interface HallPayload {
  projection: string;
  strain_ranking: StrainRow[];
  score: {
    group_a: { names: string[]; matched: string[]; area_weighted_mean_inflation_pct: number | null };
    group_b: { names: string[]; matched: string[]; area_weighted_mean_inflation_pct: number | null };
    ratio_a_over_b: number | null;
    formula: string;
    disclosure: string;
  };
  note: string;
}

const PROJECTIONS = ['Mercator', 'Robinson', 'AuthaGraph', 'Equirectangular'] as const;

const PRESET_A = 'United States, Russia, China, Canada, Australia, France, United Kingdom, Germany';
const PRESET_B = 'Chad, Mali, Niger, Bolivia, DR Congo, Indonesia, Brazil, India';

function heat(t: number): string {
  const c = Math.max(0, Math.min(1, t));
  const r = Math.round(40 + c * 215);
  const g = Math.round(120 - c * 60);
  const b = Math.round(90 - c * 40);
  return `rgb(${r},${g},${b})`;
}

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

export default function ConsensusHallPage() {
  const [projection, setProjection] = useState<string>('Mercator');
  const [groupA, setGroupA] = useState<string>(PRESET_A);
  const [groupB, setGroupB] = useState<string>(PRESET_B);
  const [st, setSt] = useState<{ loading: boolean; error: string; data: HallPayload | null }>({
    loading: true, error: '', data: null,
  });

  const load = useCallback(async () => {
    setSt((s) => ({ ...s, loading: true, error: '' }));
    try {
      const qs = new URLSearchParams({
        projection,
        group_a: groupA,
        group_b: groupB,
        limit: '200',
      });
      const res = await apiFetch(`/api/consensus-hall?${qs.toString()}`);
      if (!res.ok) throw new Error(`consensus-hall → HTTP ${res.status}`);
      const j = (await res.json()) as HallPayload;
      setSt({ loading: false, error: '', data: j });
    } catch (e) {
      setSt((s) => ({ ...s, loading: false, error: (e as Error)?.message || 'failed to load' }));
    }
  }, [projection, groupA, groupB]);

  useEffect(() => { load(); }, [load]);

  const rows = st.data?.strain_ranking || [];
  const maxAbs = useMemo(
    () => Math.max(1e-9, ...rows.map((r) => Math.abs(r.relative_error_percent || 0))),
    [rows],
  );

  const score = st.data?.score;

  return (
    <div style={{ width: '100%', maxWidth: '1200px', margin: '0 auto', color: '#e6edf3' }}>
      <header style={{ marginBottom: '14px' }}>
        <h1 style={{ fontSize: '22px', fontWeight: 300, letterSpacing: '2px' }}>🏛 CONSENSUS HALL OF SHAME</h1>
        <p style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: '12px', marginTop: '6px', lineHeight: 1.6 }}>
          How much does each scholarly projection stretch or shrink every region,
          measured against the platform&apos;s computed physical areas? The grouping
          below is an editable input, not a fact — the exact matched regions are
          always shown beside the score.
        </p>
      </header>

      <div
        style={{
          display: 'flex', flexWrap: 'wrap', gap: '10px 14px', alignItems: 'center',
          background: '#0d1117', border: '1px solid #1c2a38', borderRadius: '10px',
          padding: '12px 14px',
        }}
      >
        <span style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: 9, letterSpacing: 2 }}>PROJECTION UNDER AUDIT</span>
        {PROJECTIONS.map((p) => (
          <button
            key={p}
            onClick={() => setProjection(p)}
            style={{
              background: projection === p ? 'rgba(0,255,136,0.12)' : '#0d1117',
              border: `1px solid ${projection === p ? '#00ff88' : '#1c2a38'}`,
              color: projection === p ? '#00ff88' : '#8b9bab',
              borderRadius: '6px', padding: '7px 13px', cursor: 'pointer',
              fontFamily: 'monospace', fontSize: '11px',
            }}
          >
            {p}
          </button>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 10, margin: '14px 0' }}>
        <div style={{ background: '#0d1117', border: '1px solid #1c2a38', borderRadius: '8px', padding: '12px 14px' }}>
          <div style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: 9, letterSpacing: 2, marginBottom: 6 }}>
            GROUP A (editable preset)
          </div>
          <textarea
            value={groupA}
            onChange={(e) => setGroupA(e.target.value)}
            rows={3}
            style={{
              width: '100%', background: '#040a10', color: '#e6edf3', border: '1px solid #1c2a38',
              borderRadius: 6, fontFamily: 'monospace', fontSize: 11, padding: 8, resize: 'vertical',
            }}
          />
        </div>
        <div style={{ background: '#0d1117', border: '1px solid #1c2a38', borderRadius: '8px', padding: '12px 14px' }}>
          <div style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: 9, letterSpacing: 2, marginBottom: 6 }}>
            GROUP B (editable preset)
          </div>
          <textarea
            value={groupB}
            onChange={(e) => setGroupB(e.target.value)}
            rows={3}
            style={{
              width: '100%', background: '#040a10', color: '#e6edf3', border: '1px solid #1c2a38',
              borderRadius: 6, fontFamily: 'monospace', fontSize: 11, padding: 8, resize: 'vertical',
            }}
          />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10, marginBottom: 14 }}>
        <Stat label="Projection audited" value={projection} accent />
        <Stat label="Group A mean inflation" value={score?.group_a.area_weighted_mean_inflation_pct != null ? `${score.group_a.area_weighted_mean_inflation_pct.toFixed(2)}%` : '—'} />
        <Stat label="Group B mean inflation" value={score?.group_b.area_weighted_mean_inflation_pct != null ? `${score.group_b.area_weighted_mean_inflation_pct.toFixed(2)}%` : '—'} />
        <Stat label="Ratio A / B" value={score?.ratio_a_over_b != null ? `${score.ratio_a_over_b.toFixed(3)}×` : '—'} accent />
      </div>

      {score && (
        <div
          style={{
            background: '#0d1117', border: '1px solid #1c2a38', borderLeft: '4px solid #f59e0b',
            borderRadius: '10px', padding: '11px 14px', fontFamily: 'monospace', fontSize: 11,
            color: '#8b9bab', marginBottom: 14, lineHeight: 1.6,
          }}
        >
          <div><span style={{ color: '#5b6b7b' }}>FORMULA · </span>{score.formula}</div>
          <div><span style={{ color: '#5b6b7b' }}>DISCLOSURE · </span>{score.disclosure}</div>
          <div style={{ marginTop: 4 }}>
            <span style={{ color: '#5b6b7b' }}>MATCHED · </span>
            A [{score.group_a.matched.join(', ') || 'none'}] vs B [{score.group_b.matched.join(', ') || 'none'}]
          </div>
        </div>
      )}

      <div
        style={{
          background: '#0d1117', border: '1px solid #1c2a38', borderRadius: '10px',
          padding: '12px 14px', fontFamily: 'monospace', fontSize: 11,
        }}
      >
        <div style={{ color: '#5b6b7b', letterSpacing: 2, fontSize: 9, marginBottom: 8 }}>
          STRAIN RANKING — RELATIVE ERROR vs PHYSICAL AREA ({projection}, top {rows.length})
        </div>
        {st.loading && <div style={{ color: '#00ff88' }}>◌ auditing {projection}…</div>}
        {st.error && <div style={{ color: '#f97322' }}>⚠ {st.error}</div>}
        {!st.loading && !st.error && rows.length === 0 && (
          <div style={{ color: '#5b6b7b' }}>no stored distortion metrics for {projection} in this deployment.</div>
        )}
        {rows.map((r) => {
          const rel = r.relative_error_percent || 0;
          const w = (Math.abs(rel) / maxAbs) * 100;
          return (
            <div key={r.region} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '3px 0' }}>
              <div style={{ width: 170, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#e6edf3' }}>
                {r.region}
              </div>
              <div style={{ flex: 1, height: 10, background: '#040a10', borderRadius: 5, overflow: 'hidden' }}>
                <div
                  style={{
                    width: `${w}%`, height: '100%',
                    background: heat(Math.abs(rel) / maxAbs),
                  }}
                />
              </div>
              <div style={{ width: 90, textAlign: 'right', color: rel >= 0 ? '#ff6b6b' : '#3b82f6' }}>
                {rel >= 0 ? '+' : ''}{rel.toFixed(2)}%
              </div>
            </div>
          );
        })}
      </div>

      <p style={{ marginTop: '18px', display: 'flex', gap: '18px', flexWrap: 'wrap' }}>
        <Link href="/dashboard" style={{ color: '#06b6d4', fontFamily: 'monospace', fontSize: '12px', textDecoration: 'none' }}>
          ← back to system overview
        </Link>
        <Link href="/dashboard/earth-3d" style={{ color: '#06b6d4', fontFamily: 'monospace', fontSize: '12px', textDecoration: 'none' }}>
          ◈ intrinsic manifold viewer →
        </Link>
        <Link href="/dashboard/truth" style={{ color: '#06b6d4', fontFamily: 'monospace', fontSize: '12px', textDecoration: 'none' }}>
          ⚖️ truth portal →
        </Link>
      </p>
    </div>
  );
}
