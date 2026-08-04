//! AETHERA FFI — C-compatible bindings for Python ctypes.

pub mod c_bridge;

pub use c_bridge::{aethera_solve_2d, aethera_free_result, CEdge, CCoord, CSolveResult};
