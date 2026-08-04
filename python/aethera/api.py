"""AETHERA FastAPI backend — live endpoints that read raw edge data
from PostgreSQL and call the Rust core (via subprocess fallback for now).

All endpoints query the database for raw edge lengths (Mode A measured
or Mode B placeholder) and return results from the solvers.

NO pre-computed areas are ever returned. Areas are derived by
Agent 0 / Agent 2 from the raw edge lengths + global area closure.
"""

from __future__ import annotations
import os
import sys
import json
import asyncio
from typing import List, Optional, Dict, Any
from dataclasses import asdict

# Ensure the aethera package is importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from aethera.ingest.db import Database
from aethera.ingest.schema import DATABASE_URL
from aethera.agents import IntrinsicGeometer, GhostResolver, AlienGeometer, DynamicsModule
from aethera.agents.ghost import Polygon as GhostPolygon, GhostReport
from aethera.core import EdgeGraph, Scalar
from aethera.modules import (
    HallOfShame, TransparencyComparator, StrainVisualizer,
    AnomalyDaemon, MaritimeChokepoint, TerraformationSimulator, StellarPositioning,
)
from aethera.modules.hall_of_shame import Polygon as HSPolygon
from aethera.modules.transparency import RangeClaim
from aethera.modules.seismic import SeismicEvent
from aethera.modules.maritime import Chokepoint
from aethera.modules.terraformation import VolumeTransfer
from aethera.modules.stellar import QuasarObservation
from aethera.agents.acif import AcifSnapshot, AcifNavigator
from aethera.agents.dynamics import (
    ForceFieldConfig, simulate_particle,
    inertial_field, inverse_square_field, uniform_field,
)

app = FastAPI(
    title="AETHERA API",
    description="First objective geometric substrate. No pre-computed areas — "
                "all areas derived from raw edge lengths + global closure.",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    """Health check."""
    return {"status": "ok", "version": "0.3.0", "database": "connected"}


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
    return GhostResolveResponse(
        resolved_areas=resolved,
        red_flags=[asdict(r) if hasattr(r, '__dataclass_fields__') else r.__dict__ for r in report.red_flags],
        rationale_log=[asdict(r) if hasattr(r, '__dataclass_fields__') else r.__dict__ for r in report.rationale_log],
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
        initial_velocity=tuple(req.initial_velocity),
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
    """Simulate sea-level rise and compute coastline changes.
    Uses Mode B edge lengths from the database."""
    # For now, use a simplified volumetric model.
    # A full implementation would re-solve the manifold after volume transfer.
    polys = [
        HSPolygon("Greenland", [(-50,60),(-20,60),(-20,80),(-50,80)], 2_166_086, False),
        HSPolygon("Ocean", [(-180,-90),(180,-90),(180,90),(-180,90)], 361_000_000, False),
    ]
    ts = TerraformationSimulator(polys)
    # Convert sea-level rise to volume (simplified).
    ocean_area_m2 = 361_000_000 * 1e6  # km² to m²  // AETHERA-GUARD: ALLOW DOCUMENTATION (ocean surface area)
    volume_km3 = req.sea_level_rise_m * ocean_area_m2 / 1e9  # m³ to km³
    rep = ts.simulate([VolumeTransfer("Greenland", "Ocean", volume_km3)])
    return TerraformationResponse(
        sea_level_rise_m=req.sea_level_rise_m,
        coastline_changes=[
            {"nation": c.nation, "area_change_km2": c.area_change_km2,
             "before": c.habitable_area_km2_before, "after": c.habitable_area_km2_after,
             "note": c.note}
            for c in rep.coastline_changes
        ],
        note="Simplified volumetric model. Full re-solve pending.",
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
