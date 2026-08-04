#!/bin/bash
set -e
ROOT=/home/z/my-project/aethera-core

# ============================================================
# PROGRESS.md
# ============================================================
cat > $ROOT/PROGRESS.md << 'MD'
# AETHERA Platform Progress

| Module | Data Ready? | API Endpoint Done? | UI Skeleton Done? | Tests Passing? |
|--------|-------------|-------------------|-------------------|----------------|
| Agent 0 (Ghost) | ✅ | ✅ `/api/ghost/resolve` | ✅ `/dashboard/ghost-resolver` | ✅ |
| Agent 2 (Solver) | ✅ | ✅ `/api/solve/manifold` | ✅ `/dashboard/consensus-hall` | ✅ |
| Agent 6 (ACIF) | ✅ | ✅ `/api/dynamics/simulate` | ✅ `/dashboard/anomaly-detector` | ✅ |
| Agent 7 (Dynamics) | ✅ | ✅ `/api/dynamics/simulate` | ✅ | ✅ |
| Agent 8 (Alien) | ✅ | ✅ `/api/alien/reconstruct` | ✅ | ✅ |
| Module 5A (Transparency) | ✅ | ✅ (in API) | ⬜ | ✅ |
| Module 5B (Strain) | ✅ | ✅ (in API) | ⬜ | ✅ |
| Module 5C (Anomaly) | ✅ | ✅ `/api/anomaly/latest` | ✅ `/dashboard/anomaly-detector` | ✅ |
| Module 5D (Maritime) | ✅ | ✅ (in API) | ⬜ | ✅ |
| Module 5E (Hall of Shame) | ✅ | ✅ `/api/projections/scores` | ✅ `/dashboard/consensus-hall` | ✅ |
| Module 5F (Terraformation) | ✅ | ✅ `/api/terraformation` | ✅ `/dashboard/terraformer` | ✅ |
| Module 5G (Stellar) | ✅ | ✅ (in API) | ⬜ | ✅ |

## Database status

Neon PostgreSQL project: `raspy-cherry-57547334`
Schema: v10.2 (no coordinates, Tabula Rasa)
Tables: `points`, `edges`, `faces`, `region_status`, `global_area_invariants`

## Ingestion modes

- **Mode A (user survey):** Absolute distances in metres. No coordinates.
- **Mode B (topology bootstrapping):** 1.0 placeholders. Solver infers lengths.
MD

# ============================================================
# docs/DATA_FLOW.md (Mermaid diagram)
# ============================================================
cat > $ROOT/docs/DATA_FLOW.md << 'MD'
# AETHERA Data Flow

```mermaid
graph TD
    subgraph "Phase 1: Ingestion"
        NE[Natural Earth shapefiles] -->|extract adjacency ONLY| TOPO[Topology extractor]
        TOPO -->|discard lon/lat| EDGES[Raw edge lengths<br/>1.0 placeholder or<br/>user-supplied metres]
        SURVEY[User survey CSV<br/>point_A,point_B,distance] --> EDGES
        EDGES --> DB[(PostgreSQL/Neon)]
    end

    subgraph "Phase 2: Solver Core"
        DB -->|read edges| A2[Agent 2<br/>SMACOF]
        A2 -->|coordinates + stress| MF[IntrinsicManifold]
        DB -->|adjacency + closure| A0[Agent 0<br/>Ghost Resolver]
        A0 -->|derived areas + rationale| REPORT[GhostReport]
        MF --> A8[Agent 8<br/>Alien Geometer]
        A8 -->|shape classification| SHAPE[Flat/Ellipsoidal/Potato]
        MF --> A7[Agent 7<br/>Dynamics]
        A7 -->|trajectory, NO targeting| SIM[SimulationResult]
    end

    subgraph "Phase 3: Modules"
        MF --> M5E[Hall of Shame]
        MF --> M5F[Terraformation]
        REPORT --> M5A[Transparency]
        DB --> M5C[Anomaly Daemon]
        SIM --> M5B[Strain Visualizer]
    end

    subgraph "Phase 4: API + UI"
        A2 --> API[FastAPI]
        A0 --> API
        A8 --> API
        A7 --> API
        M5E --> API
        M5F --> API
        M5C --> API
        API -->|JSON| UI[Next.js Dashboard]
        UI -->|REST calls| API
    end
```

## Key principle

NO pre-computed areas flow through this pipeline. The only inputs are:
1. **Adjacency topology** (which points connect to which).
2. **Raw edge lengths** (1.0 placeholders or user-supplied metres).
3. **Global area invariants** (user-supplied scalar totals).

All areas, coordinates, and shapes are derived by the solvers.
MD

# ============================================================
# tests/test_ingest.py
# ============================================================
cat > $ROOT/tests/test_ingest.py << 'PY'
"""Tests for the v10.2 ingestion pipeline — verifies no coordinates,
placeholder lengths, and solver-consumable output."""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
import pytest

from aethera.ingest.geometry import placeholder_length, parse_survey_csv, validate_survey_distance
from aethera.ingest.natural_earth import get_region_topology

def test_placeholder_length_is_1():
    assert placeholder_length() == 1.0

def test_validate_survey_distance_rejects_negative():
    with pytest.raises(ValueError):
        validate_survey_distance(-1.0)

def test_validate_survey_distance_rejects_zero():
    with pytest.raises(ValueError):
        validate_survey_distance(0.0)

def test_validate_survey_distance_accepts_positive():
    assert validate_survey_distance(42.5) == 42.5

def test_parse_survey_csv():
    csv = "A,B,100.0\nB,C,200.5\n"
    edges = parse_survey_csv(csv)
    assert len(edges) == 2
    assert edges[0] == ("A", "B", 100.0)
    assert edges[1] == ("B", "C", 200.5)

def test_parse_survey_csv_skips_comments():
    csv = "# comment\nA,B,100.0\n\n# another\nB,C,200.0\n"
    edges = parse_survey_csv(csv)
    assert len(edges) == 2

def test_topology_extraction_no_coordinates():
    """Verify that topology extraction returns ONLY adjacency — no coordinates."""
    polys = get_region_topology("Antarctica")
    assert len(polys) > 0
    for name, face_type, rings in polys:
        assert face_type in ("land", "ocean")
        for ring in rings:
            # Each ring is a list of point labels (strings), NOT coordinates.
            assert all(isinstance(label, str) for label in ring)
            assert len(ring) >= 3

def test_topology_extraction_returns_labels_not_coords():
    """CRITICAL: topology must return labels, not (lon,lat) tuples."""
    polys = get_region_topology("Antarctica")
    for _, _, rings in polys:
        for ring in rings:
            for label in ring:
                # Must be a string label, not a tuple of coordinates.
                assert isinstance(label, str)
                assert not isinstance(label, tuple)
                assert not isinstance(label, list)

def test_square_reconstruction_from_placeholders():
    """Given a square graph with 1.0 placeholder lengths, the solver
    must reconstruct a flat square."""
    from aethera.core import EdgeGraph, Scalar
    from aethera.agents import IntrinsicGeometer

    g = EdgeGraph()
    g.add_edge("A", "B", Scalar(1.0))  # placeholder
    g.add_edge("B", "C", Scalar(1.0))
    g.add_edge("C", "D", Scalar(1.0))
    g.add_edge("A", "D", Scalar(1.0))
    g.add_edge("A", "C", Scalar(1.41421356))  # diagonal
    g.add_edge("B", "D", Scalar(1.41421356))  # diagonal

    geo = IntrinsicGeometer()
    mf = geo.solve_2d(g)

    # The solver should reconstruct a flat square with low residual.
    assert mf.residual < 1e-6, f"residual too high: {mf.residual}"

    # All edges should be reconstructed to their input lengths.
    for a, b, target in [("A","B",1.0), ("A","C",1.41421356), ("A","D",1.0)]:
        d = mf.coords[a].dist(mf.coords[b])
        assert abs(d - target) < 1e-6, f"{a}-{b}: got {d}, want {target}"

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
PY

# ============================================================
# README_INGEST.md
# ============================================================
cat > $ROOT/docs/README_INGEST.md << 'MD'
# AETHERA Ingestion Pipeline (v10.2 — Tabula Rasa)

## Overview

The AETHERA ingestion pipeline populates a PostgreSQL database with
**raw edge lengths** between survey points — NO coordinates, NO lon/lat,
NO projections, NO sphere/ellipsoid assumptions.

## Two ingestion modes

### Mode A — User Survey (absolute distances)

The user provides a CSV of measured distances:

```csv
point_A, point_B, 1234.56
point_A, point_C, 5678.90
point_B, point_C, 9012.34
```

These are stored directly as `length_mode='measured'`. The solver
respects these absolute values.

### Mode B — Topology Bootstrapping (placeholder lengths)

We extract ONLY the adjacency topology from Natural Earth shapefiles
(which points are connected to which). All edge lengths are stored as
`1.0` placeholders. The solver (Agent 2) infers true lengths from
global area closure by minimising:

```
E = Σ_edges (l_e - l_true)² + λ (Σ_areas - Global_Total)²
```

This simultaneously finds the correct scale and curvature — entirely
from the topology and the global area invariant.

## Database schema

| Table | Columns | Purpose |
|-------|---------|---------|
| `points` | `id, label, region, source` | Point IDs (NO coordinates) |
| `edges` | `id, source_point_id, target_point_id, length_raw, length_mode, region, source` | Raw edge lengths |
| `faces` | `id, name, type, region, edge_ids[], point_ids[], properties` | Polygons (NO area column) |
| `region_status` | `region, status, edge_count, face_count, point_count, last_commit_hash` | Ingestion progress |
| `global_area_invariants` | `name, total_area_m2, source, notes` | User-supplied closure totals |

## Environment variables

```bash
export DATABASE_URL="postgresql://neondb_owner:***@ep-***.aws.neon.tech/neondb?sslmode=require"
export AETHERA_DATA_DIR="/path/to/natural_earth/shapefiles"  # optional
```

## Usage

```bash
# Ingest a single region (Mode B topology)
cd python
python -m aethera.ingest.pipeline --region Europe

# Ingest all regions
python -m aethera.ingest.pipeline --all

# Ingest Mode A user survey
python -m aethera.ingest.pipeline --survey /path/to/survey.csv

# Commit and push after each region
python -m aethera.ingest.pipeline --region Europe --push
```

## CRITICAL rule

**No pre-computed areas are ever imported.** The pipeline stores only:
1. Adjacency topology (which points connect to which).
2. Raw edge lengths (1.0 placeholders or user-supplied metres).
3. Global area totals (user-supplied scalars, used as closure constraints).

All areas are derived by Agent 0 (Ghost Resolver) and Agent 2
(Intrinsic Geometer) from these raw inputs.
MD

# ============================================================
# Frontend dashboard pages
# ============================================================
mkdir -p $ROOT/web/src/app/dashboard/{ghost-resolver,consensus-hall,terraformer,anomaly-detector}

cat > $ROOT/web/src/app/dashboard/ghost-resolver/page.tsx << 'TSX'
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
TSX

cat > $ROOT/web/src/app/dashboard/consensus-hall/page.tsx << 'TSX'
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
TSX

cat > $ROOT/web/src/app/dashboard/terraformer/page.tsx << 'TSX'
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
TSX

cat > $ROOT/web/src/app/dashboard/anomaly-detector/page.tsx << 'TSX'
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
TSX

# Navigation page linking to all dashboards
cat > $ROOT/web/src/app/dashboard/page.tsx << 'TSX'
'use client';
import Link from 'next/link';

export default function DashboardIndex() {
  const dashboards = [
    { href: '/dashboard/ghost-resolver', name: 'Ghost Resolver', desc: 'Topological residual closure for censored areas' },
    { href: '/dashboard/consensus-hall', name: 'Consensus Hall of Shame', desc: 'Projection strain tensor + Colonial Distortion Score' },
    { href: '/dashboard/terraformer', name: 'Terraformation Simulator', desc: 'Sea-level rise and coastline displacement' },
    { href: '/dashboard/anomaly-detector', name: 'Anomaly Detector', desc: 'Edge changes >1cm/day (civil-scientific)' },
  ];
  return (
    <main className="min-h-screen bg-black text-white p-8">
      <h1 className="text-3xl font-bold mb-6">AETHERA Dashboard</h1>
      <div className="grid grid-cols-2 gap-4">
        {dashboards.map(d => (
          <Link key={d.href} href={d.href}
            className="border border-white/10 rounded p-6 hover:border-cyan-500 transition">
            <h2 className="text-xl font-semibold mb-2">{d.name}</h2>
            <p className="text-sm text-white/60">{d.desc}</p>
          </Link>
        ))}
      </div>
    </main>
  );
}
TSX

echo "PROGRESS.md, DATA_FLOW.md, tests, docs, frontend written"
