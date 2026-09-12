'use client';

/**
 * AETHERA v36.0 — CountryPolygon
 *
 * Renders ONE country as a CLOSED POLYGON with fill, border and a
 * centroid label — from DERIVED intrinsic boundary geometry served by
 * /api/boundaries/intrinsic. That geometry is reconstructed from
 * globe-agnostic scalar data only (edge lengths + walk-frame directions
 * + declared areas): no lon/lat, no WGS84, no EPSG, no pre-seeded globe
 * ever reaches this component (Axioms 2, 3, 4).
 *
 * Geometry convention: solver plane coordinates (x, y) map to world
 * (x, y=0, z) via mesh rotation +90° about X; the fill is a planar
 * THREE.Shape (holes supported), borders are fat lines per ring, and the
 * label sits at the largest ring's centroid (clamped inside).
 *
 * v37.1: optional onPickPoint — passes the WORLD-space intersection
 * point of a click so the elevation layer can sample the manifold at
 * the exact clicked location (converted back to intrinsic units by the
 * parent, which owns the viewport fit transform).
 */

import { useMemo } from 'react';
import * as THREE from 'three';
import { Line, Html } from '@react-three/drei';

export interface BoundaryRing {
  pts: [number, number][];
  kind: 'outer' | 'hole';
}

export interface CountryPolygonProps {
  name: string;
  rings: BoundaryRing[];
  fillColor: string;
  borderColor: string;
  areaKm2: number;
  major?: boolean;
  selected?: boolean;
  showLabel?: boolean;
  accent?: string;
  onPick?: (name: string) => void;
  /** v37.1 — click intersection in WORLD space (for elevation sampling). */
  onPickPoint?: (name: string, worldPoint: [number, number, number]) => void;
  onHover?: (hover: { name: string; area: number; position: [number, number, number] } | null) => void;
}

function pointInRing(x: number, y: number, ring: [number, number][]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi || 1e-12) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

export default function CountryPolygon({
  name,
  rings,
  fillColor,
  borderColor,
  areaKm2,
  major = false,
  selected = false,
  showLabel = true,
  accent = '#00ff88',
  onPick,
  onPickPoint,
  onHover,
}: CountryPolygonProps) {
  // ---- Geometry: one Shape per outer ring (holes attached) ------------
  const geometries = useMemo(() => {
    const outers = rings.filter((r) => r.kind === 'outer' && r.pts.length >= 3);
    const holes = rings.filter((r) => r.kind === 'hole' && r.pts.length >= 3);
    const geos: THREE.BufferGeometry[] = [];
    for (const outer of outers) {
      const shape = new THREE.Shape(outer.pts.map(([x, y]) => new THREE.Vector2(x, y)));
      for (const hole of holes) {
        const path = new THREE.Path(hole.pts.map(([x, y]) => new THREE.Vector2(x, y)));
        shape.holes.push(path);
      }
      geos.push(new THREE.ShapeGeometry(shape));
    }
    return geos;
  }, [rings]);

  // ---- Label anchor: centroid of the largest ring, clamped inside ------
  const labelAt = useMemo<[number, number, number] | null>(() => {
    const outers = rings.filter((r) => r.kind === 'outer' && r.pts.length >= 3);
    if (!outers.length) return null;
    let best = outers[0];
    let bestArea = 0;
    for (const r of outers) {
      let a = 0;
      for (let i = 0; i < r.pts.length; i++) {
        const [x1, y1] = r.pts[i];
        const [x2, y2] = r.pts[(i + 1) % r.pts.length];
        a += x1 * y2 - x2 * y1;
      }
      a = Math.abs(a / 2);
      if (a > bestArea) { bestArea = a; best = r; }
    }
    const n = best.pts.length;
    let cx = 0, cy = 0;
    for (let i = 0; i < n; i++) {
      const [x1, y1] = best.pts[i];
      const [x2, y2] = best.pts[(i + 1) % n];
      const cross = x1 * y2 - x2 * y1;
      cx += (x1 + x2) * cross;
      cy += (y1 + y2) * cross;
    }
    const area6 = bestArea * 6;
    if (area6 > 1e-12) { cx /= area6; cy /= area6; }
    else {
      cx = best.pts.reduce((s, p) => s + p[0], 0) / n;
      cy = best.pts.reduce((s, p) => s + p[1], 0) / n;
    }
    // Clamp a stray centroid back inside the polygon (bbox centre fallback).
    if (!pointInRing(cx, cy, best.pts)) {
      cx = (Math.min(...best.pts.map((p) => p[0])) + Math.max(...best.pts.map((p) => p[0]))) / 2;
      cy = (Math.min(...best.pts.map((p) => p[1])) + Math.max(...best.pts.map((p) => p[1]))) / 2;
    }
    return [cx, 0.06, -cy];
  }, [rings]);

  const borders = useMemo(
    () => rings
      .filter((r) => r.pts.length >= 2)
      .map((r) => r.pts.map(([x, y]) => [x, 0.02, -y] as [number, number, number])),
    [rings],
  );

  return (
    <group>
      {/* Filled territory — planar shape laid into the manifold plane */}
      {geometries.map((geo, i) => (
        <mesh
          key={`fill-${i}`}
          geometry={geo}
          rotation={[-Math.PI / 2, 0, 0]}
          onClick={(e) => {
            e.stopPropagation();
            onPick?.(name);
            if (onPickPoint) {
              const p = e.point;
              onPickPoint(name, [p.x, p.y, p.z]);
            }
          }}
          onPointerOver={(e) => {
            e.stopPropagation();
            if (labelAt) onHover?.({ name, area: areaKm2, position: [labelAt[0], labelAt[1] + 0.4, labelAt[2]] });
          }}
          onPointerOut={() => onHover?.(null)}
        >
          <meshStandardMaterial
            color={fillColor}
            side={THREE.DoubleSide}
            transparent
            opacity={0.85}
            roughness={0.65}
            polygonOffset
            polygonOffsetFactor={1}
            polygonOffsetUnits={1}
          />
        </mesh>
      ))}

      {/* Border rings — closed outlines (first point repeated to close;
          this drei version has no `closed` prop) */}
      {borders.map((pts, i) => (
        <Line
          key={`border-${i}`}
          points={pts.length > 2 ? [...pts, pts[0]] : pts}
          color={selected ? accent : borderColor}
          lineWidth={selected ? 2.6 : major ? 1.4 : 1}
          transparent
          opacity={selected ? 1 : 0.9}
        />
      ))}

      {/* Centred label — click-transparent: v37.2 fix. drei's Html in
          non-transform mode ignores the pointerEvents PROP, so the outer
          positioned div must get pointer-events:none via `style` (it
          spreads into the wrapper). Before this fix the label wrapper
          captured clicks and swallowed polygon picks (elevation +
          Truth Panel) beneath it. */}
      {showLabel && labelAt && (
        <Html
          position={labelAt}
          center
          distanceFactor={22}
          zIndexRange={[40, 0]}
          style={{ pointerEvents: 'none' }}
        >
          <div
            style={{
              color: selected || major ? accent : '#a7bccc',
              fontFamily: 'monospace',
              fontSize: major || selected ? 10 : 7.5,
              fontWeight: major || selected ? 600 : 400,
              background: selected ? 'rgba(0,255,136,0.16)' : 'rgba(4,10,16,0.72)',
              padding: major || selected ? '2px 7px' : '1px 5px',
              borderRadius: 4,
              border: `1px solid ${selected ? 'rgba(0,255,136,0.7)' : major ? 'rgba(0,255,136,0.25)' : 'rgba(140,170,190,0.16)'}`,
              whiteSpace: 'nowrap',
              pointerEvents: 'none',
              userSelect: 'none',
            }}
          >
            {name}
          </div>
        </Html>
      )}
    </group>
  );
}
