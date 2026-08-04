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
