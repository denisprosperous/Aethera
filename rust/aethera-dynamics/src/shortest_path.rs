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
