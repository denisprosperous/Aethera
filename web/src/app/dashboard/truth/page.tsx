'use client';

/**
 * AETHERA v30.1 — /dashboard/truth — THE TRUTH PORTAL
 *
 * Arbitration, not a map. Data panels + signed Truth Certificates +
 * the Global Truth Index. Every verdict is computed from absolute scalar
 * inputs (areas, edge lengths) and every certificate is HMAC-SHA256
 * signed and independently verifiable via /api/certify/verify.
 *
 * Phases served: 1 (Truth Portal) · 3 (Arbitration — maritime +
 * territorial) · 4 (Certification) · 5 (Truth Index with trend).
 */

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import LLMPalette from '@/components/LLMPalette';
import Disclaimer from '@/components/Disclaimer';
import { apiFetch } from '@/lib/api';

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

interface CertT {
  certificate_id: string;
  type: string;
  algorithm: string;
  signature: string;
  payload_hash: string;
  issued_at_iso: string;
  verify: string;
  claim?: unknown;
  findings?: unknown;
  [k: string]: unknown;
}

interface GtiT {
  gti: number;
  grade: string;
  formula: string;
  components: Record<string, { value: number; weight: number; [k: string]: unknown }>;
  trend: { ts: number; gti: number }[];
  trend_points: number;
  certificate: CertT;
}

const panel: React.CSSProperties = {
  background: '#0d1117', border: '1px solid #1c2a38', borderRadius: '10px', padding: '16px 18px',
};

const input: React.CSSProperties = {
  background: '#040a10', color: '#e6edf3', border: '1px solid #1c2a38',
  borderRadius: 6, padding: '8px 10px', fontFamily: 'monospace', fontSize: 12,
  width: '100%', boxSizing: 'border-box',
};

const btn: React.CSSProperties = {
  background: 'rgba(0,255,136,0.12)', border: '1px solid #00ff88', color: '#00ff88',
  borderRadius: 6, padding: '9px 16px', cursor: 'pointer', fontFamily: 'monospace',
  fontSize: 12, fontWeight: 700,
};

const btnDim: React.CSSProperties = {
  ...btn, background: '#0d1117', border: '1px solid #1c2a38', color: '#8b9bab', fontWeight: 400,
};

function CertificateCard({ cert }: { cert: CertT }) {
  const [verdict, setVerdict] = useState<string>('');
  const verify = useCallback(async () => {
    try {
      const url = cert.verify.startsWith('/api')
        ? cert.verify
        : `/api/certify/verify?${cert.verify.split('?')[1] || ''}`;
      const res = await apiFetch(url);
      const j = await res.json();
      setVerdict(j.valid ? '✅ SIGNATURE VALID' : `❌ ${j.reason || 'invalid'}`);
    } catch (e) {
      setVerdict(`❌ ${(e as Error).message}`);
    }
  }, [cert]);

  return (
    <div style={{ ...panel, borderLeft: '4px solid #00ff88', fontSize: 11, fontFamily: 'monospace' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
        <span style={{ color: '#00ff88', fontWeight: 700 }}>🧾 {cert.certificate_id}</span>
        <span style={{ color: '#5b6b7b' }}>{cert.type} · {cert.issued_at_iso}</span>
      </div>
      <div style={{ marginTop: 8, color: '#5b6b7b', wordBreak: 'break-all' }}>
        payload_hash: <span style={{ color: '#8b9bab' }}>{String(cert.payload_hash).slice(0, 32)}…</span>
      </div>
      <div style={{ color: '#5b6b7b', wordBreak: 'break-all' }}>
        signature: <span style={{ color: '#8b9bab' }}>{String(cert.signature).slice(0, 32)}…</span>
      </div>
      <div style={{ color: '#5b6b7b' }}>algorithm: {cert.algorithm}</div>
      <div style={{ display: 'flex', gap: 10, marginTop: 10, alignItems: 'center' }}>
        <button style={btnDim} onClick={verify}>verify signature</button>
        {verdict && <span style={{ color: verdict.startsWith('✅') ? '#00ff88' : '#ff3b3b' }}>{verdict}</span>}
      </div>
      {cert.findings != null && (
        <details style={{ marginTop: 10 }}>
          <summary style={{ color: '#06b6d4', cursor: 'pointer' }}>findings (JSON)</summary>
          <pre style={{ color: '#8b9bab', fontSize: 10, whiteSpace: 'pre-wrap', maxHeight: 260, overflow: 'auto' }}>
            {JSON.stringify(cert.findings, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}

export default function TruthPortalPage() {
  const [regions, setRegions] = useState<string[]>([]);
  const [gti, setGti] = useState<GtiT | null>(null);
  const [loadErr, setLoadErr] = useState('');

  // Maritime form
  const [partyA, setPartyA] = useState('');
  const [partyB, setPartyB] = useState('');
  const [split, setSplit] = useState(0.5);
  const [maritimeResult, setMaritimeResult] = useState<{ arbitration: Record<string, unknown>; certificate: CertT } | null>(null);
  const [busyM, setBusyM] = useState(false);

  // Territorial form
  const [disputed, setDisputed] = useState('');
  const [aName, setAName] = useState('Party A');
  const [aKm2, setAKm2] = useState('2000000');
  const [bName, setBName] = useState('Party B');
  const [bKm2, setBKm2] = useState('2200000');
  const [terrResult, setTerrResult] = useState<{ arbitration: Record<string, unknown>; certificate: CertT } | null>(null);
  const [busyT, setBusyT] = useState(false);

  // Free-form certification
  const [claimJson, setClaimJson] = useState('{\n  "statement": "The disputed region area is 2,166,086 km2",\n  "source": "operator"\n}');
  const [freeCert, setFreeCert] = useState<CertT | null>(null);
  const [busyC, setBusyC] = useState(false);
  const [certErr, setCertErr] = useState('');

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [ri, gi] = await Promise.all([
          apiFetch('/api/regions/list'),
          apiFetch('/api/truth-index'),
        ]);
        if (!ri.ok) throw new Error(`regions/list → HTTP ${ri.status}`);
        const rj = await ri.json();
        const names = ((rj.regions as Record<string, unknown>[]) || []).map((r) => String(r.name));
        if (!alive) return;
        setRegions(names);
        setPartyA(names[0] || '');
        setPartyB(names[1] || '');
        setDisputed(names.find((n) => /greenland|sahara|australia/i.test(n)) || names[2] || '');
        if (gi.ok) setGti(await gi.json());
      } catch (e) {
        if (alive) setLoadErr((e as Error).message || 'failed to load Truth Portal data');
      }
    })();
    return () => { alive = false; };
  }, []);

  const runMaritime = useCallback(async () => {
    setBusyM(true); setMaritimeResult(null);
    try {
      const res = await apiFetch('/api/arbitration/maritime', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ party_a: partyA, party_b: partyB, claimed_split: split }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${(await res.text()).slice(0, 200)}`);
      setMaritimeResult(await res.json());
    } catch (e) {
      setMaritimeResult({ arbitration: { verdict: 'ERROR', rationale: (e as Error).message }, certificate: null as unknown as CertT });
    } finally { setBusyM(false); }
  }, [partyA, partyB, split]);

  const runTerritorial = useCallback(async () => {
    setBusyT(true); setTerrResult(null);
    try {
      const res = await apiFetch('/api/arbitration/territorial', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          disputed_region: disputed,
          claim_a_name: aName, claim_a_km2: Number(aKm2) || 0,
          claim_b_name: bName, claim_b_km2: Number(bKm2) || 0,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${(await res.text()).slice(0, 200)}`);
      setTerrResult(await res.json());
    } catch (e) {
      setTerrResult({ arbitration: { verdict: 'ERROR', rationale: (e as Error).message }, certificate: null as unknown as CertT });
    } finally { setBusyT(false); }
  }, [disputed, aName, aKm2, bName, bKm2]);

  const runCertify = useCallback(async () => {
    setBusyC(true); setCertErr(''); setFreeCert(null);
    try {
      const claim = JSON.parse(claimJson);
      const res = await apiFetch('/api/certify', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(claim),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${(await res.text()).slice(0, 200)}`);
      const j = await res.json();
      setFreeCert(j.certificate);
    } catch (e) {
      setCertErr((e as Error).message);
    } finally { setBusyC(false); }
  }, [claimJson]);

  // Sparkline geometry for the GTI trend.
  const spark = (() => {
    const pts = gti?.trend || [];
    if (pts.length < 2) return null;
    const w = 560, h = 56, pad = 4;
    const vals = pts.map((p) => p.gti);
    const min = Math.min(...vals), max = Math.max(...vals);
    const span = Math.max(1e-9, max - min);
    const path = pts.map((p, i) => {
      const x = pad + (i / (pts.length - 1)) * (w - 2 * pad);
      const y = h - pad - ((p.gti - min) / span) * (h - 2 * pad);
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
    return { path, w, h, min, max };
  })();

  return (
    <div style={{ width: '100%', maxWidth: '1200px', margin: '0 auto', color: '#e6edf3' }}>
      <LLMPalette />
      <header style={{ marginBottom: '14px' }}>
        <h1 style={{ fontSize: '22px', fontWeight: 300, letterSpacing: '2px' }}>⚖️ TRUTH PORTAL</h1>
        <p style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: '12px', marginTop: '6px', lineHeight: 1.6 }}>
          Arbitration, not a map. Verdicts are computed from absolute scalar inputs only —
          areas, edge lengths and global closure. Every finding ships with a signed Truth
          Certificate (HMAC-SHA256) that anyone can verify offline.
        </p>
      </header>

      <Disclaimer compact />

      {loadErr && (
        <div style={{ ...panel, borderLeft: '4px solid #f97316', color: '#f97316', fontFamily: 'monospace', fontSize: 12, marginBottom: 14 }}>
          ⚠ {loadErr} — the backend may be restarting; retry shortly.
        </div>
      )}

      {/* PHASE 5 — GLOBAL TRUTH INDEX */}
      <section style={{ ...panel, marginBottom: 16 }}>
        <h2 style={{ fontSize: 14, fontWeight: 600, letterSpacing: 2, color: '#e6edf3', margin: 0 }}>
          📊 GLOBAL TRUTH INDEX {gti ? `— ${gti.gti.toFixed(2)} / 100 · GRADE ${gti.grade}` : ''}
        </h2>
        <p style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: 11, margin: '8px 0 12px' }}>
          {gti?.formula || 'GTI = 100 × (0.40·accuracy + 0.30·coverage + 0.30·distortion_resistance)'} — all components from absolute scalar inputs.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 10 }}>
          <Stat label="GTI" value={gti ? gti.gti.toFixed(2) : '…'} accent />
          <Stat label="Solver Accuracy" value={gti ? gti.components.solver_accuracy.value.toFixed(4) : '…'} />
          <Stat label="Data Coverage" value={gti ? `${(gti.components.data_coverage.value * 100).toFixed(1)} %` : '…'} />
          <Stat label="Distortion Resistance" value={gti ? gti.components.distortion_resistance.value.toFixed(4) : '…'} />
          <Stat label="Trend Points" value={gti ? String(gti.trend_points) : '…'} />
        </div>
        {spark && (
          <div style={{ marginTop: 12 }}>
            <div style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: 10, marginBottom: 4 }}>
              GTI TREND · min {spark.min.toFixed(2)} · max {spark.max.toFixed(2)}
            </div>
            <svg width="100%" viewBox={`0 0 ${spark.w} ${spark.h}`} style={{ display: 'block', background: '#040a10', border: '1px solid #1c2a38', borderRadius: 6 }} preserveAspectRatio="none">
              <path d={spark.path} fill="none" stroke="#00ff88" strokeWidth="1.6" />
            </svg>
          </div>
        )}
        {gti?.certificate && (
          <div style={{ marginTop: 12 }}>
            <CertificateCard cert={gti.certificate} />
          </div>
        )}
      </section>

      {/* PHASE 3 — ARBITRATION */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: 16, marginBottom: 16 }}>
        <section style={panel}>
          <h2 style={{ fontSize: 14, fontWeight: 600, letterSpacing: 2, margin: 0 }}>🌊 MARITIME ARBITRATION</h2>
          <p style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: 11, lineHeight: 1.6 }}>
            Two parties, one claimed split. The fair split is anchored to the Physical
            Truth area ratio; the shared boundary length is derived from the intrinsic
            edge graph. No coastlines, no coordinates.
          </p>
          <div style={{ display: 'grid', gap: 10 }}>
            <label style={{ fontFamily: 'monospace', fontSize: 11, color: '#5b6b7b' }}>
              PARTY A
              <select style={{ ...input, marginTop: 4 }} value={partyA} onChange={(e) => setPartyA(e.target.value)}>
                {regions.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </label>
            <label style={{ fontFamily: 'monospace', fontSize: 11, color: '#5b6b7b' }}>
              PARTY B
              <select style={{ ...input, marginTop: 4 }} value={partyB} onChange={(e) => setPartyB(e.target.value)}>
                {regions.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </label>
            <label style={{ fontFamily: 'monospace', fontSize: 11, color: '#5b6b7b' }}>
              CLAIMED SPLIT FOR PARTY A · {split.toFixed(2)}
              <input type="range" min={0} max={1} step={0.01} value={split} onChange={(e) => setSplit(Number(e.target.value))} style={{ width: '100%', marginTop: 6 }} />
            </label>
            <button style={btn} onClick={runMaritime} disabled={busyM || !partyA || !partyB}>
              {busyM ? 'arbitrating…' : '⚖ arbitrate (maritime)'}
            </button>
          </div>
          {maritimeResult && (
            <div style={{ marginTop: 12, display: 'grid', gap: 10 }}>
              <div style={{ fontSize: 12, fontFamily: 'monospace' }}>
                <span style={{ color: '#5b6b7b' }}>VERDICT · </span>
                <span style={{
                  color: maritimeResult.arbitration.verdict === 'EQUITABLE' ? '#00ff88'
                    : maritimeResult.arbitration.verdict === 'CONTESTABLE' ? '#f97316' : '#ff3b3b',
                  fontWeight: 700,
                }}>
                  {String(maritimeResult.arbitration.verdict)}
                </span>
              </div>
              <div style={{ color: '#8b9bab', fontFamily: 'monospace', fontSize: 11, lineHeight: 1.6 }}>
                {String(maritimeResult.arbitration.rationale || '')}
              </div>
              {maritimeResult.certificate && <CertificateCard cert={maritimeResult.certificate} />}
            </div>
          )}
        </section>

        <section style={panel}>
          <h2 style={{ fontSize: 14, fontWeight: 600, letterSpacing: 2, margin: 0 }}>🗺 TERRITORIAL ARBITRATION</h2>
          <p style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: 11, lineHeight: 1.6 }}>
            A disputed region, two claims. Each claim is scored against the region&apos;s
            absolute Physical Truth area; the closest claim wins the verdict.
          </p>
          <div style={{ display: 'grid', gap: 10 }}>
            <label style={{ fontFamily: 'monospace', fontSize: 11, color: '#5b6b7b' }}>
              DISPUTED REGION
              <select style={{ ...input, marginTop: 4 }} value={disputed} onChange={(e) => setDisputed(e.target.value)}>
                {regions.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <label style={{ fontFamily: 'monospace', fontSize: 11, color: '#5b6b7b' }}>
                PARTY A NAME
                <input style={{ ...input, marginTop: 4 }} value={aName} onChange={(e) => setAName(e.target.value)} />
              </label>
              <label style={{ fontFamily: 'monospace', fontSize: 11, color: '#5b6b7b' }}>
                CLAIM A (km²)
                <input style={{ ...input, marginTop: 4 }} value={aKm2} onChange={(e) => setAKm2(e.target.value)} inputMode="numeric" />
              </label>
              <label style={{ fontFamily: 'monospace', fontSize: 11, color: '#5b6b7b' }}>
                PARTY B NAME
                <input style={{ ...input, marginTop: 4 }} value={bName} onChange={(e) => setBName(e.target.value)} />
              </label>
              <label style={{ fontFamily: 'monospace', fontSize: 11, color: '#5b6b7b' }}>
                CLAIM B (km²)
                <input style={{ ...input, marginTop: 4 }} value={bKm2} onChange={(e) => setBKm2(e.target.value)} inputMode="numeric" />
              </label>
            </div>
            <button style={btn} onClick={runTerritorial} disabled={busyT || !disputed}>
              {busyT ? 'arbitrating…' : '⚖ arbitrate (territorial)'}
            </button>
          </div>
          {terrResult && (
            <div style={{ marginTop: 12, display: 'grid', gap: 10 }}>
              <div style={{ fontSize: 12, fontFamily: 'monospace' }}>
                <span style={{ color: '#5b6b7b' }}>VERDICT · </span>
                <span style={{ color: '#00ff88', fontWeight: 700 }}>{String(terrResult.arbitration.verdict)}</span>
              </div>
              <div style={{ color: '#8b9bab', fontFamily: 'monospace', fontSize: 11, lineHeight: 1.6 }}>
                {String(terrResult.arbitration.rationale || '')}
              </div>
              {terrResult.certificate && <CertificateCard cert={terrResult.certificate} />}
            </div>
          )}
        </section>
      </div>

      {/* PHASE 4 — CERTIFICATION */}
      <section style={{ ...panel, marginBottom: 16 }}>
        <h2 style={{ fontSize: 14, fontWeight: 600, letterSpacing: 2, margin: 0 }}>🧾 TRUTH CERTIFICATION</h2>
        <p style={{ color: '#5b6b7b', fontFamily: 'monospace', fontSize: 11, lineHeight: 1.6, margin: '8px 0 12px' }}>
          Any JSON claim can be attested: the payload is canonically hashed (SHA-256,
          sorted keys) and signed (HMAC-SHA256). All arbitration and index responses
          include certificates automatically.
        </p>
        <textarea
          style={{ ...input, minHeight: 110, resize: 'vertical' }}
          value={claimJson}
          onChange={(e) => setClaimJson(e.target.value)}
          spellCheck={false}
        />
        <div style={{ marginTop: 10, display: 'flex', gap: 12, alignItems: 'center' }}>
          <button style={btn} onClick={runCertify} disabled={busyC}>{busyC ? 'signing…' : 'sign & certify'}</button>
          {certErr && <span style={{ color: '#ff3b3b', fontFamily: 'monospace', fontSize: 11 }}>{certErr}</span>}
        </div>
        {freeCert && (
          <div style={{ marginTop: 12 }}>
            <CertificateCard cert={freeCert} />
          </div>
        )}
      </section>

      <p style={{ marginTop: '22px', display: 'flex', gap: '18px', flexWrap: 'wrap' }}>
        <Link href="/dashboard" style={{ color: '#06b6d4', fontFamily: 'monospace', fontSize: '12px', textDecoration: 'none' }}>
          ← back to system overview
        </Link>
        <Link href="/dashboard/earth-3d" style={{ color: '#06b6d4', fontFamily: 'monospace', fontSize: '12px', textDecoration: 'none' }}>
          🌍 3D earth simulation →
        </Link>
      </p>
    </div>
  );
}
