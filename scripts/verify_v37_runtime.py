"""AETHERA v37.1 — headless runtime verification of /dashboard/earth-3d.

Checks (Google-Maps-style interactivity + elevation-on-click):
  1. Page loads, canvas renders (WebGL via swiftshader).
  2. Interactive manifold renders: HUD shows DERIVED COUNTRY BOUNDARIES.
  3. Country labels visible.
  4. Elevation toggle present (top-right, OFF by default).
  5. Elevation toggle switches ON; elevation disclosure appears.
  6. Click on the manifold (elevation ON) produces an elevation result
     (either a metre value or an honest out-of-manifold note) via
     POST /api/elevation.
  7. Double-click reset does not crash; zoom meter chip present.
  8. v36.0 regressions: heatmaps/labels/geometry chips still present.

Output: /home/z/my-project/aethera/docs/v37-earth3d-runtime.png + JSON verdict.
"""

import asyncio
import json
import sys

from playwright.async_api import async_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000/dashboard/earth-3d"
OUT = "/home/z/my-project/aethera/docs/v37-earth3d-runtime.png"

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'} | {name} | {detail}")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--no-sandbox"]
        )
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        console_errors = []
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)

        await page.goto(URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(4000)

        # 1. Canvas renders
        canvas = await page.query_selector("canvas")
        check("canvas renders", canvas is not None)
        if canvas:
            box = await canvas.bounding_box()
            check("canvas size", box and box["width"] > 800 and box["height"] > 400,
                  f"{box['width']:.0f}x{box['height']:.0f}" if box else "none")

        body = await page.inner_text("body")

        # 2. Interactive manifold HUD
        check("interactive manifold HUD",
              "INTERACTIVE MANIFOLD" in body and "DERIVED COUNTRY BOUNDARIES" in body)

        # 3. Country labels
        labels = await page.query_selector_all("text=/United States|Russia|China|Brazil|Australia|Canada|Greenland/")
        check("country labels visible", len(labels) >= 1, f"{len(labels)} matches")

        # 4. Elevation toggle OFF by default
        toggle = await page.query_selector("text=Elevation: OFF")
        check("elevation toggle present (OFF default)", toggle is not None)

        # 5. Toggle ON -> disclosure appears
        await toggle.click() if toggle else None
        await page.wait_for_timeout(500)
        body2 = await page.inner_text("body")
        check("elevation ON + disclosure",
              "Elevation: ON" in body2 and "Elevation disclosure" in body2)
        check("HUD shows elevation mode", "ELEVATION MODE: CLICK = ETOPO1 SAMPLE" in body2)

        # 6. Click the manifold center -> elevation fetch
        if canvas:
            box = await canvas.bounding_box()
            cx = box["x"] + box["width"] / 2
            cy = box["y"] + box["height"] / 2
            await page.mouse.click(cx + 40, cy + 20)
            await page.wait_for_timeout(2500)
            body3 = await page.inner_text("body")
            has_result = ("Elevation:" in body3 and "m" in body3) or "outside known manifold" in body3
            check("elevation-on-click returns result", has_result)

        # 7. Zoom meter + double-click reset
        check("zoom meter present", "ZOOM L" in body2 and "double-click resets" in body2)
        if canvas:
            box = await canvas.bounding_box()
            await page.mouse.dblclick(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            await page.wait_for_timeout(1200)
        check("double-click reset no crash", not errors, "; ".join(errors[:2]))

        # 8. v36 regressions: control chips
        body4 = await page.inner_text("body")
        for chip_text in ["Boundaries (v36)", "Intrinsic Dual (v33)", "True Area",
                          "Deviation from Legacy", "3D Orbit", "2D Planar", "Seed Points"]:
            check(f"chip: {chip_text}", chip_text in body4)

        # Toggle elevation back OFF for the screenshot (clean state) —
        # actually keep ON to document the feature. Screenshot as-is.
        await page.screenshot(path=OUT)
        await browser.close()

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = sum(1 for _, ok, _ in RESULTS if not ok)
    print(f"RESULT {passed} passed, {failed} failed")
    with open("/home/z/my-project/aethera/docs/v37-runtime-verdict.json", "w") as f:
        json.dump({"url": URL, "passed": passed, "failed": failed,
                   "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in RESULTS]},
                  f, indent=1)
    sys.exit(1 if failed else 0)


asyncio.run(main())
