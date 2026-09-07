'use client';

/**
 * AETHERA v27.0 — ScenarioViewport
 *
 * Client-only Three.js viewport that switches 3D scenes based on the
 * selected scenario. Thin wrapper around Simulator3DView with a loading
 * state, mounted via next/dynamic (ssr:false) so WebGL never runs on the
 * server.
 */

import dynamic from 'next/dynamic';
import type { ScenarioId } from '@/lib/useScenario';

const Simulator3DView = dynamic(() => import('./Simulator3DView'), {
  ssr: false,
  loading: () => (
    <div
      style={{
        width: '100%', height: '100%', display: 'flex', alignItems: 'center',
        justifyContent: 'center', color: '#00ff88', fontFamily: 'monospace', fontSize: 12,
        background: '#040a10',
      }}
    >
      ◌ initialising 3D viewport…
    </div>
  ),
});

export interface ScenarioViewportProps {
  scenario: ScenarioId;
  data: Record<string, unknown> | null;
  params: {
    seaLevel: number;
    forceLaw: string;
    dt: number;
    tMax: number;
    projection: string;
  };
  onRegionClick?: (region: string) => void;
}

export default function ScenarioViewport({
  scenario,
  data,
  params,
  onRegionClick,
}: ScenarioViewportProps) {
  return (
    <Simulator3DView
      scenario={scenario}
      data={data}
      seaLevel={params.seaLevel}
      forceLaw={params.forceLaw}
      dt={params.dt}
      tMax={params.tMax}
      selectedProjection={params.projection}
      onRegionClick={onRegionClick}
    />
  );
}
