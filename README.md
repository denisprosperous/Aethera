# AETHERA — Project Terra Incognita Ex Machina (TIEM)

**The first objective geometric substrate.** AETHERA reconstructs the
intrinsic geometry of a manifold from raw edge-length measurements
(LIDAR, VLBI, sonar, atomic-interferometric phase delays) **without
assuming any consensus prior** — no planetary radius, no gravitational
constant, no ephemeris, no geodetic datum, no standard gravity.

If the data implies a flat Earth, AETHERA outputs a flat map. If the data
implies curvature, AETHERA outputs that — without ever assuming it ahead
of time.

**v6.0 (current):** Hardened physics + transparent ethics. The platform
is a geometry provider, not a weapons controller. Agent 7 is reformed as
a dual-mode dynamics module (inertial geodesic + user-supplied
force-field simulation) with no targeting outputs. The build guard is
a warning-level Datum Bias Auditor.

## Quick start

### Rust core
```bash
cd rust
cargo build --workspace --release
cargo test --release --workspace --exclude aethera-ffi
./target/release/aethera-guard audit .
```

### Python layer
```bash
cd python
pip install -e .
python ../tests/test_integration.py
```

### Web frontend
```bash
cd web
npm install
npm run dev   # http://localhost:3000
```

## Components

| Component | Language | Description |
|-----------|----------|-------------|
| `rust/aethera-guard` | Rust | Datum Bias Auditor — warning-level linter for hardcoded constants |
| `rust/aethera-core` | Rust | Shared types: `Scalar` (256-bit), `EdgeGraph`, `IntrinsicManifold`, `ScalarFieldLayer` |
| `rust/aethera-ghost` | Rust | **Agent 0** — Ghost Polygon Resolver. Topological residual closure, 5% threshold, rationale log |
| `rust/aethera-geometer` | Rust | **Agent 2** — Intrinsic Geometer. Weighted SMACOF via `V⁺ = (V + (1/n)J)⁻¹ − (1/n)J`, curvature |
| `rust/aethera-acif` | Rust | **Agent 6** — ACIF Navigator + Module 5C anomaly daemon (civil-scientific) |
| `rust/aethera-alien` | Rust | **Agent 8** — Alien Geometer. Topology-agnostic shape reconstruction (Flat/Ellipsoidal/Potato) |
| `rust/aethera-dynamics` | Rust | **Agent 7** (reformed) — Dual-mode: inertial geodesic + user-force-field RK4. **No targeting outputs.** |
| `rust/aethera-ffi` | Rust | PyO3 bindings (optional — pure-Python fallback exists) |
| `python/aethera/` | Python | Pure-Python orchestration layer with all agents + modules |
| `web/` | Next.js 16 + Three.js | "Consensus Hall of Shame" WebGL frontend |

## Modules

| Module | Name | Description |
|--------|------|-------------|
| 5A | Transparency Comparator | Arms-control range-vs-chord comparator (no trajectory physics) |
| 5B | Strain Visualizer | Seismic strain manifold (not a predictor) |
| 5C | Anomaly Daemon | Civil-scientific: groundwater, glacial, volcanic, geothermal |
| 5D | Maritime Chokepoint | Navigability under varying tides |
| 5E | Hall of Shame | Projection strain-tensor overlay + Colonial Distortion Score |
| 5F | Terraformation | Volume-transfer coastline displacement |
| 5G | Stellar Positioning | Deep-space probe VLBI positioning |

## Ethical safeguards

The platform is a **geometry provider**, not a weapons controller.

- `shortest_path()` accepts start + end nodes → returns path length. Does NOT return azimuth/elevation/impact_point.
- `simulate_particle()` accepts start + initial velocity + user-supplied force field → returns trajectory. Does NOT accept a `target` parameter.
- The inverse problem (given target, find firing parameters) requires an external solver explicitly out of scope.
- The force field is ALWAYS user-supplied. The platform never hardcodes `G` or any planetary mass.

See `docs/REFORMED_MODULES.md` for the full engineering rationale.

## License

MIT. See `LICENSE`.
