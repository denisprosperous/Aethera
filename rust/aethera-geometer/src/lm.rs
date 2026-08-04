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
