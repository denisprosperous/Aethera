"""AETHERA v37.2 — elevation-on-click positive-path test (API level).

The prior session's UI click tests landed on micro-islands. This test
removes the UI from the loop and clicks LARGE COUNTRIES by name:

  1. Fetch the intrinsic boundary solution from /api/boundaries/intrinsic.
  2. For each requested country (default: Brazil, Russia, Canada,
     Australia, China), compute the AREA CENTROID of its largest outer
     ring (shoelace formula) in the solver's intrinsic frame.
  3. POST /api/elevation with that intrinsic point.
  4. Assert a numeric elevation is returned and lies in a plausible
     terrain band for the country.
  5. Negative path: a point far outside the ingested world must return
     elevation_m = null with the honest "Point outside known manifold"
     message (v37.2 scale-aware coverage guard).

Usage:
    python scripts/test_elevation_click.py [BASE_URL]

    BASE_URL defaults to http://127.0.0.1:8000 (local API). Pass
    https://aethera-lime.vercel.app to verify production.
"""

import json
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"

# Plausible terrain bands (metres above sea level) — loose, they exist to
# catch gross failures (e.g. returning another continent's scalar), not to
# police real orography. Everest/Andes peaks stay inside the wide bands.
CASES = [
    ("Brazil", -150, 3000),      # Amazon basin lowlands to Brazilian highs
    ("Russian Federation", -150, 5000),  # plains to Caucasus/Altai margins
    ("Canada", -200, 3500),      # Hudson bayshore to Rockies/Yukon
    ("Australia", -200, 2500),   # bass straight to Kosciuszko plateau
    ("China", -200, 9000),       # Turin depression to Everest margin
]


def http_json(path: str, payload: dict | None = None) -> dict:
    url = BASE + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST" if data else "GET",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def largest_outer_ring_centroid(country: dict) -> tuple[float, float]:
    """Area centroid (shoelace) of the largest outer ring, intrinsic frame."""
    best, best_area = None, 0.0
    for ring, kind in zip(country["rings"], country["ring_kinds"]):
        if kind != "outer" or len(ring) < 3:
            continue
        area2 = 0.0
        n = len(ring)
        for i in range(n):
            x1, y1 = ring[i]
            x2, y2 = ring[(i + 1) % n]
            area2 += x1 * y2 - x2 * y1
        if abs(area2) > best_area:
            best_area = abs(area2)
            best = ring
    assert best, f"{country['name']}: no outer ring"
    sx = sy = a2 = 0.0
    n = len(best)
    for i in range(n):
        x1, y1 = best[i]
        x2, y2 = best[(i + 1) % n]
        w = x1 * y2 - x2 * y1
        a2 += w
        sx += (x1 + x2) * w
        sy += (y1 + y2) * w
    return sx / (3 * a2), sy / (3 * a2)


def main() -> int:
    failures = []

    print(f"[1] fetching intrinsic boundary solution from {BASE}")
    sol = http_json("/api/boundaries/intrinsic")
    by_name = {c["name"]: c for c in sol["countries"]}
    xs = [p[0] for c in sol["countries"] for r in c["rings"] for p in r]
    ys = [p[1] for c in sol["countries"] for r in c["rings"] for p in r]
    span = max(max(xs) - min(xs), max(ys) - min(ys))
    print(f"    world span: {span:,.0f} intrinsic units; "
          f"expected coverage guard ~{max(4000.0, 0.25 * span):,.0f}")

    print("[2] positive path — large-country centroid clicks")
    for name, lo, hi in CASES:
        c = by_name.get(name)
        if not c:
            failures.append(f"{name}: not present in boundary solution")
            continue
        cx, cy = largest_outer_ring_centroid(c)
        r = http_json("/api/elevation", {"x": cx, "y": cy, "z": 0.0})
        e = r.get("elevation_m")
        ok = isinstance(e, (int, float)) and lo <= e <= hi
        status = "PASS" if ok else "FAIL"
        print(f"    {status} {name:12s} centroid=({cx:9.1f},{cy:9.1f}) "
              f"elevation={e} m  source={r.get('source')} "
              f"nearest={r.get('nearest_vertex_distance', 0):.1f}")
        if not ok:
            failures.append(f"{name}: elevation {e} outside [{lo},{hi}] "
                            f"or missing (error={r.get('error')})")

    print("[3] negative path — point far outside the ingested world")
    far_x = max(xs) + span * 0.9   # ~90% of a world span beyond the east edge
    far_y = max(ys) + span * 0.9
    r = http_json("/api/elevation", {"x": far_x, "y": far_y, "z": 0.0})
    ok = (r.get("elevation_m") is None
          and "outside known manifold" in (r.get("error") or ""))
    print(f"    {'PASS' if ok else 'FAIL'} far point ({far_x:.0f},{far_y:.0f}) "
          f"→ elevation_m={r.get('elevation_m')} error={r.get('error')!r}")
    if not ok:
        failures.append("outside-manifold guard did not trip honestly")

    print("[4] stats endpoint sanity")
    s = http_json("/api/elevation/stats")
    ok = s.get("available") and s.get("samples", 0) > 90000
    print(f"    {'PASS' if ok else 'FAIL'} samples={s.get('samples')} "
          f"range=[{s.get('min_elevation_m')},{s.get('max_elevation_m')}] "
          f"source={s.get('source')}")
    if not ok:
        failures.append(f"elevation stats unhealthy: {s}")

    print()
    if failures:
        print(f"RESULT {len(failures)} FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT all elevation-click checks PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
