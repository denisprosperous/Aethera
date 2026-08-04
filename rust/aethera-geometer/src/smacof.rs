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
    let (mut x, mut y, _) = classical_mds(&delta_f, 2);
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
