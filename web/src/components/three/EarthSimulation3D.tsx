'use client';

/**
 * AETHERA v30.1 — EarthSimulation3D
 *
 * The mandatory 3D Earth Simulation, implemented principle-first.
 *
 *  • Vertices = intrinsic SMACOF coordinates [x, y, z] returned by
 *    /api/solve/physical-truth. If the solver says z ≈ 0 (flat), the
 *    object renders flat; if a future solve returns z ≠ 0, it renders
 *    curved. Nothing here bends the data.
 *  • Edges = the solver's intrinsic edge graph (real solved adjacencies),
 *    drawn in accent green; a faint Delaunay hull fills the manifold.
 *  • Colors = per-region heatmap (true area or legacy deviation).
 *  • Labels = region names (hover for the Physical Truth tooltip).
 *
 * Two display modes:
 *  • 'intrinsic'        — the solver's coordinates, exactly as produced.
 *  • 'area-preserving'  — an iterative equal-area relaxation that warps
 *    the embedding so every region's rendered area matches its absolute
 *    scalar area (km²). A purely post-hoc visual transform; the intrinsic
 *    solve itself is never mutated.
 *
 * There is NO pre-seeded sphere anywhere in this file. No lon/lat, no
 * WGS84, no EPSG — Axiom 3 (Zero Bias) and Axiom 2 (Intrinsic Emergence).
 */

import { useMemo, useState } from 'react';
import * as THREE from 'three';
import { useFrame, useThree } from '@react-three/fiber';
import { Line, Html } from '@react-three/drei';
import { Scene, ACCENT, heatColorHex, areaColorHex, ViewportHud, Tip } from './Scene';
import { delaunay, uniqueEdges, fitTransform, type Pt } from '@/lib/delaunay';

export interface EarthRegion {
  name: string;
  area: number;        // absolute area, km²
  deviation: number | null; // legacy deviation, percent (null if unknown)
}

export interface EarthSimulation3DData {
  vertices: number[][];    // [x, y, z] intrinsic coordinates from the solver
  edges: number[][] | string[][]; // solver edge graph — index or name pairs
  regions: EarthRegion[];
}

export interface EarthSimulation3DProps {
  data: EarthSimulation3DData;
  mode: 'intrinsic' | 'area-preserving';
  heatmap: 'none' | 'area' | 'deviation';
  showLabels?: boolean;
  showHull?: boolean;
  autoRotate?: boolean;
  viewPreset?: 'orbit' | 'planar';
  onRegionClick?: (region: string) => void;
  hudSuffix?: string;
}

const EXTENT = 12;

/** Camera rig for the orbit ↔ planar presets (same convention as TrueGlobe). */
function CameraRig({ preset }: { preset: 'orbit' | 'planar' }) {
  const { camera } = useThree();
  useFrame(() => {
    const targetPos =
      preset === 'planar'
        ? new THREE.Vector3(0, EXTENT * 2.6, 0.42)
        : new THREE.Vector3(EXTENT * 1.05, EXTENT * 1.0, EXTENT * 1.45);
    if (camera.position.distanceTo(targetPos) > 0.05) {
      camera.position.lerp(targetPos, 0.12);
      camera.lookAt(0, 0, 0);
    }
  });
  return null;
}

function Node({
  position,
  color,
  scale,
  name,
  area,
  onClick,
  onHover,
}: {
  position: [number, number, number];
  color: [number, number, number];
  scale: number;
  name: string;
  area: number;
  onClick: () => void;
  onHover: (v: { name: string; area: number; position: [number, number, number] } | null) => void;
}) {
  const [hot, setHot] = useState(false);
  return (
    <mesh
      position={position}
      scale={scale * (hot ? 1.7 : 1)}
      onPointerOver={(e) => {
        e.stopPropagation();
        setHot(true);
        onHover({ name, area, position });
      }}
      onPointerOut={() => {
        setHot(false);
        onHover(null);
      }}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
    >
      <sphereGeometry args={[0.15, 14, 14]} />
      <meshStandardMaterial
        color={new THREE.Color(...color)}
        emissive={new THREE.Color(...color)}
        emissiveIntensity={hot ? 1.6 : 0.55}
        roughness={0.4}
      />
    </mesh>
  );
}

/**
 * Iterative equal-area relaxation. For each vertex, its rendered area is
 * approximated by 1/3 of the total area of its Delaunay-adjacent
 * triangles (the barycentric fan). The vertex is then pushed away from /
 * toward the fan centroid so the rendered area approaches the absolute
 * scalar area. Damped and clamped; falls back to the intrinsic layout on
 * any numerical instability.
 */
function areaPreservingLayout(
  pts: Pt[],
  areas: number[],
  iterations = 36,
): Pt[] {
  const n = pts.length;
  if (n < 4 || areas.length !== n) return pts;
  let cur: Pt[] = pts.map((p) => ({ ...p }));
  try {
    for (let it = 0; it < iterations; it++) {
      const tris = delaunay(cur);
      const fan: number[][] = Array.from({ length: n }, () => []);
      const fanArea = new Float64Array(n);
      const centroidX = new Float64Array(n);
      const centroidY = new Float64Array(n);
      for (const [a, b, c] of tris) {
        const ax = cur[a].x, ay = cur[a].y, bx = cur[b].x, by = cur[b].y;
        const cx = cur[c].x, cy = cur[c].y;
        const area2 = Math.abs((bx - ax) * (cy - ay) - (cx - ax) * (by - ay)) / 2;
        if (!Number.isFinite(area2) || area2 <= 1e-12) continue;
        for (const [i, j, k] of [
          [a, b, c], [b, a, c], [c, a, b],
        ] as const) {
          fan[i].push(j, k);
          fanArea[i] += area2 / 3;
          centroidX[i] += (cur[j].x + cur[k].x) / 2 / Math.max(1, fan[i].length / 2);
          centroidY[i] += (cur[j].y + cur[k].y) / 2 / Math.max(1, fan[i].length / 2);
        }
      }
      let maxMove = 0;
      const next: Pt[] = cur.map((p, i) => {
        if (fan[i].length < 2 || fanArea[i] <= 1e-9) return p;
        const target = Math.max(1, areas[i]);
        // Correction factor clamped to keep the relaxation stable.
        const f = Math.max(0.6, Math.min(1.8, Math.sqrt(target / fanArea[i])));
        const damp = 0.12;
        const nx = centroidX[i] + (p.x - centroidX[i]) * (1 + (f - 1) * damp);
        const ny = centroidY[i] + (p.y - centroidY[i]) * (1 + (f - 1) * damp);
        if (Number.isFinite(nx) && Number.isFinite(ny)) {
          maxMove = Math.max(maxMove, Math.hypot(nx - p.x, ny - p.y));
          return { x: nx, y: ny };
        }
        return p;
      });
      cur = next;
      if (maxMove < 1e-4) break;
    }
  } catch {
    return pts; // numerical instability → intrinsic layout is the honest fallback
  }
  return cur;
}

export default function EarthSimulation3D({
  data,
  mode,
  heatmap,
  showLabels = true,
  showHull = true,
  autoRotate = false,
  viewPreset = 'orbit',
  onRegionClick,
  hudSuffix,
}: EarthSimulation3DProps) {
  const [hover, setHover] = useState<{ name: string; area: number; position: [number, number, number] } | null>(null);

  const colorFn =
    heatmap === 'deviation' ? heatColorHex :
    heatmap === 'area' ? areaColorHex :
    null;

  const model = useMemo(() => {
    const regions = data.regions;
    const vertices = data.vertices;
    if (regions.length < 3 || vertices.length < 3) return null;

    const valid = regions
      .map((r, i) => ({ r, v: vertices[i] }))
      .filter(({ v }) => v?.length >= 2 && Number.isFinite(v[0]) && Number.isFinite(v[1]));
    if (valid.length < 3) return null;

    const raw: Pt[] = valid.map(({ v }) => ({ x: v[0], y: v[1] }));
    const areas = valid.map(({ r }) => Math.max(1, r.area || 1));

    // Fit to the viewport BEFORE relaxation so both modes share a frame.
    const tf = fitTransform(raw, EXTENT);
    const fitted: Pt[] = raw.map((p) => ({
      x: (p.x - tf.cx) * tf.scale,
      y: -(p.y - tf.cy) * tf.scale,
    }));

    // Area-preserving mode: post-hoc equal-area relaxation of the embedding.
    const layout =
      mode === 'area-preserving' ? areaPreservingLayout(fitted, areas) : fitted;

    const zs = valid.map(({ v }) => (Number.isFinite(v[2]) ? v[2] : 0));
    const zSpan = Math.max(...zs.map(Math.abs), 1e-9);
    const zScale = zSpan > 1e-6 ? (EXTENT * 0.5) / zSpan : 0;

    const positions = layout.map((p, i) => ({
      x: p.x,
      y: zScale ? valid[i].v[2] * zScale : 0,
      z: p.y,
    }));

    // Heat values.
    const areaLogs = areas.map((a) => Math.log10(a));
    const lmin = Math.min(...areaLogs);
    const lmax = Math.max(...areaLogs);
    const heatOf = (i: number): number | null => {
      if (heatmap === 'deviation') {
        const d = valid[i].r.deviation;
        if (d === null || !Number.isFinite(d)) return null;
        // rel% > 0 → legacy over-reports → red (t=1); < 0 → blue (t=0).
        return 0.5 + Math.max(-1, Math.min(1, d / 200)) * 0.5;
      }
      if (heatmap === 'area') return (areaLogs[i] - lmin) / Math.max(1e-9, lmax - lmin);
      return null;
    };

    const nodes = valid.map(({ r }, i) => ({
      name: r.name,
      area: r.area,
      deviation: r.deviation,
      position: [positions[i].x, positions[i].y, positions[i].z] as [number, number, number],
      heat: heatOf(i),
      // Glyph size scales with sqrt(area) — visible area honesty.
      glyph: 0.55 + 0.85 * Math.sqrt(Math.min(1, areas[i] / 9_600_000)),
    }));

    // Solver's intrinsic edge graph (name pairs or index pairs).
    const nameToIdx = new Map(valid.map(({ r }, i) => [r.name, i]));
    const solverEdges: [[number, number, number], [number, number, number]][] = [];
    for (const pair of data.edges || []) {
      let a = -1, b = -1;
      if (pair.length === 2) {
        if (typeof pair[0] === 'number' && typeof pair[1] === 'number') {
          a = pair[0] as number; b = pair[1] as number;
        } else {
          a = nameToIdx.get(String(pair[0])) ?? -1;
          b = nameToIdx.get(String(pair[1])) ?? -1;
        }
      }
      if (a >= 0 && b >= 0 && a !== b) {
        solverEdges.push([
          [positions[a].x, positions[a].y, positions[a].z],
          [positions[b].x, positions[b].y, positions[b].z],
        ]);
      }
    }

    // Delaunay hull of the embedding (faint fill + fine wireframe).
    const pts2d: Pt[] = layout.map((p) => ({ x: p.x, y: p.y }));
    const tris = delaunay(pts2d);
    const hullEdges = uniqueEdges(tris).map(
      ([a, b]) =>
        [
          [positions[a].x, positions[a].y, positions[a].z],
          [positions[b].x, positions[b].y, positions[b].z],
        ] as [[number, number, number], [number, number, number]],
    );

    const triGeom = (() => {
      const geom = new THREE.BufferGeometry();
      const verts: number[] = [];
      const cols: number[] = [];
      const neutral = new THREE.Color('#12321f');
      for (const [a, b, c] of tris) {
        for (const idx of [a, b, c]) {
          verts.push(positions[idx].x, positions[idx].y, positions[idx].z);
          const h = heatOf(idx);
          const col = h === null ? neutral : new THREE.Color(...colorFn!(h));
          cols.push(col.r, col.g, col.b);
        }
      }
      geom.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
      geom.setAttribute('color', new THREE.Float32BufferAttribute(cols, 3));
      geom.computeVertexNormals();
      return geom;
    })();

    return { nodes, solverEdges, hullEdges, triGeom };
  }, [data, mode, heatmap]);

  const labels = useMemo(() => {
    if (!showLabels) return null;
    const top = [...data.regions].sort((a, b) => (b.area || 0) - (a.area || 0)).slice(0, 10);
    return Object.fromEntries(top.map((r) => [r.name, r.name]));
  }, [data.regions, showLabels]);

  if (!model) {
    return (
      <div
        style={{
          width: '100%', height: '100%', display: 'flex', alignItems: 'center',
          justifyContent: 'center', color: '#5b6b7b', fontFamily: 'monospace', fontSize: 12,
        }}
      >
        Need ≥ 3 finite intrinsic vertices — check /api/solve/physical-truth.
      </div>
    );
  }

  const modeHud =
    mode === 'intrinsic'
      ? 'INTRINSIC — SOLVER COORDINATES, UNTOUCHED'
      : 'AREA-PRESERVING — POST-HOC EQUAL-AREA RELAXATION';
  const heatHud =
    heatmap === 'none' ? 'NO HEATMAP' :
    heatmap === 'area' ? 'TRUE-AREA HEATMAP (LOG SCALE)' :
    'LEGACY DEVIATION HEATMAP (RED = INFLATED, BLUE = SHRUNK)';

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <Scene camera={[EXTENT * 1.05, EXTENT * 1.0, EXTENT * 1.45]} autoRotate={autoRotate}>
        <CameraRig preset={viewPreset} />
        <gridHelper args={[EXTENT * 2.9, 26, '#0f2436', '#0a1826']} />
        {showHull && (
          <mesh geometry={model.triGeom}>
            <meshStandardMaterial
              vertexColors side={THREE.DoubleSide}
              transparent opacity={0.32} roughness={0.7}
              depthWrite={false}
            />
          </mesh>
        )}
        {/* Delaunay hull wireframe — dim */}
        <Line
          points={model.hullEdges.flat()}
          color="#0e4d3a"
          lineWidth={1}
          transparent
          opacity={0.5}
        />
        {/* Solver's intrinsic edge graph — bright accent */}
        <Line
          points={model.solverEdges.flat()}
          color={ACCENT}
          lineWidth={1.6}
          transparent
          opacity={0.9}
        />
        {model.nodes.map((n, i) => (
          <Node
            key={`${n.name}-${i}`}
            position={n.position}
            color={n.heat === null ? ([0.0, 1.0, 0.53] as [number, number, number]) : colorFn!(n.heat)}
            scale={n.glyph}
            name={n.name}
            area={n.area}
            onClick={() => onRegionClick?.(n.name)}
            onHover={setHover}
          />
        ))}
        {labels &&
          Object.entries(labels).map(([name, text]) => {
            const node = model.nodes.find((nd) => nd.name === name);
            if (!node) return null;
            return (
              <group key={name} position={[node.position[0], node.position[1] + 0.55, node.position[2]]}>
                <Html center distanceFactor={22} zIndexRange={[40, 0]}>
                  <div
                    style={{
                      color: ACCENT, fontFamily: 'monospace', fontSize: 10,
                      background: 'rgba(4,10,16,0.75)', padding: '2px 7px',
                      borderRadius: 4, border: '1px solid rgba(0,255,136,0.25)',
                      whiteSpace: 'nowrap', pointerEvents: 'none', userSelect: 'none',
                    }}
                  >
                    {text}
                  </div>
                </Html>
              </group>
            );
          })}
      </Scene>

      <ViewportHud
        text={`3D EARTH SIMULATION — ${model.nodes.length} REGIONS · ${model.solverEdges.length} INTRINSIC EDGES · ${modeHud} · ${heatHud}${hudSuffix ? ` · ${hudSuffix}` : ''}`}
      />

      {hover && (
        <Tip>
          <div style={{ color: ACCENT, fontWeight: 700 }}>{hover.name}</div>
          <div>{hover.area.toLocaleString()} km²</div>
          {hover.name && (
            <div style={{ color: '#5b6b7b' }}>click → Physical Truth module</div>
          )}
        </Tip>
      )}
    </div>
  );
}
