"""AETHERA v37.2 — focused elevation-on-click positive-path check (UI).

Clicks a LARGE COUNTRY label whose rendered position is inside the
canvas (the default orbit view frames the anchored main cluster; shelf
components such as the Americas/Australia are disclosed off-frame and
reachable by pan), then expects a numeric elevation (metres) from
POST /api/elevation rendered in the ElevationToggle panel.

v37.2 hardening over v37.1:
  * waits explicitly for the toggle selector (cold-start race)
  * picks the first candidate label whose bounding rect lies INSIDE the
    canvas rect (the v37.1 version blindly clicked the first DOM match,
    which could be an off-frame shelf label at e.g. x=2655 — outside
    the 1200 px canvas — so the click landed nowhere)
"""

import asyncio
import json
import re
import sys

from playwright.async_api import async_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000/dashboard/earth-3d"
OUT = "/home/z/my-project/aethera/docs/v37-elevation-positive.png"

# Large countries whose labels are likely framed in the default view
# (anchored main cluster: Africa / Eurasia / Antarctica).
CANDIDATES = [
    "China", "Kazakhstan", "Algeria", "Saudi Arabia", "India",
    "Iran", "Mongolia", "Pakistan", "Turkey", "France", "Spain",
    "Germany", "Ukraine", "Egypt", "Libya", "Sudan", "Chad",
    "Niger", "Mali", "Ethiopia", "South Africa", "Argentina",
]

FIND_IN_CANVAS_LABEL = """
(names) => {
  const canvas = document.querySelector('canvas');
  if (!canvas) return null;
  const cr = canvas.getBoundingClientRect();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const found = [];
  while (walker.nextNode()) {
    const t = walker.currentNode.textContent.trim();
    if (!names.includes(t)) continue;
    const el = walker.currentNode.parentElement;
    const r = el.getBoundingClientRect();
    const cx = r.x + r.width / 2, cy = r.y + r.height / 2;
    const inside = cx > cr.x + 30 && cx < cr.x + cr.width - 30 &&
                   cy > cr.y + 30 && cy < cr.y + cr.height - 30;
    found.push({ name: t, x: cx, y: cy, inside });
  }
  return { canvas: { x: cr.x, y: cr.y, w: cr.width, h: cr.height }, found };
}
"""


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--no-sandbox"]
        )
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        await page.goto(URL, wait_until="networkidle", timeout=60000)
        # Cold-start race guard: wait for the viewport controls to exist.
        await page.wait_for_selector("text=Elevation: OFF", timeout=45000)
        await page.wait_for_timeout(4000)

        # Elevation ON
        toggle = await page.query_selector("text=Elevation: OFF")
        await toggle.click()
        await page.wait_for_timeout(600)

        # Find a large-country label actually rendered inside the canvas.
        probe = await page.evaluate(FIND_IN_CANVAS_LABEL, CANDIDATES)
        target = next((f for f in probe["found"] if f["inside"]), None)
        assert target, f"no in-canvas large-country label found; saw: {probe['found']}"

        await page.mouse.click(target["x"], target["y"])

        # Poll for the result (cross-origin dev hops can take a few
        # seconds; production is same-origin serverless). Either the
        # numeric elevation card or the honest guard message counts.
        ok = False
        m = None
        body = ""
        for _ in range(24):  # up to 12 s
            await page.wait_for_timeout(500)
            body = await page.inner_text("body")
            m = re.search(r"Elevation:\s*(-?[\d,]+(?:\.\d+)?)\s*m", body)
            if m or "outside known manifold" in body:
                break

        verdict = {"clicked": target["name"], "at": [round(target["x"]), round(target["y"])]}
        if m:
            verdict["elevation_m"] = float(m.group(1).replace(",", ""))
            ok = True
        elif "outside known manifold" in body:
            verdict["note"] = "outside known manifold (guard path)"
        else:
            # Failure forensics: dump every body line mentioning elevation.
            verdict["body_elevation_lines"] = [
                ln.strip()[:120] for ln in body.splitlines()
                if "elevation" in ln.lower() or "manifold" in ln.lower()
                or "sampling" in ln.lower()
            ][:12]
            verdict["pending"] = "sampling" in body
        verdict["pass"] = ok
        print(json.dumps(verdict))

        await page.screenshot(path=OUT)
        await browser.close()
        sys.exit(0 if ok else 1)


asyncio.run(main())
