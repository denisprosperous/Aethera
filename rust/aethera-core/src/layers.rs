//! Scalar Field Layers — vertex-attributed scalar data (density, pressure, etc.)
//! overlaid on the manifold. Never inferred from edge-density; always user-supplied.

use serde::{Deserialize, Serialize};
use crate::graph::NodeId;
use crate::manifold::Point3;
use std::collections::BTreeMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScalarFieldLayer {
    pub name: String,
    pub unit: String,
    pub values: BTreeMap<NodeId, f64>,
    pub source: Option<String>,
    pub epoch: Option<f64>,
}

impl ScalarFieldLayer {
    pub fn new(name: impl Into<String>, unit: impl Into<String>) -> Self {
        Self { name: name.into(), unit: unit.into(), values: BTreeMap::new(), source: None, epoch: None }
    }
    pub fn set(&mut self, node: NodeId, v: f64) { self.values.insert(node, v); }
    pub fn get(&self, node: NodeId) -> Option<f64> { self.values.get(&node).copied() }
    pub fn interpolate_at(&self, coords: &BTreeMap<NodeId, Point3>, pos: Point3, k: usize) -> Option<f64> {
        if self.values.is_empty() { return None; }
        let mut dists: Vec<(f64, f64)> = coords.iter()
            .filter_map(|(id, p)| self.values.get(id).map(|v| (p.dist(&pos), *v)))
            .collect();
        dists.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap_or(std::cmp::Ordering::Equal));
        dists.truncate(k);
        if dists.is_empty() { return None; }
        let mut w_sum = 0.0_f64; let mut v_sum = 0.0_f64;
        for (d, v) in &dists { let w = 1.0 / d.max(1e-12).powi(2); w_sum += w; v_sum += w * v; }
        if w_sum > 0.0 { Some(v_sum / w_sum) } else { None }
    }
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct LayerManager {
    pub layers: BTreeMap<String, ScalarFieldLayer>,
}

impl LayerManager {
    pub fn new() -> Self { Self::default() }
    pub fn add_layer(&mut self, layer: ScalarFieldLayer) { self.layers.insert(layer.name.clone(), layer); }
    pub fn get_layer(&self, name: &str) -> Option<&ScalarFieldLayer> { self.layers.get(name) }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn layer_basic() {
        let mut l = ScalarFieldLayer::new("density", "kg/m³");
        l.set(1, 1.225);
        assert_eq!(l.get(1), Some(1.225));
    }
}
