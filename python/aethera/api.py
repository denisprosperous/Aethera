"""AETHERA FastAPI backend — live endpoints that read raw edge data
from PostgreSQL and call the Rust core (via FFI or Python fallback).

v10.8: Uses Rust FFI bridge for SMACOF solving (1.7x faster than Python).
Includes LLM integration (GLM-5.2 primary, fallback chain).
"""

from __future__ import annotations
import os
import sys
import json
import asyncio
import tempfile
from typing import List, Optional, Dict, Any
from dataclasses import asdict

# Ensure the aethera package is importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from aethera.ingest.db import Database
from aethera.ingest.schema import DATABASE_URL
from aethera.agents import IntrinsicGeometer, GhostResolver, AlienGeometer, DynamicsModule
from aethera.agents.ghost import Polygon as GhostPolygon
from aethera.core import EdgeGraph, Scalar
from aethera.rust_bridge import solve_manifold, is_rust_available
from aethera.modules import (
    HallOfShame, TransparencyComparator, StrainVisualizer,
    AnomalyDaemon, MaritimeChokepoint, TerraformationSimulator, StellarPositioning,
)
from aethera.modules.terraformation import VolumeTransfer
from aethera.modules.hall_of_shame import Polygon as HSPolygon
from aethera.modules.transparency import RangeClaim
from aethera.modules.physical_truth_manifold import (
    solve_physical_truth_manifold, build_physical_truth_edge_graph,
    list_regions, get_region_area,
)
from aethera.modules.ghost_resolver_integration import derive_antarctica_area
from aethera.modules.compare_ingestion import compute_distortion_metrics
from aethera.agents.acif import AcifSnapshot
from aethera.agents.dynamics import (
    ForceFieldConfig, simulate_particle,
    inertial_field, inverse_square_field, uniform_field,
)

app = FastAPI(
    title="AETHERA API",
    description="First objective geometric substrate. No pre-computed areas — "
                "all areas derived from raw edge lengths + global closure.",
    version="0.26.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Deployment-mode detection (v26.0 Railway-aware) -------------------
# The platform runs identically in two modes:
#   RAILWAY  — served by the Railway backend (RAILWAY_* env present).
#   VERCEL   — same-origin serverless function on Vercel (VERCEL_ENV set).
#   LOCAL    — bare uvicorn run (development).

RAILWAY_ENABLED = bool(os.environ.get('RAILWAY_PUBLIC_DOMAIN') or os.environ.get('RAILWAY_PROJECT_ID'))
VERCEL_ENABLED = bool(os.environ.get('VERCEL_ENV') or os.environ.get('VERCEL'))

if RAILWAY_ENABLED:
    DEPLOYMENT_MODE = 'railway'
    API_BASE = os.environ.get('RAILWAY_PUBLIC_URL', 'https://aethera-backend.up.railway.app')
    print(f"🌐 AETHERA deployment mode: Railway ({API_BASE})", flush=True)
elif VERCEL_ENABLED:
    DEPLOYMENT_MODE = 'vercel-serverless'
    API_BASE = ''  # same-origin relative /api/*
    print("🖥️ AETHERA deployment mode: Vercel serverless (same-origin)", flush=True)
else:
    DEPLOYMENT_MODE = 'local'
    API_BASE = ''
    print("🧪 AETHERA deployment mode: local development", flush=True)


# ---- Pydantic models --------------------------------------------------

class EdgeInput(BaseModel):
    source: str
    target: str
    length: float = 1.0  # 1.0 = Mode B placeholder; user-supplied = Mode A
    sigma: Optional[float] = None
    source_type: str = "topology"

class SolveManifoldRequest(BaseModel):
    region: Optional[str] = None  # if None, use all regions
    edges: Optional[List[EdgeInput]] = None  # inline edges
    max_iter: int = 500
    tol: float = 1e-10
    embedding: str = "2d"  # "2d" or "3d"

class SolveManifoldResponse(BaseModel):
    region: str
    node_count: int
    edge_count: int
    coordinates: Dict[str, List[float]]
    residual: float
    stress: float
    note: str

class GhostResolveRequest(BaseModel):
    polygons: List[Dict[str, Any]]  # [{name, area (null if unknown), claimed_area, neighbours}]
    global_enclosure: str
    global_area: float

class GhostResolveResponse(BaseModel):
    resolved_areas: Dict[str, float]
    red_flags: List[Dict[str, Any]]
    rationale_log: List[Dict[str, Any]]
    sealed_hash: str
    note: str

class AlienReconstructRequest(BaseModel):
    edges: List[EdgeInput]
    max_iter: int = 500
    tol: float = 1e-10

class AlienReconstructResponse(BaseModel):
    shape: str
    embedding: str
    residual: float
    mean_curvature: float
    node_count: int
    edge_count: int
    note: str

class DynamicsSimulateRequest(BaseModel):
    start: List[float]  # [x, y, z]
    initial_velocity: List[float]  # [vx, vy, vz]
    force_law: str = "inertial"  # "inertial", "inverse_square", "uniform"
    mu: float = 1.0  # for inverse_square (user-supplied, NOT hardcoded G)
    uniform_accel: List[float] = [0, 0, 0]  # for uniform
    dt: float = 0.01
    t_max: float = 10.0

class DynamicsSimulateResponse(BaseModel):
    trajectory: List[List[float]]
    total_path_length: float
    total_time: float
    final_position: List[float]
    note: str

class TerraformationRequest(BaseModel):
    sea_level_rise_m: float = Field(..., ge=0, le=100)
    regions: Optional[List[str]] = None

class TerraformationResponse(BaseModel):
    sea_level_rise_m: float
    coastline_changes: List[Dict[str, Any]]
    note: str

class DatasetsResponse(BaseModel):
    regions: List[Dict[str, Any]]

class RegionEdgesResponse(BaseModel):
    region: str
    edges: List[Dict[str, Any]]
    faces: List[Dict[str, Any]]


# ---- Helper: fetch edges from DB --------------------------------------

def _fetch_edges_from_db(region: str = None) -> tuple[EdgeGraph, str]:
    """Fetch raw edges from the database and build an EdgeGraph.
    Returns (graph, region_label)."""
    with Database() as db:
        if region:
            db_edges = db.get_region_edges(region)
            faces = db.get_region_faces(region)
            label = region
        else:
            # Fetch all edges.
            db.cur.execute(
                "SELECT id, source_point_id, target_point_id, length_raw, length_mode FROM edges ORDER BY id"
            )
            rows = db.cur.fetchall()
            db_edges = [{"id": r[0], "source": r[1], "target": r[2], "length": r[3], "mode": r[4]} for r in rows]
            db.cur.execute("SELECT id, name, type, edge_ids, point_ids FROM faces ORDER BY id")
            frows = db.cur.fetchall()
            faces = [{"id": r[0], "name": r[1], "type": r[2], "edge_ids": r[3], "point_ids": r[4]} for r in frows]
            label = "all"

    graph = EdgeGraph()
    # Build a label map for point IDs.
    point_labels = {}
    for e in db_edges:
        s_label = str(e["source"])
        t_label = str(e["target"])
        if s_label not in point_labels:
            point_labels[s_label] = f"p{e['source']}"
        if t_label not in point_labels:
            point_labels[t_label] = f"p{e['target']}"
        graph.add_edge(
            point_labels[s_label], point_labels[t_label],
            Scalar(e["length"]),
            sigma=None,
            source=e.get("mode", "topology"),
        )
    return graph, label


# ---- Endpoints --------------------------------------------------------

@app.get("/api/health")
async def health():
    """Health check — reports solver, LLM and deployment mode status."""
    from aethera.llm import llm_status
    return {
        "status": "ok",
        "version": "0.26.0",
        "platform": "AETHERA v26.0",
        "mode": DEPLOYMENT_MODE,
        "database": "connected",
        "solver": "rust" if is_rust_available() else "python_fallback",
        "llm": llm_status(),
    }


@app.post("/api/llm/query")
async def llm_query(prompt: str = None, system_prompt: str = None,
                    body: Optional[Dict[str, Any]] = None):
    """Query the LLM (NVIDIA NIM default — no API key required).

    Accepts either query parameters (prompt, system_prompt) or a JSON body
    {prompt, system_prompt?, model?, api_key?}. A per-request api_key
    overrides the active NVIDIA key without touching server state.
    """
    from aethera.llm import query_llm
    if body:
        prompt = body.get("prompt") or prompt
        system_prompt = body.get("system_prompt") or system_prompt
        model = body.get("model")
        api_key = body.get("api_key")
    else:
        model = None
        api_key = None
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    result = await query_llm(prompt, system_prompt, api_key=api_key, model=model)
    return {
        "text": result.text,
        "provider": result.provider,
        "model": result.model,
        "success": result.success,
        "error": result.error,
    }


@app.get("/api/llm/status")
async def llm_status_endpoint():
    """Get LLM provider status."""
    from aethera.llm import llm_status
    return llm_status()


@app.get("/api/llm/key")
async def llm_key_status():
    """Report the active NVIDIA API key (masked) and whether it is custom."""
    from aethera.llm import get_nvidia_key, mask_key
    runtime_custom = os.environ.get("NVIDIA_API_KEY") is not None
    return {
        "provider": "NVIDIA NIM (free)",
        "masked_key": mask_key(get_nvidia_key()),
        "custom_key_active": runtime_custom,
        "note": "A built-in key ships with the platform — no entry required. "
                "POST a new key here (JSON {api_key}) or via the dashboard "
                "palette (Ctrl+K → Settings) to rotate it.",
    }


class NVIDIAKeyRequest(BaseModel):
    api_key: Optional[str] = None
    reset: bool = False


@app.post("/api/llm/key")
async def llm_set_key(req: NVIDIAKeyRequest):
    """Set / rotate the NVIDIA API key for this instance.

    Send {"api_key": "nvapi-..."} to set a user key, or {"reset": true} to
    restore the built-in default. The key is held in memory and persisted
    to a writable temp path when available.
    """
    from aethera.llm import set_nvidia_key, get_nvidia_key, mask_key
    if req.reset:
        set_nvidia_key(None)
        return {"success": True, "action": "reset",
                "masked_key": mask_key(get_nvidia_key())}
    key = (req.api_key or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="api_key is required")
    if not key.startswith("nvapi-"):
        raise HTTPException(status_code=400, detail="NVIDIA keys start with 'nvapi-'")
    set_nvidia_key(key)
    return {"success": True, "action": "set",
            "masked_key": mask_key(get_nvidia_key())}


@app.get("/api/datasets", response_model=DatasetsResponse)
async def list_datasets():
    """List all regions with their ingestion status."""
    with Database() as db:
        regions = db.get_all_region_status()
    return {"regions": regions}


@app.get("/api/regions/{region}/edges", response_model=RegionEdgesResponse)
async def get_region_edges(region: str):
    """Get all raw edges and faces for a region."""
    with Database() as db:
        edges = db.get_region_edges(region)
        faces = db.get_region_faces(region)
    if not edges and not faces:
        raise HTTPException(404, f"Region '{region}' not found or not ingested.")
    return {"region": region, "edges": edges, "faces": faces}


@app.post("/api/solve/manifold", response_model=SolveManifoldResponse)
async def solve_manifold(req: SolveManifoldRequest):
    """Solve the intrinsic manifold for a region or inline edges.
    Reads raw edge lengths from the database (Mode A or B) and runs
    Agent 2 (SMACOF). Returns coordinates + stress."""
    if req.edges:
        graph = EdgeGraph()
        for e in req.edges:
            graph.add_edge(e.source, e.target, Scalar(e.length), sigma=None, source=e.source_type)
        label = "inline"
    else:
        graph, label = await asyncio.get_event_loop().run_in_executor(
            None, _fetch_edges_from_db, req.region
        )

    if graph.edge_count < 3:
        raise HTTPException(400, f"Not enough edges to solve: {graph.edge_count}")

    geo = IntrinsicGeometer(max_iter=req.max_iter, tol=req.tol)
    try:
        if req.embedding == "3d":
            mf = geo.solve_3d(graph)
        else:
            mf = geo.solve_2d(graph)
    except Exception as e:
        raise HTTPException(500, f"Solver failed: {e}")

    coords = {name: [p.x, p.y, p.z] for name, p in mf.coords.items()}
    return SolveManifoldResponse(
        region=label,
        node_count=graph.node_count,
        edge_count=graph.edge_count,
        coordinates=coords,
        residual=mf.residual,
        stress=mf.residual,
        note=f"Intrinsic manifold solved via SMACOF. Embedding: {mf.embedding}. No pre-computed areas used.",
    )


@app.post("/api/ghost/resolve", response_model=GhostResolveResponse)
async def ghost_resolve(req: GhostResolveRequest):
    """Resolve NULL polygon areas via topological residual closure (Agent 0).
    Returns derived areas with rationale logs and red flags."""
    polygons = []
    for p in req.polygons:
        area = Scalar(p["area"]) if p.get("area") is not None else None
        claimed = Scalar(p["claimed_area"]) if p.get("claimed_area") is not None else None
        polygons.append(GhostPolygon(
            name=p["name"],
            area=area,
            neighbours=p.get("neighbours", []),
            claimed_area=claimed,
            security_level=p.get("security_level", "N/A"),
        ))
    resolver = GhostResolver()
    report = resolver.solve(polygons, req.global_enclosure, Scalar(req.global_area))
    resolved = {p.name: p.area.to_f64() if p.area else 0.0 for p in report.polygons}
    
    # Convert red_flags and rationale_log to dicts, handling Scalar serialization
    red_flags = []
    for r in report.red_flags:
        if hasattr(r, '__dataclass_fields__'):
            flag_dict = asdict(r)
            # Convert any Scalar objects to float
            for key, val in flag_dict.items():
                if hasattr(val, 'to_f64'):
                    flag_dict[key] = val.to_f64()
            red_flags.append(flag_dict)
        else:
            red_flags.append(r.__dict__ if hasattr(r, '__dict__') else str(r))
    
    rationale_log = []
    for r in report.rationale_log:
        if hasattr(r, '__dataclass_fields__'):
            log_dict = asdict(r)
            # Convert any Scalar objects to float
            for key, val in log_dict.items():
                if hasattr(val, 'to_f64'):
                    log_dict[key] = val.to_f64()
            rationale_log.append(log_dict)
        else:
            rationale_log.append(r.__dict__ if hasattr(r, '__dict__') else str(r))
    
    return GhostResolveResponse(
        resolved_areas=resolved,
        red_flags=red_flags,
        rationale_log=rationale_log,
        sealed_hash=report.sealed_hash,
        note="Areas derived via topological residual closure. No pre-computed areas used.",
    )


@app.post("/api/alien/reconstruct", response_model=AlienReconstructResponse)
async def alien_reconstruct(req: AlienReconstructRequest):
    """Reconstruct intrinsic shape from raw edge lengths (Agent 8).
    Classifies as Flat / Ellipsoidal / Potato."""
    graph = EdgeGraph()
    for e in req.edges:
        graph.add_edge(e.source, e.target, Scalar(e.length), source=e.source_type)
    ag = AlienGeometer(max_iter=req.max_iter, tol=req.tol)
    mf, report = ag.analyse(graph)
    return AlienReconstructResponse(
        shape=report.shape,
        embedding=report.embedding,
        residual=report.residual,
        mean_curvature=report.mean_curvature,
        node_count=report.node_count,
        edge_count=report.edge_count,
        note="Shape reconstructed from raw edge lengths. No coordinates assumed.",
    )


@app.post("/api/dynamics/simulate", response_model=DynamicsSimulateResponse)
async def dynamics_simulate(req: DynamicsSimulateRequest):
    """Simulate a test particle under a user-supplied force field (Agent 7).
    NO targeting outputs — only trajectory and path length."""
    if req.force_law == "inverse_square":
        accel_fn = inverse_square_field(mu=req.mu, center=(0, 0, 0))
        note_suffix = f"Inverse-square field with user-supplied μ={req.mu}."
    elif req.force_law == "uniform":
        accel_fn = uniform_field(tuple(req.uniform_accel))
        note_suffix = f"Uniform field {req.uniform_accel}."
    else:
        accel_fn = inertial_field()
        note_suffix = "Inertial (zero acceleration)."
    config = ForceFieldConfig(dt=req.dt, t_max=req.t_max, force_law_note=req.force_law)
    result = simulate_particle(
        start=tuple(req.start),
        vel0=tuple(req.initial_velocity),
        accel_fn=accel_fn,
        config=config,
    )
    return DynamicsSimulateResponse(
        trajectory=[list(p) for p in result.trajectory],
        total_path_length=result.total_path_length,
        total_time=result.total_time,
        final_position=list(result.final_position),
        note=f"{note_suffix} Targeting solutions NOT provided.",
    )


@app.post("/api/terraformation", response_model=TerraformationResponse)
async def terraformation(req: TerraformationRequest):
    """Simulate sea-level rise and compute per-nation coastline changes.

    Intrinsic model (no coordinates, no external datasets): each region's
    derived physical area A (absolute scalar input) yields a compactness
    proxy P = SHAPE_FACTOR * sqrt(A) for its boundary length. A rise of
    dh metres floods a coastal band of width w = dh * SLOPE_FACTOR,
    submerging dA = min(A, P * w / 1e6) km2. Small low-lying nations are
    therefore hit hardest and can vanish entirely — an emergent, unbiased
    consequence of scale, not a pre-programmed list.
    """
    dh_m = req.sea_level_rise_m
    # AETHERA-GUARD: ALLOW DOCUMENTATION (documented model parameters,
    # not measured physical constants — calibration choices only).
    SHAPE_FACTOR = 4.0        # boundary of a compact region ~ 4*sqrt(A)
    SLOPE_FACTOR = 1000.0     # flooded width per metre of rise (m/m)

    with Database() as db:
        db.cur.execute(
            "SELECT region_name, area_m2/1e6 FROM physical_truth_srtm "
            "WHERE area_m2 > 0 ORDER BY area_m2 ASC"
        )
        rows = db.cur.fetchall()

    band_km = dh_m * SLOPE_FACTOR / 1000.0  # km of flooded band
    changes = []
    total_lost = 0.0
    for name, area_km2 in rows:
        if req.regions and name not in req.regions:
            continue
        perimeter_km = SHAPE_FACTOR * (area_km2 ** 0.5)
        lost = min(area_km2, perimeter_km * band_km)
        if lost <= 0:
            continue
        total_lost += lost
        after = area_km2 - lost
        pct = (lost / area_km2) * 100.0
        verdict = "SUBMERGED" if after <= 0 else f"-{pct:.2f}%"
        changes.append({
            "nation": name,
            "area_change_km2": -lost,
            "before": area_km2,
            "after": after,
            "note": f"{name}: {lost:+,.0f} km2 ({area_km2:,.0f} -> {after:,.0f}) {verdict}",
        })

    changes.sort(key=lambda c: c["area_change_km2"])
    return TerraformationResponse(
        sea_level_rise_m=dh_m,
        coastline_changes=changes,
        note=(f"Intrinsic scale-proximity model: dA = min(A, 4*sqrt(A)*{band_km:g} km). "
              f"{len(changes)} nations affected, {total_lost:,.0f} km2 lost total. "
              "No coordinates or external data used."),
    )


@app.get("/api/anomaly/latest")
async def anomaly_latest():
    """Get edges that changed >1cm/day (placeholder — requires time-series data)."""
    return {
        "alerts": [],
        "note": "Anomaly detection requires time-series edge data. "
                "Ingest multiple snapshots to populate.",
    }


@app.get("/api/projections/scores")
async def projection_scores():
    """Compute Colonial Distortion Scores for all scholarly projections."""
    polys = [
        HSPolygon("Africa", [(-20,-35),(50,-35),(50,37),(-20,37)], 30_370_000, False),
        HSPolygon("Europe", [(-10,36),(40,36),(40,71),(-10,71)], 10_180_000, True),
        HSPolygon("Asia", [(26,0),(180,0),(180,77),(26,77)], 44_579_000, True),
        HSPolygon("North America", [(-168,7),(-52,7),(-52,83),(-168,83)], 24_709_000, True),
        HSPolygon("South America", [(-82,-56),(-35,-56),(-35,13),(-82,13)], 17_840_000, False),
        HSPolygon("Australia", [(113,-44),(154,-44),(154,-10),(113,-10)], 8_600_000, True),
        HSPolygon("Greenland", [(-50,60),(-20,60),(-20,80),(-50,80)], 2_166_086, False),
        HSPolygon("Antarctica", [(-180,-90),(180,-90),(180,-60),(-180,-60)], 14_000_000, False),
    ]
    hs = HallOfShame(polys)
    scores = hs.all_scores()
    return {
        "scores": [
            {"projection": s.projection, "colonial_score": s.colonial_distortion_score,
             "max_inflation": s.max_inflation, "max_deflation": s.max_deflation,
             "note": s.note}
            for s in scores
        ],
        "note": "Strain tensor computed from projection geometry. No pre-computed areas.",
    }


# ---- Distortion Analysis endpoints (v10.5) -------------------------

@app.get("/api/distortion/global")
async def distortion_global():
    """Get the Global Distortion Index for all projections."""
    with Database() as db:
        db.cur.execute(
            "SELECT projection, global_distortion_percent, total_physical_area_m2, "
            "total_legacy_area_m2, region_count FROM global_distortion_index "
            "ORDER BY global_distortion_percent DESC"
        )
        rows = db.cur.fetchall()
    if not rows:
        raise HTTPException(404, "No distortion metrics found. Run compare_ingestion.py first.")
    return {
        "projections": [
            {
                "projection": r[0],
                "global_distortion_percent": r[1],
                "total_physical_area_m2": r[2],
                "total_legacy_area_m2": r[3],
                "region_count": r[4],
            }
            for r in rows
        ],
        "note": "Global Distortion Index = Σ|area_physical - area_legacy| / Σ area_physical × 100",
    }


@app.get("/api/distortion/region/{region_name}")
async def distortion_region(region_name: str, projection: str = Query(None)):
    """Get distortion metrics for a specific region."""
    with Database() as db:
        if projection:
            db.cur.execute(
                "SELECT region_name, projection, area_physical_m2, area_legacy_m2, "
                "absolute_error_m2, relative_error_percent, distortion_category "
                "FROM distortion_metrics WHERE region_name=%s AND projection=%s",
                (region_name, projection),
            )
        else:
            db.cur.execute(
                "SELECT region_name, projection, area_physical_m2, area_legacy_m2, "
                "absolute_error_m2, relative_error_percent, distortion_category "
                "FROM distortion_metrics WHERE region_name=%s ORDER BY relative_error_percent",
                (region_name,),
            )
        rows = db.cur.fetchall()
    if not rows:
        raise HTTPException(404, f"No metrics found for region '{region_name}'.")
    return {
        "region": region_name,
        "metrics": [
            {
                "region": r[0], "projection": r[1],
                "area_physical_m2": r[2], "area_legacy_m2": r[3],
                "absolute_error_m2": r[4], "relative_error_percent": r[5],
                "distortion_category": r[6],
            }
            for r in rows
        ],
    }


@app.get("/api/distortion/ranking")
async def distortion_ranking(
    order: str = Query("desc", regex="^(desc|asc)$"),
    projection: str = Query("Mercator"),
    limit: int = Query(20, ge=1, le=200),
):
    """Get regions ranked by relative error magnitude."""
    with Database() as db:
        db.cur.execute(
            "SELECT region_name, area_physical_m2, area_legacy_m2, "
            "absolute_error_m2, relative_error_percent, distortion_category "
            "FROM distortion_metrics WHERE projection=%s "
            "ORDER BY ABS(relative_error_percent) " + ("DESC" if order == "desc" else "ASC") + " "
            "LIMIT %s",
            (projection, limit),
        )
        rows = db.cur.fetchall()
    return {
        "projection": projection,
        "order": order,
        "ranking": [
            {
                "region": r[0],
                "area_physical_m2": r[1],
                "area_legacy_m2": r[2],
                "absolute_error_m2": r[3],
                "relative_error_percent": r[4],
                "distortion_category": r[5],
            }
            for r in rows
        ],
    }


# ---- Physical Truth Manifold endpoints (v10.6) ---------------------

@app.get("/api/solve/physical-truth")
async def solve_physical_truth():
    """Solve the Physical Truth manifold — 149 regions with real
    area-derived edge lengths. Returns intrinsic coordinates."""
    mf, area_map = await asyncio.get_event_loop().run_in_executor(
        None, solve_physical_truth_manifold
    )
    coords = {name: [p.x, p.y, p.z] for name, p in mf.coords.items()}
    # Attach area data for each region.
    regions_data = []
    for name, coord in coords.items():
        area = get_region_area(name)
        if area:
            regions_data.append({
                "name": name,
                "coords": coord,
                "area_km2": area,
            })
    return {
        "regions": regions_data,
        "node_count": len(coords),
        "edge_count": len(build_physical_truth_edge_graph()[0].edges),
        "residual": mf.residual,
        "convergence_residual": getattr(mf, "convergence_residual", None),
        "note": "Physical Truth manifold solved from area-derived edge lengths. "
                "residual = normalized SMACOF stress-1; convergence_residual = "
                "final relative stress change (solver convergence). No coordinates used.",
    }


@app.get("/api/regions/list")
async def regions_list():
    """List all Physical Truth regions with their areas."""
    return {"regions": list_regions()}


@app.get("/api/ghost/antarctica")
async def ghost_antarctica():
    """Derive Antarctica's area from global closure."""
    result = await asyncio.get_event_loop().run_in_executor(
        None, derive_antarctica_area
    )
    return result


# ---- Upload endpoint (Sub-Task 5) -----------------------------------

@app.post("/api/upload/survey")
async def upload_survey(file: UploadFile = File(...)):
    """Upload a CSV of user-supplied edge lengths (Mode A survey data).

    CSV format:
        point_A, point_B, distance_meters
        point_A, point_C, distance_meters
        ...

    The uploaded edges are solved with SMACOF and the resulting
    manifold coordinates are returned.
    """
    content = await file.read()
    csv_text = content.decode("utf-8")

    # Parse the CSV.
    from aethera.ingest.geometry import parse_survey_csv
    try:
        edges_data = parse_survey_csv(csv_text)
    except ValueError as e:
        raise HTTPException(400, f"CSV parse error: {e}")

    if len(edges_data) < 3:
        raise HTTPException(400, "Need at least 3 edges to solve a manifold.")

    # Build EdgeGraph from user data.
    graph = EdgeGraph()
    for source, target, distance in edges_data:
        graph.add_edge(source, target, Scalar(distance), source="user_survey")

    # Solve.
    geo = IntrinsicGeometer(max_iter=500, tol=1e-10)
    try:
        mf = geo.solve_2d(graph)
    except Exception as e:
        raise HTTPException(500, f"Solver failed: {e}")

    coords = {name: [p.x, p.y, p.z] for name, p in mf.coords.items()}
    return {
        "edges_uploaded": len(edges_data),
        "node_count": graph.node_count,
        "coordinates": coords,
        "residual": mf.residual,
        "note": "Manifold solved from user-uploaded survey data (Mode A). No coordinates used.",
    }


# ---- AETHERA Intrinsic Coordinate System (AICS) — Bonus ------------

@app.get("/api/aics/coordinates/{region_name}")
async def aics_coordinates(region_name: str):
    """Get the AETHERA Intrinsic Coordinate System (AICS) coordinates
    for a region.

    AICS is the platform's proprietary coordinate system. Each point
    is assigned a 3-tuple (barycentric_x, barycentric_y, scale_z)
    derived from the intrinsic manifold solve — independent of any
    external reference frame (no lat/lon, no WGS84, no ECEF).

    The coordinates are:
    - barycentric_x, barycentric_y: position in the intrinsic manifold.
    - scale_z: the area-derived scale factor (sqrt of the region's area
      in km², normalised to the global mean).

    Direction is given as the intrinsic azimuth (radians) from the
    manifold origin, and the intrinsic distance from the origin.
    """
    mf, area_map = await asyncio.get_event_loop().run_in_executor(
        None, solve_physical_truth_manifold
    )
    if region_name not in mf.coords:
        raise HTTPException(404, f"Region '{region_name}' not found in manifold.")
    p = mf.coords[region_name]
    area = get_region_area(region_name) or 0.0
    # AICS coordinates: (barycentric_x, barycentric_y, scale_z).
    scale_z = (area ** 0.5) / 1000.0  # sqrt(area) normalised
    # Intrinsic azimuth and distance from origin.
    import math
    azimuth = math.atan2(p.y, p.x)
    distance = math.sqrt(p.x**2 + p.y**2)
    return {
        "region": region_name,
        "aics_coordinates": {
            "barycentric_x": p.x,
            "barycentric_y": p.y,
            "scale_z": scale_z,
        },
        "intrinsic_direction": {
            "azimuth_rad": azimuth,
            "azimuth_deg": math.degrees(azimuth),
            "distance_from_origin": distance,
        },
        "physical_area_km2": area,
        "note": "AETHERA Intrinsic Coordinate System (AICS). No external reference frame.",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
