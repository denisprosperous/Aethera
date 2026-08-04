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
