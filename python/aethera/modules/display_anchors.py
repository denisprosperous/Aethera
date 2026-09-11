"""Disclosed extrinsic display anchor layout (v39.0).

Builds ONE anchor point per country for component placement in the
VIEWER'S DISPLAY FRAME. Sources: the same Natural Earth 1:50m admin_0
dataset consumed at v36.0 ingestion; each country's label centroid
(LABEL_X / LABEL_Y) is mapped by a disclosed equirectangular
convention:

    x = R * lon * cos(lat)
    y = R * lat

with R = 6371 * pi / 180 (km per degree) — an area-honest local
correction (E-W distances shrink by cos(lat)), so anchor spacing is
approximately true great-circle spacing.

AXIOM DISCLOSURE (Axiom 5 - Full Transparency): the reconstruction
solver itself still receives NO coordinates - every country shape is
reconstructed from absolute scalars (edge lengths, walk-frame
directions, declared areas) and stitched across shared border
vertices. These anchors only PLACE each already-rigid stitched
component in the display frame, a deterministic disclosed convention
that replaces the v36 golden-angle shelf. They are not a projection
claim and not a globe model: the viewer renders a derived extrinsic
embedding of the intrinsic manifold.
"""

import math
import os

import shapefile

DEFAULT_NE_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "natural_earth",
    "ne_50m_admin_0_countries"))

KM_PER_DEG = 6371.0 * math.pi / 180.0


def build_display_anchor_layout(ne_dir: str = DEFAULT_NE_DIR) -> dict:
    """{country_name: [x, y]} anchor points in km display units."""
    shp = os.path.join(ne_dir, "ne_50m_admin_0_countries.shp")
    sf = shapefile.Reader(shp)
    fields = [f[0] for f in sf.fields]
    adj = {f: i - 1 for i, f in enumerate(fields) if f != "DeletionFlag"}
    ix, iy, inm = adj["LABEL_X"], adj["LABEL_Y"], adj["NAME"]

    anchors = {}
    for i in range(sf.numRecords):
        rec = sf.record(i)
        name = str(rec[inm]).strip()
        if not name:
            continue
        lon = float(rec[ix])
        lat = float(rec[iy])
        x = KM_PER_DEG * lon * math.cos(math.radians(lat))
        y = KM_PER_DEG * lat
        anchors[name] = [x, y]
    return anchors


if __name__ == "__main__":
    a = build_display_anchor_layout()
    print(f"{len(a)} display anchors")
    for probe in ("United States of America", "Brazil", "France", "Australia",
                  "Japan", "South Africa", "Russian Federation", "New Zealand"):
        if probe in a:
            print(f"  {probe:28s} ({a[probe][0]:9.1f}, {a[probe][1]:9.1f}) km")
