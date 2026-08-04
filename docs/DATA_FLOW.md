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
