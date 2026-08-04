//! Datum Bias Auditor (v6.0) — warning-level linter that scans for
//! hardcoded consensus constants. Default mode emits warnings and
//! exits 0; --strict mode exits 1 on findings.

use std::path::{Path, PathBuf};
use std::collections::HashSet;
use std::sync::OnceLock;
use thiserror::Error;
use regex::Regex;

#[derive(Debug, Error)]
pub enum ConsensusContaminationError {
    #[error("Forbidden numeric literal (>1e6) at {file}:{line}: {snippet}")]
    SuspiciousLargeConstant { file: String, line: usize, snippet: String },
    #[error("Forbidden gravitational constant at {file}:{line}: {snippet}")]
    GravitationalConstant { file: String, line: usize, snippet: String },
    #[error("Forbidden ephemeris import at {file}:{line}: {snippet}")]
    EphemerisImport { file: String, line: usize, snippet: String },
    #[error("Forbidden geodetic datum at {file}:{line}: {snippet}")]
    GeodeticDatum { file: String, line: usize, snippet: String },
    #[error("Forbidden standard gravity at {file}:{line}: {snippet}")]
    StandardGravity { file: String, line: usize, snippet: String },
}

#[derive(Debug, Clone)]
pub struct Finding {
    pub kind: FindingKind,
    pub file: PathBuf,
    pub line: usize,
    pub snippet: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FindingKind {
    SuspiciousLargeConstant,
    GravitationalConstant,
    EphemerisImport,
    GeodeticDatum,
    StandardGravity,
}

impl FindingKind {
    pub fn as_error(&self, file: &str, line: usize, snippet: &str) -> ConsensusContaminationError {
        match self {
            Self::SuspiciousLargeConstant => ConsensusContaminationError::SuspiciousLargeConstant { file: file.into(), line, snippet: snippet.into() },
            Self::GravitationalConstant => ConsensusContaminationError::GravitationalConstant { file: file.into(), line, snippet: snippet.into() },
            Self::EphemerisImport => ConsensusContaminationError::EphemerisImport { file: file.into(), line, snippet: snippet.into() },
            Self::GeodeticDatum => ConsensusContaminationError::GeodeticDatum { file: file.into(), line, snippet: snippet.into() },
            Self::StandardGravity => ConsensusContaminationError::StandardGravity { file: file.into(), line, snippet: snippet.into() },
        }
    }
}

fn large_numeric_re() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r"\b\d[\d_]*(\.\d+)?([eE][-+]?\d+)?\b").unwrap())
}
fn gravity_re() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r"(?i)\bG\s*[:=].*(gravity|gravitational|m\^?3|kg\^?-1|Newton)").unwrap())
}
fn ephem_re() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r#"(?i)\b(use|import|from|require)\s+[\w."']*(ephem|skyfield|spiceypy|astropy|pyerfa|skyfield_data|astroquery|jplephem)\b"#).unwrap())
}
fn datum_re() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r"(?i)\b(WGS84|WGS-84|EGM96|EGM-96|WMM\b|World Geodetic System|Geodetic Reference System 1980|GRS80)").unwrap())  // AETHERA-GUARD: ALLOW GUARD_SELF_TEST
}

pub fn scan_file(path: &Path) -> Vec<Finding> {
    let Ok(text) = std::fs::read_to_string(path) else { return vec![]; };
    let mut out = vec![];
    for (idx, raw) in text.lines().enumerate() {
        let line_no = idx + 1;
        if raw.contains("AETHERA-GUARD: ALLOW") { continue; }
        for m in large_numeric_re().captures_iter(raw) {
            let s = m.get(0).unwrap().as_str();
            let cleaned: String = s.chars().filter(|c| *c != '_').collect();
            if let Ok(v) = cleaned.parse::<f64>() {
                if v > 1.0e6 {
                    out.push(Finding { kind: FindingKind::SuspiciousLargeConstant, file: path.to_path_buf(), line: line_no, snippet: raw.trim().to_string() });
                }
            }
        }
        if raw.contains("6.674") || raw.contains("6_674") || gravity_re().is_match(raw) {  // AETHERA-GUARD: ALLOW GUARD_SELF_TEST
            out.push(Finding { kind: FindingKind::GravitationalConstant, file: path.to_path_buf(), line: line_no, snippet: raw.trim().to_string() });
        }
        if ephem_re().is_match(raw) {
            out.push(Finding { kind: FindingKind::EphemerisImport, file: path.to_path_buf(), line: line_no, snippet: raw.trim().to_string() });
        }
        if datum_re().is_match(raw) {
            out.push(Finding { kind: FindingKind::GeodeticDatum, file: path.to_path_buf(), line: line_no, snippet: raw.trim().to_string() });
        }
        if raw.contains("9.80665") || raw.contains("9_80665") {  // AETHERA-GUARD: ALLOW GUARD_SELF_TEST
            out.push(Finding { kind: FindingKind::StandardGravity, file: path.to_path_buf(), line: line_no, snippet: raw.trim().to_string() });
        }
    }
    out
}

pub fn scan_tree(root: &Path) -> Vec<Finding> {
    let mut findings = vec![];
    let skip: HashSet<&str> = ["target","node_modules",".git",".venv","__pycache__","dist","build",".next","site-packages"].iter().copied().collect();
    for entry in walkdir::WalkDir::new(root).into_iter().filter_entry(|e| {
        if e.file_type().is_dir() { let n = e.file_name().to_string_lossy(); !skip.contains(&*n) } else { true }
    }) {
        let Ok(entry) = entry else { continue };
        if !entry.file_type().is_file() { continue; }
        let path = entry.path();
        let ext = path.extension().and_then(|s| s.to_str()).unwrap_or("");
        if !matches!(ext, "rs"|"py"|"ts"|"tsx"|"js"|"jsx"|"toml"|"md") { continue; }
        findings.extend(scan_file(path));
    }
    findings
}

pub fn validate(findings: &[Finding]) -> Result<(), ConsensusContaminationError> {
    for f in findings {
        let file = f.file.to_string_lossy().to_string();
        return Err(f.kind.as_error(&file, f.line, &f.snippet));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] // AETHERA-GUARD: ALLOW GUARD_SELF_TEST
    fn detects_large() {
        let tmp = std::env::temp_dir().join("ag_large.txt");
        std::fs::write(&tmp, "let r = 6_371_000.0;\n").unwrap();  // AETHERA-GUARD: ALLOW GUARD_SELF_TEST
        let f = scan_file(&tmp);
        assert!(f.iter().any(|x| x.kind == FindingKind::SuspiciousLargeConstant));
        std::fs::remove_file(&tmp).ok();
    }
    #[test] // AETHERA-GUARD: ALLOW GUARD_SELF_TEST
    fn detects_gravity() {
        let tmp = std::env::temp_dir().join("ag_g.txt");
        std::fs::write(&tmp, "const G = 6.67430e-11;\n").unwrap();  // AETHERA-GUARD: ALLOW GUARD_SELF_TEST
        let f = scan_file(&tmp);
        assert!(f.iter().any(|x| x.kind == FindingKind::GravitationalConstant));
        std::fs::remove_file(&tmp).ok();
    }
    #[test] // AETHERA-GUARD: ALLOW GUARD_SELF_TEST
    fn allow_annotation_bypasses() {
        let tmp = std::env::temp_dir().join("ag_allow.txt");
        std::fs::write(&tmp, "let r = 6_371_000.0; // AETHERA-GUARD: ALLOW DOCUMENTATION\n").unwrap();
        let f = scan_file(&tmp);
        assert!(f.is_empty());
        std::fs::remove_file(&tmp).ok();
    }
}
