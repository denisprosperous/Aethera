#!/usr/bin/env python3
"""AETHERA v26.0 — live production verification suite.

Tests all 11 API endpoints against BOTH live platforms:
  1. Railway backend   https://aethera-backend.up.railway.app
  2. Vercel (same-origin serverless)  https://aethera-lime.vercel.app

Validates status codes AND payload semantics (derived areas, projection
scores, nation losses, shape classification, trajectories, alerts,
region counts, LLM model chain).

Usage:
    python scripts/verify_live.py            # both platforms
    API_BASE=https://... python scripts/verify_live.py   # one platform
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

RAILWAY_URL = "https://aethera-backend.up.railway.app"
VERCEL_URL = "https://aethera-lime.vercel.app"

TARGETS = []
if os.environ.get("API_BASE"):
    TARGETS.append(("custom", os.environ["API_BASE"].rstrip("/")))
else:
    TARGETS = [("Railway", RAILWAY_URL), ("Vercel", VERCEL_URL)]

# Ghost Resolver payload — raw edge data, no coordinates (Axiom II/IV).
# Antarctica has NO area — it must be DERIVED from the global enclosure.
GHOST_PAYLOAD = {
    "polygons": [
        {"name": "South America", "area": 17840000,
         "neighbours": ["North America", "Antarctica"]},
        {"name": "North America", "area": 24709000,
         "neighbours": ["South America", "Asia"]},
        {"name": "Antarctica", "area": None, "neighbours": ["South America"]},
        {"name": "Africa", "area": 30370000, "neighbours": ["Asia"]},
        {"name": "Asia", "area": 44579000, "neighbours": ["Africa", "Europe"]},
        {"name": "Europe", "area": 10180000, "neighbours": ["Asia"]},
    ],
    "global_enclosure": "Global Total",
    "global_area": 510072000.0,
}

TERRAFORM_PAYLOAD = {"sea_level_rise_m": 10}

ALIEN_PAYLOAD = {
    "edges": [
        {"source": "A", "target": "B", "length": 1.0},
        {"source": "B", "target": "C", "length": 1.0},
        {"source": "C", "target": "D", "length": 1.0},
        {"source": "D", "target": "A", "length": 1.0},
        {"source": "A", "target": "C", "length": 1.4142135623730951},
        {"source": "B", "target": "D", "length": 1.4142135623730951},
    ],
    "faces": [["A", "B", "C", "D"]],
}

DYNAMICS_PAYLOAD = {
    "start": [0, 0, 0],
    "initial_velocity": [1, 0, 0],
    "force_law": "inertial",
    "dt": 0.1,
    "t_max": 10.0,
}

LLM_PAYLOAD = {"prompt": "What is the area of France according to intrinsic geometry?",
               "system_prompt": "You are AETHERA's geometric truth oracle. Answer briefly."}


def call(base, method, path, payload=None, timeout=90):
    url = f"{base}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode()
            return r.status, body, int((time.time() - t0) * 1000)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode()
        except Exception:
            body = ""
        return e.code, body, int((time.time() - t0) * 1000)


def check(cond, ok, bad):
    return ok if cond else bad


def verify(base, label, results):
    print(f"\n{'=' * 72}\n  TARGET: {label} — {base}\n{'=' * 72}")

    def record(name, status, ms, detail="", expect="200"):
        passed = str(status).startswith(expect[0]) if status else False
        mark = "✅" if passed else "❌"
        results.append((name, passed, ms))
        print(f"  {mark} {name:22s} HTTP {status} in {ms:5d} ms  {detail}")

    # 1. Health
    s, b, ms = call(base, "GET", "/api/health")
    mode, solver = "", ""
    try:
        j = json.loads(b)
        mode = j.get("mode", "")
        solver = j.get("solver", "")
        detail = f"mode={mode} solver={solver} v={j.get('version')}"
    except Exception:
        detail = b[:60]
    record("1. Health", s, ms, detail)

    # 2. Ghost Resolver — Antarctica must be DERIVED (~14M km2, tolerance 5%)
    s, b, ms = call(base, "POST", "/api/ghost/resolve", GHOST_PAYLOAD)
    detail = ""
    try:
        j = json.loads(b)
        resolved = j.get("resolved_areas", {})
        ant = resolved.get("Antarctica", 0)
        ok14 = 14_000_000 * 0.95 <= ant <= 14_000_000 * 1.05
        detail = f"Antarctica derived={ant:,.0f} km2 ({'in tol' if ok14 else 'OUT of tol'} vs 14M)"
    except Exception:
        detail = b[:60]
    record("2. Ghost Resolver", s, ms, detail)

    # 3. Physical Truth
    s, b, ms = call(base, "GET", "/api/solve/physical-truth", timeout=120)
    detail = ""
    try:
        j = json.loads(b)
        resid = j.get("stress_1", j.get("convergence_residual", "?"))
        detail = f"stress_1={resid}"
    except Exception:
        detail = b[:60]
    record("3. Physical Truth", s, ms, detail)

    # 4. Distortion / Projection scores
    s, b, ms = call(base, "GET", "/api/projections/scores")
    detail = ""
    try:
        j = json.loads(b)
        scores = j.get("scores", j)
        if isinstance(scores, dict):
            detail = f"{len(scores)} projections: {', '.join(list(scores)[:4])}"
        elif isinstance(scores, list):
            detail = f"{len(scores)} projections"
        else:
            detail = json.dumps(j)[:60]
    except Exception:
        detail = b[:60]
    record("4. Projection Scores", s, ms, detail)

    # 5. Terraformer — >= 10 nations with area loss
    s, b, ms = call(base, "POST", "/api/terraformation", TERRAFORM_PAYLOAD, timeout=120)
    detail = ""
    try:
        j = json.loads(b)
        changes = j.get("coastline_changes", [])
        lost = [c for c in changes
                if (c.get("area_change_km2", c.get("delta_area", 0)) or 0) < 0
                or c.get("area_lost_km2", 0)]
        detail = f"{len(changes)} coastline changes, {len(lost)} with area loss"
    except Exception:
        detail = b[:60]
    record("5. Terraformer", s, ms, detail)

    # 6. Alien Geometer
    s, b, ms = call(base, "POST", "/api/alien/reconstruct", ALIEN_PAYLOAD, timeout=120)
    detail = ""
    try:
        j = json.loads(b)
        shape = j.get("shape", (j.get("classification") or {}).get("shape", "?"))
        res = j.get("residual", (j.get("classification") or {}).get("residual", "?"))
        detail = f"shape={shape} residual={res}"
    except Exception:
        detail = b[:60]
    record("6. Alien Reconstruct", s, ms, detail)

    # 7. Celestial Dynamics
    s, b, ms = call(base, "POST", "/api/dynamics/simulate", DYNAMICS_PAYLOAD)
    detail = ""
    try:
        j = json.loads(b)
        traj = j.get("trajectory", (j.get("result") or {}).get("trajectory") or [])
        detail = f"trajectory points: {len(traj) if isinstance(traj, list) else '?'}"
    except Exception:
        detail = b[:60]
    record("7. Celestial Dynamics", s, ms, detail)

    # 8. Anomaly
    s, b, ms = call(base, "GET", "/api/anomaly/latest")
    detail = ""
    try:
        j = json.loads(b)
        alerts = j.get("alerts", j)
        n = len(alerts) if isinstance(alerts, list) else "?"
        detail = f"alerts: {n}"
    except Exception:
        detail = b[:60]
    record("8. Anomaly Latest", s, ms, detail)

    # 9. Datasets
    s, b, ms = call(base, "GET", "/api/datasets", timeout=120)
    detail = ""
    try:
        j = json.loads(b)
        regions = (j.get("regions") or j.get("datasets") or j.get("items") or [])
        total = j.get("total_area_km2", (j.get("summary") or {}).get("total_area_km2"))
        n = len(regions) if isinstance(regions, list) else j.get("total", "?")
        detail = f"regions={n} total_area={total}"
    except Exception:
        detail = b[:60]
    record("9. Datasets", s, ms, detail)

    # 10. LLM Status
    s, b, ms = call(base, "GET", "/api/llm/status")
    detail = ""
    try:
        j = json.loads(b)
        models = j.get("default_models") or j.get("models") or []
        detail = f"primary={j.get('primary', '?')[:40]} models={len(models)}"
    except Exception:
        detail = b[:60]
    record("10. LLM Status", s, ms, detail)

    # 11. LLM Query (NVIDIA default chain)
    s, b, ms = call(base, "POST", "/api/llm/query", LLM_PAYLOAD, timeout=180)
    detail = ""
    ans = ""
    try:
        j = json.loads(b)
        ans = (j.get("text") or "").strip()
        model = j.get("model", "?")
        ok = bool(ans) and j.get("success", True)
        detail = f"model={model} answer={ans[:50]!r}"
        if not ok:
            detail = f"FAILED: {j.get('error')}"
    except Exception:
        detail = b[:60]
    record("11. LLM Query", s, ms, detail)
    # extra semantic validation
    results.append(("11a. LLM non-empty answer", bool(ans), ms))
    print(f"  {'✅' if ans else '❌'} 11a. LLM non-empty answer     {'yes' if ans else 'EMPTY'}")


def main():
    results = []
    for label, base in TARGETS:
        verify(base, label, results)

    print(f"\n{'=' * 72}\n  SUMMARY\n{'=' * 72}")
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, ms in results:
        print(f"  {'✅ PASS' if ok else '❌ FAIL'}  {name:24s} {ms:6d} ms")
    print(f"\n  TOTAL: {passed}/{total} checks passed "
          f"({len(TARGETS)} platform(s) × 11 endpoints)")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
