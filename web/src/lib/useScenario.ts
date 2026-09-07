/**
 * AETHERA v27.0 — unified scenario data runner.
 *
 * Executes any of the six master-prompt simulation scenarios against the
 * dual-mode API (Railway → same-origin serverless failover via apiFetch)
 * and returns raw data + computed stats panels. Shared by the 2D
 * simulator and the 3D-first simulator3d experience.
 */

import { apiFetch } from '@/lib/api';
import {
  ALIEN_SAMPLES,
  DYNAMICS_DEFAULT,
  GHOST_PAYLOAD,
  type ForceLaw,
  type ProjectionType,
} from '@/lib/samples';

export type ScenarioId =
  | 'dynamics'
  | 'terraformation'
  | 'projections'
  | 'physical-truth'
  | 'alien'
  | 'ghost';

export interface StatItem {
  label: string;
  value: string;
  accent?: boolean;
}

export interface ScenarioParams {
  // dynamics
  forceLaw: ForceLaw;
  vx: number;
  vy: number;
  vz: number;
  mu: number;
  dt: number;
  tMax: number;
  // terraformation
  seaLevel: number;
  // projections / distortion
  projection: ProjectionType;
  // alien
  alienSample: string;
  // ghost
  ghostCustom: unknown | null;
}

export const DEFAULT_PARAMS: ScenarioParams = {
  forceLaw: DYNAMICS_DEFAULT.force_law,
  vx: DYNAMICS_DEFAULT.initial_velocity[0],
  vy: DYNAMICS_DEFAULT.initial_velocity[1],
  vz: DYNAMICS_DEFAULT.initial_velocity[2],
  mu: DYNAMICS_DEFAULT.mu,
  dt: DYNAMICS_DEFAULT.dt,
  tMax: DYNAMICS_DEFAULT.t_max,
  seaLevel: 10,
  projection: 'Mercator',
  alienSample: ALIEN_SAMPLES[0].id,
  ghostCustom: null,
};

export interface ScenarioResult {
  data: Record<string, unknown>;
  stats: StatItem[];
  note: string;
}

async function fetchJson(path: string, init?: RequestInit): Promise<Record<string, unknown>> {
  const res = await apiFetch(path, init);
  const j = await res.json();
  if (j && typeof j === 'object' && 'detail' in j) {
    throw new Error(
      typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail),
    );
  }
  return j as Record<string, unknown>;
}

export const SCENARIO_META: Record<
  ScenarioId,
  { label: string; icon: string; blurb: string; view: string }
> = {
  dynamics: {
    label: 'Celestial',
    icon: '🪐',
    blurb: 'Particle trajectory under user-defined force fields',
    view: 'celestial',
  },
  terraformation: {
    label: 'Terraform',
    icon: '🌊',
    blurb: 'Sea-level rise — area loss per nation',
    view: 'terraformer',
  },
  projections: {
    label: 'Distortion',
    icon: '📊',
    blurb: 'Colonial distortion scores of map projections',
    view: 'distortion',
  },
  'physical-truth': {
    label: 'Truth Manifold',
    icon: '🌍',
    blurb: 'SMACOF-derived world embedding from DEM edges',
    view: 'physical',
  },
  alien: {
    label: 'Alien Geometer',
    icon: '👽',
    blurb: 'Intrinsic shape classification from edge lengths',
    view: 'alien',
  },
  ghost: {
    label: 'Ghost Resolver',
    icon: '🔮',
    blurb: 'Derive unknown areas from closure constraints',
    view: 'ghost',
  },
};

export async function runScenario(
  sc: ScenarioId,
  p: ScenarioParams,
): Promise<ScenarioResult> {
  if (sc === 'dynamics') {
    const j = await fetchJson('/api/dynamics/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        start: DYNAMICS_DEFAULT.start,
        initial_velocity: [p.vx, p.vy, p.vz],
        force_law: p.forceLaw,
        mu: p.mu,
        uniform_accel: DYNAMICS_DEFAULT.uniform_accel,
        dt: p.dt,
        t_max: p.tMax,
      }),
    });
    const traj = (j.trajectory as number[][]) || [];
    const final = (j.final_position as number[]) || [0, 0, 0];
    return {
      data: j,
      stats: [
        { label: 'Trajectory Points', value: String(traj.length), accent: true },
        { label: 'Path Length', value: `${(Number(j.total_path_length) || 0).toFixed(3)} u` },
        { label: 'Sim Time', value: `${(Number(j.total_time) || 0).toFixed(2)} s` },
        {
          label: 'Final Position',
          value: final.map((v) => v.toFixed(2)).join(', '),
        },
      ],
      note: String(j.note || ''),
    };
  }

  if (sc === 'terraformation') {
    const j = await fetchJson('/api/terraformation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sea_level_rise_m: p.seaLevel }),
    });
    const cc = (j.coastline_changes as Record<string, unknown>[]) || [];
    const total = cc.reduce(
      (s, c) => s + Math.min(Number(c.area_change_km2) || 0, 0),
      0,
    );
    return {
      data: j,
      stats: [
        { label: 'Nations Simulated', value: String(cc.length), accent: true },
        {
          label: 'With Area Loss',
          value: String(cc.filter((c) => Number(c.area_change_km2) < 0).length),
          accent: true,
        },
        { label: 'Total Loss', value: `${Math.abs(total).toLocaleString()} km²` },
        { label: 'Sea Level Rise', value: `+${p.seaLevel} m` },
      ],
      note: String(j.note || ''),
    };
  }

  if (sc === 'projections') {
    const j = await fetchJson('/api/projections/scores');
    const scores = (j.scores as Record<string, unknown>[]) || [];
    return {
      data: { ...j, selected: p.projection },
      stats: scores.map((s) => ({
        label: `${s.projection} score`,
        value: Number(s.colonial_score).toFixed(4),
        accent: Number(s.colonial_score) >= 0,
      })),
      note: '',
    };
  }

  if (sc === 'physical-truth') {
    const j = await fetchJson('/api/solve/physical-truth');
    const regions = (j.regions as Record<string, unknown>[]) || [];
    return {
      data: j,
      stats: [
        { label: 'Nodes (regions)', value: String(j.node_count ?? regions.length), accent: true },
        { label: 'Edges', value: String(j.edge_count ?? '-') },
        {
          label: 'Convergence Residual',
          value: Number(j.convergence_residual ?? j.residual ?? 0).toExponential(4),
          accent: true,
        },
        { label: 'Solver', value: 'SMACOF (Rust FFI)' },
      ],
      note: String(j.note || ''),
    };
  }

  if (sc === 'alien') {
    const sample = ALIEN_SAMPLES.find((s) => s.id === p.alienSample) || ALIEN_SAMPLES[0];
    const j = await fetchJson('/api/alien/reconstruct', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ edges: sample.edges }),
    });
    // Solve the same graph with a 3D embedding for the 3D reconstruction view.
    let coords: Record<string, number[]> | null = null;
    try {
      const m = await fetchJson('/api/solve/manifold', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ edges: sample.edges, embedding: '3d' }),
      });
      coords = (m.coordinates as Record<string, number[]>) || null;
    } catch {
      coords = null;
    }
    return {
      data: { ...j, sample_id: sample.id, sample_label: sample.label, edges: sample.edges, coords },
      stats: [
        { label: 'Shape', value: String(j.shape || '?'), accent: true },
        { label: 'Residual', value: Number(j.residual ?? 0).toExponential(4), accent: true },
        { label: 'Mean Curvature', value: Number(j.mean_curvature ?? 0).toExponential(4) },
        { label: 'Nodes / Edges', value: `${j.node_count} / ${j.edge_count}` },
      ],
      note: String(j.note || ''),
    };
  }

  // ghost
  const payload = p.ghostCustom || GHOST_PAYLOAD;
  const j = await fetchJson('/api/ghost/resolve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const areas = (j.resolved_areas as Record<string, number>) || {};
  const names = Object.keys(areas);
  const redFlags = (j.red_flags as Record<string, unknown>[]) || [];
  return {
    data: { ...j, payload },
    stats: [
      { label: 'Resolved Zones', value: String(names.length), accent: true },
      { label: 'Red Flags', value: String(redFlags.length), accent: redFlags.length > 0 },
      { label: 'Sealed Hash', value: `${String(j.sealed_hash || '-').slice(0, 18)}…` },
    ],
    note: String(j.note || ''),
  };
}

/** Fetch per-region legacy deviation for a projection (Distortion 3D / TrueGlobe). */
export async function fetchDistortionRanking(
  projection: string,
  limit = 200,
): Promise<Record<string, unknown>[]> {
  const j = await fetchJson(
    `/api/distortion/ranking?projection=${encodeURIComponent(projection)}&limit=${limit}`,
  );
  return (j.ranking as Record<string, unknown>[]) || [];
}

/** Module-level cache of the Physical Truth manifold (coords + areas). */
let manifoldCache: {
  regions: { name: string; coords: [number, number, number]; area_km2: number }[];
  nodeCount: number;
  edgeCount: number;
  residual: number;
} | null = null;

export async function getManifold(): Promise<NonNullable<typeof manifoldCache>> {
  if (manifoldCache) return manifoldCache;
  const j = await fetchJson('/api/solve/physical-truth');
  const regions = ((j.regions as Record<string, unknown>[]) || []).map((r) => ({
    name: String(r.name),
    coords: (r.coords as [number, number, number]) || [0, 0, 0],
    area_km2: Number(r.area_km2) || 0,
  }));
  manifoldCache = {
    regions,
    nodeCount: Number(j.node_count) || regions.length,
    edgeCount: Number(j.edge_count) || 0,
    residual: Number(j.residual) || 0,
  };
  return manifoldCache;
}
