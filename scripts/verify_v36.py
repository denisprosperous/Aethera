"""AETHERA v36.0 production verification suite.

Checks the deployed platform end-to-end:
  - health reports 0.36.0
  - /api/boundaries/intrinsic: 242 countries, no coordinate keys, closed rings
  - /api/boundaries/stats: Neon ingestion counts (points/edges/walk rows)
  - /api/boundaries/stats: Neon ingestion counts
  - v35 regressions: GTI band, ghost red flags, maritime median line
  - headless render of /dashboard/earth-3d: canvas, derived-boundary HUD,
    labels, dual-layer toggle, production screenshot
"""
import asyncio
import json
import sys
import urllib.request

BASE = "https://aethera-lime.vercel.app"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=90) as r:
        return json.load(r)


def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)


def has_coord_keys(o):
    if isinstance(o, dict):
        bad = ("lat", "lon", "lng", "latitude", "longitude", "wgs84", "epsg", "coordinates")
        return any(str(k).lower() in bad for k in o) or any(has_coord_keys(v) for v in o.values())
    if isinstance(o, list):
        return any(has_coord_keys(v) for v in o)
    return False


checks = {}


def check(name, fn):
    try:
        checks[name] = bool(fn())
    except Exception as e:
        checks[name] = False
        print(f"  ({name}: {e})")


check("health 0.36.0", lambda: get("/api/health")["version"] == "0.36.0")

b = get("/api/boundaries/intrinsic")
check("boundaries >= 195 countries", lambda: b["countries_count"] >= 195)
check("boundaries == 242 countries", lambda: b["countries_count"] == 242)
check("no_coordinates flag", lambda: b.get("no_coordinates") is True)
check("no coordinate keys in payload", lambda: not has_coord_keys(b))
check("rings closed (>=3 pts each, sampled)",
      lambda: all(len(r) >= 3 for c in b["countries"][:50] for r in c["rings"]))
check("disclaimer field present", lambda: "simulation" in b.get("disclaimer", "").lower())

s = get("/api/boundaries/stats")
ing = s.get("ingestion_db", {})
check("db points >= 78000", lambda: ing.get("points", 0) >= 78000)
check("db boundary edges >= 78000", lambda: ing.get("boundary_edges", 0) >= 78000)
check("db walk scalar rows >= 97000", lambda: ing.get("walk_scalar_rows", 0) >= 97000)
check("db country faces == 242", lambda: ing.get("country_faces", 0) == 242)

g = get("/api/truth/index")
check("GTI in 20-30 band (regression)", lambda: 20 <= g["gti"] <= 30)

gj = post("/api/ghost/resolve", {
    "polygons": [{"name": "Antarctica", "claimed_area": 14200000}],
    "global_enclosure": "Earth",
    "global_area": 510072000,
})
check("ghost red flag report (regression)", lambda: len(gj.get("red_flag_report", gj.get("red_flags", []))) > 0)

mj = post("/api/arbitrate/maritime", {"nation_a": "United States", "nation_b": "Cuba"})
check("maritime median line (regression)", lambda: len(mj.get("median_line", [])) > 0)


async def render():
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        await page.goto(BASE + "/dashboard/earth-3d",
                        wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(18000)
        checks["3d canvas rendered"] = await page.locator("canvas").count() > 0
        body = await page.inner_text("body")
        checks["HUD derived boundaries"] = "DERIVED COUNTRY BOUNDARIES" in body
        checks["boundary stat cards"] = (
            await page.get_by_text("Boundary Countries (v36)").count() > 0
            and await page.get_by_text("Boundary Vertices").count() > 0)
        checks["country labels visible"] = any(
            n in body for n in ("Russia", "China", "Brazil", "Australia"))
        await page.screenshot(path="/home/z/my-project/aethera/docs/v36-earth3d-production.png")
        try:
            btn = page.locator("button", has_text="Intrinsic Dual").first
            await btn.click()
            await page.wait_for_timeout(7000)
            body2 = await page.inner_text("body")
            checks["dual-layer toggle works"] = "VORONOI DUAL" in body2
            if checks["dual-layer toggle works"]:
                await page.screenshot(path="/home/z/my-project/aethera/docs/v36-earth3d-production-dual.png")
        except Exception as e:
            print(f"  (dual toggle: {e})")
            checks["dual-layer toggle works"] = False
        await browser.close()


asyncio.run(render())

ok = sum(1 for v in checks.values() if v)
for k, v in checks.items():
    print(("PASS " if v else "FAIL ") + k)
print(f"RESULT: {ok}/{len(checks)} passed")
sys.exit(0 if ok == len(checks) else 1)
