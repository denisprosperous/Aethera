//! C-compatible FFI bindings for the AETHERA solver.
//!
//! Exposes `aethera_solve_2d` as a C function that Python can call
//! via ctypes. This avoids the PyO3 dependency (which is heavy) and
//! produces a simple .so library.

use std::ffi::CStr;
use std::os::raw::{c_char, c_int};
use aethera_core::{EdgeGraph, Scalar};
use aethera_geometer::solve_2d;

/// Input edge: (source_name, target_name, length_f64).
/// Names are null-terminated C strings.
#[repr(C)]
pub struct CEdge {
    pub source: *const c_char,
    pub target: *const c_char,
    pub length: f64,
}

/// Output coordinate: (name, x, y).
#[repr(C)]
pub struct CCoord {
    pub name: *mut c_char,
    pub x: f64,
    pub y: f64,
}

/// Output: array of coordinates + stress.
#[repr(C)]
pub struct CSolveResult {
    pub coords: *mut CCoord,
    pub count: c_int,
    pub stress: f64,
}

/// Solve a 2D manifold from edge lengths.
///
/// # Safety
/// - `edges` must point to an array of `edge_count` CEdge structs.
/// - String pointers in CEdge must be valid null-terminated C strings.
/// - The caller must free the result with `aethera_free_result`.
#[no_mangle]
pub extern "C" fn aethera_solve_2d(
    edges: *const CEdge,
    edge_count: c_int,
    max_iter: c_int,
    tol: f64,
) -> CSolveResult {
    if edges.is_null() || edge_count <= 0 {
        return CSolveResult {
            coords: std::ptr::null_mut(),
            count: 0,
            stress: -1.0,
        };
    }

    let mut graph = EdgeGraph::new();
    let edges_slice = unsafe { std::slice::from_raw_parts(edges, edge_count as usize) };
    for edge in edges_slice {
        let source = unsafe { CStr::from_ptr(edge.source) };
        let target = unsafe { CStr::from_ptr(edge.target) };
        let source_str = source.to_str().unwrap_or("");
        let target_str = target.to_str().unwrap_or("");
        graph.add_edge(
            source_str,
            target_str,
            Scalar::from_f64(edge.length),
            None,
            None,
            None,
        );
    }

    match solve_2d(&graph, max_iter as usize, tol, 256) {
        Ok(mf) => {
            let count = mf.coords.len();
            let mut coords: Vec<CCoord> = Vec::with_capacity(count);
            for (id, point) in &mf.coords {
                let name = graph.node_name(*id).unwrap_or("?");
                let c_name = std::ffi::CString::new(name).unwrap();
                coords.push(CCoord {
                    name: c_name.into_raw(),
                    x: point.x,
                    y: point.y,
                });
            }
            let coords_ptr = coords.as_mut_ptr();
            std::mem::forget(coords);
            CSolveResult {
                coords: coords_ptr,
                count: count as c_int,
                stress: mf.residual,
            }
        }
        Err(_) => CSolveResult {
            coords: std::ptr::null_mut(),
            count: 0,
            stress: -1.0,
        },
    }
}

/// Free a CSolveResult returned by aethera_solve_2d.
///
/// # Safety
/// - `result` must point to a CSolveResult returned by aethera_solve_2d.
/// - Must not be called twice on the same result.
#[no_mangle]
pub extern "C" fn aethera_free_result(result: *mut CSolveResult) {
    if result.is_null() {
        return;
    }
    let result = unsafe { &mut *result };
    if result.coords.is_null() || result.count == 0 {
        return;
    }
    let coords = unsafe { std::slice::from_raw_parts_mut(result.coords, result.count as usize) };
    for coord in coords {
        if !coord.name.is_null() {
            unsafe {
                let _ = std::ffi::CString::from_raw(coord.name);
            }
        }
    }
    unsafe {
        libc::free(result.coords as *mut std::ffi::c_void);
    }
    result.coords = std::ptr::null_mut();
    result.count = 0;
}
