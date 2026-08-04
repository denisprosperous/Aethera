//! Discrete Gaussian curvature via angular deficit: K(v) = 2π − Σ θ_ij.

use aethera_core::{EdgeGraph, NodeId};
use aethera_core::manifold::Point3;
use std::collections::BTreeMap;

pub fn discrete_gaussian_curvature(graph: &EdgeGraph, coords: &BTreeMap<NodeId, Point3>) -> BTreeMap<NodeId, f64> {
    let mut out = BTreeMap::new();
    for (&id, p) in coords.iter() {
        let Some(adj) = graph.adj.get(&id) else { continue };
        let neigh: Vec<(NodeId, f64, f64)> = adj.iter().filter_map(|(_, nb)| {
            coords.get(nb).map(|q| {
                let dx = q.x - p.x; let dy = q.y - p.y;
                let r = (dx*dx + dy*dy).sqrt();
                let theta = dy.atan2(dx);
                (*nb, r, theta)
            })
        }).collect();
        if neigh.len() < 3 { continue; }
        let mut sorted = neigh.clone();
        sorted.sort_by(|a, b| a.2.partial_cmp(&b.2).unwrap_or(std::cmp::Ordering::Equal));
        let mut sum_angles = 0.0_f64;
        let n = sorted.len();
        for i in 0..n {
            let j = (i + 1) % n;
            let (a_id, a_r, _) = sorted[i];
            let (b_id, b_r, _) = sorted[j];
            let (Some(pa), Some(pb)) = (coords.get(&a_id), coords.get(&b_id)) else { continue };
            let cab = ((pa.x - pb.x).powi(2) + (pa.y - pb.y).powi(2)).sqrt();
            if a_r < 1e-12 || b_r < 1e-12 { continue; }
            let cos_t = ((a_r*a_r + b_r*b_r - cab*cab) / (2.0 * a_r * b_r)).clamp(-1.0, 1.0);
            sum_angles += cos_t.acos();
        }
        out.insert(id, 2.0 * std::f64::consts::PI - sum_angles);
    }
    out
}
