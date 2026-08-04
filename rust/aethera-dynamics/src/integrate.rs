//! Mode B — User-Defined Force-Field Simulation (RK4).
//! User supplies the acceleration field; platform never hardcodes G.
//! Does NOT accept 'target'; does NOT return azimuth/elevation/impact_point.

use crate::{DynamicsError, Result, ETHICS_NOTE};
use serde::{Deserialize, Serialize};

pub trait AccelerationField: Send + Sync {
    fn accel(&self, pos: (f64, f64, f64), vel: (f64, f64, f64), t: f64) -> (f64, f64, f64);
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ForceFieldConfig {
    pub dt: f64,
    pub t_max: f64,
    pub force_law_note: String,
}
impl Default for ForceFieldConfig {
    fn default() -> Self { Self { dt: 0.01, t_max: 100.0, force_law_note: "user-supplied".into() } }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SimulationResult {
    pub trajectory: Vec<(f64, f64, f64)>,
    pub times: Vec<f64>,
    pub total_path_length: f64,
    pub total_time: f64,
    pub final_position: (f64, f64, f64),
    pub final_velocity: (f64, f64, f64),
    pub note: String,
}

pub fn simulate_particle(start: (f64, f64, f64), vel0: (f64, f64, f64), field: &dyn AccelerationField, cfg: &ForceFieldConfig) -> Result<SimulationResult> {
    if cfg.dt <= 0.0 { return Err(DynamicsError::IntegrationFailed("dt must be > 0".into())); }
    if cfg.t_max <= 0.0 { return Err(DynamicsError::IntegrationFailed("t_max must be > 0".into())); }
    let mut trajectory = vec![start]; let mut times = vec![0.0];
    let mut pos = start; let mut vel = vel0; let mut t = 0.0_f64; let mut total = 0.0_f64;
    let n = (cfg.t_max / cfg.dt).ceil() as usize;
    let n = n.min(10_000_000); // AETHERA-GUARD: ALLOW DOCUMENTATION (iteration cap)
    for _ in 0..n {
        if t >= cfg.t_max - 1e-12 { break; }
        let (np, nv, nt) = rk4_step(pos, vel, t, cfg.dt, field);
        let dx = np.0 - pos.0; let dy = np.1 - pos.1; let dz = np.2 - pos.2;
        total += (dx*dx + dy*dy + dz*dz).sqrt();
        pos = np; vel = nv; t = nt;
        trajectory.push(pos); times.push(t);
        if t >= cfg.t_max { break; }
    }
    Ok(SimulationResult {
        trajectory, times, total_path_length: total, total_time: t,
        final_position: pos, final_velocity: vel,
        note: format!("Force law: {}. Path: {:.6}. Time: {:.6}s. {ETHICS_NOTE}", cfg.force_law_note, total, t),
    })
}

fn rk4_step(pos: (f64,f64,f64), vel: (f64,f64,f64), t: f64, dt: f64, field: &dyn AccelerationField) -> ((f64,f64,f64), (f64,f64,f64), f64) {
    let a1 = field.accel(pos, vel, t);
    let k1p = vel; let k1v = a1;
    let p2 = (pos.0 + 0.5*dt*k1p.0, pos.1 + 0.5*dt*k1p.1, pos.2 + 0.5*dt*k1p.2);
    let v2 = (vel.0 + 0.5*dt*k1v.0, vel.1 + 0.5*dt*k1v.1, vel.2 + 0.5*dt*k1v.2);
    let a2 = field.accel(p2, v2, t + 0.5*dt);
    let k2p = v2; let k2v = a2;
    let p3 = (pos.0 + 0.5*dt*k2p.0, pos.1 + 0.5*dt*k2p.1, pos.2 + 0.5*dt*k2p.2);
    let v3 = (vel.0 + 0.5*dt*k2v.0, vel.1 + 0.5*dt*k2v.1, vel.2 + 0.5*dt*k2v.2);
    let a3 = field.accel(p3, v3, t + 0.5*dt);
    let k3p = v3; let k3v = a3;
    let p4 = (pos.0 + dt*k3p.0, pos.1 + dt*k3p.1, pos.2 + dt*k3p.2);
    let v4 = (vel.0 + dt*k3v.0, vel.1 + dt*k3v.1, vel.2 + dt*k3v.2);
    let a4 = field.accel(p4, v4, t + dt);
    let k4p = v4; let k4v = a4;
    let np = (
        pos.0 + dt/6.0 * (k1p.0 + 2.0*k2p.0 + 2.0*k3p.0 + k4p.0),
        pos.1 + dt/6.0 * (k1p.1 + 2.0*k2p.1 + 2.0*k3p.1 + k4p.1),
        pos.2 + dt/6.0 * (k1p.2 + 2.0*k2p.2 + 2.0*k3p.2 + k4p.2),
    );
    let nv = (
        vel.0 + dt/6.0 * (k1v.0 + 2.0*k2v.0 + 2.0*k3v.0 + k4v.0),
        vel.1 + dt/6.0 * (k1v.1 + 2.0*k2v.1 + 2.0*k3v.1 + k4v.1),
        vel.2 + dt/6.0 * (k1v.2 + 2.0*k2v.2 + 2.0*k3v.2 + k4v.2),
    );
    (np, nv, t + dt)
}

// Built-in example fields (user-supplied μ, NOT hardcoded G).
pub struct InertialField;
impl AccelerationField for InertialField {
    fn accel(&self, _pos: (f64,f64,f64), _vel: (f64,f64,f64), _t: f64) -> (f64, f64, f64) { (0.0, 0.0, 0.0) }
}
pub struct InverseSquareField { pub mu: f64, pub center: (f64, f64, f64) }
impl AccelerationField for InverseSquareField {
    fn accel(&self, pos: (f64,f64,f64), _vel: (f64,f64,f64), _t: f64) -> (f64,f64,f64) {
        let dx = pos.0 - self.center.0; let dy = pos.1 - self.center.1; let dz = pos.2 - self.center.2;
        let r2 = dx*dx + dy*dy + dz*dz;
        let r = r2.sqrt().max(1e-12);
        let a = -self.mu / r2.max(1e-12);
        (a*dx/r, a*dy/r, a*dz/r)
    }
}
pub struct UniformField { pub accel: (f64, f64, f64) }
impl AccelerationField for UniformField {
    fn accel(&self, _pos: (f64,f64,f64), _vel: (f64,f64,f64), _t: f64) -> (f64, f64, f64) { self.accel }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn inertial_straight_line() {
        let r = simulate_particle((0.0,0.0,0.0), (1.0,0.0,0.0), &InertialField, &ForceFieldConfig { dt: 0.1, t_max: 10.0, force_law_note: "inertial".into() }).unwrap();
        assert!((r.final_position.0 - 10.0).abs() < 1e-3);
        assert!(r.note.contains("Targeting solutions"));
    }
    #[test]
    fn inverse_square_orbit() {
        let f = InverseSquareField { mu: 1.0, center: (0.0,0.0,0.0) };
        let r = simulate_particle((1.0,0.0,0.0), (0.0,1.0,0.0), &f, &ForceFieldConfig { dt: 0.001, t_max: 6.2832, force_law_note: "inverse-square".into() }).unwrap();
        assert!((r.final_position.0 - 1.0).abs() < 0.05);
    }
    #[test]
    fn uniform_field_parabola() {
        let f = UniformField { accel: (0.0, -1.0, 0.0) };
        let r = simulate_particle((0.0,0.0,0.0), (1.0,0.0,0.0), &f, &ForceFieldConfig { dt: 0.01, t_max: 2.0, force_law_note: "uniform".into() }).unwrap();
        assert!((r.final_position.0 - 2.0).abs() < 1e-3);
        assert!((r.final_position.1 - (-2.0)).abs() < 1e-3);
    }
}
