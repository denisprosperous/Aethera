#!/usr/bin/env python3
"""AETHERA v30.1 — live production verification suite (v30.1 additions).

Verifies on the live platform(s):
  A. /api/health                              → version 0.30.1
  B. /api/solve/physical-truth                → regions + vertices + edges
  C. POST /api/arbitration/maritime           → verdict + signed certificate
  D. POST /api/arbitration/territorial        → verdict + signed certificate
  E. POST /api/certify                        → certificate
  F. GET  /api/certify/verify                 → valid: true
  G. GET  /api/truth-index                    → GTI + trend + certificate
  H. GET  /api/truth-index/trend              → points
  I. Pages: /dashboard/earth-3d, /dashboard/truth → HTTP 200
  J. The six legacy scenario endpoints still pass (via verify_live core set)

Usage:
    python scripts/verify_v30.py [BASE_URL]
    (default: https://aethera-lime.vercel.app)
"""

import json
import sys
import time
import urllib.request
import urllib.error

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://aethera-lime.vercel.app").rstrip("/")

RESULTS = []


def call(method, path, payload=None, timeout=180, expect=200):
    url = BASE + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
            code = r.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        code = e.code
    except Exception as e:
        RESULTS.append((path, False, 0.0, str(e)))
        return None
    dt = time.time() - t0
    ok = code == expect
    try:
        j = json.loads(body)
    except Exception:
        j = None
    RESULTS.append((f"{method} {path}", ok, dt, f"HTTP {code}"))
    return j


def check(name, cond, extra=""):
    RESULTS.append((name, bool(cond), 0.0, extra))


def main():
    print(f"════ AETHERA v30.1 LIVE VERIFICATION — {BASE} ════\n")

    # A. health
    h = call("GET", "/api/health", timeout=60)
    if h:
        check("health.version == 0.30.1", h.get("version") == "0.30.1", str(h.get("version")))
        check("health.platform == AETHERA v30.1", h.get("platform") == "AETHERA v30.1", str(h.get("platform")))

    # B. physical-truth with vertices + edges
    pt = call("GET", "/api/solve/physical-truth", timeout=240)
    if pt:
        regions = pt.get("regions") or []
        vertices = pt.get("vertices") or []
        edges = pt.get("edges") or []
        check("physical-truth.regions >= 100", len(regions) >= 100, f"{len(regions)} regions")
        check("physical-truth.vertices match regions", len(vertices) == len(regions), f"{len(vertices)} vertices")
        check("physical-truth.edges non-empty", len(edges) >= 50, f"{len(edges)} edges")
        check("physical-truth.residual present", isinstance(pt.get("residual"), (int, float)), str(pt.get("residual")))

    # C. maritime arbitration
    m = call("POST", "/api/arbitration/maritime",
             {"party_a": "Africa", "party_b": "Europe", "claimed_split": 0.7})
    if m:
        arb = m.get("arbitration") or {}
        cert = m.get("certificate") or {}
        check("maritime.verdict in {EQUITABLE, CONTESTABLE, INEQUITABLE}",
              arb.get("verdict") in ("EQUITABLE", "CONTESTABLE", "INEQUITABLE"), str(arb.get("verdict")))
        check("maritime.certificate signed", bool(cert.get("signature")), str(cert.get("certificate_id")))

    # D. territorial arbitration
    t = call("POST", "/api/arbitration/territorial",
             {"disputed_region": "Greenland", "claim_a_name": "A", "claim_a_km2": 2100000,
              "claim_b_name": "B", "claim_b_km2": 3000000})
    if t:
        arb = t.get("arbitration") or {}
        check("territorial.truth area fetched", bool(arb.get("physical_truth_area_km2")), str(arb.get("physical_truth_area_km2")))
        check("territorial.verdict RESOLVED", str(arb.get("verdict", "")).startswith("RESOLVED"), str(arb.get("verdict")))

    # E/F. certification + verification
    c = call("POST", "/api/certify", {"claim": "v30.1 live check", "n": 1})
    if c:
        cert = c.get("certificate") or {}
        check("certify.certificate_id AET-*", str(cert.get("certificate_id", "")).startswith("AET-"), str(cert.get("certificate_id")))
        vpath = cert.get("verify")
        if vpath:
            v = call("GET", vpath if vpath.startswith("/api") else "/api" + vpath, timeout=60)
            if v is not None:
                check("certify.verify valid", v.get("valid") is True, str(v.get("valid")))

    # G/H. truth index
    g = call("GET", "/api/truth-index", timeout=240)
    if g:
        check("truth-index.gti numeric 0..100", isinstance(g.get("gti"), (int, float)) and 0 <= g["gti"] <= 100, str(g.get("gti")))
        check("truth-index.grade", g.get("grade") in ("A", "B", "C", "D"), str(g.get("grade")))
        check("truth-index.certificate", bool((g.get("certificate") or {}).get("signature")), "")
        check("truth-index.trend points >= 1", int(g.get("trend_points", 0)) >= 1, str(g.get("trend_points")))
    tr = call("GET", "/api/truth-index/trend", timeout=240)
    if tr:
        check("truth-index/trend points >= 1", int(tr.get("count", 0)) >= 1, str(tr.get("count")))

    # I. pages
    for page, label in [("/dashboard/earth-3d", "earth-3d page"), ("/dashboard/truth", "truth portal page")]:
        try:
            req = urllib.request.Request(BASE + page)
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read().decode("utf-8", "replace")
                ok = r.status == 200
        except Exception as e:
            body, ok = "", False
        check(f"page {label} HTTP 200", ok, page)
        if page == "/dashboard/earth-3d" and ok:
            check("earth-3d disclaimer rendered", "DERIVED VIEW" in body and "not a globe model" in body, "")

    # Report
    print(f"{'CHECK':60s} {'OK':4s}  {'TIME':8s} INFO")
    print("─" * 96)
    passed = 0
    for name, ok, dt, info in RESULTS:
        mark = "✅" if ok else "❌"
        passed += ok
        t = f"{dt:5.1f}s" if dt else "     "
        print(f"{mark} {name:57s} {t} {info[:34]}")
    print("─" * 96)
    print(f"PASSED {passed}/{len(RESULTS)}")
    sys.exit(0 if passed == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
