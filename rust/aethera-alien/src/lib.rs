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
    let (mf, embedding) = if m2.residual < 1e-4 {
        (m2, "2D".to_string())
    } else {
        match solve_3d(graph, max_iter, tol, prec) {
            Ok(m3) if m3.residual < m2.residual => (m3, "3D".to_string()),
            _ => (m2, "2D".to_string()),
        }
    };
    let residual = mf.residual;
    let curvs: Vec<f64> = mf.gaussian_curvature.values().copied().collect();
    let shape = if residual < 1e-6 { ShapeClassification::Flat }
    else if residual < 1e-2 {
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
        shape, embedding, residual,
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
