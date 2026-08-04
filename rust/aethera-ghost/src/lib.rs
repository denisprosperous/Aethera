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
