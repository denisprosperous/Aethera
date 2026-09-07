'use client';

/**
 * AETHERA v27.0 — Manifold3D
 *
 * The Physical Truth intrinsic manifold rendered as a true 3D object:
 *  • Vertices = intrinsic SMACOF coordinates [x, y, z] (z ≈ 0 — the data
 *    genuinely says the world manifold is planar; nothing is bent).
 *  • Faces = Delaunay triangulation of the intrinsic points.
 *  • Colors = true-area heatmap (log-scaled).
 * Hover any node for its Physical Truth area; click to navigate.
 */

import { useMemo, useState } from 'react';
import * as THREE from 'three';
import { useFrame, useThree } from '@react-three/fiber';
import { Line, Html } from '@react-three/drei';
import { Scene, ACCENT, heatColorHex, areaColorHex, ViewportHud, Tip } from './Scene';
import { delaunay, uniqueEdges, fitTransform, type Pt } from '@/lib/delaunay';

export interface ManifoldRegion {
  name: string;
  coords: [number, number, number];
  area_km2: number;
}

interface Manifold3DProps {
  regions: ManifoldRegion[];
  edgeCount?: number;
  residual?: number;
  /** Optional per-region heatmap value override (0..1). */
  heatValues?: Record<string, number> | null;
  /** Optional extra HUD text. */
  hud?: string;
  onRegionClick?: (region: string) => void;
  /** Labels for named regions (rendered as floating text). */
  labels?: Record<string, string> | null;
  showMesh?: boolean;
  viewPreset?: 'orbit' | 'planar';
  autoRotate?: boolean;
}

const EXTENT = 12;

/**
 * Camera rig — imperatively moves the camera when the caller toggles
 * between the free 3D orbit and the top-down 2D planar inspection view.
 */
function CameraRig({ preset }: { preset: 'orbit' | 'planar' }) {
  const { camera } = useThree();
  useFrame(() => {
    const targetPos =
      preset === 'planar'
        ? new THREE.Vector3(0, EXTENT * 2.6, 0.42)
        : new THREE.Vector3(EXTENT * 1.05, EXTENT * 1.0, EXTENT * 1.45);
    const dist = camera.position.distanceTo(targetPos);
    if (dist > 0.05) {
      camera.position.lerp(targetPos, 0.12);
      camera.lookAt(0, 0, 0);
    }
  });
  return null;
}

function Node({
  position,
  color,
  name,
  area,
  onClick,
  onHover,
}: {
  position: [number, number, number];
  color: [number, number, number];
  name: string;
  area: number;
  onClick: () => void;
  onHover: (v: { name: string; area: number; position: [number, number, number] } | null) => void;
}) {
  const [hot, setHot] = useState(false);
  return (
    <mesh
      position={position}
      scale={hot ? 1.8 : 1}
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
      <sphereGeometry args={[0.16, 14, 14]} />
      <meshStandardMaterial
        color={new THREE.Color(...color)}
        emissive={new THREE.Color(...color)}
        emissiveIntensity={hot ? 1.6 : 0.55}
        roughness={0.4}
      />
    </mesh>
  );
}

export default function Manifold3D({
  regions,
  edgeCount,
  residual,
  heatValues = null,
  hud,
  onRegionClick,
  labels = null,
  showMesh = true,
  viewPreset = 'orbit',
  autoRotate = false,
}: Manifold3DProps) {
  const [hover, setHover] = useState<{ name: string; area: number; position: [number, number, number] } | null>(null);

  // Legacy mode (heatValues supplied) uses the blue↔red deviation scale;
  // true-area mode uses the single-hue green ramp.
  const colorFn = heatValues ? heatColorHex : areaColorHex;

  const model = useMemo(() => {
    const valid = regions.filter(
      (r) => r.coords?.length >= 2 && Number.isFinite(r.coords[0]) && Number.isFinite(r.coords[1]),
    );
    if (valid.length < 3) return null;
    const pts: Pt[] = valid.map((r) => ({ x: r.coords[0], y: r.coords[1] }));
    const tf = fitTransform(pts, EXTENT);
    const zs = valid.map((r) => (Number.isFinite(r.coords[2]) ? r.coords[2] : 0));
    const zSpan = Math.max(...zs.map(Math.abs), 1e-9);
    const zScale = zSpan > 1e-6 ? (EXTENT * 0.5) / zSpan : 0;

    const positions = valid.map((r, i) => ({
      x: (r.coords[0] - tf.cx) * tf.scale,
      y: zScale ? r.coords[2] * zScale : 0,
      z: -(r.coords[1] - tf.cy) * tf.scale,
    }));

    const areas = valid.map((r) => Math.max(1, r.area_km2 || 1));
    const logs = areas.map((a) => Math.log10(a));
    const lmin = Math.min(...logs);
    const lmax = Math.max(...logs);

    const nodes = valid.map((r, i) => ({
      name: r.name,
      area: r.area_km2,
      position: [positions[i].x, positions[i].y, positions[i].z] as [number, number, number],
      heat: heatValues
        ? heatValues[r.name] ?? null
        : (logs[i] - lmin) / Math.max(1e-9, lmax - lmin),
    }));

    const tris = delaunay(pts);
    const colorAt = (idx: number) => colorFn(nodes[idx].heat ?? 0.5);
    const edges = uniqueEdges(tris).map(
      ([a, b]) =>
        [
          [positions[a].x, positions[a].y, positions[a].z],
          [positions[b].x, positions[b].y, positions[b].z],
        ] as [[number, number, number], [number, number, number]],
    );
    // Triangle mesh with vertex colors (true-area heatmap).
    const triGeom = (() => {
      const geom = new THREE.BufferGeometry();
      const verts: number[] = [];
      const cols: number[] = [];
      for (const [a, b, c] of tris) {
        for (const idx of [a, b, c]) {
          verts.push(positions[idx].x, positions[idx].y, positions[idx].z);
          const col = colorAt(idx);
          cols.push(col[0], col[1], col[2]);
        }
      }
      geom.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
      geom.setAttribute('color', new THREE.Float32BufferAttribute(cols, 3));
      geom.computeVertexNormals();
      return geom;
    })();

    return { nodes, edges, triGeom };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [regions, heatValues]);

  if (!model) {
    return (
      <div
        style={{
          width: '100%', height: '100%', display: 'flex', alignItems: 'center',
          justifyContent: 'center', color: '#5b6b7b', fontFamily: 'monospace', fontSize: 12,
        }}
      >
        Manifold needs ≥ 3 finite coordinates — load the Physical Truth scenario first.
      </div>
    );
  }

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <Scene camera={[EXTENT * 1.05, EXTENT * 1.0, EXTENT * 1.45]} autoRotate={autoRotate}>
        <CameraRig preset={viewPreset} />
        <gridHelper args={[EXTENT * 2.9, 26, '#0f2436', '#0a1826']} />
        {showMesh && (
          <mesh geometry={model.triGeom}>
            <meshStandardMaterial
              vertexColors side={THREE.DoubleSide}
              transparent opacity={0.34} roughness={0.7}
              depthWrite={false}
            />
          </mesh>
        )}
        <Line
          points={model.edges.flat()}
          color="#0e4d3a"
          lineWidth={1}
          transparent
          opacity={0.85}
        />
        {model.nodes.map((n, i) => (
          <Node
            key={`${n.name}-${i}`}
            position={n.position}
            color={colorFn(n.heat ?? 0.5)}
            name={n.name}
            area={n.area}
            onClick={() => onRegionClick?.(n.name)}
            onHover={setHover}
          />
        ))}
        {labels &&
          Object.entries(labels).map(([name, text]) => {
            const node = model.nodes.find((n) => n.name === name);
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
        text={
          hud ||
          `PHYSICAL TRUTH MANIFOLD — ${model.nodes.length} NODES · ${edgeCount ?? '?'} EDGES · RESIDUAL ${(residual ?? 0).toExponential(3)} · EMERGENT SHAPE, NO SPHERE`
        }
      />

      {hover && (
        <Tip>
          <div style={{ color: ACCENT, fontWeight: 700 }}>{hover.name}</div>
          <div>{hover.area.toLocaleString()} km²</div>
          <div style={{ color: '#5b6b7b' }}>click → module page</div>
        </Tip>
      )}
    </div>
  );
}
