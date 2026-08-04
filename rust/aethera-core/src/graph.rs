//! Edge-weighted graph. Nodes are string IDs; edges carry arbitrary-precision scalars.

use crate::Scalar;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::sync::atomic::{AtomicU64, Ordering};

pub type NodeId = u64;
static NEXT_ID: AtomicU64 = AtomicU64::new(1);
pub fn fresh_node_id() -> NodeId { NEXT_ID.fetch_add(1, Ordering::Relaxed) }

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize, PartialOrd, Ord)]
pub struct EdgeId(pub u64);

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Edge {
    pub id: EdgeId,
    pub a: NodeId,
    pub b: NodeId,
    pub weight: Scalar,
    pub sigma: Option<Scalar>,
    pub source: Option<String>,
    pub epoch: Option<f64>,
}

#[derive(Debug, Default, Clone, Serialize, Deserialize)]
pub struct EdgeGraph {
    pub nodes: BTreeMap<NodeId, String>,
    pub name_index: BTreeMap<String, NodeId>,
    pub edges: BTreeMap<EdgeId, Edge>,
    pub adj: BTreeMap<NodeId, Vec<(EdgeId, NodeId)>>,
    next_edge: u64,
}

impl EdgeGraph {
    pub fn new() -> Self { Self::default() }
    pub fn add_node(&mut self, name: impl Into<String>) -> NodeId {
        let name = name.into();
        if let Some(&id) = self.name_index.get(&name) { return id; }
        let id = fresh_node_id();
        self.nodes.insert(id, name.clone());
        self.name_index.insert(name, id);
        self.adj.entry(id).or_default();
        id
    }
    pub fn node_name(&self, id: NodeId) -> Option<&str> { self.nodes.get(&id).map(|s| s.as_str()) }
    pub fn node_id(&self, name: &str) -> Option<NodeId> { self.name_index.get(name).copied() }
    pub fn add_edge(&mut self, a: impl Into<String>, b: impl Into<String>, weight: Scalar, sigma: Option<Scalar>, source: Option<String>, epoch: Option<f64>) -> EdgeId {
        let na = self.add_node(a);
        let nb = self.add_node(b);
        let id = EdgeId(self.next_edge);
        self.next_edge += 1;
        let edge = Edge { id, a: na, b: nb, weight, sigma, source, epoch };
        self.edges.insert(id, edge.clone());
        self.adj.entry(na).or_default().push((id, nb));
        self.adj.entry(nb).or_default().push((id, na));
        id
    }
    pub fn edge_count(&self) -> usize { self.edges.len() }
    pub fn node_count(&self) -> usize { self.nodes.len() }
    pub fn to_json(&self) -> serde_json::Result<String> { serde_json::to_string_pretty(self) }
    pub fn from_json(s: &str) -> serde_json::Result<Self> { serde_json::from_str(s) }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn build_triangle() {
        let mut g = EdgeGraph::new();
        g.add_edge("A","B", Scalar::from_f64(3.0), None, None, None);
        g.add_edge("B","C", Scalar::from_f64(4.0), None, None, None);
        g.add_edge("A","C", Scalar::from_f64(5.0), None, None, None);
        assert_eq!(g.node_count(), 3);
        assert_eq!(g.edge_count(), 3);
    }
}
