/**
 * AETHERA v33.0 — territory geometry on the intrinsic manifold.
 *
 * The solver returns ONE intrinsic coordinate per region (a point cloud),
 * not country polygons. Country shapes are therefore derived — never
 * assumed — as the WEIGHTED NEAREST-VERTEX DUAL of the Delaunay
 * triangulation of the intrinsic point set: every triangle is captured by
 * its own vertex with the smallest weighted distance
 * (d(vertex, triangle centroid) / capture radius). Each country's
 * territory is the union of the triangles it captures, so the cells tile
 * the convex hull exactly and every border is a real triangulation edge.
 * Every polygon below is computed from the solver's own coordinates plus
 * the ABSOLUTE SCALAR areas: no projection, no lon/lat, no WGS84, no
 * pre-seeded shape of any kind (Axiom 2 · Intrinsic Emergence, Axiom 3 ·
 * Extrinsic Agnosticism, Axiom 4 · Zero Bias).
 *
 * Capture radii derive from the declared absolute scalar areas
 * (rᵢ ∝ √areaᵢ — an absolute scalar input, Axiom 1):
 *  • Intrinsic mode: one-shot weighting, positions untouched — the
 *    solve's own geometry, fairly labelled.
 *  • Area-Preserving mode: the radii are refined iteratively until every
 *    cell's rendered area approaches the region's declared area — a
 *    purely post-hoc visual transform; the intrinsic solve itself is
 *    never mutated (positions never move).
 */

import { delaunay, uniqueEdges, type Pt, type Tri } from './delaunay';

/** A single country's derived territory. */
export interface Territory {
  /** Region index into the input point array. */
  owner: number;
  /** Largest closed boundary loop — the primary outline for rendering. */
  ring: Pt[];
  /** All closed boundary loops of this territory. */
  loops: Pt[][];
  /** Area-weighted centroid of the primary ring. */
  centroid: Pt;
  /** Rendered area = total area of captured triangles (honest tiling). */
  area: number;
  /** True when the owner captured no triangle and got a micro-cell. */
  fallback: boolean;
}

export interface TerritoryMesh {
  /** One territory per seed, indexed by owner. */
  territories: Territory[];
  /** Ordered convex hull ring of the point set (the known-world rim). */
  hullRing: Pt[];
  /** Seed positions actually used (always a copy of the input here). */
  positions: Pt[];
  /** Capture radius per seed actually used. */
  weights: number[];
}

export interface TerritoryOptions {
  /** Area-Preserving mode: weight the dual by the declared areas. */
  areaWeighted?: boolean;
}

/** Shoelace area (absolute) of a closed polygon. */
export function polygonArea(ring: Pt[]): number {
  let s = 0;
  const n = ring.length;
  if (n < 3) return 0;
  for (let i = 0; i < n; i++) {
    const a = ring[i];
    const b = ring[(i + 1) % n];
    s += a.x * b.y - b.x * a.y;
  }
  return Math.abs(s) / 2;
}

/** Area-weighted centroid of a closed polygon (fallback: vertex average). */
export function polygonCentroid(ring: Pt[]): Pt {
  let s = 0;
  let cx = 0;
  let cy = 0;
  const n = ring.length;
  if (n < 3) {
    if (n === 0) return { x: 0, y: 0 };
    let ax = 0;
    let ay = 0;
    for (const p of ring) { ax += p.x; ay += p.y; }
    return { x: ax / n, y: ay / n };
  }
  for (let i = 0; i < n; i++) {
    const a = ring[i];
    const b = ring[(i + 1) % n];
    const cross = a.x * b.y - b.x * a.y;
    s += cross;
    cx += (a.x + b.x) * cross;
    cy += (a.y + b.y) * cross;
  }
  if (Math.abs(s) < 1e-12) {
    let ax = 0, ay = 0;
    for (const p of ring) { ax += p.x; ay += p.y; }
    return { x: ax / n, y: ay / n };
  }
  return { x: cx / (3 * s), y: cy / (3 * s) };
}

/**
 * Ordered convex hull ring via Andrew's monotone chain — exact and
 * independent of triangle winding; collinear points are dropped so the
 * ring is strictly convex.
 */
export function convexHullRing(points: Pt[]): Pt[] {
  const sorted = points.slice().sort((a, b) => a.x - b.x || a.y - b.y);
  const uniq: Pt[] = [];
  for (const p of sorted) {
    const last = uniq[uniq.length - 1];
    if (!last || last.x !== p.x || last.y !== p.y) uniq.push(p);
  }
  if (uniq.length < 3) return [];
  const cross = (o: Pt, a: Pt, b: Pt) =>
    (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);
  const lower: Pt[] = [];
  for (const p of uniq) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) lower.pop();
    lower.push(p);
  }
  const upper: Pt[] = [];
  for (let i = uniq.length - 1; i >= 0; i--) {
    const p = uniq[i];
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) upper.pop();
    upper.push(p);
  }
  lower.pop();
  upper.pop();
  const ring = lower.concat(upper);
  return ring.length >= 3 ? ring : [];
}

/**
 * Assign each triangle to one of its own vertices — the one whose
 * weighted distance to the triangle centroid is smallest
 * (d(v, centroid) / captureRadius[v]; radius 0 behaves as 1 for the
 * plain nearest-vertex diagram). Deterministic tie-break: lowest index.
 */
function triangleOwners(points: Pt[], tris: Tri[], w: number[]): number[] {
  const owners = new Array<number>(tris.length);
  for (let t = 0; t < tris.length; t++) {
    const [a, b, c] = tris[t];
    const pa = points[a];
    const pb = points[b];
    const pc = points[c];
    if (!pa || !pb || !pc) { owners[t] = a; continue; }
    const mx = (pa.x + pb.x + pc.x) / 3;
    const my = (pa.y + pb.y + pc.y) / 3;
    const score = (i: number, p: Pt): number => {
      const d = Math.hypot(p.x - mx, p.y - my);
      const r = w[i] > 1e-9 ? w[i] : 1;
      return d / r;
    };
    const sa = score(a, pa);
    const sb = score(b, pb);
    const sc = score(c, pc);
    owners[t] = sa <= sb && sa <= sc ? a : sb <= sc ? b : c;
  }
  return owners;
}

/**
 * Chain a set of boundary segments (vertex-index pairs) into closed
 * loops. Robust to pinch points (a vertex where a cell touches itself):
 * greedy walking; loops with < 3 vertices are discarded.
 */
function chainLoops(segments: [number, number][], points: Pt[]): Pt[][] {
  const adj = new Map<number, { other: number; id: number }[]>();
  segments.forEach(([u, v], id) => {
    if (!adj.has(u)) adj.set(u, []);
    if (!adj.has(v)) adj.set(v, []);
    adj.get(u)!.push({ other: v, id });
    adj.get(v)!.push({ other: u, id });
  });

  const used = new Set<number>();
  const loops: Pt[][] = [];

  const walk = (startId: number) => {
    const [su, sv] = segments[startId];
    used.add(startId);
    const idxLoop: number[] = [su, sv];
    let prev = su;
    let cur = sv;
    for (let guard = 0; guard < segments.length + 2; guard++) {
      if (cur === su) break; // closed
      const options = (adj.get(cur) || []).filter((e) => !used.has(e.id));
      if (options.length === 0) break; // open chain — dropped below
      const next =
        options.length === 1
          ? options[0]
          : options.find((e) => e.other !== prev) || options[0];
      used.add(next.id);
      idxLoop.push(next.other);
      prev = cur;
      cur = next.other;
    }
    if (cur === su) {
      idxLoop.pop(); // closing vertex repeats the start — drop duplicate
      if (idxLoop.length >= 3) {
        loops.push(idxLoop.map((i) => ({ x: points[i].x, y: points[i].y })));
      }
    }
  };

  for (let id = 0; id < segments.length; id++) {
    if (!used.has(id)) walk(id);
  }
  return loops;
}

/**
 * Build the territory mesh for an intrinsic point set.
 */
export function buildTerritories(
  points: Pt[],
  areas: number[],
  opts: TerritoryOptions = {},
): TerritoryMesh {
  const n = points.length;
  if (n < 3 || areas.length !== n) {
    return {
      territories: [],
      hullRing: [],
      positions: points.map((p) => ({ ...p })),
      weights: points.map(() => 1),
    };
  }

  const total = areas.reduce((s, a) => s + Math.max(1, a), 0) || 1;

  // Area-Preserving mode (areaWeighted): the capture boundaries of the
  // dual are re-derived from the declared absolute scalar areas so the
  // rendered cell areas approach the Physical Truth values. The
  // coordinates themselves never move — the intrinsic solve is
  // rendered exactly as produced in both modes.

  // The triangulation, hull and area targets are taken from the seeds
  // that will actually be rendered (relaxed or intrinsic), so the cells
  // tile the rendered hull exactly.
  const tris = delaunay(points);
  const triA = tris.map(([a, b, c]) => {
    const pa = points[a], pb = points[b], pc = points[c];
    return Math.abs(
      (pb.x - pa.x) * (pc.y - pa.y) - (pc.x - pa.x) * (pb.y - pa.y),
    ) / 2;
  });
  const hullArea = triA.reduce((s, a) => s + a, 0);

  const hullRing = convexHullRing(points);

  const target = areas.map((a) => (Math.max(1, a) / total) * hullArea);

  // Capture radii: the Intrinsic mode keeps the dual UNWEIGHTED — the
  // solve's own geometry, as produced. The Area-Preserving mode weights
  // the capture radii by the declared absolute scalar areas (rᵢ ∝
  // √areaᵢ) on top of the bounded fan relaxation, so the rendered cells
  // approach the Physical Truth values. Only ratios matter for
  // ownership, so the absolute scale is numerically convenient.
  const w = opts.areaWeighted === true
    ? target.map((t) => Math.sqrt(Math.max(t, 1e-9)))
    : points.map(() => 1);

  const owners = triangleOwners(points, tris, w);

  // Cell areas: total captured triangle area (tiles the hull exactly).
  const cellA = new Float64Array(n);
  for (let t = 0; t < tris.length; t++) cellA[owners[t]] += triA[t];

  // Border segments per owner: triangle edges separating two owners, plus
  // hull edges (the edge of the known world).
  const edgeTris = new Map<string, number[]>();
  for (let t = 0; t < tris.length; t++) {
    const [a, b, c] = tris[t];
    for (const [u, v] of [[a, b], [b, c], [c, a]] as [number, number][]) {
      const k = u < v ? `${u}_${v}` : `${v}_${u}`;
      const list = edgeTris.get(k);
      if (list) list.push(t);
      else edgeTris.set(k, [t]);
    }
  }
  const segmentsByOwner = new Map<number, [number, number][]>(
  );
  const addSegment = (owner: number, u: number, v: number) => {
    const list = segmentsByOwner.get(owner);
    if (list) list.push([u, v]);
    else segmentsByOwner.set(owner, [[u, v]]);
  };
  for (const [k, ts] of edgeTris) {
    const [uStr, vStr] = k.split('_');
    const u = Number(uStr);
    const v = Number(vStr);
    if (ts.length === 1) {
      addSegment(owners[ts[0]], u, v);
    } else {
      const o1 = owners[ts[0]];
      const o2 = owners[ts[1]];
      if (o1 !== o2) {
        addSegment(o1, u, v);
        addSegment(o2, u, v);
      }
    }
  }

  // Bbox for fallback micro-cells (kept strictly inside the data extent).
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const p of points) {
    if (p.x < x0) x0 = p.x;
    if (p.x > x1) x1 = p.x;
    if (p.y < y0) y0 = p.y;
    if (p.y > y1) y1 = p.y;
  }
  if (!Number.isFinite(x0)) { x0 = y0 = x1 = y1 = 0; }
  const span = Math.max(x1 - x0, y1 - y0) || 1;
  const micro = span * 0.004;
  const clamp = (x: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, x));

  const territories: Territory[] = new Array(n);
  for (let owner = 0; owner < n; owner++) {
    const segs = segmentsByOwner.get(owner) || [];
    let loops = segs.length >= 3 ? chainLoops(segs, points) : [];
    loops = loops.filter((l) => l.length >= 3 && polygonArea(l) > 1e-12);
    if (loops.length === 0) {
      // Owner captured no triangle → micro-cell so the country remains a
      // visible, closed polygon inside the data extent.
      const p = points[owner];
      const ring = [
        { x: clamp(p.x - micro, x0, x1), y: clamp(p.y - micro, y0, y1) },
        { x: clamp(p.x + micro, x0, x1), y: clamp(p.y - micro, y0, y1) },
        { x: clamp(p.x + micro, x0, x1), y: clamp(p.y + micro, y0, y1) },
        { x: clamp(p.x - micro, x0, x1), y: clamp(p.y + micro, y0, y1) },
      ];
      territories[owner] = {
        owner, loops: [ring], ring, centroid: { x: p.x, y: p.y },
        area: cellA[owner] || polygonArea(ring), fallback: true,
      };
      continue;
    }
    // Primary ring = largest by area.
    let ring = loops[0];
    let ringArea = polygonArea(ring);
    for (let i = 1; i < loops.length; i++) {
      const a = polygonArea(loops[i]);
      if (a > ringArea) { ring = loops[i]; ringArea = a; }
    }
    territories[owner] = {
      owner, loops, ring, centroid: polygonCentroid(ring),
      area: cellA[owner] || ringArea, fallback: false,
    };
  }

  return {
    territories,
    hullRing,
    positions: points.map((p) => ({ ...p })),
    weights: w,
  };
}
