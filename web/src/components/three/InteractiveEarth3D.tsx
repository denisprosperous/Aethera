'use client';

/**
 * AETHERA v39.0 — InteractiveEarth3D
 *
 * THE STITCHED WORLD VIEWER (Google-Maps-style interaction).
 *
 * Renders /api/solve/world: every country as its DERIVED closed polygon
 * (ring-level exact stitching from scalar data — edge lengths, walk
 * directions, declared areas; no lon/lat, no WGS84, no EPSG, no
 * pre-seeded globe — Axioms 2-4) with ocean basins beneath.
 *
 * Interaction contract (v39.0):
 *   • OrbitControls — wheel zoom, drag pan, right-drag rotate/tilt.
 *   • Click a country (elevation OFF) → camera zooms to it + Truth
 *     Panel deep link (handled by the page).
 *   • Elevation mode ON → ANY click maps to the intrinsic point and
 *     POSTs /api/elevation (ETOPO1, sea-level reference); the result
 *     shows as a surface tooltip + HUD line. "Outside manifold" is
 *     disclosed for out-of-coverage clicks (scale-aware guard).
 *
 * The view is a derived extrinsic embedding of the intrinsic manifold —
 * NOT a globe model (mandatory disclaimer rendered by the page).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls, Text, Html } from '@react-three/drei';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import CountryPolygon from './CountryPolygon';
import OceanPolygon from './OceanPolygon';

export interface WorldCountry {
  name: string;
  rings: [number, number][][];
  ringKinds: ('outer' | 'hole')[];
  declared: number;
  placement: string;
  anchored: boolean;
}

export interface WorldOcean {
  name: string;
  kind: 'ocean' | 'sea';
  area_km2: number;
  coastline_ring_display?: [number, number][];
}

export interface ElevationHit {
  x: number;
  y: number;
  elevation_m: number | null;
  in_manifold: boolean;
}

export interface InteractiveEarth3DProps {
  countries: WorldCountry[];
  oceans: WorldOcean[];
  elevationMode: boolean;
  selected?: string | null;
  showLabels: boolean;
  showOceans: boolean;
  autoRotate: boolean;
  onCountryClick?: (name: string) => void;
  onElevationHit?: (hit: ElevationHit | null) => void;
  zoomTarget?: { name: string; nonce: number } | null;
}

function worldBounds(countries: WorldCountry[]) {
  let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
  for (const c of countries) {
    for (const r of c.rings) {
      for (const [x, y] of r) {
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minZ) minZ = y;
        if (y > maxZ) maxZ = y;
      }
    }
  }
  const cx = (minX + maxX) / 2;
  const cz = (minZ + maxZ) / 2;
  const radius = Math.max(maxX - minX, maxZ - minZ) / 2;
  return { center: new THREE.Vector3(cx, 0, cz), radius: radius || 1000 };
}

function centroid3D(c: WorldCountry): [number, number, number] {
  let sx = 0, sz = 0, n = 0;
  let best = 0, bx = 0, bz = 0, bn = 0;
  for (const r of c.rings) {
    for (const [x, y] of r) {
      sx += x; sz += y; n += 1;
    }
    const area = Math.abs(polyArea(r));
    if (area > best) {
      best = area;
      bx = r.reduce((s, p) => s + p[0], 0) / r.length;
      bz = r.reduce((s, p) => s + p[1], 0) / r.length;
      bn = r.length;
    }
  }
  void sx; void sz; void n; void bn;
  return [bx, 0, bz];
}

function polyArea(r: [number, number][]): number {
  let a = 0;
  for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
    a += (r[j][0] - r[i][0]) * (r[j][1] + r[i][1]);
  }
  return a / 2;
}

function boundingRadius(c: WorldCountry): number {
  const [cx, , cz] = centroid3D(c);
  let r = 10;
  for (const ring of c.rings) {
    for (const [x, y] of ring) {
      const d = Math.hypot(x - cx, y - cz);
      if (d > r) r = d;
    }
  }
  return r;
}

/** Camera flight: eased zoom to a country or back to the world view. */
function CameraFlight({
  controlsRef,
  target,
  goalPos,
  goalTarget,
  active,
  onDone,
}: {
  controlsRef: React.MutableRefObject<OrbitControlsImpl | null>;
  target: THREE.Vector3;
  goalPos: THREE.Vector3;
  goalTarget: THREE.Vector3;
  active: boolean;
  onDone?: () => void;
}) {
  const { camera } = useThree();
  const t = useRef(0);
  const from = useRef({ pos: new THREE.Vector3(), tgt: new THREE.Vector3() });

  useEffect(() => {
    if (active) {
      from.current.pos.copy(camera.position);
      from.current.tgt.copy(target);
      t.current = 0;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, goalPos, goalTarget]);

  useFrame((_, dt) => {
    if (!active || !controlsRef.current) return;
    t.current = Math.min(1, t.current + dt * 1.4);
    const e = 1 - Math.pow(1 - t.current, 3); // ease-out cubic
    camera.position.lerpVectors(from.current.pos, goalPos, e);
    controlsRef.current.target.lerpVectors(from.current.tgt, goalTarget, e);
    controlsRef.current.update();
    if (t.current >= 1) onDone?.();
  });
  return null;
}

function ElevationProbe({
  elevationMode,
  onElevationHit,
}: {
  elevationMode: boolean;
  onElevationHit?: (hit: ElevationHit | null) => void;
}) {
  const { gl, scene, camera } = useThree();
  const busy = useRef(false);

  useEffect(() => {
    if (!elevationMode) return;
    const canvas = gl.domElement;

    const pick = async (ev: PointerEvent) => {
      if (busy.current || ev.button !== 0) return;
      const rect = canvas.getBoundingClientRect();
      const ndc = new THREE.Vector2(
        ((ev.clientX - rect.left) / rect.width) * 2 - 1,
        -((ev.clientY - rect.top) / rect.height) * 2 + 1,
      );
      const ray = new THREE.Raycaster();
      ray.setFromCamera(ndc, camera);
      const hits = ray.intersectObjects(scene.children, true);
      const hit = hits.find((h) => Math.abs(h.point.y) < 60);
      if (!hit) return;
      busy.current = true;
      const x = hit.point.x;
      const y = hit.point.z;
      onElevationHit?.({ x, y, elevation_m: null, in_manifold: true });
      try {
        const res = await fetch('/api/elevation', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ x, y, z: 0 }),
        });
        const j = await res.json();
        onElevationHit?.({
          x,
          y,
          elevation_m: j.elevation_m,
          in_manifold: Boolean(j.in_manifold),
        });
      } catch {
        onElevationHit?.({ x, y, elevation_m: null, in_manifold: false });
      } finally {
        busy.current = false;
      }
    };

    canvas.addEventListener('pointerdown', pick);
    return () => canvas.removeEventListener('pointerdown', pick);
  }, [elevationMode, gl, scene, camera, onElevationHit]);

  return null;
}

/** Elevation tooltip marker for the latest probe. */
function ElevationMarker({ hit }: { hit: ElevationHit | null }) {
  if (!hit) return null;
  const label =
    hit.elevation_m === null
      ? '◌ Outside manifold'
      : `${hit.elevation_m > 0 ? '▲' : '▼'} ${Math.round(hit.elevation_m)} m`;
  const color = hit.elevation_m === null
    ? '#f59e0b'
    : hit.elevation_m > 0
      ? '#00ff88'
      : '#38bdf8';
  return (
    <group position={[hit.x, 5, hit.y]}>
      <Html center distanceFactor={900} zIndexRange={[60, 0]}>
        <div
          style={{
            background: 'rgba(4,10,16,0.92)',
            border: `1px solid ${color}`,
            color,
            fontFamily: 'monospace',
            fontSize: 13,
            padding: '5px 10px',
            borderRadius: 6,
            whiteSpace: 'nowrap',
            pointerEvents: 'none',
          }}
        >
          {label}
        </div>
      </Html>
    </group>
  );
}

let lastHitAt = 0;

export default function InteractiveEarth3D({
  countries,
  oceans,
  elevationMode,
  selected,
  showLabels,
  showOceans,
  autoRotate,
  onCountryClick,
  onElevationHit,
  zoomTarget,
}: InteractiveEarth3DProps) {
  const controlsRef = useRef<OrbitControlsImpl | null>(null);
  const [flight, setFlight] = useState<{
    goalPos: THREE.Vector3;
    goalTarget: THREE.Vector3;
    nonce: number;
  } | null>(null);
  const bounds = useMemo(() => worldBounds(countries), [countries]);
  const [elevHit, setElevHitLocal] = useState<ElevationHit | null>(null);

  const handleElevationHit = useCallback(
    (hit: ElevationHit | null) => {
      lastHitAt = Date.now();
      setElevHitLocal(hit);
      onElevationHit?.(hit);
    },
    [onElevationHit],
  );

  const zoomTo = useCallback(
    (name: string | null) => {
      const dir = new THREE.Vector3(0, 0.95, 0.75).normalize();
      if (!name) {
        const d = bounds.radius * 2.6;
        setFlight({
          goalPos: bounds.center.clone().add(dir.multiplyScalar(d)),
          goalTarget: bounds.center.clone(),
          nonce: Date.now(),
        });
        return;
      }
      const c = countries.find((k) => k.name === name);
      if (!c) return;
      const cen3 = new THREE.Vector3(...centroid3D(c));
      const dist = Math.max(boundingRadius(c) * 3.2, bounds.radius * 0.08);
      setFlight({
        goalPos: cen3.clone().add(
          dir.clone().multiplyScalar(dist)),
        goalTarget: cen3,
        nonce: Date.now(),
      });
    },
    [countries, bounds],
  );

  useEffect(() => {
    if (zoomTarget) zoomTo(zoomTarget.name);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zoomTarget?.nonce]);

  const majorLabels = useMemo(() => {
    if (!showLabels) return [];
    const majors = countries.filter((c) => c.declared >= 400000);
    const cap = majors.length > 90
      ? majors.sort((a, b) => b.declared - a.declared).slice(0, 90)
      : majors;
    return cap.map((c) => ({
      name: c.name,
      pos: centroid3D(c),
      area: c.declared,
    }));
  }, [countries, showLabels]);

  return (
    <Canvas
      dpr={[1, 1.75]}
      camera={{
        position: [
          bounds.center.x,
          bounds.radius * 2.2,
          bounds.center.z + bounds.radius * 1.7,
        ],
        near: 1,
        far: bounds.radius * 12,
        fov: 42,
      }}
      gl={{ antialias: true, powerPreference: 'high-performance' }}
      onPointerMissed={() => {
        if (!elevationMode) onCountryClick?.('');
      }}
    >
      <color attach="background" args={['#040a10']} />
      <ambientLight intensity={0.9} />
      <directionalLight position={[bounds.radius, bounds.radius * 2, bounds.radius]} intensity={0.7} />

      {showOceans &&
        oceans.map((o) =>
          o.coastline_ring_display && o.coastline_ring_display.length > 2 ? (
            <OceanPolygon
              key={o.name}
              name={o.name}
              kind={o.kind}
              ring={o.coastline_ring_display}
            />
          ) : null,
        )}

      {countries.map((c) => (
        <CountryPolygon
          key={c.name}
          name={c.name}
          rings={c.rings.map((pts, i) => ({
            pts,
            kind: (c.ringKinds[i] || 'outer') as 'outer' | 'hole',
          }))}
          fillColor={
            selected === c.name
              ? '#1c6b46'
              : c.placement === 'region_adjacent'
                ? '#3f3b2a'
                : '#14532d'
          }
          borderColor={selected === c.name ? '#00ff88' : '#2f7f55'}
          areaKm2={c.declared}
          showLabel={false}
          onPick={() => {
            if (!elevationMode) {
              zoomTo(c.name);
              onCountryClick?.(c.name);
            }
          }}
        />
      ))}

      {majorLabels.map((l) => (
        <group key={l.name} position={l.pos}>
          <Billboardish position={[0, 0, 0]}>
            <Text
              fontSize={Math.max(bounds.radius * 0.012, 45)}
              color="#9fe8c2"
              anchorX="center"
              anchorY="middle"
              outlineWidth={bounds.radius * 0.0012}
              outlineColor="#040a10"
            >
              {l.name}
            </Text>
          </Billboardish>
        </group>
      ))}

      <ElevationProbe
        elevationMode={elevationMode}
        onElevationHit={handleElevationHit}
      />
      <ElevationMarker hit={elevHit} />

      <OrbitControls
        ref={controlsRef}
        enableDamping
        dampingFactor={0.08}
        zoomSpeed={1.2}
        rotateSpeed={0.6}
        panSpeed={0.8}
        minDistance={bounds.radius * 0.02}
        maxDistance={bounds.radius * 6}
        maxPolarAngle={Math.PI * 0.49}
        target={[bounds.center.x, 0, bounds.center.z]}
        autoRotate={autoRotate}
        autoRotateSpeed={0.35}
        mouseButtons={{
          LEFT: THREE.MOUSE.PAN,
          MIDDLE: THREE.MOUSE.DOLLY,
          RIGHT: THREE.MOUSE.ROTATE,
        }}
      />

      <CameraFlight
        controlsRef={controlsRef}
        target={bounds.center}
        goalPos={flight?.goalPos ?? bounds.center}
        goalTarget={flight?.goalTarget ?? bounds.center}
        active={!!flight}
        onDone={() => setFlight(null)}
      />
    </Canvas>
  );
}

function Billboardish({
  position,
  children,
}: {
  position: [number, number, number];
  children: React.ReactNode;
}) {
  const ref = useRef<THREE.Group>(null);
  useFrame(({ camera }) => {
    if (ref.current) ref.current.quaternion.copy(camera.quaternion);
  });
  return (
    <group ref={ref} position={position}>
      {children}
    </group>
  );
}
