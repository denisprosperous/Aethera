'use client';

/**
 * AETHERA v27.0 — Simulator3DView
 *
 * Scenario dispatcher: takes the raw payload fetched by the scenario
 * runner and renders the matching Three.js 3D scene. Used by both the
 * classic simulator page (3D toggle) and the dedicated /dashboard/simulator3d
 * experience. If the payload for the active scenario isn't loaded yet, a
 * compact placeholder is shown — never a broken canvas.
 */

import dynamic from 'next/dynamic';
import type { ScenarioId } from '@/lib/useScenario';

const Celestial3D = dynamic(() => import('./Celestial3D'), { ssr: false });
const Terraformer3D = dynamic(() => import('./Terraformer3D'), { ssr: false });
const Distortion3D = dynamic(() => import('./Distortion3D'), { ssr: false });
const Manifold3D = dynamic(() => import('./Manifold3D'), { ssr: false });
const Alien3D = dynamic(() => import('./Alien3D'), { ssr: false });
const Ghost3D = dynamic(() => import('./Ghost3D'), { ssr: false });

export type Simulator3DScenario =
  | 'celestial'
  | 'terraformer'
  | 'distortion'
  | 'physical'
  | 'alien'
  | 'ghost';

interface Simulator3DViewProps {
  scenario: ScenarioId;
  data: Record<string, unknown> | null;
  selectedProjection?: string;
  seaLevel?: number;
  forceLaw?: string;
  dt?: number;
  tMax?: number;
  onRegionClick?: (region: string) => void;
}

function Placeholder({ text }: { text: string }) {
  return (
    <div
      style={{
        width: '100%', height: '100%', display: 'flex', alignItems: 'center',
        justifyContent: 'center', color: '#3d4a58', fontFamily: 'monospace',
        fontSize: 12, flexDirection: 'column', gap: 10,
      }}
    >
      <div style={{ fontSize: 26, opacity: 0.7 }}>🧊</div>
      <div>{text}</div>
    </div>
  );
}

export default function Simulator3DView({
  scenario,
  data,
  selectedProjection = 'Mercator',
  seaLevel = 10,
  forceLaw = 'inertial',
  dt = 0.1,
  tMax = 10,
  onRegionClick,
}: Simulator3DViewProps) {
  if (!data) {
    return <Placeholder text="Run the simulation to populate the 3D viewport." />;
  }

  switch (scenario) {
    case 'dynamics': {
      const trajectory = (data.trajectory as number[][]) || [];
      if (trajectory.length < 2) {
        return <Placeholder text="Trajectory empty for these parameters — adjust and re-run." />;
      }
      return (
        <Celestial3D
          trajectory={trajectory}
          forceLaw={String(data.force_law || forceLaw)}
          dt={dt}
          tMax={tMax}
        />
      );
    }

    case 'terraformation': {
      const cc = (data.coastline_changes as Record<string, unknown>[]) || [];
      if (cc.length === 0) return <Placeholder text="No coastline changes returned." />;
      return <Terraformer3D coastlineChanges={cc} seaLevel={seaLevel} onRegionClick={onRegionClick} />;
    }

    case 'projections': {
      const scores = (data.scores as Record<string, unknown>[]) || [];
      if (scores.length === 0) return <Placeholder text="No projection scores returned." />;
      return (
        <Distortion3D
          scores={scores}
          selectedProjection={selectedProjection}
          onRegionClick={onRegionClick}
        />
      );
    }

    case 'physical-truth': {
      const regions = (data.regions as Record<string, unknown>[]) || [];
      if (regions.length < 3) return <Placeholder text="Manifold not loaded yet." />;
      return (
        <Manifold3D
          regions={regions.map((r) => ({
            name: String(r.name),
            coords: (r.coords as [number, number, number]) || [0, 0, 0],
            area_km2: Number(r.area_km2) || 0,
          }))}
          edgeCount={Number(data.edge_count) || undefined}
          residual={Number(data.residual) || 0}
          onRegionClick={onRegionClick}
        />
      );
    }

    case 'alien': {
      return (
        <Alien3D
          shape={String(data.shape || '?')}
          embedding={String(data.embedding || '3d')}
          meanCurvature={Number(data.mean_curvature) || 0}
          residual={Number(data.residual) || 0}
          coords={(data.coords as Record<string, number[]>) || null}
          edges={((data.edges as { source: string; target: string }[]) || [])}
          onRegionClick={onRegionClick}
        />
      );
    }

    case 'ghost': {
      return (
        <Ghost3D
          resolvedAreas={(data.resolved_areas as Record<string, number>) || {}}
          redFlags={(data.red_flags as Record<string, unknown>[]) || []}
          payload={
            (data.payload as {
              polygons?: {
                name: string;
                area?: number | null;
                claimed_area?: number | null;
                neighbours?: string[];
              }[];
            }) || {}
          }
          onRegionClick={onRegionClick}
        />
      );
    }

    default:
      return <Placeholder text="No 3D view available for this scenario." />;
  }
}
