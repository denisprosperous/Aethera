/**
 * AETHERA v27.0 — shared scenario sample payloads.
 *
 * Single source of truth for the default simulation inputs used by both
 * the 2D simulator page and the 3D simulator. All payloads match the
 * real backend schemas (v0.26.x).
 */

export const FORCES = ['inertial', 'inverse_square', 'uniform'] as const;
export type ForceLaw = (typeof FORCES)[number];

export const DYNAMICS_DEFAULT = {
  start: [0, 0, 0] as [number, number, number],
  initial_velocity: [1, 0, 0] as [number, number, number],
  force_law: 'inertial' as ForceLaw,
  mu: 1.0,
  uniform_accel: [0, 0, 0] as [number, number, number],
  dt: 0.1,
  t_max: 10.0,
};

export interface AlienEdgeSample {
  id: string;
  label: string;
  edges: { source: string; target: string; length: number; source_type: string }[];
}

/** Planar square with diagonals — classifies as Flat (2D intrinsic). */
const SQUARE_EDGES = [
  { source: 'A', target: 'B', length: 1.0, source_type: 'topology' },
  { source: 'B', target: 'C', length: 1.0, source_type: 'topology' },
  { source: 'C', target: 'D', length: 1.0, source_type: 'topology' },
  { source: 'D', target: 'A', length: 1.0, source_type: 'topology' },
  { source: 'A', target: 'C', length: 1.4142135623730951, source_type: 'topology' },
  { source: 'B', target: 'D', length: 1.4142135623730951, source_type: 'topology' },
];

/** Regular tetrahedron K4 — intrinsic structure that prefers a 3D embedding. */
const TETRA_EDGES = (() => {
  const names = ['A', 'B', 'C', 'D'];
  const edges: { source: string; target: string; length: number; source_type: string }[] = [];
  for (let i = 0; i < names.length; i++) {
    for (let j = i + 1; j < names.length; j++) {
      edges.push({ source: names[i], target: names[j], length: 1.0, source_type: 'topology' });
    }
  }
  return edges;
})();

/** Octahedral graph — six vertices, twelve edges, genuinely 3D. */
const OCTA_EDGES = (() => {
  // Octahedron: 6 vertices (±x, ±y, ±z poles), edges between every pair of
  // non-opposite vertices. Edge length = sqrt(2) with unit circumradius.
  const poles = ['X+', 'X-', 'Y+', 'Y-', 'Z+', 'Z-'];
  const opposite: Record<string, string> = {
    'X+': 'X-', 'X-': 'X+', 'Y+': 'Y-', 'Y-': 'Y+', 'Z+': 'Z-', 'Z-': 'Z+',
  };
  const edges: { source: string; target: string; length: number; source_type: string }[] = [];
  for (let i = 0; i < poles.length; i++) {
    for (let j = i + 1; j < poles.length; j++) {
      if (opposite[poles[i]] === poles[j]) continue;
      edges.push({ source: poles[i], target: poles[j], length: Math.SQRT2, source_type: 'topology' });
    }
  }
  return edges;
})();

export const ALIEN_SAMPLES: AlienEdgeSample[] = [
  { id: 'square', label: 'Square (planar)', edges: SQUARE_EDGES },
  { id: 'tetra', label: 'Tetrahedron (K4)', edges: TETRA_EDGES },
  { id: 'octa', label: 'Octahedron (3D)', edges: OCTA_EDGES },
];

export interface GhostPolygon {
  name: string;
  area: number | null;
  claimed_area?: number | null;
  neighbours: string[];
}

/** Default Ghost Resolver enclosure problem (v26.1 sample, kept stable). */
export const GHOST_PAYLOAD = {
  polygons: [
    { name: 'World', area: 510000000000000, neighbours: [] as string[] },
    { name: 'Known', area: 400000000000000, neighbours: ['World'] },
    { name: 'Unknown', area: null, claimed_area: 50000000000000, neighbours: ['World'] },
  ] as GhostPolygon[],
  global_enclosure: 'World',
  global_area: 510000000000000,
};

export const PROJECTION_TYPES = [
  'Mercator',
  'Robinson',
  'AuthaGraph',
  'Equirectangular',
  'Gall-Peters',
  'Winkel-Tripel',
] as const;
export type ProjectionType = (typeof PROJECTION_TYPES)[number];
