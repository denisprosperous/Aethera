//! Agent 6 — ACIF Navigator. Ingests raw interferometric phase data
//! and VLBI angular separations; solves intrinsic frame via SMACOF.
//! Includes Module 5C anomaly daemon (civil-scientific).

use aethera_core::{EdgeGraph, Scalar};
use aethera_core::manifold::IntrinsicManifold;
use aethera_geometer::solve_2d;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub mod anomaly;
pub mod importers;
pub use anomaly::{AnomalyDaemon, AnomalyAlert};

pub fn solve_acif_frame(graph: &EdgeGraph, max_iter: usize, tol: f64, prec: u32) -> Result<IntrinsicManifold, aethera_core::errors::AetheraError> {
    solve_2d(graph, max_iter, tol, prec)
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AcifSnapshot {
    pub epoch: f64,
    pub frame: IntrinsicManifold,
    pub edge_lengths: Vec<(String, String, f64)>,
}

impl AcifSnapshot {
    pub fn from_graph(epoch: f64, graph: &EdgeGraph, frame: IntrinsicManifold) -> Self {
        let edge_lengths = graph.edges.values().map(|e| (
            graph.node_name(e.a).unwrap_or("?").to_string(),
            graph.node_name(e.b).unwrap_or("?").to_string(),
            e.weight.to_f64(),
        )).collect();
        Self { epoch, frame, edge_lengths }
    }
}
