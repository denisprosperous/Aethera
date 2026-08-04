//! Reconstructed intrinsic manifold — output of the Intrinsic Geometer.

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use crate::graph::NodeId;

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct Point3 { pub x: f64, pub y: f64, pub z: f64 }
impl Point3 {
    pub fn new(x: f64, y: f64, z: f64) -> Self { Self { x, y, z } }
    pub fn dist(&self, other: &Self) -> f64 {
        let dx = self.x - other.x;
        let dy = self.y - other.y;
        let dz = self.z - other.z;
        (dx*dx + dy*dy + dz*dz).sqrt()
    }
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum Embedding { Planar2D, Spatial3D }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IntrinsicManifold {
    pub embedding: Embedding,
    pub coords: BTreeMap<NodeId, Point3>,
    pub residual: f64,
    pub gaussian_curvature: BTreeMap<NodeId, f64>,
    pub origin: String,
}

impl IntrinsicManifold {
    pub fn new_2d(coords: BTreeMap<NodeId, Point3>, residual: f64, origin: impl Into<String>) -> Self {
        Self { embedding: Embedding::Planar2D, coords, residual, gaussian_curvature: BTreeMap::new(), origin: origin.into() }
    }
    pub fn to_json(&self) -> serde_json::Result<String> { serde_json::to_string_pretty(self) }
}
