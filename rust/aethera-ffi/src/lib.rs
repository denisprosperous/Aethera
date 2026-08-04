//! Python bindings for AETHERA's Rust core. Exposed as `aethera._rust`.
//! The Python layer uses this if available, else falls back to pure Python.

use aethera_core::{EdgeGraph, Scalar};
use pyo3::prelude::*;

#[derive(serde::Deserialize)]
struct EdgeSpec { a: String, b: String, weight: f64, sigma: Option<f64>, source: Option<String>, epoch: Option<f64> }

#[pyfunction]
fn solve_intrinsic_2d(edges_json: &str, max_iter: usize, tol: f64, prec: u32) -> pyo3::PyResult<String> {
    let edges: Vec<EdgeSpec> = serde_json::from_str(edges_json).map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("bad edges: {e}")))?;
    let mut g = EdgeGraph::new();
    for e in &edges { g.add_edge(&e.a, &e.b, Scalar::from_f64(e.weight), e.sigma.map(Scalar::from_f64), e.source.clone(), e.epoch); }
    let mf = aethera_geometer::solve_2d(&g, max_iter, tol, prec).map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("solver: {e}")))?;
    Ok(mf.to_json().map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("serialise: {e}")))?)
}

#[pymodule]
fn _rust(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(solve_intrinsic_2d, m)?)?;
    Ok(())
}
