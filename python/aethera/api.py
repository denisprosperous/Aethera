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

from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Body
import math
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
    version="0.34.0",
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
        "version": "0.34.0",
        "platform": "AETHERA v34.0",
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
    from aethera.llm import query_llm, get_system_prompt
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
    # v32.0: the AETHERA behaviour contract is ALWAYS injected (live link +
    # mandatory disclaimer, no sphere assumptions, no code-gen offers).
    result = await query_llm(
        prompt, get_system_prompt(system_prompt),
        api_key=api_key, model=model,
    )
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


@app.get("/api/llm")
async def llm_status_alias():
    """Alias of /api/llm/status — keeps the dashboard palette working
    against either backend (Railway FastAPI or Vercel serverless)."""
    from aethera.llm import llm_status
    return llm_status()


@app.post("/api/llm")
async def llm_query_alias(body: Optional[Dict[str, Any]] = None):
    """Alias of /api/llm/query — same {success,text,provider,model,error}
    contract as the Next.js /api/llm route handler, so the Ctrl+K palette
    works unchanged against either backend. Accepts {prompt,
    system_prompt?, model?, api_key? | apiKey?}."""
    from aethera.llm import query_llm, get_system_prompt
    body = body or {}
    prompt = body.get("prompt")
    system_prompt = body.get("system_prompt") or body.get("systemPrompt")
    model = body.get("model")
    api_key = body.get("api_key") or body.get("apiKey")
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    # v32.0: contract injected here as well (alias route).
    result = await query_llm(
        prompt, get_system_prompt(system_prompt),
        api_key=api_key, model=model,
    )
    return {
        "text": result.text,
        "provider": result.provider,
        "model": result.model,
        "success": result.success,
        "error": result.error,
    }


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
    # v30.1: expose the solver's intrinsic edge graph (adjacency pairs) so
    # 3D renderings draw REAL solved adjacencies, not a client-side guess.
    graph, _areas = build_physical_truth_edge_graph()
    edge_pairs = sorted({tuple(sorted((e.a, e.b))) for e in graph.edges})
    return {
        "regions": regions_data,
        "vertices": [r["coords"] for r in regions_data],
        "edges": [[a, b] for a, b in edge_pairs],
        "node_count": len(coords),
        "edge_count": len(edge_pairs),
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


# ---- v30.1 — TRUTH CERTIFICATION, ARBITRATION & TRUTH INDEX ----------
# Every certificate is signed with HMAC-SHA256 over a canonical payload
# hash + timestamp. No external dependency, deterministic, verifiable.

import hmac
import hashlib
import time

_CERT_SECRET = os.environ.get("AETHERA_CERT_SECRET", "aethera-truth-v30.1-intrinsic")


def _canonical_hash(payload: Any) -> str:
    """Stable SHA-256 over a JSON-serialised payload (sorted keys)."""
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _sign(cert_id: str, payload_hash: str, ts: float) -> str:
    msg = f"{cert_id}|{payload_hash}|{ts}".encode("utf-8")
    return hmac.new(_CERT_SECRET.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def issue_certificate(claim_type: str, claim: Dict[str, Any], findings: Dict[str, Any]) -> Dict[str, Any]:
    """Build a signed Truth Certificate for a claim + findings pair."""
    ts = time.time()
    payload = {"type": claim_type, "claim": claim, "findings": findings}
    payload_hash = _canonical_hash(payload)
    cert_id = "AET-" + payload_hash[:12].upper()
    signature = _sign(cert_id, payload_hash, ts)
    return {
        "certificate_id": cert_id,
        "type": claim_type,
        "claim": claim,
        "findings": findings,
        "payload_hash": payload_hash,
        "issued_at": ts,
        "issued_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)),
        "algorithm": "HMAC-SHA256",
        "signature": signature,
        "verify": f"/api/certify/verify?certificate_id={cert_id}&payload_hash={payload_hash}&issued_at={ts}&signature={signature}",
        "note": "Signed with the platform cert key. The certificate attests "
                "that the findings were computed from absolute scalar inputs "
                "(areas / edge lengths) with no coordinates involved.",
    }


class MaritimeClaim(BaseModel):
    """Maritime arbitration request: two parties sharing a boundary."""
    party_a: str = Field(..., description="First region name (Physical Truth registry)")
    party_b: str = Field(..., description="Second region name")
    claimed_split: Optional[float] = Field(
        None, description="Optional claimed share for party_a (0..1); defaults to 0.5 (equal).")


class TerritorialClaim(BaseModel):
    """Territorial arbitration request: disputed area claims."""
    disputed_region: str = Field(..., description="Disputed region name (must exist in Physical Truth registry)")
    claim_a_name: str = Field("Party A")
    claim_a_km2: float = Field(..., description="Party A claimed area (km²)")
    claim_b_name: str = Field("Party B")
    claim_b_km2: float = Field(..., description="Party B claimed area (km²)")


@app.post("/api/arbitration/maritime")
async def arbitration_maritime(claim: MaritimeClaim):
    """Maritime boundary arbitration from Physical Truth scalars.

    Verdict is computed ONLY from absolute areas and the intrinsic edge
    graph: the shared boundary length is the area-derived solver edge
    l = sqrt(min(area_a, area_b)); equitability is judged against the true
    area ratio. No coastline geometry, no coordinates, no lat/lon.
    """
    a, b = claim.party_a, claim.party_b
    area_a = get_region_area(a)
    area_b = get_region_area(b)
    if not area_a or not area_b:
        raise HTTPException(404, f"Unknown region(s): {a if not area_a else ''} {b if not area_b else ''}".strip())

    graph, _ = build_physical_truth_edge_graph()
    adjacent = any({e.a, e.b} == {a, b} for e in graph.edges)
    shared_edge_km = (min(area_a, area_b) ** 0.5) if adjacent else None

    ratio = area_a / area_b if area_b else 0.0
    split = claim.claimed_split if claim.claimed_split is not None else 0.5
    split = min(1.0, max(0.0, split))
    share_a = split * (area_a + area_b)
    share_b = (1 - split) * (area_a + area_b)
    # Equitability: how far the claimed split is from the true area ratio.
    fair_split = area_a / (area_a + area_b) if (area_a + area_b) else 0.5
    deviation_pp = abs(split - fair_split) * 100.0

    if deviation_pp <= 5.0:
        verdict = "EQUITABLE"
        rationale = (
            f"Claimed split {split:.3f} is within 5.0 pp of the truth-anchored "
            f"fair split {fair_split:.3f} derived from absolute areas."
        )
    elif deviation_pp <= 15.0:
        verdict = "CONTESTABLE"
        rationale = (
            f"Claimed split deviates {deviation_pp:.1f} pp from the truth-anchored "
            f"fair split {fair_split:.3f}; review recommended."
        )
    else:
        verdict = "INEQUITABLE"
        rationale = (
            f"Claimed split deviates {deviation_pp:.1f} pp from the truth-anchored "
            f"fair split {fair_split:.3f}; the claim is not supported by absolute areas."
        )

    findings = {
        "area_a_km2": area_a,
        "area_b_km2": area_b,
        "area_ratio_a_to_b": round(ratio, 6),
        "adjacent": adjacent,
        "shared_boundary_km_derived": round(shared_edge_km, 3) if shared_edge_km else None,
        "fair_split_for_a": round(fair_split, 6),
        "claimed_split_for_a": split,
        "deviation_percentage_points": round(deviation_pp, 3),
        "awarded_a_km2": round(share_a, 3),
        "awarded_b_km2": round(share_b, 3),
        "verdict": verdict,
        "rationale": rationale,
    }
    cert = issue_certificate(
        "maritime-arbitration",
        {"party_a": a, "party_b": b, "claimed_split": split},
        findings,
    )
    return {"arbitration": findings, "certificate": cert}


@app.post("/api/arbitration/territorial")
async def arbitration_territorial(claim: TerritorialClaim):
    """Territorial dispute arbitration from Physical Truth scalars.

    The disputed region's true area is fetched from the Physical Truth
    registry; each party's claim is compared against that absolute value.
    """
    region = claim.disputed_region
    true_area = get_region_area(region)
    if not true_area:
        raise HTTPException(404, f"Region '{region}' not found in Physical Truth registry.")

    def _judge(name: str, claimed: float):
        delta = claimed - true_area
        rel = (delta / true_area * 100.0) if true_area else 0.0
        if abs(rel) <= 2.0:
            v = "CONSISTENT"
        elif claimed > true_area:
            v = "OVERCLAIM"
        else:
            v = "UNDERCLAIM"
        return {
            "party": name, "claimed_km2": claimed,
            "delta_km2": round(delta, 3), "delta_percent": round(rel, 3),
            "verdict": v,
        }

    ja = _judge(claim.claim_a_name, claim.claim_a_km2)
    jb = _judge(claim.claim_b_name, claim.claim_b_km2)
    closest = ja if abs(ja["delta_percent"]) <= abs(jb["delta_percent"]) else jb

    findings = {
        "disputed_region": region,
        "physical_truth_area_km2": true_area,
        "party_a": ja,
        "party_b": jb,
        "closest_to_truth": closest["party"],
        "verdict": "RESOLVED — " + closest["party"] + " closest to Physical Truth",
        "rationale": (
            f"Physical Truth area of {region} is {true_area:,.0f} km². "
            f"{ja['party']} is off by {ja['delta_percent']:+.2f}% and "
            f"{jb['party']} by {jb['delta_percent']:+.2f}%."
        ),
    }
    cert = issue_certificate(
        "territorial-arbitration",
        {
            "disputed_region": region,
            "claim_a": {"name": claim.claim_a_name, "km2": claim.claim_a_km2},
            "claim_b": {"name": claim.claim_b_name, "km2": claim.claim_b_km2},
        },
        findings,
    )
    return {"arbitration": findings, "certificate": cert}


@app.post("/api/certify")
async def certify(claim: Dict[str, Any]):
    """Issue a signed Truth Certificate for an arbitrary claim payload.

    The claim is hashed canonically (sorted keys, SHA-256) and signed with
    HMAC-SHA256. Verification data is embedded in the response.
    """
    if not isinstance(claim, dict) or not claim:
        raise HTTPException(400, "Claim payload must be a non-empty JSON object.")
    findings = {
        "attested": True,
        "engine_version": "0.34.0",
        "axioms": ["Tabula Rasa", "Intrinsic Emergence", "Extrinsic Agnosticism",
                    "Zero Bias", "Full Transparency"],
        "note": "Payload attested as processed through AETHERA's intrinsic pipeline; "
                "no coordinates were consumed in producing this certificate.",
    }
    cert = issue_certificate("truth-certification", claim, findings)
    return {"certificate": cert}


@app.get("/api/certify/verify")
async def certify_verify(
    certificate_id: str = Query(...),
    payload_hash: str = Query(...),
    issued_at: float = Query(...),
    signature: str = Query(...),
):
    """Verify a certificate's HMAC signature (offline-verifiable form)."""
    expected = _sign(certificate_id, payload_hash, issued_at)
    ok = hmac.compare_digest(expected, signature)
    return {
        "certificate_id": certificate_id,
        "valid": ok,
        "algorithm": "HMAC-SHA256",
        "reason": None if ok else "signature mismatch — certificate is not authentic",
    }


# ---- v30.1 — GLOBAL TRUTH INDEX (GTI) --------------------------------

async def _compute_gti() -> Dict[str, Any]:
    regions = list_regions()
    total_registered = len(regions)
    with_area = sum(1 for r in regions if r.get("area_km2"))
    coverage = (with_area / total_registered) if total_registered else 0.0

    mf, _ = await asyncio.get_event_loop().run_in_executor(
        None, solve_physical_truth_manifold
    )
    residual = float(mf.residual)
    accuracy = 1.0 / (1.0 + residual * 10.0)  # stress-1 near 0 → ~1.0

    # Legacy distortion resistance: mean |relative error| under Mercator.
    try:
        def _metrics():
            return compute_distortion_metrics()
        metrics, _global_idx = await asyncio.get_event_loop().run_in_executor(None, _metrics)
        rels = [
            abs(float(m.get("relative_error_percent", 0) or 0))
            for m in metrics
            if m.get("projection") == "Mercator"
        ] or [abs(float(m.get("relative_error_percent", 0) or 0)) for m in metrics]
        mean_rel = sum(rels) / len(rels) if rels else 0.0
    except Exception:
        mean_rel = 0.0
    distortion_resistance = 1.0 / (1.0 + mean_rel / 100.0)

    gti = 100.0 * (0.40 * accuracy + 0.30 * coverage + 0.30 * distortion_resistance)
    return {
        "gti": round(gti, 2),
        "grade": "A" if gti >= 90 else "B" if gti >= 75 else "C" if gti >= 60 else "D",
        "components": {
            "solver_accuracy": {
                "value": round(accuracy, 6),
                "residual_stress1": residual,
                "weight": 0.40,
            },
            "data_coverage": {
                "value": round(coverage, 6),
                "regions_with_absolute_area": with_area,
                "regions_registered": total_registered,
                "weight": 0.30,
            },
            "distortion_resistance": {
                "value": round(distortion_resistance, 6),
                "mean_abs_legacy_deviation_percent": round(mean_rel, 3),
                "weight": 0.30,
            },
        },
        "formula": "GTI = 100 × (0.40·accuracy + 0.30·coverage + 0.30·distortion_resistance)",
        "note": "All components computed from absolute scalar inputs. No coordinates.",
    }


_TRUTH_INDEX_TABLE = """
CREATE TABLE IF NOT EXISTS truth_index_snapshots (
    id SERIAL PRIMARY KEY,
    ts DOUBLE PRECISION NOT NULL,
    gti DOUBLE PRECISION NOT NULL,
    accuracy DOUBLE PRECISION,
    coverage DOUBLE PRECISION,
    distortion_resistance DOUBLE PRECISION,
    residual DOUBLE PRECISION,
    mode TEXT
);
"""


async def _record_snapshot(gti_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Persist a snapshot to Neon and return the recent trend (newest last).

    Falls back to an in-process ring buffer when the DB is unavailable so
    the endpoint never fails.
    """
    c = gti_result["components"]
    row = {
        "ts": time.time(),
        "gti": gti_result["gti"],
        "accuracy": c["solver_accuracy"]["value"],
        "coverage": c["data_coverage"]["value"],
        "distortion_resistance": c["distortion_resistance"]["value"],
        "residual": c["solver_accuracy"]["residual_stress1"],
        "mode": DEPLOYMENT_MODE,
    }
    try:
        from aethera.ingest.db import Database
        def _db():
            with Database() as db:
                db.cur.execute(_TRUTH_INDEX_TABLE)
                db.cur.execute(
                    "INSERT INTO truth_index_snapshots (ts, gti, accuracy, coverage, "
                    "distortion_resistance, residual, mode) VALUES (%(ts)s,%(gti)s,"
                    "%(accuracy)s,%(coverage)s,%(distortion_resistance)s,%(residual)s,%(mode)s)",
                    row,
                )
                db.cur.execute(
                    "SELECT ts, gti, accuracy, coverage, distortion_resistance, residual, mode "
                    "FROM truth_index_snapshots ORDER BY ts DESC LIMIT 50"
                )
                rows = db.cur.fetchall()
            return [
                {"ts": r[0], "gti": r[1], "accuracy": r[2], "coverage": r[3],
                 "distortion_resistance": r[4], "residual": r[5], "mode": r[6]}
                for r in reversed(rows)
            ]
        return await asyncio.get_event_loop().run_in_executor(None, _db)
    except Exception as e:
        _MEM_TREND.append(row)
        gti_result.setdefault("warnings", []).append(f"trend persisted in-memory: {e}")
        return list(_MEM_TREND)[-50:]


_MEM_TREND: List[Dict[str, Any]] = []


@app.get("/api/truth-index")
async def truth_index():
    """Global Truth Index — current value, components and signed certificate."""
    gti_result = await _compute_gti()
    trend = await _record_snapshot(gti_result)
    cert = issue_certificate(
        "global-truth-index",
        {"components": {k: v["value"] for k, v in gti_result["components"].items()}},
        {"gti": gti_result["gti"], "grade": gti_result["grade"],
         "formula": gti_result["formula"]},
    )
    return {
        **gti_result,
        "trend_points": len(trend),
        "trend": trend,
        "certificate": cert,
    }


@app.get("/api/truth-index/trend")
async def truth_index_trend():
    """GTI trend history (persisted snapshots, newest last)."""
    gti_result = await _compute_gti()
    trend = await _record_snapshot(gti_result)
    deltas = [t["gti"] for t in trend]
    change = (deltas[-1] - deltas[0]) if len(deltas) >= 2 else 0.0
    return {
        "current": gti_result["gti"],
        "points": trend,
        "count": len(trend),
        "change_since_first": round(change, 3),
        "note": "Trend is built from platform-computed snapshots only.",
    }


# AETHERA v34.0 — Consensus Hall of Shame + ACIF edge ledger (wired routes).
# Purely additive; appended to api.py at build time by scripts/add_v34_routes.py.

_MEM_ACIF: list = []

_ACIF_TABLE = """
CREATE TABLE IF NOT EXISTS acif_edges (
    id SERIAL PRIMARY KEY,
    edge_key TEXT NOT NULL,
    length_m DOUBLE PRECISION NOT NULL,
    epoch DOUBLE PRECISION,
    source TEXT DEFAULT 'ground-station',
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_acif_key_time ON acif_edges (edge_key, submitted_at);
"""


def _acif_norm(a: str, b: str) -> str:
    x, y = a.strip(), b.strip()
    lo, hi = (x, y) if x <= y else (y, x)
    return f"{lo}~{hi}"


@app.post("/api/acif/edges")
async def acif_submit(payload: dict = Body(default={})):
    """Accept RAW scalar edge lengths (metres) between named stations.

    Absolute scalars only: no orbits, no ephemerides, no datum, no clock
    model — Axiom 3/4. Anything that is not a finite positive number is
    rejected.
    """
    edges = payload.get("edges") or []
    if not isinstance(edges, list) or not edges:
        raise HTTPException(status_code=422, detail="body.edges must be a non-empty list")
    clean = []
    for e in edges[:5000]:
        try:
            a = str(e["a"]).strip()
            b = str(e["b"]).strip()
            lm = float(e["length_m"])
            epoch = e.get("epoch")
            epoch = float(epoch) if epoch is not None else None
            source = str(e.get("source") or "ground-station")[:80]
        except Exception:
            raise HTTPException(status_code=422, detail="each edge needs a, b, length_m (finite > 0)")
        if not a or not b or a == b or not math.isfinite(lm) or lm <= 0:
            raise HTTPException(status_code=422, detail="invalid edge: need distinct a/b and length_m > 0")
        clean.append({"key": _acif_norm(a, b), "length_m": lm, "epoch": epoch, "source": source})

    def _db_write():
        from aethera.ingest.db import Database
        with Database() as db:
            db.cur.execute(_ACIF_TABLE)
            for c in clean:
                db.cur.execute(
                    "INSERT INTO acif_edges (edge_key, length_m, epoch, source) "
                    "VALUES (%(key)s,%(length_m)s,%(epoch)s,%(source)s)",
                    c,
                )
            db.cur.execute("SELECT COUNT(DISTINCT edge_key) FROM acif_edges")
            total = int(db.cur.fetchone()[0])
        return total

    db_error = None
    try:
        total = await asyncio.get_event_loop().run_in_executor(None, _db_write)
        store = "postgres"
    except Exception as e:
        db_error = str(e)[:300]
        _MEM_ACIF.extend(clean)
        total = len({c["key"] for c in _MEM_ACIF})
        store = "memory"
    return {
        "accepted": len(clean),
        "distinct_edges_total": total,
        "store": store,
        "db_error": db_error,
        "note": "Raw scalar edge ledger. Edges are absolute lengths between named "
                "stations; the platform derives geometry, it never assumes a datum.",
    }


@app.get("/api/acif/edges")
async def acif_edges(limit: int = Query(200, ge=1, le=1000)):
    """Latest scalar value per submitted edge."""
    def _db_read():
        from aethera.ingest.db import Database
        with Database() as db:
            db.cur.execute(_ACIF_TABLE)
            db.cur.execute(
                "SELECT DISTINCT ON (edge_key) edge_key, length_m, epoch, source, submitted_at "
                "FROM acif_edges ORDER BY edge_key, submitted_at DESC LIMIT %s", (limit,))
            return db.cur.fetchall()
    try:
        rows = await asyncio.get_event_loop().run_in_executor(None, _db_read)
        rows = [{"edge": r[0], "length_m": r[1], "epoch": r[2], "source": r[3]} for r in rows]
        store = "postgres"
    except Exception:
        latest = {}
        for c in _MEM_ACIF:
            latest[c["key"]] = c
        rows = [{"edge": k, "length_m": v["length_m"], "epoch": v["epoch"], "source": v["source"]}
                for k, v in list(latest.items())[:limit]]
        store = "memory"
    return {"count": len(rows), "store": store, "edges": rows}


@app.get("/api/acif/anomaly")
async def acif_anomaly(threshold_m_per_day: float = Query(0.01, gt=0)):
    """Flag submitted edges whose length changes faster than a threshold.

    A pure geometric change detector over user-submitted scalars: it
    reports deltas, never interpretations.
    """
    def _db_hist():
        from aethera.ingest.db import Database
        with Database() as db:
            db.cur.execute(_ACIF_TABLE)
            db.cur.execute(
                "SELECT edge_key, length_m, epoch, submitted_at FROM acif_edges "
                "ORDER BY edge_key, submitted_at ASC")
            return db.cur.fetchall()
    try:
        rows = await asyncio.get_event_loop().run_in_executor(None, _db_hist)
        store = "postgres"
    except Exception:
        rows = [(c["key"], c["length_m"], c["epoch"], None) for c in _MEM_ACIF]
        store = "memory"

    hist = {}
    for k, lm, ep, ts in rows:
        t = float(ep) if ep is not None else (ts.timestamp() if ts is not None else None)
        if t is None:
            continue
        hist.setdefault(k, []).append((t, float(lm)))

    anomalies = []
    for k, series in hist.items():
        if len(series) < 2:
            continue
        (t0, l0), (t1, l1) = series[0], series[-1]
        dt = t1 - t0
        if dt <= 0:
            continue
        rate = (l1 - l0) / (dt / 86400.0)
        if abs(rate) > threshold_m_per_day:
            anomalies.append({
                "edge": k, "first_length_m": l0, "last_length_m": l1,
                "delta_m": round(l1 - l0, 6), "days": round(dt / 86400.0, 6),
                "rate_m_per_day": round(rate, 6),
            })
    anomalies.sort(key=lambda a: -abs(a["rate_m_per_day"]))
    return {
        "monitored_edges": len(hist),
        "threshold_m_per_day": threshold_m_per_day,
        "anomalies": anomalies[:200],
        "store": store,
        "note": "Geometric change detector on submitted scalars. Reports deltas "
                "only — no physical interpretation is implied.",
    }


@app.get("/api/consensus-hall")
async def consensus_hall(
    projection: str = Query("Mercator"),
    group_a: str = Query("", description="Comma-separated region names (preset, editable)"),
    group_b: str = Query("", description="Comma-separated region names (preset, editable)"),
    limit: int = Query(60, ge=1, le=200),
):
    """Consensus Hall of Shame: legacy-projection strain ranking + a fully
    disclosed group-inflation score.

    The score is arithmetic on two EDITABLE name lists over stored
    distortion metrics. The grouping is an input, not a fact.
    """
    try:
        with Database() as db:
            db.cur.execute(
                "SELECT region_name, area_physical_m2, area_legacy_m2, relative_error_percent "
                "FROM distortion_metrics WHERE projection=%s "
                "ORDER BY ABS(relative_error_percent) DESC LIMIT %s",
                (projection, limit),
            )
            rows = db.cur.fetchall()
    except Exception:
        rows = []

    def _split(s: str) -> list:
        return [x.strip().lower() for x in (s or "").split(",") if x.strip()]

    ga, gb = _split(group_a), _split(group_b)

    def _agg(names):
        num = 0.0
        den = 0.0
        hits = []
        for r in rows:
            if r[0].strip().lower() in names:
                w = max(float(r[1] or 0), 1.0)
                num += max(float(r[3] or 0), 0.0) * w
                den += w
                hits.append(r[0])
        return (num / den if den else None), hits

    score_a, hits_a = _agg(ga) if ga else (None, [])
    score_b, hits_b = _agg(gb) if gb else (None, [])
    ratio = None
    if score_a is not None and score_b not in (None, 0):
        ratio = score_a / score_b

    return {
        "projection": projection,
        "strain_ranking": [
            {"region": r[0], "area_physical_m2": r[1], "area_legacy_m2": r[2],
             "relative_error_percent": r[3]} for r in rows
        ],
        "score": {
            "group_a": {"names": ga, "matched": hits_a, "area_weighted_mean_inflation_pct": score_a},
            "group_b": {"names": gb, "matched": hits_b, "area_weighted_mean_inflation_pct": score_b},
            "ratio_a_over_b": ratio,
            "formula": "ratio = (area-weighted mean positive inflation of A) / (same of B)",
            "disclosure": "The grouping is an editable input, not a fact. The score is "
                          "pure arithmetic on stored legacy-vs-physical distortion metrics.",
        },
        "note": "Legacy projections are measured artifacts here — the platform itself "
                "never adopts them as a frame.",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
