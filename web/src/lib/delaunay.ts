/**
 * AETHERA v27.0 — dependency-free Delaunay triangulation (Bowyer–Watson).
 *
 * Used to build a triangulated mesh over the solved intrinsic manifold
 * coordinates returned by /api/solve/physical-truth. The manifold is what
 * it is — if the data says planar, the mesh renders planar. No spherical
 * assumption is ever applied.
 */

export interface Pt {
  x: number;
  y: number;
}

export type Tri = [number, number, number];

interface Circle {
  cx: number;
  cy: number;
  r2: number;
}

function circumcircle(a: Pt, b: Pt, c: Pt): Circle | null {
  const ax = a.x, ay = a.y;
  const bx = b.x, by = b.y;
  const cx = c.x, cy = c.y;
  const d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by));
  if (Math.abs(d) < 1e-12) return null; // collinear — skip
  const a2 = ax * ax + ay * ay;
  const b2 = bx * bx + by * by;
  const c2 = cx * cx + cy * cy;
  const ux = (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d;
  const uy = (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d;
  const dx = ax - ux, dy = ay - uy;
  return { cx: ux, cy: uy, r2: dx * dx + dy * dy };
}

/**
 * Compute Delaunay triangles over 2D points. Returns index triples.
 * Robust enough for the ~140-point world manifold; O(n²) worst case is
 * irrelevant at this scale.
 */
export function delaunay(points: Pt[]): Tri[] {
  const n = points.length;
  if (n < 3) return [];

  // Bounding box → super-triangle with generous padding.
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const p of points) {
    if (p.x < minX) minX = p.x;
    if (p.x > maxX) maxX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.y > maxY) maxY = p.y;
  }
  const dx = maxX - minX || 1;
  const dy = maxY - minY || 1;
  const dmax = Math.max(dx, dy) * 20;
  const midx = (minX + maxX) / 2;
  const midy = (minY + maxY) / 2;

  // Super-triangle vertices get indices n, n+1, n+2.
  const pts: Pt[] = [
    ...points,
    { x: midx - dmax, y: midy - dmax },
    { x: midx + dmax, y: midy - dmax },
    { x: midx, y: midy + dmax },
  ];

  let tris: Tri[] = [[n, n + 1, n + 2]];
  let circles: (Circle | null)[] = [
    circumcircle(pts[n], pts[n + 1], pts[n + 2]),
  ];

  for (let i = 0; i < n; i++) {
    const p = pts[i];
    const bad: number[] = [];
    for (let t = 0; t < tris.length; t++) {
      const c = circles[t];
      if (!c) continue;
      const ddx = p.x - c.cx;
      const ddy = p.y - c.cy;
      if (ddx * ddx + ddy * ddy <= c.r2) bad.push(t);
    }
    if (bad.length === 0) continue;

    // Boundary edges of the cavity (edges appearing exactly once).
    const edgeCount = new Map<string, [number, number]>();
    for (const t of bad) {
      const [a, b, c] = tris[t];
      for (const [u, v] of [[a, b], [b, c], [c, a]] as [number, number][]) {
        const key = u < v ? `${u}_${v}` : `${v}_${u}`;
        if (edgeCount.has(key)) edgeCount.delete(key);
        else edgeCount.set(key, [u, v]);
      }
    }

    // Remove bad triangles.
    const badSet = new Set(bad);
    const keptTris: Tri[] = [];
    const keptCircles: (Circle | null)[] = [];
    for (let t = 0; t < tris.length; t++) {
      if (!badSet.has(t)) {
        keptTris.push(tris[t]);
        keptCircles.push(circles[t]);
      }
    }
    tris = keptTris;
    circles = keptCircles;

    // Re-triangulate: connect each cavity edge to the new point.
    for (const [u, v] of edgeCount.values()) {
      tris.push([u, v, i]);
      circles.push(circumcircle(pts[u], pts[v], p));
    }
  }

  // Drop every triangle touching the super-triangle.
  return tris.filter(
    (t) => t[0] < n && t[1] < n && t[2] < n,
  ) as Tri[];
}

/** Unique undirected edges from a triangle soup (for wireframe rendering). */
export function uniqueEdges(tris: Tri[]): [number, number][] {
  const seen = new Set<string>();
  const edges: [number, number][] = [];
  for (const [a, b, c] of tris) {
    for (const [u, v] of [[a, b], [b, c], [c, a]] as [number, number][]) {
      const key = u < v ? `${u}_${v}` : `${v}_${u}`;
      if (!seen.has(key)) {
        seen.add(key);
        edges.push(u < v ? [u, v] : [v, u]);
      }
    }
  }
  return edges;
}

/** Compute the centroid + scale factor to fit points into a target extent. */
export function fitTransform(
  points: Pt[],
  extent = 10,
): { cx: number; cy: number; scale: number } {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const p of points) {
    if (p.x < minX) minX = p.x;
    if (p.x > maxX) maxX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.y > maxY) maxY = p.y;
  }
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  const span = Math.max(maxX - minX, maxY - minY) || 1;
  return { cx, cy, scale: (extent * 2) / span };
}
