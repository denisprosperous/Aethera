#!/bin/bash
set -e
ROOT=/home/z/my-project/aethera-core

# ============================================================
# RUST: aethera-alien (Agent 8 — Alien Geometer)
# ============================================================

cat > $ROOT/rust/aethera-alien/Cargo.toml << 'TOML'
[package]
name = "aethera-alien"
version.workspace = true
edition.workspace = true
license.workspace = true

[lib]
name = "aethera_alien"
path = "src/lib.rs"

[dependencies]
aethera-core = { path = "../aethera-core" }
aethera-geometer = { path = "../aethera-geometer" }
rug = { workspace = true }
serde = { workspace = true }
serde_json = { workspace = true }
thiserror = { workspace = true }
tracing = { workspace = true }
TOML

cat > $ROOT/rust/aethera-alien/src/lib.rs << 'RUST'
//! Agent 8 — Alien Geometer. Topology-agnostic shape reconstruction
//! from raw LIDAR/altimetry edges. Classifies as Flat / Ellipsoidal / Potato.

use aethera_core::{EdgeGraph, Scalar};
use aethera_core::manifold::IntrinsicManifold;
use aethera_geometer::{solve_2d, solve_3d};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum ShapeClassification { Flat, Ellipsoidal, Potato, Underdetermined }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AlienReport {
    pub shape: ShapeClassification,
    pub embedding: String,
    pub residual: f64,
    pub mean_curvature: f64,
    pub max_curvature: f64,
    pub min_curvature: f64,
    pub node_count: usize,
    pub edge_count: usize,
}

pub fn analyse(graph: &EdgeGraph, max_iter: usize, tol: f64, prec: u32) -> Result<(IntrinsicManifold, AlienReport), String> {
    let m2 = match solve_2d(graph, max_iter, tol, prec) {
        Ok(m) => m,
        Err(e) => return Err(format!("2D solve failed: {e}")),
    };
    let (mf, embedding) = if m2.residual < 1e-4 { (m2, "2D".to_string()) }
    else {
        match solve_3d(graph, max_iter, tol, prec) {
            Ok(m3) if m3.residual < m2.residual => (m3, "3D".to_string()),
            _ => (m2, "2D".to_string()),
        }
    };
    let curvs: Vec<f64> = mf.gaussian_curvature.values().copied().collect();
    let shape = if mf.residual < 1e-6 { ShapeClassification::Flat }
    else if mf.residual < 1e-2 {
        if curvs.is_empty() { ShapeClassification::Ellipsoidal }
        else {
            let mean = curvs.iter().sum::<f64>() / curvs.len() as f64;
            let var = curvs.iter().map(|c| (c - mean).powi(2)).sum::<f64>() / curvs.len() as f64;
            let std = var.sqrt();
            if mean.abs() < 1e-9 || std / mean.abs().max(1e-12) < 0.3 { ShapeClassification::Ellipsoidal } else { ShapeClassification::Potato }
        }
    } else { ShapeClassification::Potato };
    let mean_c = curvs.iter().sum::<f64>() / curvs.len().max(1) as f64;
    let max_c = curvs.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    let min_c = curvs.iter().cloned().fold(f64::INFINITY, f64::min);
    Ok((mf, AlienReport {
        shape, embedding, residual: mf.residual,
        mean_curvature: mean_c, max_curvature: max_c, min_curvature: min_c,
        node_count: graph.node_count(), edge_count: graph.edge_count(),
    }))
}

pub fn safest_touchdown_ellipse(graph: &EdgeGraph, manifold: &IntrinsicManifold, radius_m: f64) -> Option<(f64, f64)> {
    if manifold.coords.is_empty() { return None; }
    let coords: Vec<(f64, f64, u64)> = manifold.coords.iter().map(|(id, p)| (p.x, p.y, *id)).collect();
    let mut best_score = f64::INFINITY; let mut best = None;
    for (i, &(x, y, _)) in coords.iter().enumerate() {
        let mut sum_dev = 0.0; let mut cnt = 0;
        for (j, &(x2, y2, _)) in coords.iter().enumerate() {
            if i == j { continue; }
            let d = ((x - x2).powi(2) + (y - y2).powi(2)).sqrt();
            if d > radius_m * 2.0 { continue; }
            sum_dev += d; cnt += 1;
        }
        if cnt == 0 { continue; }
        let score = (sum_dev / cnt as f64 - radius_m).abs();
        if score < best_score { best_score = score; best = Some((x, y)); }
    }
    best
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn classifies_flat_graph_as_flat() {
        let mut g = EdgeGraph::new();
        g.add_edge("A","B", Scalar::from_f64(1.0), None, None, None);
        g.add_edge("B","C", Scalar::from_f64(1.0), None, None, None);
        g.add_edge("C","D", Scalar::from_f64(1.0), None, None, None);
        g.add_edge("A","D", Scalar::from_f64(1.0), None, None, None);
        g.add_edge("A","C", Scalar::from_f64(1.41421356), None, None, None);
        g.add_edge("B","D", Scalar::from_f64(1.41421356), None, None, None);
        let (_, report) = analyse(&g, 1000, 1e-12, 128).unwrap();
        assert_eq!(report.shape, ShapeClassification::Flat);
    }
}
RUST

# ============================================================
# RUST: aethera-dynamics (Agent 7 — reformed, dual-mode, no targeting)
# ============================================================

cat > $ROOT/rust/aethera-dynamics/Cargo.toml << 'TOML'
[package]
name = "aethera-dynamics"
version.workspace = true
edition.workspace = true
license.workspace = true

[lib]
name = "aethera_dynamics"
path = "src/lib.rs"

[dependencies]
aethera-core = { path = "../aethera-core" }
serde = { workspace = true }
serde_json = { workspace = true }
thiserror = { workspace = true }
tracing = { workspace = true }

[dev-dependencies]
aethera-geometer = { path = "../aethera-geometer" }
TOML

cat > $ROOT/rust/aethera-dynamics/src/lib.rs << 'RUST'
//! Agent 7 — Dynamics Module (v6.0 reformulated).
//! Dual-mode: inertial geodesic + user-supplied force-field simulation.
//! The platform is a geometry provider, NOT a weapons controller.
//! No targeting outputs (azimuth, elevation, impact point).

use aethera_core::{EdgeGraph, NodeId, manifold::IntrinsicManifold};
use serde::{Deserialize, Serialize};
use thiserror::Error;

pub mod shortest_path;
pub mod integrate;

pub use shortest_path::{shortest_path, PathResult};
pub use integrate::{simulate_particle, ForceFieldConfig, SimulationResult, AccelerationField};

#[derive(Debug, Error)]
pub enum DynamicsError {
    #[error("node not found: {0}")]
    NodeNotFound(NodeId),
    #[error("start == end")]
    SameNode,
    #[error("no path {0}↔{1}")]
    NoPath(NodeId, NodeId),
    #[error("integration failed: {0}")]
    IntegrationFailed(String),
}

pub type Result<T> = std::result::Result<T, DynamicsError>;

pub const ETHICS_NOTE: &str =
    "This is a geometric simulation under user-supplied parameters. \
     Targeting solutions (azimuth, elevation, impact point) are not \
     provided. The platform is a geometry provider, not a weapons \
     controller.";
RUST

cat > $ROOT/rust/aethera-dynamics/src/shortest_path.rs << 'RUST'
//! Mode A — Inertial Geodesic (Dijkstra on the manifold).
//! Pure graph routing. Returns path length, NOT targeting data.

use crate::{DynamicsError, Result, ETHICS_NOTE};
use aethera_core::{EdgeGraph, NodeId, manifold::IntrinsicManifold};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, BTreeSet};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PathResult {
    pub path: Vec<NodeId>,
    pub path_length: f64,
    pub waypoints: Vec<(f64, f64, f64)>,
    pub note: String,
}

pub fn shortest_path(graph: &EdgeGraph, manifold: &IntrinsicManifold, start: NodeId, end: NodeId) -> Result<PathResult> {
    if start == end { return Err(DynamicsError::SameNode); }
    if !manifold.coords.contains_key(&start) { return Err(DynamicsError::NodeNotFound(start)); }
    if !manifold.coords.contains_key(&end) { return Err(DynamicsError::NodeNotFound(end)); }
    let mut adj: HashMap<NodeId, Vec<(NodeId, f64)>> = HashMap::new();
    for e in graph.edges.values() {
        let d = e.weight.to_f64();
        adj.entry(e.a).or_default().push((e.b, d));
        adj.entry(e.b).or_default().push((e.a, d));
    }
    let mut dist: HashMap<NodeId, f64> = HashMap::new();
    let mut prev: HashMap<NodeId, NodeId> = HashMap::new();
    let mut visited: BTreeSet<NodeId> = BTreeSet::new();
    dist.insert(start, 0.0);
    loop {
        let best: Option<(NodeId, f64)> = dist.iter()
            .filter(|(id, _)| !visited.contains(id))
            .min_by(|a, b| a.1.partial_cmp(b.1).unwrap_or(std::cmp::Ordering::Equal))
            .map(|(id, d)| (*id, *d));
        let (u, du) = match best { Some(x) => x, None => break };
        visited.insert(u);
        if u == end { break; }
        if let Some(neigh) = adj.get(&u) {
            for (v, w) in neigh {
                if visited.contains(v) { continue; }
                let nd = du + w;
                if nd < dist.get(v).copied().unwrap_or(f64::INFINITY) {
                    dist.insert(*v, nd);
                    prev.insert(*v, u);
                }
            }
        }
    }
    let total = dist.get(&end).copied().unwrap_or(f64::INFINITY);
    if !total.is_finite() { return Err(DynamicsError::NoPath(start, end)); }
    let mut path = vec![end]; let mut cur = end;
    while cur != start {
        match prev.get(&cur) { Some(p) => { path.push(*p); cur = *p; } None => return Err(DynamicsError::NoPath(start, end)) }
    }
    path.reverse();
    let waypoints: Vec<(f64, f64, f64)> = path.iter()
        .map(|id| manifold.coords.get(id).map(|p| (p.x, p.y, p.z)).unwrap_or((0.0, 0.0, 0.0)))
        .collect();
    Ok(PathResult {
        path, path_length: total, waypoints,
        note: format!("Inertial geodesic. Length: {:.6}. {ETHICS_NOTE}", total),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use aethera_core::Scalar;
    use aethera_geometer::solve_2d;
    fn build_graph() -> (EdgeGraph, NodeId, NodeId) {
        let mut g = EdgeGraph::new();
        g.add_edge("A","B", Scalar::from_f64(1.0), None, None, None);
        g.add_edge("B","C", Scalar::from_f64(1.0), None, None, None);
        g.add_edge("A","D", Scalar::from_f64(1.0), None, None, None);
        g.add_edge("D","E", Scalar::from_f64(1.0), None, None, None);
        g.add_edge("E","F", Scalar::from_f64(1.0), None, None, None);
        g.add_edge("F","C", Scalar::from_f64(1.0), None, None, None);
        g.add_edge("A","E", Scalar::from_f64(1.41421356), None, None, None);
        g.add_edge("B","E", Scalar::from_f64(1.0), None, None, None);
        g.add_edge("B","F", Scalar::from_f64(1.41421356), None, None, None);
        (g.clone(), g.node_id("A").unwrap(), g.node_id("C").unwrap())
    }
    #[test]
    fn finds_shortest_path() {
        let (g, a, c) = build_graph();
        let mf = solve_2d(&g, 500, 1e-10, 256).unwrap();
        let r = shortest_path(&g, &mf, a, c).unwrap();
        assert_eq!(r.path.len(), 3);
        assert!((r.path_length - 2.0).abs() < 1e-6);
        assert!(r.note.contains("Targeting solutions"));
    }
}
RUST

cat > $ROOT/rust/aethera-dynamics/src/integrate.rs << 'RUST'
//! Mode B — User-Defined Force-Field Simulation (RK4).
//! User supplies the acceleration field; platform never hardcodes G.
//! Does NOT accept 'target'; does NOT return azimuth/elevation/impact_point.

use crate::{DynamicsError, Result, ETHICS_NOTE};
use serde::{Deserialize, Serialize};

pub trait AccelerationField: Send + Sync {
    fn accel(&self, pos: (f64, f64, f64), vel: (f64, f64, f64), t: f64) -> (f64, f64, f64);
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ForceFieldConfig {
    pub dt: f64,
    pub t_max: f64,
    pub force_law_note: String,
}
impl Default for ForceFieldConfig {
    fn default() -> Self { Self { dt: 0.01, t_max: 100.0, force_law_note: "user-supplied".into() } }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SimulationResult {
    pub trajectory: Vec<(f64, f64, f64)>,
    pub times: Vec<f64>,
    pub total_path_length: f64,
    pub total_time: f64,
    pub final_position: (f64, f64, f64),
    pub final_velocity: (f64, f64, f64),
    pub note: String,
}

pub fn simulate_particle(start: (f64, f64, f64), vel0: (f64, f64, f64), field: &dyn AccelerationField, cfg: &ForceFieldConfig) -> Result<SimulationResult> {
    if cfg.dt <= 0.0 { return Err(DynamicsError::IntegrationFailed("dt must be > 0".into())); }
    if cfg.t_max <= 0.0 { return Err(DynamicsError::IntegrationFailed("t_max must be > 0".into())); }
    let mut trajectory = vec![start]; let mut times = vec![0.0];
    let mut pos = start; let mut vel = vel0; let mut t = 0.0_f64; let mut total = 0.0_f64;
    let n = (cfg.t_max / cfg.dt).ceil() as usize;
    let n = n.min(10_000_000); // AETHERA-GUARD: ALLOW DOCUMENTATION (iteration cap)
    for _ in 0..n {
        if t >= cfg.t_max - 1e-12 { break; }
        let (np, nv, nt) = rk4_step(pos, vel, t, cfg.dt, field);
        let dx = np.0 - pos.0; let dy = np.1 - pos.1; let dz = np.2 - pos.2;
        total += (dx*dx + dy*dy + dz*dz).sqrt();
        pos = np; vel = nv; t = nt;
        trajectory.push(pos); times.push(t);
        if t >= cfg.t_max { break; }
    }
    Ok(SimulationResult {
        trajectory, times, total_path_length: total, total_time: t,
        final_position: pos, final_velocity: vel,
        note: format!("Force law: {}. Path: {:.6}. Time: {:.6}s. {ETHICS_NOTE}", cfg.force_law_note, total, t),
    })
}

fn rk4_step(pos: (f64,f64,f64), vel: (f64,f64,f64), t: f64, dt: f64, field: &dyn AccelerationField) -> ((f64,f64,f64), (f64,f64,f64), f64) {
    let a1 = field.accel(pos, vel, t);
    let k1p = vel; let k1v = a1;
    let p2 = (pos.0 + 0.5*dt*k1p.0, pos.1 + 0.5*dt*k1p.1, pos.2 + 0.5*dt*k1p.2);
    let v2 = (vel.0 + 0.5*dt*k1v.0, vel.1 + 0.5*dt*k1v.1, vel.2 + 0.5*dt*k1v.2);
    let a2 = field.accel(p2, v2, t + 0.5*dt);
    let k2p = v2; let k2v = a2;
    let p3 = (pos.0 + 0.5*dt*k2p.0, pos.1 + 0.5*dt*k2p.1, pos.2 + 0.5*dt*k2p.2);
    let v3 = (vel.0 + 0.5*dt*k2v.0, vel.1 + 0.5*dt*k2v.1, vel.2 + 0.5*dt*k2v.2);
    let a3 = field.accel(p3, v3, t + 0.5*dt);
    let k3p = v3; let k3v = a3;
    let p4 = (pos.0 + dt*k3p.0, pos.1 + dt*k3p.1, pos.2 + dt*k3p.2);
    let v4 = (vel.0 + dt*k3v.0, vel.1 + dt*k3v.1, vel.2 + dt*k3v.2);
    let a4 = field.accel(p4, v4, t + dt);
    let k4p = v4; let k4v = a4;
    let np = (
        pos.0 + dt/6.0 * (k1p.0 + 2.0*k2p.0 + 2.0*k3p.0 + k4p.0),
        pos.1 + dt/6.0 * (k1p.1 + 2.0*k2p.1 + 2.0*k3p.1 + k4p.1),
        pos.2 + dt/6.0 * (k1p.2 + 2.0*k2p.2 + 2.0*k3p.2 + k4p.2),
    );
    let nv = (
        vel.0 + dt/6.0 * (k1v.0 + 2.0*k2v.0 + 2.0*k3v.0 + k4v.0),
        vel.1 + dt/6.0 * (k1v.1 + 2.0*k2v.1 + 2.0*k3v.1 + k4v.1),
        vel.2 + dt/6.0 * (k1v.2 + 2.0*k2v.2 + 2.0*k3v.2 + k4v.2),
    );
    (np, nv, t + dt)
}

// Built-in example fields (user-supplied μ, NOT hardcoded G).
pub struct InertialField;
impl AccelerationField for InertialField {
    fn accel(&self, _, _, _) -> (f64, f64, f64) { (0.0, 0.0, 0.0) }
}
pub struct InverseSquareField { pub mu: f64, pub center: (f64, f64, f64) }
impl AccelerationField for InverseSquareField {
    fn accel(&self, pos: (f64,f64,f64), _, _) -> (f64,f64,f64) {
        let dx = pos.0 - self.center.0; let dy = pos.1 - self.center.1; let dz = pos.2 - self.center.2;
        let r2 = dx*dx + dy*dy + dz*dz;
        let r = r2.sqrt().max(1e-12);
        let a = -self.mu / r2.max(1e-12);
        (a*dx/r, a*dy/r, a*dz/r)
    }
}
pub struct UniformField { pub accel: (f64, f64, f64) }
impl AccelerationField for UniformField {
    fn accel(&self, _, _, _) -> (f64, f64, f64) { self.accel }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn inertial_straight_line() {
        let r = simulate_particle((0.0,0.0,0.0), (1.0,0.0,0.0), &InertialField, &ForceFieldConfig { dt: 0.1, t_max: 10.0, force_law_note: "inertial".into() }).unwrap();
        assert!((r.final_position.0 - 10.0).abs() < 1e-3);
        assert!(r.note.contains("Targeting solutions"));
    }
    #[test]
    fn inverse_square_orbit() {
        let f = InverseSquareField { mu: 1.0, center: (0.0,0.0,0.0) };
        let r = simulate_particle((1.0,0.0,0.0), (0.0,1.0,0.0), &f, &ForceFieldConfig { dt: 0.001, t_max: 6.2832, force_law_note: "inverse-square".into() }).unwrap();
        assert!((r.final_position.0 - 1.0).abs() < 0.05);
    }
    #[test]
    fn uniform_field_parabola() {
        let f = UniformField { accel: (0.0, -1.0, 0.0) };
        let r = simulate_particle((0.0,0.0,0.0), (1.0,0.0,0.0), &f, &ForceFieldConfig { dt: 0.01, t_max: 2.0, force_law_note: "uniform".into() }).unwrap();
        assert!((r.final_position.0 - 2.0).abs() < 1e-3);
        assert!((r.final_position.1 - (-2.0)).abs() < 1e-3);
    }
}
RUST

# ============================================================
# RUST: aethera-ffi (PyO3 bindings — minimal, optional)
# ============================================================

cat > $ROOT/rust/aethera-ffi/Cargo.toml << 'TOML'
[package]
name = "aethera-ffi"
version.workspace = true
edition.workspace = true
license.workspace = true

[lib]
name = "aethera_ffi"
path = "src/lib.rs"
crate-type = ["cdylib", "rlib"]

[dependencies]
aethera-core = { path = "../aethera-core" }
aethera-ghost = { path = "../aethera-ghost" }
aethera-geometer = { path = "../aethera-geometer" }
aethera-acif = { path = "../aethera-acif" }
aethera-alien = { path = "../aethera-alien" }
pyo3 = { workspace = true }
serde = { workspace = true }
serde_json = { workspace = true }
TOML

cat > $ROOT/rust/aethera-ffi/src/lib.rs << 'RUST'
//! Python bindings for AETHERA's Rust core. Exposed as `aethera._rust`.
//! The Python layer uses this if available, else falls back to pure Python.

use aethera_core::{EdgeGraph, Scalar};
use pyo3::prelude::*;

#[derive(serde::Deserialize)]
struct EdgeSpec { a: String, b: String, weight: f64, sigma: Option<f64>, source: Option<String>, epoch: Option<f64> }

#[pyfunction]
fn solve_intrinsic_2d(edges_json: &str, max_iter: usize, tol: f64, prec: u32) -> pyo3::PyResult<String> {
    let edges: Vec<EdgeSpec> = serde_json::from_str(edges_json).map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("bad edges: {e}")))?;
    let mut g = EdgeGraph::new();
    for e in &edges { g.add_edge(&e.a, &e.b, Scalar::from_f64(e.weight), e.sigma.map(Scalar::from_f64), e.source.clone(), e.epoch); }
    let mf = aethera_geometer::solve_2d(&g, max_iter, tol, prec).map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("solver: {e}")))?;
    Ok(mf.to_json().map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("serialise: {e}")))?)
}

#[pymodule]
fn _rust(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(solve_intrinsic_2d, m)?)?;
    Ok(())
}
RUST

echo "alien + dynamics + ffi written"
