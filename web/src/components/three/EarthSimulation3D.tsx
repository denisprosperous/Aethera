'use client';

/**
 * AETHERA v33.0 — EarthSimulation3D
 *
 * THE 3D EARTH SIMULATION, principle-first: COUNTRY TERRITORIES.
 *
 * v33.0 change — the simulator no longer renders a node cloud. Each
 * region is drawn as a CLOSED TERRITORY POLYGON derived from the solver's
 * own intrinsic coordinates:
 *
 *  • Vertices = intrinsic SMACOF coordinates [x, y, z] returned by
 *    /api/solve/physical-truth. If the solver says z ≈ 0 (flat), the
 *    object renders flat; if a future solve returns z ≠ 0, it renders
 *    curved. Nothing here bends the data.
 *  • Territories = the weighted nearest-vertex dual of the Delaunay
 *    triangulation of the intrinsic point set (see lib/geometry.ts) — a
 *    closed polygon per country with real border edges, filled by heatmap
 *    and labelled at its polygon centroid. Intrinsic mode keeps the dual
 *    unweighted (pure geometry of the solve); Area-Preserving mode
 *    weights the capture boundaries by the declared absolute scalar
 *    areas so cell areas approach the Physical Truth values. Computed,
 *    never assumed.
 *  • Borders = the cells' shared boundary edges (plus the convex-hull
 *    rim, the edge of the known world).
 *  • Labels = centred on each polygon, area-scaled, always readable.
 *  • Seed markers (the old "nodes") are OFF by default and exist only as
 *    an explicit toggle — flat circular markers, not spheres.
 *
 * There is NO pre-seeded shape anywhere in this file. No lon/lat, no
 * WGS84, no EPSG, no globe — Axiom 3 (Zero Bias) and Axiom 2 (Intrinsic
 * Emergence).
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import { useFrame, useThree } from '@react-three/fiber';
import { Line, Html, Billboard } from '@react-three/drei';
import { Scene, ACCENT, heatColorHex, areaColorHex, ViewportHud } from './Scene';
import { delaunay, uniqueEdges, fitTransform, type Pt } from '@/lib/delaunay';
import { buildTerritories, type TerritoryMesh } from '@/lib/geometry';

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

/** Reported to the page once territories are computed (transparency). */
export interface TerritoryRenderStats {
  cells: number;
  borderSegments: number;
  /** Pearson r between log(rendered cell area) and log(declared area). */
  areaCorrelation: number | null;
}

export interface EarthSimulation3DProps {
  data: EarthSimulation3DData;
  mode: 'intrinsic' | 'area-preserving';
  heatmap: 'none' | 'area' | 'deviation';
  showLabels?: boolean;
  showHull?: boolean;
  /** v33.0: seed markers — OFF by default; countries are the rendering. */
  showNodes?: boolean;
  autoRotate?: boolean;
  viewPreset?: 'orbit' | 'planar';
  onRegionClick?: (region: string) => void;
  hudSuffix?: string;
  /** v32.0 deep link: region name to highlight (accent border + marker). */
  selectedRegion?: string | null;
  /** v32.1 country visibility: how many region labels to render. */
  labelDensity?: 'all' | 'major' | 'none';
  /** v33.0: territory stats for the legend panel. */
  onRenderStats?: (stats: TerritoryRenderStats) => void;
}

const EXTENT = 12;

/** Camera rig for the orbit ↔ planar presets. */
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

function pearson(xs: number[], ys: number[]): number | null {
  const n = Math.min(xs.length, ys.length);
  if (n < 3) return null;
  let sx = 0, sy = 0;
  for (let i = 0; i < n; i++) { sx += xs[i]; sy += ys[i]; }
  const mx = sx / n, my = sy / n;
  let sxy = 0, sxx = 0, syy = 0;
  for (let i = 0; i < n; i++) {
    const dx = xs[i] - mx, dy = ys[i] - my;
    sxy += dx * dy; sxx += dx * dx; syy += dy * dy;
  }
  if (sxx <= 1e-12 || syy <= 1e-12) return null;
  return sxy / Math.sqrt(sxx * syy);
}

export default function EarthSimulation3D({
  data,
  mode,
  heatmap,
  showLabels = true,
  showHull = true,
  showNodes = false,
  autoRotate = false,
  viewPreset = 'orbit',
  onRegionClick,
  hudSuffix,
  selectedRegion = null,
  labelDensity = 'all',
  onRenderStats,
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

    // Fit to the viewport so both modes share a frame.
    const tf = fitTransform(raw, EXTENT);
    const fitted: Pt[] = raw.map((p) => ({
      x: (p.x - tf.cx) * tf.scale,
      y: -(p.y - tf.cy) * tf.scale,
    }));

    // ---- v33.0: COUNTRY TERRITORIES (weighted-nearest-vertex dual) ------
    // Intrinsic mode: unweighted dual — the solve's own geometry, as
    // produced. Area-Preserving mode: capture boundaries re-derived from
    // the declared absolute scalar areas so rendered cell areas approach
    // the Physical Truth values. Coordinates never move in either mode.
    const territory: TerritoryMesh = buildTerritories(fitted, areas, {
      areaWeighted: mode === 'area-preserving',
    });
    const effective = territory.positions; // 2D seeds actually rendered

    const zs = valid.map(({ v }) => (Number.isFinite(v[2]) ? v[2] : 0));
    const zSpan = Math.max(...zs.map(Math.abs), 1e-9);
    const zScale = zSpan > 1e-6 ? (EXTENT * 0.5) / zSpan : 0;
    const zOf = (i: number) => (zScale ? valid[i].v[2] * zScale : 0);

    // 3D positions of the seeds (solver z-lift preserved).
    const positions = effective.map((p, i) => ({
      x: p.x,
      y: zOf(i),
      z: p.y,
    }));

    // Heat values per region.
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

    // Solid fill: each convex cell fan-triangulated from its centroid,
    // one flat colour per country (the owner's heat colour). Cells sit at
    // their seed's solver z-altitude (planar solves stay exactly flat).
    const fillTriOwners: number[] = [];
    const fillGeom = (() => {
      const geom = new THREE.BufferGeometry();
      const verts: number[] = [];
      const cols: number[] = [];
      const neutral = new THREE.Color('#12321f');
      for (const cell of territory.territories) {
        if (!cell || cell.ring.length < 3) continue;
        const h = heatOf(cell.owner);
        const col = h === null ? neutral : new THREE.Color(...colorFn!(h));
        const zc = zOf(cell.owner);
        const c = cell.centroid;
        const ring = cell.ring;
        for (let i = 0; i < ring.length; i++) {
          const a = ring[i];
          const b = ring[(i + 1) % ring.length];
          for (const p of [c, a, b]) {
            verts.push(p.x, zc, p.y);
            cols.push(col.r, col.g, col.b);
          }
          fillTriOwners.push(cell.owner);
        }
      }
      geom.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
      geom.setAttribute('color', new THREE.Float32BufferAttribute(cols, 3));
      geom.computeVertexNormals();
      return geom;
    })();

    // Border rings between territories — the country outlines (closed).
    const borderPts: [number, number, number][] = [];
    let borderSegmentCount = 0;
    for (const cell of territory.territories) {
      if (!cell || cell.ring.length < 3) continue;
      const zc = zOf(cell.owner) + 0.015;
      const ring = cell.ring;
      for (let i = 0; i < ring.length; i++) {
        const a = ring[i];
        const b = ring[(i + 1) % ring.length];
        borderPts.push([a.x, zc, a.y], [b.x, zc, b.y]);
        borderSegmentCount++;
      }
    }

    // Interior triangulation edges (optional faint mesh layer).
    const meshEdges = uniqueEdges(delaunay(effective)).map(
      ([a, b]) =>
        [
          [positions[a].x, positions[a].y, positions[a].z],
          [positions[b].x, positions[b].y, positions[b].z],
        ] as [[number, number, number], [number, number, number]],
    );

    // Solver's intrinsic adjacency graph (name pairs or index pairs).
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

    // Deep-link highlight: the selected country's derived border ring.
    const selIdx = selectedRegion
      ? valid.findIndex(({ r }) => r.name === selectedRegion)
      : -1;
    const selCell = selIdx >= 0 ? territory.territories[selIdx] : null;
    const selectedLoops: [number, number, number][][] =
      selCell && selCell.ring.length >= 3
        ? [
            [
              ...selCell.ring.map((p) => [p.x, zOf(selIdx) + 0.03, p.y] as [number, number, number]),
              [selCell.ring[0].x, zOf(selIdx) + 0.03, selCell.ring[0].y] as [number, number, number],
            ],
          ]
        : [];

    // Seed markers (explicit toggle only).
    const seeds = valid.map(({ r }, i) => ({
      name: r.name,
      area: r.area,
      position: [positions[i].x, positions[i].y, positions[i].z] as [number, number, number],
      radius: 0.05 + 0.1 * Math.sqrt(Math.min(1, areas[i] / 9_600_000)),
    }));

    // Label anchors at polygon centroids.
    const labels = valid.map(({ r }, i) => {
      const cell = territory.territories[i];
      const c = cell && cell.ring.length >= 3 ? cell.centroid : effective[i];
      return {
        name: r.name,
        area: r.area,
        position: [c.x, zOf(i) + 0.05, c.y] as [number, number, number],
      };
    });

    // Transparency stats: rendered dual-cell area vs declared area.
    const xs: number[] = [];
    const ys: number[] = [];
    territory.territories.forEach((cell, i) => {
      if (!cell || cell.ring.length < 3) return;
      if (cell.area > 1e-9 && areas[i] > 1) {
        xs.push(Math.log10(cell.area));
        ys.push(Math.log10(areas[i]));
      }
    });

    return {
      regions: valid.map(({ r }) => r),
      fillGeom,
      fillTriOwners,
      borderPts,
      meshEdges,
      solverEdges,
      seeds,
      labels,
      selectedLoops,
      selIdx,
      stats: {
        cells: territory.territories.filter((c) => c && c.ring.length >= 3).length,
        borderSegments: borderSegmentCount,
        areaCorrelation: pearson(xs, ys),
      } as TerritoryRenderStats,
    };
  }, [data, mode, heatmap]);

  // Report territory stats to the page (transparency panel).
  const statsRef = useRef<TerritoryRenderStats | null>(null);
  useEffect(() => {
    if (!model || !onRenderStats) return;
    const s = model.stats;
    const prev = statsRef.current;
    if (
      prev &&
      prev.cells === s.cells &&
      prev.borderSegments === s.borderSegments &&
      Math.abs((prev.areaCorrelation ?? -2) - (s.areaCorrelation ?? -2)) < 1e-9
    ) return;
    statsRef.current = s;
    onRenderStats(s);
  }, [model, onRenderStats]);

  // Label anchors visible under the current density setting.
  const labelSet = useMemo(() => {
    if (!model || !showLabels || labelDensity === 'none') return null;
    const sorted = [...model.labels].sort((a, b) => (b.area || 0) - (a.area || 0));
    const picked = labelDensity === 'major' ? sorted.slice(0, 24) : sorted;
    return Object.fromEntries(picked.map((l) => [l.name, l]));
  }, [model, showLabels, labelDensity]);

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
      ? 'INTRINSIC — SOLVER COORDINATES + UNWEIGHTED DUAL, AS PRODUCED'
      : 'AREA-PRESERVING — DUAL RE-DERIVED FROM DECLARED AREAS, COORDINATES UNTOUCHED';
  const heatHud =
    heatmap === 'none' ? 'NO HEATMAP' :
    heatmap === 'area' ? 'TRUE-AREA HEATMAP (LOG SCALE)' :
    'LEGACY DEVIATION HEATMAP (RED = INFLATED, BLUE = SHRUNK)';

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden', borderRadius: '10px' }}>
      <Scene camera={[EXTENT * 1.05, EXTENT * 1.0, EXTENT * 1.45]} autoRotate={autoRotate}>
        <CameraRig preset={viewPreset} />
        <gridHelper args={[EXTENT * 2.9, 26, '#0f2436', '#0a1826']} />

        {/* Country territories — closed convex polygons, one flat colour per
            country (the owner's heat colour). Pointer events resolve the
            hovered/clicked country via faceIndex → owner. */}
        <mesh
          geometry={model.fillGeom}
          onPointerMove={(e) => {
            e.stopPropagation();
            const t = e.faceIndex;
            if (t === undefined || t === null) return;
            const owner = model.fillTriOwners[t];
            const r = model.regions[owner];
            if (!r) return;
            const lp = model.labels[owner]?.position;
            if (!lp) return;
            setHover({ name: r.name, area: r.area, position: [lp[0], lp[1] + 0.4, lp[2]] });
          }}
          onPointerOut={() => setHover(null)}
          onClick={(e) => {
            e.stopPropagation();
            const t = e.faceIndex;
            if (t === undefined || t === null) return;
            const owner = model.fillTriOwners[t];
            const r = model.regions[owner];
            if (r) onRegionClick?.(r.name);
          }}
        >
          <meshStandardMaterial
            vertexColors side={THREE.DoubleSide}
            transparent opacity={0.85} roughness={0.65}
            polygonOffset polygonOffsetFactor={1} polygonOffsetUnits={1}
          />
        </mesh>

        {/* Interior triangulation mesh (optional, faint — the honest grid). */}
        {showHull && (
          <Line
            points={model.meshEdges.flat()}
            color="#0e4d3a"
            lineWidth={1}
            transparent
            opacity={0.4}
          />
        )}

        {/* Country borders — the derived outlines (v33.0). */}
        <Line
          points={model.borderPts}
          segments
          color="#e8fff4"
          lineWidth={1.6}
          transparent
          opacity={0.95}
        />

        {/* Solver's intrinsic adjacency graph — accent, behind borders. */}
        <Line
          points={model.solverEdges.flat()}
          color={ACCENT}
          lineWidth={1.1}
          transparent
          opacity={0.5}
        />

        {/* Seed markers — explicit toggle only (v33.0 default OFF).
            Flat circular markers in the manifold plane, not spheres. */}
        {showNodes &&
          model.seeds.map((s, i) => (
            <mesh
              key={`${s.name}-seed-${i}`}
              position={s.position}
              rotation={[-Math.PI / 2, 0, 0]}
            >
              <circleGeometry args={[s.radius, 12]} />
              <meshBasicMaterial color={ACCENT} side={THREE.DoubleSide} transparent opacity={0.9} />
            </mesh>
          ))}

        {/* v32.0 deep-link focus, v33.0 form: the selected country's
            derived border ring glows accent + a marker at its centroid. */}
        {model.selectedLoops.map((loop, i) => (
          <Line
            key={`sel-${i}`}
            points={loop}
            color={ACCENT}
            lineWidth={3}
            transparent
            opacity={1}
          />
        ))}
        {model.selIdx >= 0 && model.labels[model.selIdx] && (
          <Billboard position={model.labels[model.selIdx].position}>
            <mesh>
              <ringGeometry args={[0.3, 0.42, 32]} />
              <meshBasicMaterial color={ACCENT} side={THREE.DoubleSide} transparent opacity={0.85} />
            </mesh>
          </Billboard>
        )}

        {/* Country labels — centred on each territory polygon. */}
        {labelSet &&
          Object.entries(labelSet).map(([name, label]) => {
            const major = (label.area || 0) >= 1_000_000;
            const isSel = name === selectedRegion;
            return (
              <Html
                key={name}
                position={label.position}
                center
                distanceFactor={22}
                zIndexRange={[40, 0]}
              >
                <div
                  style={{
                    color: isSel || major ? ACCENT : '#a7bccc', fontFamily: 'monospace',
                    fontSize: major || isSel ? 10 : 7.5,
                    fontWeight: major || isSel ? 600 : 400,
                    background: isSel ? 'rgba(0,255,136,0.16)' : 'rgba(4,10,16,0.72)',
                    padding: major || isSel ? '2px 7px' : '1px 5px',
                    borderRadius: 4,
                    border: `1px solid ${isSel ? 'rgba(0,255,136,0.7)' : major ? 'rgba(0,255,136,0.25)' : 'rgba(140,170,190,0.16)'}`,
                    whiteSpace: 'nowrap', pointerEvents: 'none', userSelect: 'none',
                  }}
                >
                  {name}
                </div>
              </Html>
            );
          })}

        {/* Hover tooltip — anchored to the hovered country's centroid. */}
        {hover && (
          <Html position={hover.position} center distanceFactor={16} zIndexRange={[50, 0]}>
            <div
              style={{
                background: 'rgba(4,10,16,0.94)', border: `1px solid ${ACCENT}55`,
                borderRadius: 6, padding: '7px 11px', color: '#e6edf3',
                fontFamily: 'monospace', fontSize: 11, lineHeight: 1.5,
                pointerEvents: 'none', whiteSpace: 'nowrap', userSelect: 'none',
              }}
            >
              <div style={{ color: ACCENT, fontWeight: 700 }}>{hover.name}</div>
              <div>{hover.area.toLocaleString()} km²</div>
              <div style={{ color: '#5b6b7b' }}>click → Physical Truth module</div>
            </div>
          </Html>
        )}
      </Scene>

      <ViewportHud
        text={`3D EARTH SIMULATION — ${model.stats.cells} COUNTRY TERRITORIES · ${model.stats.borderSegments} BORDER SEGMENTS · VORONOI DUAL OF THE INTRINSIC POINT SET · ${modeHud} · ${heatHud}${hudSuffix ? ` · ${hudSuffix}` : ''}`}
      />

      {/* Hover fallback strip (non-3D text under the HUD) */}
      {hover && (
        <div
          style={{
            position: 'absolute', bottom: 10, left: 12, zIndex: 5,
            background: 'rgba(4,10,16,0.85)', border: `1px solid ${ACCENT}44`,
            borderRadius: 6, padding: '4px 10px', color: ACCENT,
            fontFamily: 'monospace', fontSize: 10, letterSpacing: 1,
            pointerEvents: 'none',
          }}
        >
          ◉ {hover.name} · {hover.area.toLocaleString()} km²
        </div>
      )}
    </div>
  );
}
