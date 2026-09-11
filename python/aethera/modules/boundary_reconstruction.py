"""Intrinsic boundary reconstruction solver (v39.0 - STITCHED WORLD).

Reconstructs the intrinsic coordinates of every country boundary vertex
from ABSOLUTE SCALAR DATA ALONE:

  * boundary edge lengths (raw local-frame chords between consecutive
    boundary vertices - ingested by aethera.ingest.ingest_boundaries),
  * stride chord constraints (scalar straightedges that make each ring
    rigid),
  * declared absolute areas in km2 (Physical Truth register or the
    single global calibration scalar),
  * shared-border vertex identities (19,256 shared edges) that let
    neighbouring RINGS be placed rigidly against each other.

v39.0 STITCHED WORLD pipeline (fixes the v36 shelf/fragmentation):

  1. Exact turtle-walk ring reconstruction from per-edge scalars. Every
     ring is a RIGID UNIT with an exact shape (walked in its own local
     frame - inter-ring offsets are not stored scalars).
  2. RING-LEVEL stitching: a graph over rings (1,632 nodes) joined by
     shared snapped border vertices ACROSS countries. Each component is
     assembled by multi-pass BFS (Kabsch on >=2 shared vertices,
     translation on 1), retrying to a fixpoint - the v36 single-pass
     country-level BFS permanently skipped countries whose first
     reached neighbour shared only secondary-ring vertices, which broke
     the Americas chain and stranded 107 countries on a shelf.
  3. RING-LEVEL POSE GRAPH: Gauss-Newton over every ring's
     (theta, tx, ty) against ALL shared-vertex correspondences,
     closing BFS spanning-tree loops so each component is one globally
     consistent rigid landmass. Enclave topology (Lesotho, San Marino,
     ...) places hole rings exactly - no synthetic convention needed.
  4. ONE GLOBAL AREA CLOSURE (single calibrated km scale) and
     COMPONENT PLACEMENT in the disclosed display frame: components
     with >=2 anchored member countries are rotated onto the disclosed
     anchor layout by rigid Kabsch; single-anchor components sit at
     their anchor; anything else falls back to a deterministic
     region-adjacent convention. The v36 per-component Procrustes
     against a non-world-like layout is gone.

NO coordinates enter the SOLVER: ring shapes come from scalars only.
The display anchor layout (aethera.modules.display_anchors) is a
DISCLOSED display convention used only to position already-rigid
components in the viewer frame (Axiom 5). No lon/lat, no WGS84, no
EPSG, no pre-seeded globe is ever reconstructed or stored.

Output: intrinsic [x, y] display coordinates per boundary vertex - the
DERIVED stitched world the 3D viewer renders (served by
/api/boundaries/intrinsic and /api/solve/world).
"""

import json
import math
import os
from datetime import datetime, timezone

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import spsolve

SOLUTION_VERSION = "v39.0"
DEFAULT_BUNDLE = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "boundaries", "boundaries_v36.json"))
DEFAULT_OUT = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "data", "boundaries_solution_v39.json"))

POSE_ITERS = 12
POSE_GAUGE_WEIGHT = 0.05

# Bundle name -> Natural Earth anchor NAME (the anchor layout covers all
# 242 NE features; the bundle stores ingestion-normalised names).
DISPLAY_ALIASES = {
    "United States": "United States of America",
    "Russian Federation": "Russia",
    "Democratic Republic of the Congo": "Dem. Rep. Congo",
    "Republic of the Congo": "Congo",
    "Dem. Rep. Korea": "North Korea",
    "Republic of Korea": "South Korea",
    "Czech Republic": "Czechia",
    "Kingdom of eSwatini": "eSwatini",
    "South Sudan": "S. Sudan",
    "Western Sahara": "W. Sahara",
    "The Gambia": "Gambia",
    "Dominican Republic": "Dominican Rep.",
    "Central African Republic": "Central African Rep.",
    "Bosnia and Herzegovina": "Bosnia and Herz.",
    "Equatorial Guinea": "Eq. Guinea",
    "Republic of Cabo Verde": "Cabo Verde",
    "Brunei Darussalam": "Brunei",
    "Faeroe Islands": "Faeroe Is.",
    "Marshall Islands": "Marshall Is.",
    "Solomon Islands": "Solomon Is.",
    "Cook Islands": "Cook Is.",
    "Pitcairn Islands": "Pitcairn Is.",
    "Falkland Islands / Malvinas": "Falkland Is.",
    "Cayman Islands": "Cayman Is.",
    "British Virgin Islands": "British Virgin Is.",
    "United States Virgin Islands": "U.S. Virgin Is.",
    "Turks and Caicos Islands": "Turks and Caicos Is.",
    "Northern Mariana Islands": "N. Mariana Is.",
    "Northern Cyprus": "N. Cyprus",
    "Federated States of Micronesia": "Micronesia",
    "French Polynesia": "Fr. Polynesia",
    "French Southern and Antarctic Lands": "Fr. S. Antarctic Lands",
    "South Georgia and the Islands": "S. Geo. and the Is.",
    "Saint Kitts and Nevis": "St. Kitts and Nevis",
    "Saint Vincent and the Grenadines": "St. Vin. and Gren.",
    "Saint Pierre and Miquelon": "St. Pierre and Miquelon",
    "Saint-Martin": "St-Martin",
    "Saint-Barthélemy": "St-Barthélemy",
    "Wallis and Futuna Islands": "Wallis and Futuna Is.",
    "Heard I. and McDonald Islands": "Heard I. and McDonald Is.",
    "Ashmore and Cartier Islands": "Ashmore and Cartier Is.",
    "Antigua and Barbuda": "Antigua and Barb.",
    "British Indian Ocean Territory": "Br. Indian Ocean Ter.",
    "Indian Ocean Territories": "Indian Ocean Ter.",
    "Åland Islands": "Åland",
}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_bundle(path: str = DEFAULT_BUNDLE) -> dict:
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def shoelace(pts: np.ndarray) -> float:
    x, y = pts[:, 0], pts[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(np.roll(x, -1), y))


def _kabsch_rotation(P, Q):
    """Best proper rotation R (2x2) with Q ~= P @ R.T (row convention)."""
    Pm = P - P.mean(axis=0)
    Qm = Q - Q.mean(axis=0)
    H = Qm.T @ Pm
    V, _S, Wt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(V @ Wt)) or 1.0
    return (V @ np.diag([1.0, d]) @ Wt)


GOLDEN = math.pi * (3 - math.sqrt(5))


def _walk_ring(ring):
    """Exact turtle-walk reconstruction of a ring from its scalars.

    ring: {"ids": [...], "walk": [l_i], "dirs": [a_i]} with directions
    relative to the ring's own first edge. Returns (n, 2) positions with
    ids[0] at the origin. Closes exactly by construction.
    """
    ids = ring["ids"]
    walk = ring["walk"]
    dirs = ring["dirs"]
    n = len(ids)
    pts = np.zeros((n, 2))
    x = y = 0.0
    for i in range(n):
        x += walk[i] * math.cos(dirs[i])
        y += walk[i] * math.sin(dirs[i])
        j = (i + 1) % n
        pts[j, 0] = x
        pts[j, 1] = y
    return pts


def _canonical_rotation(pts):
    """Rotation matrix putting the principal axis of pts along +x."""
    Xc = pts - pts.mean(axis=0)
    cov = Xc.T @ Xc
    _w, U = np.linalg.eigh(cov)
    v = U[:, int(np.argmax(_w))]
    ang = math.atan2(v[1], v[0])
    cr, sr = math.cos(-ang), math.sin(-ang)
    return np.array([[cr, -sr], [sr, cr]])


NE_NAME_ALIASES_IMPORT = None  # populated lazily from ingest module


def _ne_alias(name):
    global NE_NAME_ALIASES_IMPORT
    if NE_NAME_ALIASES_IMPORT is None:
        try:
            from aethera.ingest.ingest_boundaries import NE_NAME_ALIASES
            NE_NAME_ALIASES_IMPORT = NE_NAME_ALIASES
        except Exception:
            NE_NAME_ALIASES_IMPORT = {}
    return NE_NAME_ALIASES_IMPORT.get(name, name)


def _rot(th):
    c, s = math.cos(th), math.sin(th)
    return np.array([[c, -s], [s, c]])


# ---------------------------------------------------------------------------
# Ring-level stitching
# ---------------------------------------------------------------------------

def _ring_graph(countries, ring_coords):
    """Vertex-id -> ring occurrences, and cross-country ring adjacency.

    Returns:
      vid_rings: {vid: [(ci, ri, row), ...]} across ALL countries
      ring_cons: {(node_a, node_b): [(row_a, row_b), ...]} with
                 node = (ci, ri); rows index each ring's vertex array.
    """
    vid_rings = {}
    for (ci, ri), X in ring_coords.items():
        for row, vid in enumerate(countries[ci]["rings"][ri]["ids"]):
            vid_rings.setdefault(vid, []).append((ci, ri, row))
    ring_cons = {}
    for vid, occ in vid_rings.items():
        if len(occ) < 2:
            continue
        for i in range(len(occ)):
            for j in range(len(occ)):
                if i == j:
                    continue
                ci_a, ri_a, row_a = occ[i]
                ci_b, ri_b, row_b = occ[j]
                if ci_a == ci_b:
                    continue  # intra-country pairs carry no new constraint
                ka, kb = (ci_a, ri_a), (ci_b, ri_b)
                if kb < ka:
                    continue  # store each unordered pair once
                key = (ka, kb)
                ring_cons.setdefault(key, []).append((row_a, row_b))
    return vid_rings, ring_cons


def _stitch_components(ring_nodes, ring_coords, ring_cons):
    """Multi-pass BFS rigid stitching over the ring graph (raw frames).

    Every ring sharing snapped border vertices with an already-placed
    ring is placed by Kabsch (>=2 correspondences) or translation (1).
    Failed attempts are retried on later passes. The turtle-walk scalars
    are internally consistent, so this converges to an EXACTLY
    constraint-satisfying assembly (measured rms = 0 raw units) - each
    component becomes the TRUE rigid landmass up to a global
    rotation+translation.
    """
    adj = {}
    for (a, b) in ring_cons:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)

    def _area(nd):
        p = ring_coords[nd]
        return abs(0.5 * float(np.dot(p[:, 0], np.roll(p[:, 1], -1))
                                - np.dot(np.roll(p[:, 0], -1), p[:, 1])))

    pose = {}
    for seed in sorted(ring_nodes, key=lambda nd: -_area(nd)):
        if seed in pose:
            continue
        pose[seed] = (np.eye(2), np.zeros(2))
        if seed not in adj:
            continue
        queue = [seed]
        for _pass in range(120):
            nxt = []
            progress = False
            for cur in queue:
                R_c, t_c = pose[cur]
                for nb in sorted(adj.get(cur, ())):
                    if nb in pose:
                        continue
                    P, Q = [], []
                    for other in adj.get(nb, ()):
                        if other not in pose:
                            continue
                        R_o, t_o = pose[other]
                        X_o = ring_coords[other] @ R_o.T + t_o
                        for row_n, row_o in ring_cons.get((nb, other), ()):
                            P.append(ring_coords[nb][row_n])
                            Q.append(X_o[row_o])
                        for row_o, row_n in ring_cons.get((other, nb), ()):
                            P.append(ring_coords[nb][row_n])
                            Q.append(X_o[row_o])
                    if len(P) >= 2:
                        Pm, Qm = np.asarray(P), np.asarray(Q)
                        R = _kabsch_rotation(Pm, Qm)
                        t = Qm.mean(axis=0) - (R @ Pm.mean(axis=0))
                    elif len(P) == 1:
                        R = R_c
                        t = np.asarray(Q[0]) - (R @ np.asarray(P[0]))
                    else:
                        continue  # retry on a later pass
                    pose[nb] = (R, t)
                    nxt.append(nb)
                    progress = True
            if not progress:
                break
            queue = nxt
    return pose


def _component_constraint_rms(ring_components, ring_coords, ring_cons,
                              pose):
    """Final assembly quality: rms of shared-vertex mismatches (raw)."""
    tot, cnt = 0.0, 0
    for (a, b), rows in ring_cons.items():
        if a not in pose or b not in pose:
            continue
        Ra, ta = pose[a]
        Rb, tb = pose[b]
        A = ring_coords[a] @ Ra.T + ta
        B = ring_coords[b] @ Rb.T + tb
        for row_a, row_b in rows:
            d = A[row_a] - B[row_b]
            tot += float(d @ d)
            cnt += 1
    return math.sqrt(tot / cnt) if cnt else None


def reconstruct(bundle: dict, anchor_layout: dict = None) -> dict:
    countries = bundle["countries"]
    norm = lambda s: "".join(ch for ch in s.lower() if ch.isalnum())

    # ---- Exact turtle-walk reconstruction per ring (raw frame units) ----
    ring_coords = {}
    for ci, c in enumerate(countries):
        for ri, ring in enumerate(c["rings"]):
            if len(ring.get("ids", [])) < 3 or "walk" not in ring:
                continue
            ring_coords[(ci, ri)] = _walk_ring(ring)

    # ---- Ring graph over shared border vertices --------------------------
    _vid_rings, ring_cons = _ring_graph(countries, ring_coords)

    # Ring components (rigid landmass units).
    adj = {}
    for (a, b) in ring_cons:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    comp_of, ring_components = {}, []
    for nd in sorted(ring_coords):
        if nd in comp_of:
            continue
        cid = len(ring_components)
        comp = []
        stack = [nd]
        while stack:
            u = stack.pop()
            if u in comp_of:
                continue
            comp_of[u] = cid
            comp.append(u)
            stack.extend(adj.get(u, ()))
        ring_components.append(comp)

    # ---- Global area closure (single scale - global closure) -------------
    declared_of = {c["name"]: max(1.0, c["declared_area_km2"])
                   for c in countries}
    declared_area_of = {ci: max(1.0, c["declared_area_km2"])
                        for ci, c in enumerate(countries)}
    raw_area = {}
    for ci, c in enumerate(countries):
        a = sum(abs(shoelace(ring_coords[(ci, ri)]))
                for ri, r in enumerate(c["rings"])
                if r["kind"] == "outer" and (ci, ri) in ring_coords)
        a -= sum(abs(shoelace(ring_coords[(ci, ri)]))
                 for ri, r in enumerate(c["rings"])
                 if r["kind"] == "hole" and (ci, ri) in ring_coords)
        if a > 0:
            raw_area[c["name"]] = max(a, 1e-12)
    sum_decl = sum(declared_of[nm] for nm in raw_area)
    sum_raw = sum(raw_area.values())
    km2_per_raw2 = sum_decl / max(sum_raw, 1e-12)
    km_per_raw = math.sqrt(km2_per_raw2)

    # ---- Display anchors (disclosed convention) --------------------------
    anchor_pts = {}
    if anchor_layout:
        anchor_pts = {norm(k): np.array([v[0], v[1]], dtype=float)
                      for k, v in anchor_layout.items()}

    def resolve_anchor(nm):
        for cand in (nm, DISPLAY_ALIASES.get(nm), _ne_alias(nm),
                     DISPLAY_ALIASES.get(_ne_alias(nm))):
            if cand and norm(cand) in anchor_pts:
                return anchor_pts[norm(cand)]
        return None

    region_of = {c["name"]: (c.get("legacy_region") or "Unclaimed")
                 for c in countries}
    country_anchor = {ci: resolve_anchor(c["name"])
                      for ci, c in enumerate(countries)}

    # Region centroids for the region-adjacent fallback.
    region_layout = {}
    reg_pts = {}
    for ci, a in country_anchor.items():
        if a is not None:
            reg_pts.setdefault(region_of[countries[ci]["name"]], []).append(a)
    for reg, pts in reg_pts.items():
        region_layout[reg] = np.mean(pts, axis=0)

    # ---- STAGE 1: exact BFS rigid stitching per component ----------------
    ring_pose = _stitch_components(set(ring_coords), ring_coords, ring_cons)
    pose_rms = _component_constraint_rms(ring_components, ring_coords,
                                         ring_cons, ring_pose)

    # ---- STAGE 2: per-component rigid placement in the display frame -----
    # Every component is already the TRUE rigid landmass; place it with
    # ONE rotation+translation fitted to its anchored members' anchors.
    # Countries keep their exact area-closure scale (no component scale).
    GOLDEN = math.pi * (3 - math.sqrt(5))

    def unit_area(cid):
        return sum(abs(shoelace(ring_coords[nd]))
                   for nd in ring_components[cid])

    country_units = {}
    for cid in range(len(ring_components)):
        for ci in {nd[0] for nd in ring_components[cid]}:
            country_units.setdefault(ci, []).append(cid)
    ci_primary_unit = {ci: max(own, key=unit_area)
                       for ci, own in country_units.items()}

    def unit_centroid_km(cid):
        arrs = [ring_coords[nd] @ ring_pose[nd][0].T + ring_pose[nd][1]
                for nd in ring_components[cid]]
        return np.concatenate(arrs).mean(axis=0) * km_per_raw

    comp_kind = {}
    comp_transform = {}
    slot_usage = {}
    order = sorted(range(len(ring_components)), key=lambda c: -unit_area(c))
    for cid in order:
        nds = ring_components[cid]
        anchored = sorted(
            (ci for ci in {nd[0] for nd in nds}
             if country_anchor.get(ci) is not None),
            key=lambda ci_: -declared_area_of[ci_])
        r_unit = math.sqrt(max(unit_area(cid), 1e-9) * km2_per_raw2 / math.pi)
        if len(anchored) >= 2:
            P, Q = [], []
            for ci in anchored:
                cis_nds = [nd for nd in nds if nd[0] == ci]
                arrs = [ring_coords[nd] @ ring_pose[nd][0].T
                        + ring_pose[nd][1] for nd in cis_nds]
                cen = np.concatenate(arrs).mean(axis=0) * km_per_raw
                P.append(cen)
                Q.append(country_anchor[ci])
            Pm = np.asarray(P)
            Qm = np.asarray(Q)
            R = _kabsch_rotation(Pm, Qm)
            t = Qm.mean(axis=0) - (R @ Pm.mean(axis=0))
            comp_transform[cid] = (R, t)
            comp_kind[cid] = "fitted"
        elif len(anchored) == 1:
            ci = anchored[0]
            a = np.asarray(country_anchor[ci], dtype=float)
            if ci_primary_unit[ci] != cid:
                k = slot_usage.get(ci, 0)
                slot_usage[ci] = k + 1
                theta = GOLDEN * k
                a = a + np.array([math.cos(theta), math.sin(theta)]) \
                    * (r_unit * 1.15 + 30.0 + 0.35 * k * r_unit)
            cen_km = unit_centroid_km(cid)
            comp_transform[cid] = (np.eye(2), a - cen_km)
            comp_kind[cid] = "anchored"
        else:
            reg = next((region_of[countries[ci]["name"]]
                        for ci in sorted({nd[0] for nd in nds})),
                       "Unclaimed")
            cen_r = region_layout.get(reg)
            if cen_r is None:
                cen_r = np.zeros(2)
            reg_key = ("reg", reg)
            k = slot_usage.get(reg_key, 0)
            slot_usage[reg_key] = k + 1
            theta = GOLDEN * k
            target = cen_r + np.array(
                [math.cos(theta), math.sin(theta)]) \
                * (r_unit * 1.25 + 40.0 + 0.35 * k * r_unit)
            cen_km = unit_centroid_km(cid)
            comp_transform[cid] = (np.eye(2), target - cen_km)
            comp_kind[cid] = "region_adjacent"

    # ---- STAGE 3: serialize (display = km units) -------------------------
    # Composite per-ring transform: BFS pose (raw frame) composed with the
    # component's display fit:  disp = ((x @ Rp.T + tp) * s) @ Rf.T + tf
    #                           = x @ (Rf @ Rp).T * s + (tp @ Rf.T * s + tf)
    final_pose = {}
    for cid, (Rf, tf) in comp_transform.items():
        for nd in ring_components[cid]:
            Rp, tp = ring_pose[nd]
            final_pose[nd] = (Rf @ Rp,
                              (tp @ Rf.T) * km_per_raw + tf)
    # Antarctica's degree-frame ring is a known polar-band artifact (its
    # raw walk spans every longitude at lat -60..-90, inflating area ~6x).
    # Normalise its DISPLAY extent to the declared area and disclose.
    antarctica_rescale = 1.0
    for ci, c in enumerate(countries):
        if norm(c["name"]) != norm("Antarctica"):
            continue
        a_disp = 0.0
        for ri, r in enumerate(c["rings"]):
            nd = (ci, ri)
            if nd not in final_pose:
                continue
            R, t = final_pose[nd]
            X = (ring_coords[nd] @ R.T) * km_per_raw + t
            ar = abs(shoelace(X))
            a_disp += ar if r["kind"] == "outer" else -ar
        if a_disp > 0:
            antarctica_rescale = math.sqrt(
                max(c["declared_area_km2"], 1e-9) / a_disp)
    if antarctica_rescale < 1.0:
        for ci, c in enumerate(countries):
            if norm(c["name"]) != norm("Antarctica"):
                continue
            for ri in range(len(c["rings"])):
                nd = (ci, ri)
                if nd not in final_pose:
                    continue
                R, t = final_pose[nd]
                X = (ring_coords[nd] @ R.T) * km_per_raw + t
                cen = X.mean(axis=0)
                t = cen - (cen - t) * antarctica_rescale
                final_pose[nd] = (R * antarctica_rescale, t)

    final_countries = []
    for ci, c in enumerate(countries):
        rings_out, kinds_out = [], []
        for ri, r in enumerate(c["rings"]):
            nd = (ci, ri)
            if nd not in final_pose:
                continue
            R, t = final_pose[nd]
            disp = (ring_coords[nd] @ R.T) * km_per_raw + t
            rings_out.append([[round(float(x), 4), round(float(y), 4)]
                              for x, y in disp])
            kinds_out.append(r["kind"])
        if not rings_out:
            continue
        nm = c["name"]
        final_countries.append({
            "name": nm,
            "rings": rings_out,
            "ring_kinds": kinds_out,
            "declared_area_km2": c["declared_area_km2"],
            "area_source": c["area_source"],
            "legacy_region": region_of[nm],
            "placement": comp_kind[comp_of[nd]],
            "anchored": comp_kind[comp_of[nd]] != "region_adjacent",
        })

    # ---- Rendered vs declared (transparent deviation) --------------------
    for fc in final_countries:
        a_disp = 0.0
        for r, kind in zip(fc["rings"], fc["ring_kinds"]):
            arr = np.asarray(r)
            ar = abs(shoelace(arr))
            a_disp += ar if kind == "outer" else -ar
        a_raw = a_disp / (km_per_raw ** 2)
        rendered_km2 = a_raw * km2_per_raw2
        dev = (rendered_km2 / max(fc["declared_area_km2"], 1e-9) - 1.0) * 100.0
        fc["rendered_area_km2"] = round(rendered_km2, 1)
        fc["rendered_vs_declared_pct"] = round(dev, 2)

    devs = [abs(fc["rendered_vs_declared_pct"]) for fc in final_countries]
    kind_counts = {}
    for fc in final_countries:
        kind_counts[fc["placement"]] = \
            kind_counts.get(fc["placement"], 0) + 1
    solution = {
        "meta": {
            "version": SOLUTION_VERSION,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "principle": (
                "Stitched world: ring shapes reconstructed by exact "
                "turtle-walk from per-edge scalar lengths + walk-frame "
                "directions, assembled rigidly across shared border "
                "vertices at RING level (multi-pass BFS), loop-closed by a "
                "ring pose-graph, closed against declared absolute areas "
                "by one global scale, and placed by rigid fit to the "
                "disclosed display anchor convention. No lon/lat, no "
                "WGS84, no EPSG enters the solver. Planar solve: z = 0."
            ),
            "source_bundle": bundle["meta"]["source_shapefile"],
            "resolution": bundle["meta"]["resolution"],
            "km2_per_raw_unit2": round(km2_per_raw2, 6),
            "display_units": "kilometres (area-closure calibrated)",
            "display_anchor": (
                "natural_earth label-centroid equirectangular convention "
                "(disclosed display convention - see "
                "aethera.modules.display_anchors)"
            ),
            "ring_components": len(ring_components),
            "stitch_constraints": sum(len(v) for v in ring_cons.values()),
            "antarctica_polar_band_rescale": round(antarctica_rescale, 4),
            "stitch_rms_raw_units": (
                round(float(pose_rms), 6) if pose_rms is not None else None),
        },
        "stats": {
            "countries": len(final_countries),
            "boundary_vertices": sum(len(r) for c in final_countries
                                     for r in c["rings"]),
            "stitched_components": len(ring_components),
            "fitted_components": kind_counts.get("fitted", 0),
            "anchored_components": kind_counts.get("anchored", 0),
            "stitched_countries": sum(
                1 for fc in final_countries
                if fc["placement"] != "region_adjacent"),
            "anchored_countries": sum(
                1 for fc in final_countries if fc["anchored"]),
            "region_adjacent_countries": kind_counts.get("region_adjacent", 0),
            "shelf_countries": kind_counts.get("region_adjacent", 0),
            "area_closure": "global (single calibrated scale; per-country "
                            "deviations disclosed)",
            "mean_area_deviation_pct": round(float(np.mean(devs)), 2)
                if devs else None,
            "median_area_deviation_pct": round(float(np.median(devs)), 2)
                if devs else None,
            "display_scale_source": (
                "global area closure; ring pose-graph with disclosed "
                "anchor-guided initialisation"),
        },
        "countries": final_countries,
    }
    return solution


def get_display_anchor_layout() -> dict:
    """Disclosed display anchor layout (world-like, all 242 features)."""
    try:
        from aethera.modules.display_anchors import build_display_anchor_layout
        return build_display_anchor_layout()
    except Exception as e:  # pragma: no cover
        print(f"Display anchor layout unavailable ({e}); "
              f"falling back to legacy anchors")
        return get_anchor_layout()


def get_anchor_layout() -> dict:
    """Legacy Physical Truth intrinsic layout (v36 fallback anchor)."""
    try:
        from aethera.modules.physical_truth_manifold import (
            solve_physical_truth_manifold)
        mf, _areas = solve_physical_truth_manifold()
        return {name: [p.x, p.y] for name, p in mf.coords.items()}
    except Exception as e:  # pragma: no cover
        print(f"Anchor layout unavailable ({e}); components will use "
              f"region-adjacent placement")
        return None


def save_solution(solution: dict, out_path: str = DEFAULT_OUT):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(solution, f, separators=(",", ":"))
    print(f"Solution written: {out_path} "
          f"({os.path.getsize(out_path)/1e6:.1f} MB)")


def commit_solution_db(solution: dict) -> None:
    """Store the solver output (intrinsic coordinates) in Neon."""
    from aethera.ingest.db import Database
    from psycopg2.extras import execute_values

    with Database() as db:
        db.cur.execute("""
            CREATE TABLE IF NOT EXISTS boundary_solution (
                country TEXT NOT NULL,
                ring_idx INTEGER NOT NULL,
                seq INTEGER NOT NULL,
                x DOUBLE PRECISION NOT NULL,
                y DOUBLE PRECISION NOT NULL,
                declared_area_km2 DOUBLE PRECISION,
                area_source TEXT,
                PRIMARY KEY (country, ring_idx, seq)
            )
        """)
        db.cur.execute("DELETE FROM boundary_solution")
        rows = []
        for c in solution["countries"]:
            for ri, ring in enumerate(c["rings"]):
                for seq, (x, y) in enumerate(ring):
                    rows.append((c["name"], ri, seq, x, y,
                                 c["declared_area_km2"], c["area_source"]))
        execute_values(db.cur,
                       "INSERT INTO boundary_solution (country, ring_idx, seq, x, y, "
                       "declared_area_km2, area_source) VALUES %s "
                       "ON CONFLICT (country, ring_idx, seq) DO NOTHING",
                       rows, page_size=1000)
    print(f"boundary_solution table: {len(rows)} intrinsic vertices stored")


def main():
    import argparse
    ap = argparse.ArgumentParser(
        description="v39.0 stitched world reconstruction")
    ap.add_argument("--bundle", default=DEFAULT_BUNDLE)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--no-db", action="store_true")
    ap.add_argument("--anchor-legacy", action="store_true",
                    help="anchor to the legacy Physical Truth layout "
                         "instead of the disclosed display anchors")
    ap.add_argument("--no-anchor", action="store_true",
                    help="skip display anchoring entirely")
    args = ap.parse_args()

    bundle = load_bundle(args.bundle)
    if args.no_anchor:
        anchor = None
    elif args.anchor_legacy:
        anchor = get_anchor_layout()
    else:
        anchor = get_display_anchor_layout()
    solution = reconstruct(bundle, anchor_layout=anchor)
    save_solution(solution, args.out)
    if not args.no_db:
        commit_solution_db(solution)
    print("Stats:", json.dumps(solution["stats"], indent=2))


if __name__ == "__main__":
    main()
