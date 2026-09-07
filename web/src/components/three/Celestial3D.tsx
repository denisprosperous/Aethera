'use client';

/**
 * AETHERA v27.0 — Celestial3D
 *
 * 3D trajectory viewer for the Celestial Dynamics scenario: renders the
 * full [x, y, z] trajectory as a glowing path with an animated orbiting
 * body, velocity/force field arrows, and the orbital plane grid. Includes
 * a time-slider to scrub the animation. No projection, no bias — the path
 * is exactly what the Rust integrator produced.
 */

import { useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';
import { Line } from '@react-three/drei';
import { Scene, ACCENT, ViewportHud } from './Scene';

interface Celestial3DProps {
  trajectory: number[][];
  forceLaw: string;
  dt?: number;
  tMax?: number;
}

const ARROW_SAMPLES = 14;

function Orbiter({
  points,
  speedRef,
}: {
  points: THREE.Vector3[];
  speedRef: React.MutableRefObject<number>;
}) {
  const mesh = useRef<THREE.Mesh>(null);
  const prog = useRef(0);
  const segRef = useRef(0);

  useFrame((_, delta) => {
    if (points.length < 2) return;
    prog.current += delta * speedRef.current * (points.length / 260);
    if (prog.current >= points.length - 1) prog.current = 0;
    const seg = Math.min(points.length - 2, Math.floor(prog.current));
    if (seg !== segRef.current) segRef.current = seg;
    const f = prog.current - seg;
    const p = points[seg].clone().lerp(points[seg + 1], f);
    if (mesh.current) mesh.current.position.copy(p);
  });

  return (
    <mesh ref={mesh}>
      <sphereGeometry args={[0.32, 24, 24]} />
      <meshStandardMaterial
        color={ACCENT}
        emissive={ACCENT}
        emissiveIntensity={2.4}
        roughness={0.25}
      />
      <pointLight color={ACCENT} intensity={2.2} distance={9} />
    </mesh>
  );
}

export default function Celestial3D({
  trajectory,
  forceLaw,
  dt = 0.1,
  tMax = 10,
}: Celestial3DProps) {
  const [speed, setSpeed] = useState(1);
  const speedRef = useRef(1);
  speedRef.current = speed;

  // Fit the raw trajectory into view space.
  const { points, extent } = useMemo(() => {
    const pts = trajectory.filter(
      (p) => Array.isArray(p) && p.length >= 3 && p.every((v) => Number.isFinite(v)),
    );
    if (pts.length < 2) {
      return { points: [] as THREE.Vector3[], extent: 10 };
    }
    let minX = Infinity, minY = Infinity, minZ = Infinity;
    let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
    for (const p of pts) {
      minX = Math.min(minX, p[0]); minY = Math.min(minY, p[1]); minZ = Math.min(minZ, p[2]);
      maxX = Math.max(maxX, p[0]); maxY = Math.max(maxY, p[1]); maxZ = Math.max(maxZ, p[2]);
    }
    const span = Math.max(maxX - minX, maxY - minY, maxZ - minZ, 1e-6);
    const ext = 14;
    const s = (ext * 2) / span;
    const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2, cz = (minZ + maxZ) / 2;
    const scaled = pts.map(
      (p) => new THREE.Vector3((p[0] - cx) * s, (p[1] - cy) * s, (p[2] - cz) * s),
    );
    return { points: scaled, extent: ext };
  }, [trajectory]);

  // Velocity arrows sampled along the path (finite-difference direction).
  const arrows = useMemo(() => {
    if (points.length < 4) return [];
    const out: { origin: THREE.Vector3; dir: THREE.Vector3; len: number }[] = [];
    for (let i = 1; i < ARROW_SAMPLES; i++) {
      const t = Math.round((i / ARROW_SAMPLES) * (points.length - 2));
      const dir = points[t + 1].clone().sub(points[t]);
      const len = dir.length();
      if (len < 1e-9) continue;
      out.push({ origin: points[t], dir: dir.normalize(), len });
    }
    return out;
  }, [points]);

  const linePts = useMemo(() => points.map((v) => [v.x, v.y, v.z] as [number, number, number]), [points]);

  if (points.length < 2) {
    return (
      <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#5b6b7b', fontFamily: 'monospace', fontSize: 12 }}>
        No finite trajectory points — run the simulation first.
      </div>
    );
  }

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <Scene camera={[extent * 1.1, extent * 0.9, extent * 1.4]}>
        {/* Orbital plane grid (XY) */}
        <gridHelper
          args={[extent * 2.6, 22, '#0f2436', '#0a1826']}
          rotation={[Math.PI / 2, 0, 0]}
        />
        {/* Full trajectory path */}
        <Line
          points={linePts}
          color={ACCENT}
          lineWidth={1.6}
          transparent
          opacity={0.85}
        />
        {/* Launch marker */}
        <mesh position={points[0]}>
          <octahedronGeometry args={[0.22, 0]} />
          <meshBasicMaterial color="#06b6d4" wireframe />
        </mesh>
        {/* Force-field arrows */}
        {arrows.map((a, i) => (
          <arrowHelper
            key={i}
            args={[a.dir, a.origin, Math.max(0.7, a.len * 6), '#06b6d4', 0.22, 0.12]}
          />
        ))}
        <Orbiter points={points} speedRef={speedRef} />
      </Scene>

      <ViewportHud text={`CELESTIAL DYNAMICS — ${forceLaw.toUpperCase()} · dt=${dt} · t_max=${tMax} · ${trajectory.length} PTS`} />

      {/* Time / speed scrubber */}
      <div
        style={{
          position: 'absolute', bottom: 12, left: 12, right: 12, zIndex: 6,
          display: 'flex', alignItems: 'center', gap: 10,
          background: 'rgba(4,10,16,0.85)', border: '1px solid #1c2a38',
          borderRadius: 8, padding: '8px 12px', fontFamily: 'monospace',
        }}
      >
        <span style={{ color: '#5b6b7b', fontSize: 10, letterSpacing: 1 }}>TIME&nbsp;FLOW</span>
        <input
          type="range" min={0} max={4} step={0.05} value={speed}
          onChange={(e) => setSpeed(Number(e.target.value))}
          style={{ flex: 1, accentColor: ACCENT, cursor: 'pointer' }}
          aria-label="Animation speed"
        />
        <span style={{ color: ACCENT, fontSize: 11, minWidth: 44 }}>{speed.toFixed(2)}×</span>
      </div>
    </div>
  );
}
