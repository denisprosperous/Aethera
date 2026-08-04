//! Agent 2 — Intrinsic Geometer. Weighted SMACOF via the exact
//! pseudoinverse V⁺ = (V + (1/n)J)⁻¹ − (1/n)J, with classical-MDS
//! warm start and discrete Gaussian curvature.

use aethera_core::{EdgeGraph, NodeId, Scalar};
use aethera_core::manifold::{IntrinsicManifold, Point3, Embedding};
use aethera_core::errors::{AetheraError, Result};
use std::collections::BTreeMap;
use rug::Float;
use rayon::prelude::*;

pub mod smacof;
pub mod curvature;
pub mod lm;

pub use smacof::{smacof_2d, smacof_3d};

pub fn solve_2d(graph: &EdgeGraph, max_iter: usize, tol: f64, prec: u32) -> Result<IntrinsicManifold> {
    let nodes: Vec<NodeId> = graph.nodes.keys().copied().collect();
    let n = nodes.len();
    if n < 3 { return Err(AetheraError::InvalidInput(format!("need >= 3 nodes, got {n}"))); }
    if graph.edge_count() < 2 * n - 3 {
        return Err(AetheraError::Underconstrained(n, graph.edge_count()));
    }
    let idx: BTreeMap<NodeId, usize> = nodes.iter().enumerate().map(|(i, &id)| (id, i)).collect();
    let mut delta = vec![vec![Float::new(prec); n]; n];
    let mut weight = vec![vec![Float::new(prec); n]; n];
    for e in graph.edges.values() {
        let i = idx[&e.a]; let j = idx[&e.b];
        let d = e.weight.raw().clone();
        delta[i][j] = d.clone(); delta[j][i] = d;
        let w = match &e.sigma {
            Some(s) => { let s2 = s.raw().clone() * s.raw().clone(); if s2.to_f64() > 0.0 { Float::with_val(prec, 1) / s2 } else { Float::with_val(prec, 1) } }
            None => Float::with_val(prec, 1),
        };
        weight[i][j] = w.clone(); weight[j][i] = w;
    }
    let (coords, stress) = smacof_2d(&nodes, &delta, &weight, max_iter, tol, prec)?;
    let mut coords_map = BTreeMap::new();
    for (i, &id) in nodes.iter().enumerate() {
        coords_map.insert(id, Point3::new(coords[i].0, coords[i].1, 0.0));
    }
    let mut mf = IntrinsicManifold::new_2d(coords_map, stress, "Agent 2 — Intrinsic Geometer");
    let curv = curvature::discrete_gaussian_curvature(graph, &mf.coords);
    mf.gaussian_curvature = curv;
    Ok(mf)
}

pub fn solve_3d(graph: &EdgeGraph, max_iter: usize, tol: f64, prec: u32) -> Result<IntrinsicManifold> {
    let nodes: Vec<NodeId> = graph.nodes.keys().copied().collect();
    let n = nodes.len();
    if n < 4 { return Err(AetheraError::InvalidInput(format!("need >= 4 nodes for 3D, got {n}"))); }
    let idx: BTreeMap<NodeId, usize> = nodes.iter().enumerate().map(|(i, &id)| (id, i)).collect();
    let mut delta = vec![vec![Float::new(prec); n]; n];
    let mut weight = vec![vec![Float::new(prec); n]; n];
    for e in graph.edges.values() {
        let i = idx[&e.a]; let j = idx[&e.b];
        let d = e.weight.raw().clone();
        delta[i][j] = d.clone(); delta[j][i] = d;
        weight[i][j] = Float::with_val(prec, 1); weight[j][i] = Float::with_val(prec, 1);
    }
    let (coords, stress) = smacof_3d(&nodes, &delta, &weight, max_iter, tol, prec)?;
    let coords_map: BTreeMap<NodeId, Point3> = nodes.iter().enumerate()
        .map(|(i, &id)| (id, Point3::new(coords[i].0, coords[i].1, coords[i].2))).collect();
    let mut mf = IntrinsicManifold {
        embedding: Embedding::Spatial3D, coords: coords_map, residual: stress,
        gaussian_curvature: BTreeMap::new(), origin: "Agent 2 — Intrinsic Geometer (3D)".into(),
    };
    let curv = curvature::discrete_gaussian_curvature(graph, &mf.coords);
    mf.gaussian_curvature = curv;
    Ok(mf)
}

pub fn reconstruction_error(graph: &EdgeGraph, mf: &IntrinsicManifold) -> (f64, (String, String, f64)) {
    let mut total = 0.0_f64; let mut worst = 0.0_f64; let mut we = (String::new(), String::new(), 0.0);
    for e in graph.edges.values() {
        let (Some(a), Some(b)) = (mf.coords.get(&e.a), mf.coords.get(&e.b)) else { continue };
        let d = a.dist(b);
        let diff = d - e.weight.to_f64();
        total += diff * diff;
        if diff.abs() > worst { worst = diff.abs(); we = (graph.node_name(e.a).unwrap_or("?").into(), graph.node_name(e.b).unwrap_or("?").into(), diff); }
    }
    (total.sqrt(), we)
}
