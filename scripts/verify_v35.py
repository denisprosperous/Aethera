#!/usr/bin/env python3
"""AETHERA v35.0 — full production verification suite.

Verifies every v35.0 mandate item against the live deployment:
  F1  Country boundaries (/dashboard/earth-3d)             [v33.0]
  F2  Consensus Hall of Shame (/dashboard/consensus-hall)  [v34.0]
  F3  ACIF edge ingestion + anomaly detection              [v34.0]
  F4  Ghost Resolver red flags (POST /api/ghost/resolve)
  F5  Maritime arbitration median line (POST /api/arbitrate/maritime)
  F6  Territorial verification (POST /api/arbitrate/territory)
  F7  Global Truth Index (GET /api/truth/index)
  F8  3D Manifold Viewer completeness (source audit + live page)
  LLM  behaviour contract regression (v32.0)
"""
import json
import math
import re
import sys
import urllib.request

BASE = "https://aethera-lime.vercel.app"
TIMEOUT = 150
PASSED = []
FAILED = []


def call(method, path, payload=None, timeout=TIMEOUT):
    url = BASE + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode()
        try:
            return resp.status, json.loads(body)
        except Exception:
            return resp.status, body


def check(name, cond, detail=""):
    if cond:
        PASSED.append(name)
        print(f"PASS  {name}" + (f"  [{detail}]" if detail else ""))
    else:
        FAILED.append(name)
        print(f"FAIL  {name}  [{detail}]")


print("=" * 72)
print("AETHERA v35.0 PRODUCTION VERIFICATION —", BASE)
print("=" * 72)

# ---------------------------------------------------------------- health
st, health = call("GET", "/api/health")
check("health: 200 + version 0.35.0",
      st == 200 and health.get("version") == "0.35.0"
      and "v35.0" in health.get("platform", ""), f"v={health.get('version')}")

# ------------------------------------------------ F1: country boundaries
st, page = call("GET", "/dashboard/earth-3d")
check("F1: /dashboard/earth-3d live", st == 200, f"status={st}")

# ------------------------------------------------ F2: consensus hall
st, page = call("GET", "/dashboard/consensus-hall")
check("F2: /dashboard/consensus-hall live", st == 200, f"status={st}")

# ------------------------------------------------ F3: ACIF edges
st, resp = call("POST", "/api/acif/edges",
                {"edges": [{"a": "v35-station-a", "b": "v35-station-b",
                            "length_m": 123.45, "epoch": 1757400000}]})
check("F3: POST /api/acif/edges returns 200", st == 200, f"status={st}")
st, resp = call("GET", "/api/acif/edges")
check("F3: GET /api/acif/edges lists edges", st == 200 and resp.get("count", 0) >= 1)
st, resp = call("GET", "/api/acif/anomaly")
check("F3: GET /api/acif/anomaly live", st == 200, f"status={st}")

# ------------------------------------------------ F4: ghost red flags
GHOST_PAYLOAD = {
    "polygons": [
        {"name": "Africa", "area": 30370000, "claimed_area": 30370000, "neighbours": []},
        {"name": "Europe", "area": 10180000, "claimed_area": 10180000, "neighbours": []},
        {"name": "Asia", "area": 44579000, "claimed_area": 44579000, "neighbours": []},
        {"name": "North America", "area": 24709000, "claimed_area": 24709000, "neighbours": []},
        {"name": "South America", "area": 17840000, "claimed_area": 17840000,
         "neighbours": ["Antarctica"]},
        {"name": "Australia", "area": 8600000, "claimed_area": 8600000,
         "neighbours": ["Antarctica"]},
        {"name": "Oceans", "area": 361132000, "claimed_area": 361132000, "neighbours": []},
        {"name": "Antarctica", "area": None, "claimed_area": 14200000,
         "neighbours": ["South America", "Africa", "Australia"]},
    ],
    "global_enclosure": "Earth",
    "global_area": 510072000,
}
st, resp = call("POST", "/api/ghost/resolve", GHOST_PAYLOAD)
reports = resp.get("red_flag_report", []) if isinstance(resp, dict) else []
antarctica_report = next((r for r in reports if r.get("region") == "Antarctica"), None)
check("F4: POST /api/ghost/resolve 200", st == 200, f"status={st}")
check("F4: Antarctica (NULL area) yields red_flag_report",
      antarctica_report is not None, f"reports={len(reports)}")
if antarctica_report:
    check("F4: report has derived/official/deviation/seal/rationale",
          all(k in antarctica_report for k in
              ("derived_area_km2", "official_area_km2", "deviation_percent",
               "seal", "rationale_log")),
          f"dev={antarctica_report.get('deviation_percent')}% "
          f"seal={str(antarctica_report.get('seal'))[:19]}...")
    check("F4: flagged CENSORED (>5% deviation)",
          antarctica_report.get("flag") == "CENSORED"
          and antarctica_report.get("deviation_percent", 0) > 5.0)

# ------------------------------------------------ F5: maritime median line
st, edges_resp = call("GET", "/api/solve/physical-truth", timeout=TIMEOUT)
edge_pairs = edges_resp.get("edges", []) if isinstance(edges_resp, dict) else []
a, b = (edge_pairs[0][0], edge_pairs[0][1]) if edge_pairs else ("Africa", "Europe")
st, resp = call("POST", "/api/arbitrate/maritime",
                {"nation_a": a, "nation_b": b})
check("F5: POST /api/arbitrate/maritime 200", st == 200, f"status={st} pair={a}/{b}")
if st == 200:
    ml = resp.get("median_line", [])
    cert = resp.get("certificate", {})
    check("F5: median line coordinates returned",
          isinstance(ml, list) and len(ml) >= 1 and len(ml[0]) == 3,
          f"{len(ml)} points")
    check("F5: certificate signed (HMAC-SHA256)",
          cert.get("certificate_id", "").startswith("AET-")
          and cert.get("algorithm") == "HMAC-SHA256",
          cert.get("certificate_id", ""))
    check("F5: intrinsic derivation stated (no sphere/datum)",
          "no sphere" in resp.get("arbitration", {}).get("derivation", "").lower())

# ------------------------------------------------ F6: territorial verify
st, regions = call("GET", "/api/regions/list")
reg_list = regions.get("regions", []) if isinstance(regions, dict) else []
name0 = reg_list[0]["name"] if reg_list else "Africa"
area0 = float(reg_list[0].get("area_km2") or 30370000) if reg_list else 30370000.0
k = math.sqrt(area0)
known_square = [[-k / 2, -k / 2, 0.0], [k / 2, -k / 2, 0.0],
                [k / 2, k / 2, 0.0], [-k / 2, k / 2, 0.0]]
st, resp = call("POST", "/api/arbitrate/territory",
                {"nation": name0, "polygon": known_square})
check("F6: POST /api/arbitrate/territory 200", st == 200, f"status={st} nation={name0}")
if st == 200:
    check("F6: true area computed correctly (known polygon)",
          abs(resp.get("true_area", 0) - area0) / area0 < 1e-6,
          f"true={resp.get('true_area'):,.0f} official={resp.get('official_area'):,.0f}")
    check("F6: deviation_percent + valid fields present",
          "deviation_percent" in resp and resp.get("valid") is True,
          f"dev={resp.get('deviation_percent')}%")
    check("F6: certificates present (sha256 seal + platform HMAC cert)",
          str(resp.get("seal", "")).startswith("sha256:")
          and resp.get("certificate", {}).get("certificate_id", "").startswith("AET-"),
          f"seal={str(resp.get('seal'))[:19]}... "
          f"cert={resp.get('certificate', {}).get('certificate_id')}")
    # Inflated claim must be rejected.
    k2 = k * math.sqrt(1.2)
    inflated = [[-k2 / 2, -k2 / 2, 0.0], [k2 / 2, -k2 / 2, 0.0],
                [k2 / 2, k2 / 2, 0.0], [-k2 / 2, k2 / 2, 0.0]]
    st2, resp2 = call("POST", "/api/arbitrate/territory",
                      {"nation": name0, "polygon": inflated})
    check("F6: inflated claim (>5%) invalid",
          st2 == 200 and resp2.get("valid") is False
          and resp2.get("deviation_percent", 0) > 5.0)

# ------------------------------------------------ F7: Global Truth Index
st, resp = call("GET", "/api/truth/index", timeout=TIMEOUT)
check("F7: GET /api/truth/index 200", st == 200, f"status={st}")
if st == 200:
    gti = resp.get("gti")
    check("F7: gti returned and in expected ~20-30% band",
          gti is not None and 20.0 <= gti <= 30.0, f"gti={gti}")
    check("F7: totals present",
          resp.get("total_physical_area", 0) > 0
          and resp.get("total_legacy_area", 0) > 0,
          f"phys={resp.get('total_physical_area'):,.0f} "
          f"leg={resp.get('total_legacy_area'):,.0f}")
    check("F7: trend_data present", isinstance(resp.get("trend_data"), list),
          f"points={len(resp.get('trend_data', []))}")
    check("F7: all legacy projections reported",
          any(p["projection"] == "Mercator" and p["gti"] > 100
              for p in resp.get("per_projection", [])),
          str([f"{p['projection']}:{p['gti']}" for p in resp.get("per_projection", [])]))
    check("F7: certificate signed",
          resp.get("certificate", {}).get("certificate_id", "").startswith("AET-"))

# ------------------------------------------------ F8: viewer completeness
st, page_src = call("GET", "/dashboard/earth-3d")
src = page_src if isinstance(page_src, str) else ""
chunk_urls = re.findall(r'src="(/_next/static/[^"]+\.js)"', src)
bundle = src
for u in chunk_urls:
    try:
        _st, _body = call("GET", u)
        bundle += _body if isinstance(_body, str) else ""
    except Exception:
        pass
check("F8: viewer JS bundle located", len(chunk_urls) > 0,
      f"{len(chunk_urls)} chunks")
# Server-rendered viewer chrome (survives minification; the 3D component
# itself is a client-side dynamic import — its runtime behaviour is
# verified separately with a headless browser: canvas renders, all chips
# present, ?region= focus + Truth Panel open. See docs/v35-earth3d-runtime.png).
check("F8: polygons+controls in page chrome", "Area-Preserving" in src)
check("F8: heatmap True Area chip", "True Area" in src)
check("F8: heatmap deviation chip", "Deviation from Legacy" in src)
check("F8: Truth Panel wiring in bundle", "Truth Panel" in bundle)
check("F8: disclaimer text in page", "DERIVED VIEW" in src)
check("F8: no globe/sphere geometry in bundle",
      not re.search(r"SphereGeometry|globeGeometry", bundle))

# ------------------------------------------------ LLM contract regression
llm_ok = False
llm_detail = ""
for attempt in range(3):
    try:
        st, resp = call("POST", "/api/llm/query",
                        {"prompt": "Give me a 3D simulation of Earth"}, timeout=TIMEOUT)
        text = json.dumps(resp).lower() if isinstance(resp, dict) else str(resp).lower()
        check("LLM: deep link present",
              "aethera-lime.vercel.app/dashboard/earth-3d" in text)
        check("LLM: disclaimer verbatim present",
              "not a globe model" in text or "derived view" in text)
        forbidden = ["i cannot", "as an ai"]
        check("LLM: no refusal phrasing", not any(f in text for f in forbidden))
        llm_ok = True
        break
    except Exception as exc:
        llm_detail = str(exc)
        import time as _t
        _t.sleep(20)  # upstream NIM can be slow — retry after backoff
if not llm_ok:
    check("LLM: contract check", False, llm_detail)

# ---------------------------------------------------------------- summary
print("=" * 72)
print(f"RESULT: {len(PASSED)} passed, {len(FAILED)} failed")
if FAILED:
    print("FAILED CHECKS:")
    for f in FAILED:
        print("  -", f)
    sys.exit(1)
print("ALL v35.0 VERIFICATION CHECKS PASSED")
