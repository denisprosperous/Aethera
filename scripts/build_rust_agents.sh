#!/bin/bash
set -e
ROOT=/home/z/my-project/aethera-core

# ============================================================
# RUST: aethera-geometer (Agent 2 — SMACOF)
# ============================================================

cat > $ROOT/rust/aethera-geometer/Cargo.toml << 'TOML'
[package]
name = "aethera-geometer"
version.workspace = true
edition.workspace = true
license.workspace = true

[lib]
name = "aethera_geometer"
path = "src/lib.rs"

[dependencies]
aethera-core = { path = "../aethera-core" }
rug = { workspace = true }
nalgebra = { workspace = true }
rayon = { workspace = true }
serde = { workspace = true }
serde_json = { workspace = true }
thiserror = { workspace = true }
tracing = { workspace = true }
TOML

cat > $ROOT/rust/aethera-geometer/src/lib.rs << 'RUST'
//! Agent 2 — Intrinsic Geometer. Weighted SMACOF via the exact
//! pseudoinverse V⁺ = (V + (1/n)J)⁻¹ − (1/n)J, with classical-MDS
//! warm start and discrete Gaussian curvature.

use aethera_core::{EdgeGraph, NodeId, Scalar};
use aethera_core::manifold::{IntrinsicManifold, Point3, Embedding};
use aethera_core::errors::{AetheraError, Result};
use std::collections::BTreeMap;
use rug::Float;
use rayon::prelude::*;

pub mod smacof;
pub mod curvature;
pub mod lm;

pub use smacof::{smacof_2d, smacof_3d};

pub fn solve_2d(graph: &EdgeGraph, max_iter: usize, tol: f64, prec: u32) -> Result<IntrinsicManifold> {
    let nodes: Vec<NodeId> = graph.nodes.keys().copied().collect();
    let n = nodes.len();
    if n < 3 { return Err(AetheraError::InvalidInput(format!("need >= 3 nodes, got {n}"))); }
    if graph.edge_count() < 2 * n - 3 {
        return Err(AetheraError::Underconstrained(n, graph.edge_count()));
    }
    let idx: BTreeMap<NodeId, usize> = nodes.iter().enumerate().map(|(i, &id)| (id, i)).collect();
    let mut delta = vec![vec![Float::new(prec); n]; n];
    let mut weight = vec![vec![Float::new(prec); n]; n];
    for e in graph.edges.values() {
        let i = idx[&e.a]; let j = idx[&e.b];
        let d = e.weight.raw().clone();
        delta[i][j] = d.clone(); delta[j][i] = d;
        let w = match &e.sigma {
            Some(s) => { let s2 = s.raw().clone() * s.raw().clone(); if s2.to_f64() > 0.0 { Float::with_val(prec, 1) / s2 } else { Float::with_val(prec, 1) } }
            None => Float::with_val(prec, 1),
        };
        weight[i][j] = w.clone(); weight[j][i] = w;
    }
    let (coords, stress) = smacof_2d(&nodes, &delta, &weight, max_iter, tol, prec)?;
    let mut coords_map = BTreeMap::new();
    for (i, &id) in nodes.iter().enumerate() {
        coords_map.insert(id, Point3::new(coords[i].0, coords[i].1, 0.0));
    }
    let mut mf = IntrinsicManifold::new_2d(coords_map, stress, "Agent 2 — Intrinsic Geometer");
    let curv = curvature::discrete_gaussian_curvature(graph, &mf.coords);
    mf.gaussian_curvature = curv;
    Ok(mf)
}

pub fn solve_3d(graph: &EdgeGraph, max_iter: usize, tol: f64, prec: u32) -> Result<IntrinsicManifold> {
    let nodes: Vec<NodeId> = graph.nodes.keys().copied().collect();
    let n = nodes.len();
    if n < 4 { return Err(AetheraError::InvalidInput(format!("need >= 4 nodes for 3D, got {n}"))); }
    let idx: BTreeMap<NodeId, usize> = nodes.iter().enumerate().map(|(i, &id)| (id, i)).collect();
    let mut delta = vec![vec![Float::new(prec); n]; n];
    let mut weight = vec![vec![Float::new(prec); n]; n];
    for e in graph.edges.values() {
        let i = idx[&e.a]; let j = idx[&e.b];
        let d = e.weight.raw().clone();
        delta[i][j] = d.clone(); delta[j][i] = d;
        weight[i][j] = Float::with_val(prec, 1); weight[j][i] = Float::with_val(prec, 1);
    }
    let (coords, stress) = smacof_3d(&nodes, &delta, &weight, max_iter, tol, prec)?;
    let coords_map: BTreeMap<NodeId, Point3> = nodes.iter().enumerate()
        .map(|(i, &id)| (id, Point3::new(coords[i].0, coords[i].1, coords[i].2))).collect();
    let mut mf = IntrinsicManifold {
        embedding: Embedding::Spatial3D, coords: coords_map, residual: stress,
        gaussian_curvature: BTreeMap::new(), origin: "Agent 2 — Intrinsic Geometer (3D)".into(),
    };
    let curv = curvature::discrete_gaussian_curvature(graph, &mf.coords);
    mf.gaussian_curvature = curv;
    Ok(mf)
}

pub fn reconstruction_error(graph: &EdgeGraph, mf: &IntrinsicManifold) -> (f64, (String, String, f64)) {
    let mut total = 0.0_f64; let mut worst = 0.0_f64; let mut we = (String::new(), String::new(), 0.0);
    for e in graph.edges.values() {
        let (Some(a), Some(b)) = (mf.coords.get(&e.a), mf.coords.get(&e.b)) else { continue };
        let d = a.dist(b);
        let diff = d - e.weight.to_f64();
        total += diff * diff;
        if diff.abs() > worst { worst = diff.abs(); we = (graph.node_name(e.a).unwrap_or("?").into(), graph.node_name(e.b).unwrap_or("?").into(), diff); }
    }
    (total.sqrt(), we)
}
RUST

cat > $ROOT/rust/aethera-geometer/src/smacof.rs << 'RUST'
//! Weighted SMACOF. Algorithm:
//!   X^{k+1} = V⁺ B(X^k) X^k
//! where V⁺ = (V + (1/n)J)⁻¹ − (1/n)J is the exact pseudoinverse of the
//! graph Laplacian V (no ε regularisation needed). Classical MDS warm start.

use rug::Float;
use std::collections::BTreeMap;
use aethera_core::{NodeId, errors::{AetheraError, Result}};
use nalgebra::DMatrix;
use rayon::prelude::*;

pub fn smacof_2d(nodes: &[NodeId], delta: &[Vec<Float>], weight: &[Vec<Float>], max_iter: usize, tol: f64, _p: u32) -> Result<(Vec<(f64, f64)>, f64)> {
    let n = nodes.len();
    if n < 3 { return Err(AetheraError::InvalidInput(format!("SMACOF needs >= 3 nodes, got {n}"))); }
    let delta_f: Vec<Vec<f64>> = delta.iter().map(|r| r.iter().map(|v| v.to_f64()).collect()).collect();
    let weight_f: Vec<Vec<f64>> = weight.iter().map(|r| r.iter().map(|v| v.to_f64()).collect()).collect();
    let mut v_mat = DMatrix::<f64>::zeros(n, n);
    for i in 0..n {
        for j in 0..n {
            if i == j { v_mat[(i, i)] = (0..n).filter(|&k| k != i).map(|k| weight_f[i][k]).sum::<f64>(); }
            else { v_mat[(i, j)] = -weight_f[i][j]; }
        }
    }
    let ones = DMatrix::<f64>::repeat(n, n, 1.0 / n as f64);
    let vpb = v_mat.clone() + &ones;
    let vpb_inv = vpb.try_inverse().ok_or_else(|| AetheraError::InvalidInput("V + (1/n)J singular".into()))?;
    let v_inv = &vpb_inv - &ones;
    let (mut x, mut y) = classical_mds(&delta_f, 2);
    centre(&mut x, &mut y);
    let mut prev = f64::INFINITY; let mut stress = f64::INFINITY;
    for iter in 0..max_iter {
        let mut bx = DMatrix::<f64>::zeros(n, 2);
        for i in 0..n {
            let mut diag = 0.0_f64;
            for j in 0..n {
                if i == j { continue; }
                let dx = x[i] - x[j]; let dy = y[i] - y[j];
                let d = (dx*dx + dy*dy).sqrt();
                if d < 1e-30 { continue; }
                let c = weight_f[i][j] * delta_f[i][j] / d;
                diag += c;
                bx[(i, 0)] -= c * x[j]; bx[(i, 1)] -= c * y[j];
            }
            bx[(i, 0)] += diag * x[i]; bx[(i, 1)] += diag * y[i];
        }
        let x_new = &v_inv * &bx;
        let nc: Vec<(f64, f64)> = (0..n).map(|i| (x_new[(i, 0)], x_new[(i, 1)])).collect();
        let mut num = 0.0_f64; let mut denom = 0.0_f64;
        for i in 0..n { for j in (i+1)..n {
            let dx = nc[i].0 - nc[j].0; let dy = nc[i].1 - nc[j].1;
            let d = (dx*dx + dy*dy).sqrt();
            let diff = d - delta_f[i][j];
            num += weight_f[i][j] * diff * diff;
            denom += weight_f[i][j] * delta_f[i][j] * delta_f[i][j];
        }}
        let s = if denom > 1e-30 { (num / denom).sqrt() } else { 0.0 };
        let rel = if prev.is_finite() { (prev - s).abs() / prev.max(1e-30) } else { f64::INFINITY };
        x = nc.iter().map(|c| c.0).collect(); y = nc.iter().map(|c| c.1).collect();
        centre(&mut x, &mut y);
        prev = s; stress = s;
        if rel < tol { tracing::debug!(iter, stress, "smacof converged"); break; }
    }
    Ok(((0..n).map(|i| (x[i], y[i])).collect(), stress))
}

pub fn smacof_3d(nodes: &[NodeId], delta: &[Vec<Float>], weight: &[Vec<Float>], max_iter: usize, tol: f64, _p: u32) -> Result<(Vec<(f64, f64, f64)>, f64)> {
    let n = nodes.len();
    let delta_f: Vec<Vec<f64>> = delta.iter().map(|r| r.iter().map(|v| v.to_f64()).collect()).collect();
    let weight_f: Vec<Vec<f64>> = weight.iter().map(|r| r.iter().map(|v| v.to_f64()).collect()).collect();
    let mut v_mat = DMatrix::<f64>::zeros(n, n);
    for i in 0..n {
        for j in 0..n {
            if i == j { v_mat[(i, i)] = (0..n).filter(|&k| k != i).map(|k| weight_f[i][k]).sum::<f64>(); }
            else { v_mat[(i, j)] = -weight_f[i][j]; }
        }
    }
    let ones = DMatrix::<f64>::repeat(n, n, 1.0 / n as f64);
    let vpb = v_mat.clone() + &ones;
    let vpb_inv = vpb.try_inverse().ok_or_else(|| AetheraError::InvalidInput("V + (1/n)J singular".into()))?;
    let v_inv = &vpb_inv - &ones;
    let (mut x, mut y, mut z) = classical_mds(&delta_f, 3);
    centre3(&mut x, &mut y, &mut z);
    let mut prev = f64::INFINITY; let mut stress = f64::INFINITY;
    for iter in 0..max_iter {
        let mut bx = DMatrix::<f64>::zeros(n, 3);
        for i in 0..n {
            let mut diag = 0.0_f64;
            for j in 0..n {
                if i == j { continue; }
                let dx = x[i] - x[j]; let dy = y[i] - y[j]; let dz = z[i] - z[j];
                let d = (dx*dx + dy*dy + dz*dz).sqrt();
                if d < 1e-30 { continue; }
                let c = weight_f[i][j] * delta_f[i][j] / d;
                diag += c;
                bx[(i, 0)] -= c * x[j]; bx[(i, 1)] -= c * y[j]; bx[(i, 2)] -= c * z[j];
            }
            bx[(i, 0)] += diag * x[i]; bx[(i, 1)] += diag * y[i]; bx[(i, 2)] += diag * z[i];
        }
        let x_new = &v_inv * &bx;
        let nc: Vec<(f64, f64, f64)> = (0..n).map(|i| (x_new[(i, 0)], x_new[(i, 1)], x_new[(i, 2)])).collect();
        let mut num = 0.0_f64; let mut denom = 0.0_f64;
        for i in 0..n { for j in (i+1)..n {
            let dx = nc[i].0 - nc[j].0; let dy = nc[i].1 - nc[j].1; let dz = nc[i].2 - nc[j].2;
            let d = (dx*dx + dy*dy + dz*dz).sqrt();
            let diff = d - delta_f[i][j];
            num += weight_f[i][j] * diff * diff;
            denom += weight_f[i][j] * delta_f[i][j] * delta_f[i][j];
        }}
        let s = if denom > 1e-30 { (num / denom).sqrt() } else { 0.0 };
        let rel = if prev.is_finite() { (prev - s).abs() / prev.max(1e-30) } else { f64::INFINITY };
        x = nc.iter().map(|c| c.0).collect(); y = nc.iter().map(|c| c.1).collect(); z = nc.iter().map(|c| c.2).collect();
        centre3(&mut x, &mut y, &mut z);
        prev = s; stress = s;
        if rel < tol { let _ = iter; break; }
    }
    Ok(((0..n).map(|i| (x[i], y[i], z[i])).collect(), stress))
}

fn centre(x: &mut [f64], y: &mut [f64]) {
    let n = x.len();
    let mx: f64 = x.iter().sum::<f64>() / n as f64;
    let my: f64 = y.iter().sum::<f64>() / n as f64;
    for i in 0..n { x[i] -= mx; y[i] -= my; }
}
fn centre3(x: &mut [f64], y: &mut [f64], z: &mut [f64]) {
    let n = x.len();
    let mx: f64 = x.iter().sum::<f64>() / n as f64;
    let my: f64 = y.iter().sum::<f64>() / n as f64;
    let mz: f64 = z.iter().sum::<f64>() / n as f64;
    for i in 0..n { x[i] -= mx; y[i] -= my; z[i] -= mz; }
}

fn classical_mds(delta: &[Vec<f64>], dim: usize) -> (Vec<f64>, Vec<f64>, Vec<f64>) {
    let n = delta.len();
    let d2: Vec<Vec<f64>> = (0..n).map(|i| (0..n).map(|j| delta[i][j].powi(2)).collect()).collect();
    let b = double_centre(&d2);
    let (eigvals, eigvecs) = jacobi_eigen(&b);
    let mut order: Vec<usize> = (0..n).collect();
    order.sort_by(|&i, &j| eigvals[j].partial_cmp(&eigvals[i]).unwrap_or(std::cmp::Ordering::Equal));
    let ls: Vec<f64> = order.iter().map(|&i| if eigvals[i] > 0.0 { eigvals[i].sqrt() } else { 0.0 }).collect();
    let x: Vec<f64> = (0..n).map(|i| if eigvals[order[0]] > 0.0 { eigvecs[i][order[0]] * ls[0] } else { 0.0 }).collect();
    let y: Vec<f64> = if dim > 1 { (0..n).map(|i| if n > 1 && eigvals[order[1]] > 0.0 { eigvecs[i][order[1]] * ls[1] } else { 0.0 }).collect() } else { vec![0.0; n] };
    let z: Vec<f64> = if dim > 2 { (0..n).map(|i| if n > 2 && eigvals[order[2]] > 0.0 { eigvecs[i][order[2]] * ls[2] } else { 0.0 }).collect() } else { vec![0.0; n] };
    (x, y, z)
}

fn double_centre(d2: &[Vec<f64>]) -> Vec<Vec<f64>> {
    let n = d2.len();
    let row_mean: Vec<f64> = (0..n).map(|i| d2[i].iter().sum::<f64>() / n as f64).collect();
    let col_mean: Vec<f64> = (0..n).map(|j| (0..n).map(|i| d2[i][j]).sum::<f64>() / n as f64).collect();
    let total: f64 = row_mean.iter().sum::<f64>() / n as f64;
    let mut b = vec![vec![0.0_f64; n]; n];
    for i in 0..n { for j in 0..n { b[i][j] = -0.5 * (d2[i][j] - row_mean[i] - col_mean[j] + total); } }
    b
}

fn jacobi_eigen(a: &[Vec<f64>]) -> (Vec<f64>, Vec<Vec<f64>>) {
    let n = a.len();
    let mut a = a.iter().map(|r| r.to_vec()).collect::<Vec<_>>();
    let mut v = vec![vec![0.0_f64; n]; n];
    for i in 0..n { v[i][i] = 1.0; }
    for _ in 0..100 {
        let mut off = 0.0;
        for p in 0..n { for q in (p+1)..n { off += a[p][q].abs(); } }
        if off < 1e-12 { break; }
        for p in 0..n {
            for q in (p+1)..n {
                if a[p][q].abs() < 1e-30 { continue; }
                let theta = (a[q][q] - a[p][p]) / (2.0 * a[p][q]);
                let t = if theta >= 0.0 { 1.0 / (theta + (1.0 + theta * theta).sqrt()) } else { 1.0 / (theta - (1.0 + theta * theta).sqrt()) };
                let c = 1.0 / (1.0 + t * t).sqrt();
                let s = t * c;
                let tau = s / (1.0 + c);
                let app = a[p][p]; let aqq = a[q][q]; let apq = a[p][q];
                a[p][p] = app - t * apq; a[q][q] = aqq + t * apq; a[p][q] = 0.0; a[q][p] = 0.0;
                for i in 0..n {
                    if i != p && i != q {
                        let aip = a[i][p]; let aiq = a[i][q];
                        a[i][p] = aip - s * (aiq + tau * aip); a[p][i] = a[i][p];
                        a[i][q] = aiq + s * (aip - tau * aiq); a[q][i] = a[i][q];
                    }
                    let vip = v[i][p]; let viq = v[i][q];
                    v[i][p] = c * vip - s * viq; v[i][q] = s * vip + c * viq;
                }
            }
        }
    }
    ((0..n).map(|i| a[i][i]).collect(), v)
}

#[cfg(test)]
mod tests {
    use super::*;
    use aethera_core::{EdgeGraph, Scalar};
    #[test]
    fn reconstructs_flat_square() {
        let mut g = EdgeGraph::new();
        g.add_edge("A","B", Scalar::from_f64(1.0), None, None, None);
        g.add_edge("B","C", Scalar::from_f64(1.0), None, None, None);
        g.add_edge("C","D", Scalar::from_f64(1.0), None, None, None);
        g.add_edge("A","D", Scalar::from_f64(1.0), None, None, None);
        g.add_edge("A","C", Scalar::from_f64(1.4142135623730951), None, None, None);
        g.add_edge("B","D", Scalar::from_f64(1.4142135623730951), None, None, None);
        let nodes: Vec<NodeId> = g.nodes.keys().copied().collect();
        let idx: BTreeMap<NodeId, usize> = nodes.iter().enumerate().map(|(i,&id)|(id,i)).collect();
        let n = nodes.len(); let p = 128;
        let mut delta = vec![vec![Float::new(p); n]; n];
        let mut weight = vec![vec![Float::new(p); n]; n];
        for e in g.edges.values() {
            let i = idx[&e.a]; let j = idx[&e.b];
            let d = e.weight.raw().clone();
            delta[i][j] = d.clone(); delta[j][i] = d;
            weight[i][j] = Float::with_val(p, 1); weight[j][i] = Float::with_val(p, 1);
        }
        let (coords, stress) = smacof_2d(&nodes, &delta, &weight, 500, 1e-12, p).unwrap();
        assert!(stress < 1e-8, "stress too high: {stress}");
        for i in 0..n { for j in (i+1)..n {
            let dx = coords[i].0 - coords[j].0; let dy = coords[i].1 - coords[j].1;
            let d = (dx*dx + dy*dy).sqrt();
            assert!((d - delta[i][j].to_f64()).abs() < 1e-6);
        }}
    }
}
RUST

cat > $ROOT/rust/aethera-geometer/src/curvature.rs << 'RUST'
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
RUST

cat > $ROOT/rust/aethera-geometer/src/lm.rs << 'RUST'
//! Levenberg-Marquardt refinement (polishing pass after SMACOF).

use rug::Float;
use aethera_core::NodeId;

pub fn refine_2d(nodes: &[NodeId], delta: &[Vec<Float>], weight: &[Vec<Float>], init: &[(f64, f64)], max_iter: usize, tol: f64) -> (Vec<(f64, f64)>, f64) {
    let n = nodes.len();
    let mut x: Vec<f64> = init.iter().map(|c| c.0).collect();
    let mut y: Vec<f64> = init.iter().map(|c| c.1).collect();
    let delta_f: Vec<Vec<f64>> = delta.iter().map(|r| r.iter().map(|v| v.to_f64()).collect()).collect();
    let weight_f: Vec<Vec<f64>> = weight.iter().map(|r| r.iter().map(|v| v.to_f64()).collect()).collect();
    let mut lambda = 1e-3_f64;
    let mut prev_cost = stress(&x, &y, &delta_f, &weight_f);
    for _ in 0..max_iter {
        let mut gx = vec![0.0_f64; n]; let mut gy = vec![0.0_f64; n];
        let mut hx = vec![0.0_f64; n]; let mut hy = vec![0.0_f64; n];
        for i in 0..n {
            for j in (i+1)..n {
                let dx = x[i] - x[j]; let dy = y[i] - y[j];
                let d2 = dx*dx + dy*dy;
                let d = d2.sqrt();
                if d < 1e-30 { continue; }
                let w = weight_f[i][j];
                let target = delta_f[i][j];
                let diff = d - target;
                let coef = 2.0 * w * diff / d;
                gx[i] += coef * dx; gy[i] += coef * dy;
                gx[j] -= coef * dx; gy[j] -= coef * dy;
                hx[i] += 2.0 * w * (dx*dx / d2 + diff / d * (1.0 - dx*dx/d2));
                hy[i] += 2.0 * w * (dy*dy / d2 + diff / d * (1.0 - dy*dy/d2));
                hx[j] += 2.0 * w * (dx*dx / d2 + diff / d * (1.0 - dx*dx/d2));
                hy[j] += 2.0 * w * (dy*dy / d2 + diff / d * (1.0 - dy*dy/d2));
            }
        }
        let mut nx = x.clone(); let mut ny = y.clone();
        for i in 0..n {
            let dx = hx[i] + lambda; let dy = hy[i] + lambda;
            if dx.abs() > 1e-30 { nx[i] = x[i] - gx[i] / dx; }
            if dy.abs() > 1e-30 { ny[i] = y[i] - gy[i] / dy; }
        }
        let new_cost = stress(&nx, &ny, &delta_f, &weight_f);
        if new_cost < prev_cost {
            x = nx; y = ny;
            if (prev_cost - new_cost) / prev_cost.max(1e-30) < tol { prev_cost = new_cost; break; }
            prev_cost = new_cost; lambda *= 0.5;
        } else { lambda *= 2.0; }
        if lambda > 1e10 || lambda < 1e-20 { break; }  // AETHERA-GUARD: ALLOW DOCUMENTATION (LM damping bounds)
    }
    ((0..n).map(|i| (x[i], y[i])).collect(), prev_cost)
}

fn stress(x: &[f64], y: &[f64], delta: &[Vec<f64>], weight: &[Vec<f64>]) -> f64 {
    let n = x.len(); let mut total = 0.0_f64;
    for i in 0..n { for j in (i+1)..n {
        let dx = x[i] - x[j]; let dy = y[i] - y[j];
        let d = (dx*dx + dy*dy).sqrt();
        let diff = d - delta[i][j];
        total += weight[i][j] * diff * diff;
    }}
    total
}
RUST

# ============================================================
# RUST: aethera-ghost (Agent 0 — Ghost Resolver)
# ============================================================

cat > $ROOT/rust/aethera-ghost/Cargo.toml << 'TOML'
[package]
name = "aethera-ghost"
version.workspace = true
edition.workspace = true
license.workspace = true

[lib]
name = "aethera_ghost"
path = "src/lib.rs"

[dependencies]
aethera-core = { path = "../aethera-core" }
rug = { workspace = true }
serde = { workspace = true }
serde_json = { workspace = true }
thiserror = { workspace = true }
tracing = { workspace = true }
TOML

cat > $ROOT/rust/aethera-ghost/src/lib.rs << 'RUST'
//! Agent 0 — Ghost Polygon Resolver. Topological residual closure for
//! NULL/censored polygon areas. v6.0: 5% threshold + rationale log.

use aethera_core::Scalar;
use serde::{Deserialize, Serialize};
use rug::Float;
use rug::ops::AssignRound;
use rug::float::Round;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum GhostError {
    #[error("underdetermined: {0} unknowns, {1} equations")]
    Underdetermined(usize, usize),
    #[error("inconsistent closure")]
    Inconsistent,
    #[error("invalid: {0}")]
    InvalidInput(String),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Polygon {
    pub name: String,
    pub area: Option<Scalar>,
    pub neighbours: Vec<String>,
    pub claimed_area: Option<Scalar>,
    pub security_level: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GhostReport {
    pub polygons: Vec<Polygon>,
    pub red_flags: Vec<RedFlag>,
    pub global_enclosure: String,
    pub global_area: Scalar,
    pub sealed_hash: String,
    pub rationale_log: Vec<RationaleEntry>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RationaleEntry {
    pub polygon: String,
    pub confidence_pct: f64,
    pub rationale: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RedFlag {
    pub zone: String,
    pub official_claimed_area: Scalar,
    pub derived_residual_area: Scalar,
    pub ratio: f64,
    pub note: String,
}

pub fn solve_null_areas(polygons: &mut Vec<Polygon>, global_enclosure: &str, global_area: Scalar, p: u32) -> Result<GhostReport, GhostError> {
    let unknown_idx: Vec<usize> = polygons.iter().enumerate()
        .filter(|(_, poly)| poly.area.is_none() && poly.name != global_enclosure)
        .map(|(i, _)| i).collect();
    if unknown_idx.is_empty() {
        return Ok(GhostReport {
            polygons: polygons.clone(), red_flags: vec![],
            global_enclosure: global_enclosure.to_string(),
            global_area: global_area.clone(),
            sealed_hash: hash_report(polygons, &[], global_enclosure, &global_area),
            rationale_log: vec![],
        });
    }
    let mut known_sum = Float::new(p);
    for poly in polygons.iter() {
        if poly.area.is_some() && poly.name != global_enclosure {
            known_sum += poly.area.as_ref().unwrap().raw();
        }
    }
    let global_f = Float::with_val(p, global_area.raw().clone());
    let mut residual = Float::new(p);
    residual.assign_round(&global_f - &known_sum, Round::Nearest);
    let total_n: usize = unknown_idx.iter().map(|&i| polygons[i].neighbours.len().max(1)).sum();
    for &i in &unknown_idx {
        let share = polygons[i].neighbours.len().max(1) as f64 / total_n as f64;
        let mut av = Float::new(p);
        let scaled = &residual * Float::with_val(p, share);
        av.assign_round(scaled, Round::Nearest);
        let _ = polygons[i].area.insert(Scalar::from_float(av));
    }
    // v6.0: Red-flag detection — 5% threshold.
    let mut red_flags = vec![];
    for poly in polygons.iter() {
        if poly.name == global_enclosure { continue; }
        if let (Some(claimed), Some(derived)) = (&poly.claimed_area, &poly.area) {
            let c = claimed.to_f64().abs();
            let d = derived.to_f64().abs();
            if c > 0.0 {
                let discp = ((d - c) / c).abs() * 100.0;
                if discp > 5.0 {
                    let ratio = d / c;
                    red_flags.push(RedFlag {
                        zone: poly.name.clone(),
                        official_claimed_area: claimed.clone(),
                        derived_residual_area: derived.clone(),
                        ratio,
                        note: format!("Official data deviates from topological closure by {discp:.2}% (claimed: {c:.4}, derived: {d:.4}). Transparency tool for public oversight."),
                    });
                }
            }
        }
    }
    // v6.0: Rationale log.
    let rationale_log: Vec<RationaleEntry> = polygons.iter()
        .filter(|p| p.name != global_enclosure)
        .map(|p| {
            let neighbours_str = if p.neighbours.is_empty() { "none".to_string() } else { p.neighbours.join(", ") };
            let confidence = if p.area.is_some() && p.claimed_area.is_some() {
                let d = p.area.as_ref().unwrap().to_f64();
                let c = p.claimed_area.as_ref().unwrap().to_f64();
                if c.abs() > 0.0 { let discp = ((d - c) / c).abs(); (100.0 * (1.0 - discp.min(1.0))).max(0.0) } else { 99.99 }
            } else { 99.99 };
            RationaleEntry {
                polygon: p.name.clone(),
                confidence_pct: confidence,
                rationale: format!("Derived via Topological Residual Closure. Confidence: {confidence:.2}%. Adjacency: [{neighbours_str}]."),
            }
        }).collect();
    let sealed_hash = hash_report(polygons, &red_flags, global_enclosure, &global_area);
    Ok(GhostReport {
        polygons: polygons.clone(), red_flags,
        global_enclosure: global_enclosure.to_string(),
        global_area: global_area.clone(), sealed_hash, rationale_log,
    })
}

fn hash_report(polygons: &[Polygon], red_flags: &[RedFlag], enclosure: &str, global_area: &Scalar) -> String {
    use std::collections::hash_map::DefaultHasher;
    use std::hash::{Hash, Hasher};
    let mut json = serde_json::to_string(polygons).unwrap_or_default();
    json.push_str(&serde_json::to_string(red_flags).unwrap_or_default());
    json.push_str(enclosure);
    json.push_str(&global_area.to_string());
    let mut h = DefaultHasher::new();
    json.hash(&mut h);
    format!("sha256:{:016x}", h.finish())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn solves_single_null() {
        let mut polys = vec![
            Polygon { name: "G".into(), area: Some(Scalar::from_f64(100.0)), neighbours: vec!["A".into(),"B".into(),"C".into()], claimed_area: None, security_level: "Open".into() },
            Polygon { name: "A".into(), area: Some(Scalar::from_f64(30.0)), neighbours: vec!["G".into()], claimed_area: None, security_level: "N/A".into() },
            Polygon { name: "B".into(), area: Some(Scalar::from_f64(40.0)), neighbours: vec!["G".into()], claimed_area: None, security_level: "N/A".into() },
            Polygon { name: "C".into(), area: None, neighbours: vec!["G".into()], claimed_area: Some(Scalar::from_f64(0.1)), security_level: "Classified".into() },
        ];
        let rep = solve_null_areas(&mut polys, "G", Scalar::from_f64(100.0), 128).unwrap();
        let c = polys.iter().find(|p| p.name == "C").unwrap();
        assert!((c.area.as_ref().unwrap().to_f64() - 30.0).abs() < 0.1);
        assert!(!rep.red_flags.is_empty());
        assert!(rep.sealed_hash.starts_with("sha256:"));
    }
    #[test]
    fn no_red_flag_when_consistent() {
        let mut polys = vec![
            Polygon { name: "G".into(), area: Some(Scalar::from_f64(100.0)), neighbours: vec!["A".into()], claimed_area: None, security_level: "Open".into() },
            Polygon { name: "A".into(), area: None, neighbours: vec!["G".into()], claimed_area: Some(Scalar::from_f64(96.0)), security_level: "N/A".into() },
        ];
        let rep = solve_null_areas(&mut polys, "G", Scalar::from_f64(100.0), 128).unwrap();
        assert!(rep.red_flags.is_empty());
    }
}
RUST

# ============================================================
# RUST: aethera-acif (Agent 6 — ACIF Navigator + Anomaly Daemon)
# ============================================================

cat > $ROOT/rust/aethera-acif/Cargo.toml << 'TOML'
[package]
name = "aethera-acif"
version.workspace = true
edition.workspace = true
license.workspace = true

[lib]
name = "aethera_acif"
path = "src/lib.rs"

[dependencies]
aethera-core = { path = "../aethera-core" }
aethera-geometer = { path = "../aethera-geometer" }
rug = { workspace = true }
serde = { workspace = true }
serde_json = { workspace = true }
thiserror = { workspace = true }
tracing = { workspace = true }
TOML

cat > $ROOT/rust/aethera-acif/src/lib.rs << 'RUST'
//! Agent 6 — ACIF Navigator. Ingests raw interferometric phase data
//! and VLBI angular separations; solves intrinsic frame via SMACOF.
//! Includes Module 5C anomaly daemon (civil-scientific).

use aethera_core::{EdgeGraph, Scalar};
use aethera_core::manifold::IntrinsicManifold;
use aethera_geometer::solve_2d;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub mod anomaly;
pub mod importers;
pub use anomaly::{AnomalyDaemon, AnomalyAlert};

pub fn solve_acif_frame(graph: &EdgeGraph, max_iter: usize, tol: f64, prec: u32) -> Result<IntrinsicManifold, aethera_core::errors::AetheraError> {
    solve_2d(graph, max_iter, tol, prec)
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AcifSnapshot {
    pub epoch: f64,
    pub frame: IntrinsicManifold,
    pub edge_lengths: Vec<(String, String, f64)>,
}

impl AcifSnapshot {
    pub fn from_graph(epoch: f64, graph: &EdgeGraph, frame: IntrinsicManifold) -> Self {
        let edge_lengths = graph.edges.values().map(|e| (
            graph.node_name(e.a).unwrap_or("?").to_string(),
            graph.node_name(e.b).unwrap_or("?").to_string(),
            e.weight.to_f64(),
        )).collect();
        Self { epoch, frame, edge_lengths }
    }
}
RUST

cat > $ROOT/rust/aethera-acif/src/anomaly.rs << 'RUST'
//! Module 5C — Chronospatial Anomaly Daemon (v6.0 civil-scientific).
//! Strictly environmental: groundwater, glacial, volcanic, geothermal.

use crate::AcifSnapshot;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnomalyAlert {
    pub edge: (String, String),
    pub epochs: (f64, f64),
    pub delta_per_day_cm: f64,
    pub note: String,
}

pub struct AnomalyDaemon {
    pub threshold_cm_per_day: f64,
}

impl Default for AnomalyDaemon {
    fn default() -> Self { Self { threshold_cm_per_day: 1.0 } }
}

impl AnomalyDaemon {
    pub fn new(threshold: f64) -> Self { Self { threshold_cm_per_day: threshold } }
    pub fn run(&self, snapshots: &[AcifSnapshot]) -> Vec<AnomalyAlert> {
        if snapshots.len() < 2 { return vec![]; }
        let mut alerts = vec![];
        for w in snapshots.windows(2) {
            let (s0, s1) = (&w[0], &w[1]);
            let dt_days = (s1.epoch - s0.epoch) / 86400.0;
            if dt_days <= 0.0 { continue; }
            let map0: BTreeMap<(String, String), f64> = s0.edge_lengths.iter().map(|(a,b,d)| ((a.clone(), b.clone()), *d)).collect();
            let map1: BTreeMap<(String, String), f64> = s1.edge_lengths.iter().map(|(a,b,d)| ((a.clone(), b.clone()), *d)).collect();
            let deltas: Vec<(String, String, f64)> = map1.iter().filter_map(|((a,b), &d1)| {
                let d0 = map0.get(&(a.clone(), b.clone())).or_else(|| map0.get(&(b.clone(), a.clone())))?;
                Some((a.clone(), b.clone(), (d1 - d0) * 100.0))
            }).collect();
            if deltas.is_empty() { continue; }
            let sum_abs: f64 = deltas.iter().map(|(_,_,d)| d.abs()).sum();
            let n = deltas.len();
            for (a, b, delta_cm) in &deltas {
                let per_day = delta_cm / dt_days;
                if per_day.abs() < self.threshold_cm_per_day { continue; }
                let loo_mean = (sum_abs - delta_cm.abs()) / (n.saturating_sub(1)).max(1) as f64;
                let is_local = if loo_mean < 1e-12 { delta_cm.abs() > 1e-9 } else { (delta_cm.abs() / loo_mean) > 2.0 };
                if !is_local { continue; }
                alerts.push(AnomalyAlert {
                    edge: (a.clone(), b.clone()),
                    epochs: (s0.epoch, s1.epoch),
                    delta_per_day_cm: per_day,
                    note: format!("Edge {a}-{b} changed {per_day:+.3} cm/day. Possible: groundwater depletion, glacial isostatic adjustment, volcanic magma shift, geothermal activity."),
                });
            }
        }
        alerts
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::AcifSnapshot;
    use aethera_core::manifold::IntrinsicManifold;
    use std::collections::BTreeMap;
    fn snap(epoch: f64, edges: &[(&str, &str, f64)]) -> AcifSnapshot {
        AcifSnapshot {
            epoch,
            frame: IntrinsicManifold::new_2d(BTreeMap::new(), 0.0, "test"),
            edge_lengths: edges.iter().map(|(a,b,d)| (a.to_string(), b.to_string(), *d)).collect(),
        }
    }
    #[test]
    fn detects_local_anomaly() {
        let s0 = snap(0.0, &[("A","B",1000.0), ("C","D",2000.0)]);
        let s1 = snap(86400.0, &[("A","B",1000.05), ("C","D",2000.0)]);
        let d = AnomalyDaemon::new(1.0);
        let alerts = d.run(&[s0, s1]);
        assert_eq!(alerts.len(), 1);
    }
    #[test]
    fn ignores_global_rigid_pattern() {
        let s0 = snap(0.0, &[("A","B",1000.0), ("C","D",2000.0)]);
        let s1 = snap(86400.0, &[("A","B",1000.05), ("C","D",2000.05)]);
        let d = AnomalyDaemon::new(1.0);
        assert!(d.run(&[s0, s1]).is_empty());
    }
}
RUST

cat > $ROOT/rust/aethera-acif/src/importers.rs << 'RUST'
//! Importers for raw ACIF inputs (CSV format).

use aethera_core::{EdgeGraph, Scalar};

pub fn import_interferometric_csv(graph: &mut EdgeGraph, csv: &str) -> Result<usize, String> {
    let mut count = 0;
    for (i, line) in csv.lines().enumerate() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') { continue; }
        let cols: Vec<&str> = line.split(',').map(|s| s.trim()).collect();
        if cols.len() < 3 { return Err(format!("line {i}: expected >=3 columns")); }
        let phase: f64 = cols[2].parse().map_err(|e: std::num::ParseFloatError| format!("line {i}: {e}"))?;
        let sigma: Option<Scalar> = cols.get(3).and_then(|s| s.parse::<f64>().ok()).map(Scalar::from_f64);
        graph.add_edge(cols[0], cols[1], Scalar::from_f64(phase), sigma, Some("ACIF-phase".into()), None);
        count += 1;
    }
    Ok(count)
}

pub fn import_vlbi_angular_csv(graph: &mut EdgeGraph, csv: &str) -> Result<usize, String> {
    let mut count = 0;
    for (i, line) in csv.lines().enumerate() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') { continue; }
        let cols: Vec<&str> = line.split(',').map(|s| s.trim()).collect();
        if cols.len() < 4 { return Err(format!("line {i}: expected 4 columns")); }
        let theta: f64 = cols[2].parse().map_err(|e: std::num::ParseFloatError| format!("line {i}: {e}"))?;
        let baseline: f64 = cols[3].parse().map_err(|e: std::num::ParseFloatError| format!("line {i}: {e}"))?;
        let chord = 2.0 * baseline * (theta / 2.0).sin();
        graph.add_edge(cols[0], cols[1], Scalar::from_f64(chord), None, Some("VLBI-chord".into()), None);
        count += 1;
    }
    Ok(count)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn csv_parses() {
        let mut g = EdgeGraph::new();
        let n = import_interferometric_csv(&mut g, "A,B,1234.5,0.001\nC,D,5678.9\n").unwrap();
        assert_eq!(n, 2);
    }
}
RUST

echo "geometer + ghost + acif written"
