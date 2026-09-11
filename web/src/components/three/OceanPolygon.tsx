'use client';

/**
 * AETHERA v39.0 — OceanPolygon
 *
 * Renders ONE ocean basin or sea as a translucent flat mesh in the
 * stitched-world display frame (x, y=0, z), below the country layer.
 * Ocean coastline polygons are an 8-arc-minute disclosed convention
 * derived from ETOPO1 bathymetry (see aethera.ingest.ingest_oceans).
 * Oceans are NOT clickable — they carry area truth, not selection.
 */

import { useMemo } from 'react';
import * as THREE from 'three';

export interface OceanPolygonProps {
  name: string;
  ring: [number, number][];
  kind: 'ocean' | 'sea';
  color?: string;
  opacity?: number;
}

export default function OceanPolygon({
  name,
  ring,
  kind,
  color = '#0b3a5e',
  opacity,
}: OceanPolygonProps) {
  const geometry = useMemo(() => {
    if (!ring || ring.length < 3) return null;
    const pts = ring.map(([x, y]) => new THREE.Vector2(x, y));
    const shape = new THREE.Shape(pts);
    return new THREE.ShapeGeometry(shape);
  }, [ring]);

  const op = opacity ?? (kind === 'ocean' ? 0.32 : 0.42);

  if (!geometry) return null;
  return (
    <mesh
      geometry={geometry}
      rotation={[Math.PI / 2, 0, 0]}
      position={[0, -0.5, 0]}
      renderOrder={-1}
    >
      <meshBasicMaterial
        color={color}
        transparent
        opacity={op}
        side={THREE.DoubleSide}
        depthWrite={false}
      />
    </mesh>
  );
}
