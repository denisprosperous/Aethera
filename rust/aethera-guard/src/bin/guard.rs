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
