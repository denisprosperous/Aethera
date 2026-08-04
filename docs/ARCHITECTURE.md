# AETHERA Architecture

## Repository layout

```
aethera-core/
├── rust/                       # Rust workspace
│   ├── Cargo.toml
│   ├── aethera-guard/         # Phase 0 build guard (Datum Bias Auditor)
│   ├── aethera-core/          # Shared types: Scalar, EdgeGraph, IntrinsicManifold
│   ├── aethera-ghost/         # Agent 0 — Ghost Polygon Resolver
│   ├── aethera-geometer/      # Agent 2 — Intrinsic Geometer (SMACOF)
│   ├── aethera-acif/          # Agent 6 — ACIF Navigator + Anomaly Daemon
│   ├── aethera-alien/         # Agent 8 — Alien Geometer
│   ├── aethera-dynamics/      # Agent 7 — Dynamics Module (reformed)
│   └── aethera-ffi/           # PyO3 bindings (optional)
├── python/aethera/            # Python orchestration layer
│   ├── core.py                # Scalar, EdgeGraph, IntrinsicManifold
│   ├── _smacof.py             # Pure-Python SMACOF
│   ├── agents/                # Agent wrappers
│   └── modules/               # Modules 5A-5G
├── web/                       # Next.js 16 + Three.js frontend
│   └── src/
│       ├── app/               # Next.js App Router
│       ├── components/         # StrainTensorView (WebGL)
│       └── lib/               # Projection math, polygon data
├── tests/                     # Integration tests
└── docs/                      # Documentation
```

## Data flow

```
Raw measurements (CSV/JSON)
    │
    ▼
EdgeGraph { nodes, edges: [(a, b, Scalar, sigma, source, epoch)] }
    │
    ├──> Agent 0 (Ghost Resolver) ──> Resolved polygons + Red Flags + Rationale Log
    │
    ├──> Agent 2 (Intrinsic Geometer)
    │       ├── Classical MDS warm start
    │       └── Weighted SMACOF: X^{k+1} = V⁺ B(X^k) X^k
    │           where V⁺ = (V + (1/n)J)⁻¹ − (1/n)J
    │
    ├──> Agent 6 (ACIF Navigator) ──> Intrinsic frame + anomaly alerts
    │
    ├──> Agent 7 (Dynamics, reformed)
    │       ├── Mode A: Dijkstra shortest path (graph routing)
    │       └── Mode B: RK4 under user-supplied force field (no targeting)
    │
    └──> Agent 8 (Alien Geometer) ──> Shape classification (Flat/Ellipsoidal/Potato)
                                │
                                ▼
                  IntrinsicManifold + Modules 5A-5G
```

## Numerical precision

| Layer | Precision | Rationale |
|-------|-----------|-----------|
| Input scalars (`Scalar`) | 256-bit (`rug::Float` / `mpmath.mpf`) | User measurements preserved exactly. |
| SMACOF inner loop | f64 | Numerical error ~1e-12, well below measurement noise (1e-3 to 1e-6). |
| Output coords | f64 | Visualisation does not need sub-f64 precision. |
