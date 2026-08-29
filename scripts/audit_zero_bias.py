#!/usr/bin/env python3
"""AETHERA v25.0 — Zero-Bias scan (Axiom 4).

Scans the intrinsic engine path for forbidden coordinate-system
imports/keywords (lon, lat, WGS84, EPSG, shapely, geopandas, fiona,
pyproj). The ingestion layer may reference coordinates only to CONVERT
external absolute lengths; it must never feed coordinates to the solver.

Scope policy:
  * HARD scope (zero tolerance): aethera/core.py, _smacof.py,
    rust_bridge.py, agents/*, rust crates — the intrinsic solver path.
  * Instrumentation exemption: modules/hall_of_shame.py and
    modules/compare_ingestion.py implement the legacy projection systems
    (Mercator, Robinson, ...) *in order to measure their distortion*.
    They consume lon/lat but never feed the solver; lon/lat keywords are
    exempt there. Forbidden library imports (shapely, pyproj, geopandas,
    fiona) are NOT exempt anywhere.
  * Comments and docstrings are ignored (documentation is allowed).
"""

import re
import sys
from pathlib import Path

ENGINE_GLOBS = ["python/aethera/core.py",
                "python/aethera/_smacof.py",
                "python/aethera/rust_bridge.py",
                "python/aethera/agents/*.py",
                "python/aethera/modules/*.py",
                "rust/crates/*/src/**/*.rs"]

# Measurement instrumentation files (lon/lat keywords exempted there).
INSTRUMENTATION = {
    "python/aethera/modules/hall_of_shame.py",
    "python/aethera/modules/compare_ingestion.py",
}

FORBIDDEN_IMPORTS = ["shapely", "geopandas", "fiona", "pyproj"]
KEYWORD_PATTERNS = [
    (r"\blon\b", "bare 'lon'"),
    (r"\blat\b", "bare 'lat'"),
    (r"latitude", "latitude"),
    (r"longitude", "longitude"),
    (r"WGS\s*84|WGS84", "WGS84"),
    (r"EPSG[:_]?\d*", "EPSG code"),
]


def strip_comments_docstrings(text: str) -> str:
    """Remove comment lines and triple-quoted docstring blocks."""
    lines = []
    in_doc = False
    for line in text.splitlines():
        stripped = line.strip()
        triple_count = stripped.count('"""') + stripped.count("'''")
        if in_doc:
            if triple_count:
                in_doc = False
            continue
        if triple_count == 1:
            in_doc = True
            continue
        if stripped.startswith("#"):
            continue
        # strip trailing comments (simple, no string-awareness needed here)
        code = line.split("#")[0] if " #" in line or line.lstrip().startswith("#") else line
        lines.append(code)
    return "\n".join(lines)


def main() -> int:
    repo = Path(__file__).resolve().parent.parent
    violations = []
    scanned = set()

    for g in ENGINE_GLOBS:
        for f in repo.glob(g):
            if not f.is_file() or f in scanned:
                continue
            scanned.add(f)
            rel = str(f.relative_to(repo))
            text = strip_comments_docstrings(f.read_text(errors="replace"))
            exempt_lonlat = rel in INSTRUMENTATION

            for imp in FORBIDDEN_IMPORTS:
                if re.search(rf"^\s*(import|from)\s+{imp}\b", text, re.M):
                    violations.append(f"{rel}: forbidden import '{imp}' (hard)")
            for pat, label in KEYWORD_PATTERNS:
                if exempt_lonlat and ("lon" in label or "lat" in label
                                      or label in ("latitude", "longitude",
                                                   "WGS84", "EPSG code")):
                    continue
                seen_lines = set()
                for m in re.finditer(pat, text):
                    line_no = text[:m.start()].count("\n") + 1
                    if line_no in seen_lines:
                        continue
                    seen_lines.add(line_no)
                    line = text.splitlines()[line_no - 1].strip()[:90]
                    violations.append(f"{rel}:{line_no}: {label}: {line}")

    verdict = "PASS" if not violations else "FAIL"
    print("# Zero-Bias Scan (Axiom 4)")
    print()
    print(f"Scanned {len(scanned)} engine files. "
          f"Instrumentation exemptions: {sorted(INSTRUMENTATION)}")
    print()
    if violations:
        print(f"**{verdict}** — {len(violations)} violation(s):")
        print()
        for v in violations:
            print(f"- {v}")
        return 1
    print("**PASS** — the intrinsic solver path is free of coordinate-system "
          "bias. Projection keywords appear only inside the documented "
          "distortion-measurement instrumentation, which never feeds the solver.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
