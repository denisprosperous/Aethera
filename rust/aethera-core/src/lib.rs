//! Shared types for AETHERA. The fundamental datum is the Edge: an
//! absolute scalar distance between two named nodes, stripped of any
//! interpretation (no assumed radius, geoid, or gravity).

pub mod scalar;
pub mod graph;
pub mod manifold;
pub mod layers;
pub mod errors;

pub use scalar::Scalar;
pub use graph::{EdgeGraph, NodeId, EdgeId, Edge};
pub use manifold::{IntrinsicManifold, Embedding, Point3};
pub use layers::{ScalarFieldLayer, LayerManager};
pub use errors::{AetheraError, Result};
