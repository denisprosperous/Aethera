#!/bin/bash
# Reconstruct the AETHERA project from inline file contents.
# Each file is written with heredocs.

set -e
ROOT=/home/z/my-project/aethera-core

# ============================================================
# RUST: aethera-guard
# ============================================================

cat > $ROOT/rust/aethera-guard/Cargo.toml << 'TOML'
[package]
name = "aethera-guard"
version.workspace = true
edition.workspace = true
license.workspace = true

[lib]
name = "aethera_guard"
path = "src/lib.rs"

[[bin]]
name = "aethera-guard"
path = "src/bin/guard.rs"

[dependencies]
walkdir = "2"
regex = "1"
clap = { version = "4", features = ["derive"] }
serde = { workspace = true }
serde_json = { workspace = true }
thiserror = { workspace = true }
TOML

cat > $ROOT/rust/aethera-guard/src/lib.rs << 'RUST'
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
    R.get_or_init(|| Regex::new(r"(?i)\b(WGS84|WGS-84|EGM96|EGM-96|WMM\b|World Geodetic System|Geodetic Reference System 1980|GRS80)").unwrap())
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
        if raw.contains("6.674") || raw.contains("6_674") || gravity_re().is_match(raw) {
            out.push(Finding { kind: FindingKind::GravitationalConstant, file: path.to_path_buf(), line: line_no, snippet: raw.trim().to_string() });
        }
        if ephem_re().is_match(raw) {
            out.push(Finding { kind: FindingKind::EphemerisImport, file: path.to_path_buf(), line: line_no, snippet: raw.trim().to_string() });
        }
        if datum_re().is_match(raw) {
            out.push(Finding { kind: FindingKind::GeodeticDatum, file: path.to_path_buf(), line: line_no, snippet: raw.trim().to_string() });
        }
        if raw.contains("9.80665") || raw.contains("9_80665") {
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
RUST

cat > $ROOT/rust/aethera-guard/src/bin/guard.rs << 'RUST'
//! CLI for the Datum Bias Auditor (v6.0).
//! Default: warning mode (exit 0). --strict: exit 1. --interactive: prompt.

use clap::{Parser, Subcommand};
use aethera_guard::{scan_tree, validate};

#[derive(Parser)]
#[command(name = "aethera-guard", version, about = "Datum Bias Auditor (v6.0) — warning-level linter")]
struct Cli { #[command(subcommand)] cmd: Cmd }

#[derive(Subcommand)]
enum Cmd {
    Audit { path: String, #[arg(long)] strict: bool, #[arg(long)] interactive: bool },
    Scan { path: String },
    Validate { path: String },
}

fn main() {
    let cli = Cli::parse();
    match cli.cmd {
        Cmd::Scan { path } => run(&path, false),
        Cmd::Validate { path } => run(&path, true),
        Cmd::Audit { path, strict, interactive } => { let _ = interactive; run(&path, strict) },
    }
}

fn run(path: &str, strict: bool) {
    let findings = scan_tree(std::path::Path::new(path));
    if findings.is_empty() {
        println!("datum-bias-auditor: clean — no hardcoded consensus constants detected.");
        return;
    }
    eprintln!("datum-bias-auditor: {} finding(s):", findings.len());
    for f in &findings {
        eprintln!("  WARNING  {:?}  {}:{}  | {}", f.kind, f.file.display(), f.line, f.snippet);
    }
    eprintln!("\n(v6.0 mode: warning-level. Build NOT halted.)");
    if strict {
        if let Err(e) = validate(&findings) {
            eprintln!("\nSTRICT MODE — failing build.\n{e}");
            std::process::exit(1);
        }
    }
}
RUST

# ============================================================
# RUST: aethera-core
# ============================================================

cat > $ROOT/rust/aethera-core/Cargo.toml << 'TOML'
[package]
name = "aethera-core"
version.workspace = true
edition.workspace = true
license.workspace = true

[lib]
name = "aethera_core"
path = "src/lib.rs"

[dependencies]
rug = { workspace = true }
serde = { workspace = true }
serde_json = { workspace = true }
thiserror = { workspace = true }
nalgebra = { workspace = true }
rayon = { workspace = true }
tracing = { workspace = true }
TOML

cat > $ROOT/rust/aethera-core/src/lib.rs << 'RUST'
//! Shared types for AETHERA. The fundamental datum is the Edge: an
//! absolute scalar distance between two named nodes, stripped of any
//! interpretation (no assumed radius, geoid, or gravity).

pub mod scalar;
pub mod graph;
pub mod manifold;
pub mod layers;
pub mod errors;

pub use scalar::Scalar;
pub use graph::{EdgeGraph, NodeId, EdgeId, Edge};
pub use manifold::{IntrinsicManifold, Embedding, Point3};
pub use layers::{ScalarFieldLayer, LayerManager};
pub use errors::{AetheraError, Result};
RUST

cat > $ROOT/rust/aethera-core/src/scalar.rs << 'RUST'
//! Arbitrary-precision scalar wrapper around rug::Float at 256-bit default.

use rug::Float;
use rug::float::Round;
use rug::ops::AssignRound;
use serde::{Deserialize, Serialize};

pub const DEFAULT_PRECISION: u32 = 256;

#[derive(Clone, Debug)]
pub struct Scalar { val: Float }

impl Scalar {
    pub fn from_f64(v: f64) -> Self { Self { val: Float::with_val(DEFAULT_PRECISION, v) } }
    pub fn from_i64(v: i64) -> Self { Self { val: Float::with_val(DEFAULT_PRECISION, v) } }
    pub fn from_str(s: &str) -> Result<Self, String> {
        match Float::parse(s) {
            Ok(p) => Ok(Self { val: Float::with_val(DEFAULT_PRECISION, p) }),
            Err(e) => Err(format!("invalid scalar {s:?}: {e}")),
        }
    }
    pub fn to_f64(&self) -> f64 { self.val.to_f64() }
    pub fn raw(&self) -> &Float { &self.val }
    pub fn from_float(f: Float) -> Self { Self { val: f } }
}

impl std::ops::Add for Scalar {
    type Output = Scalar;
    fn add(self, rhs: Self) -> Self {
        let p = self.val.prec().max(rhs.val.prec());
        let mut out = Float::new(p);
        out.assign_round(&self.val + &rhs.val, Round::Nearest);
        Scalar { val: out }
    }
}
impl std::ops::Sub for Scalar {
    type Output = Scalar;
    fn sub(self, rhs: Self) -> Self {
        let p = self.val.prec().max(rhs.val.prec());
        let mut out = Float::new(p);
        out.assign_round(&self.val - &rhs.val, Round::Nearest);
        Scalar { val: out }
    }
}
impl std::ops::Mul for Scalar {
    type Output = Scalar;
    fn mul(self, rhs: Self) -> Self {
        let p = self.val.prec().max(rhs.val.prec());
        let mut out = Float::new(p);
        out.assign_round(&self.val * &rhs.val, Round::Nearest);
        Scalar { val: out }
    }
}
impl std::ops::Div for Scalar {
    type Output = Scalar;
    fn div(self, rhs: Self) -> Self {
        let p = self.val.prec().max(rhs.val.prec());
        let mut out = Float::new(p);
        out.assign_round(&self.val / &rhs.val, Round::Nearest);
        Scalar { val: out }
    }
}
impl PartialOrd for Scalar {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> { self.val.partial_cmp(&other.val) }
}
impl PartialEq for Scalar {
    fn eq(&self, other: &Self) -> bool { self.val == other.val }
}
impl std::fmt::Display for Scalar {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result { write!(f, "{:.30}", self.val) }
}
impl Serialize for Scalar {
    fn serialize<S: serde::Serializer>(&self, s: S) -> Result<S::Ok, S::Error> { s.serialize_str(&self.to_string()) }
}
impl<'de> Deserialize<'de> for Scalar {
    fn deserialize<D: serde::Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        let s = String::deserialize(d)?;
        Scalar::from_str(&s).map_err(serde::de::Error::custom)
    }
}

pub fn sqrt(s: &Scalar) -> Scalar {
    let mut out = Float::new(s.val.prec());
    let r = s.val.clone().sqrt();
    out.assign_round(r, Round::Nearest);
    Scalar { val: out }
}
pub fn sq(s: &Scalar) -> Scalar { s.clone() * s.clone() }

#[cfg(test)]
mod tests {
    use super::*;
    #[test] // AETHERA-GUARD: ALLOW GUARD_SELF_TEST
    fn arithmetic() {
        let a = Scalar::from_f64(3.0);
        let b = Scalar::from_f64(4.0);
        let c = sqrt(&(sq(&a) + sq(&b)));
        assert!((c.to_f64() - 5.0).abs() < 1e-20);
    }
    #[test] // AETHERA-GUARD: ALLOW GUARD_SELF_TEST
    fn precision_preserved() {
        let a = Scalar::from_str("1").unwrap();
        let b = Scalar::from_str("3").unwrap();
        let c = a / b;
        let s = c.to_string();
        let three_count = s.chars().filter(|&c| c == '3').count();
        assert!(three_count >= 25, "got {three_count} threes in: {s}");
    }
}
RUST

cat > $ROOT/rust/aethera-core/src/graph.rs << 'RUST'
//! Edge-weighted graph. Nodes are string IDs; edges carry arbitrary-precision scalars.

use crate::Scalar;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::sync::atomic::{AtomicU64, Ordering};

pub type NodeId = u64;
static NEXT_ID: AtomicU64 = AtomicU64::new(1);
pub fn fresh_node_id() -> NodeId { NEXT_ID.fetch_add(1, Ordering::Relaxed) }

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize, PartialOrd, Ord)]
pub struct EdgeId(pub u64);

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Edge {
    pub id: EdgeId,
    pub a: NodeId,
    pub b: NodeId,
    pub weight: Scalar,
    pub sigma: Option<Scalar>,
    pub source: Option<String>,
    pub epoch: Option<f64>,
}

#[derive(Debug, Default, Clone, Serialize, Deserialize)]
pub struct EdgeGraph {
    pub nodes: BTreeMap<NodeId, String>,
    pub name_index: BTreeMap<String, NodeId>,
    pub edges: BTreeMap<EdgeId, Edge>,
    pub adj: BTreeMap<NodeId, Vec<(EdgeId, NodeId)>>,
    next_edge: u64,
}

impl EdgeGraph {
    pub fn new() -> Self { Self::default() }
    pub fn add_node(&mut self, name: impl Into<String>) -> NodeId {
        let name = name.into();
        if let Some(&id) = self.name_index.get(&name) { return id; }
        let id = fresh_node_id();
        self.nodes.insert(id, name.clone());
        self.name_index.insert(name, id);
        self.adj.entry(id).or_default();
        id
    }
    pub fn node_name(&self, id: NodeId) -> Option<&str> { self.nodes.get(&id).map(|s| s.as_str()) }
    pub fn node_id(&self, name: &str) -> Option<NodeId> { self.name_index.get(name).copied() }
    pub fn add_edge(&mut self, a: impl Into<String>, b: impl Into<String>, weight: Scalar, sigma: Option<Scalar>, source: Option<String>, epoch: Option<f64>) -> EdgeId {
        let na = self.add_node(a);
        let nb = self.add_node(b);
        let id = EdgeId(self.next_edge);
        self.next_edge += 1;
        let edge = Edge { id, a: na, b: nb, weight, sigma, source, epoch };
        self.edges.insert(id, edge.clone());
        self.adj.entry(na).or_default().push((id, nb));
        self.adj.entry(nb).or_default().push((id, na));
        id
    }
    pub fn edge_count(&self) -> usize { self.edges.len() }
    pub fn node_count(&self) -> usize { self.nodes.len() }
    pub fn to_json(&self) -> serde_json::Result<String> { serde_json::to_string_pretty(self) }
    pub fn from_json(s: &str) -> serde_json::Result<Self> { serde_json::from_str(s) }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn build_triangle() {
        let mut g = EdgeGraph::new();
        g.add_edge("A","B", Scalar::from_f64(3.0), None, None, None);
        g.add_edge("B","C", Scalar::from_f64(4.0), None, None, None);
        g.add_edge("A","C", Scalar::from_f64(5.0), None, None, None);
        assert_eq!(g.node_count(), 3);
        assert_eq!(g.edge_count(), 3);
    }
}
RUST

cat > $ROOT/rust/aethera-core/src/manifold.rs << 'RUST'
//! Reconstructed intrinsic manifold — output of the Intrinsic Geometer.

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use crate::graph::NodeId;

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct Point3 { pub x: f64, pub y: f64, pub z: f64 }
impl Point3 {
    pub fn new(x: f64, y: f64, z: f64) -> Self { Self { x, y, z } }
    pub fn dist(&self, other: &Self) -> f64 {
        let dx = self.x - other.x;
        let dy = self.y - other.y;
        let dz = self.z - other.z;
        (dx*dx + dy*dy + dz*dz).sqrt()
    }
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum Embedding { Planar2D, Spatial3D }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IntrinsicManifold {
    pub embedding: Embedding,
    pub coords: BTreeMap<NodeId, Point3>,
    pub residual: f64,
    pub gaussian_curvature: BTreeMap<NodeId, f64>,
    pub origin: String,
}

impl IntrinsicManifold {
    pub fn new_2d(coords: BTreeMap<NodeId, Point3>, residual: f64, origin: impl Into<String>) -> Self {
        Self { embedding: Embedding::Planar2D, coords, residual, gaussian_curvature: BTreeMap::new(), origin: origin.into() }
    }
    pub fn to_json(&self) -> serde_json::Result<String> { serde_json::to_string_pretty(self) }
}
RUST

cat > $ROOT/rust/aethera-core/src/layers.rs << 'RUST'
//! Scalar Field Layers — vertex-attributed scalar data (density, pressure, etc.)
//! overlaid on the manifold. Never inferred from edge-density; always user-supplied.

use serde::{Deserialize, Serialize};
use crate::graph::NodeId;
use crate::manifold::Point3;
use std::collections::BTreeMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScalarFieldLayer {
    pub name: String,
    pub unit: String,
    pub values: BTreeMap<NodeId, f64>,
    pub source: Option<String>,
    pub epoch: Option<f64>,
}

impl ScalarFieldLayer {
    pub fn new(name: impl Into<String>, unit: impl Into<String>) -> Self {
        Self { name: name.into(), unit: unit.into(), values: BTreeMap::new(), source: None, epoch: None }
    }
    pub fn set(&mut self, node: NodeId, v: f64) { self.values.insert(node, v); }
    pub fn get(&self, node: NodeId) -> Option<f64> { self.values.get(&node).copied() }
    pub fn interpolate_at(&self, coords: &BTreeMap<NodeId, Point3>, pos: Point3, k: usize) -> Option<f64> {
        if self.values.is_empty() { return None; }
        let mut dists: Vec<(f64, f64)> = coords.iter()
            .filter_map(|(id, p)| self.values.get(id).map(|v| (p.dist(&pos), *v)))
            .collect();
        dists.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap_or(std::cmp::Ordering::Equal));
        dists.truncate(k);
        if dists.is_empty() { return None; }
        let mut w_sum = 0.0_f64; let mut v_sum = 0.0_f64;
        for (d, v) in &dists { let w = 1.0 / d.max(1e-12).powi(2); w_sum += w; v_sum += w * v; }
        if w_sum > 0.0 { Some(v_sum / w_sum) } else { None }
    }
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct LayerManager {
    pub layers: BTreeMap<String, ScalarFieldLayer>,
}

impl LayerManager {
    pub fn new() -> Self { Self::default() }
    pub fn add_layer(&mut self, layer: ScalarFieldLayer) { self.layers.insert(layer.name.clone(), layer); }
    pub fn get_layer(&self, name: &str) -> Option<&ScalarFieldLayer> { self.layers.get(name) }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn layer_basic() {
        let mut l = ScalarFieldLayer::new("density", "kg/m³");
        l.set(1, 1.225);
        assert_eq!(l.get(1), Some(1.225));
    }
}
RUST

cat > $ROOT/rust/aethera-core/src/errors.rs << 'RUST'
use thiserror::Error;

#[derive(Debug, Error)]
pub enum AetheraError {
    #[error("underconstrained: {0} nodes, {1} edges")]
    Underconstrained(usize, usize),
    #[error("disconnected graph: {0}")]
    Disconnected(String),
    #[error("solver did not converge in {0} iterations (residual = {1})")]
    NoConverge(usize, f64),
    #[error("invalid input: {0}")]
    InvalidInput(String),
}

pub type Result<T> = std::result::Result<T, AetheraError>;
RUST

echo "aethera-core written"
