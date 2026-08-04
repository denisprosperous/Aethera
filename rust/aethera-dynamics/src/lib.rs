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
