'use client';

/**
 * AETHERA v37.1 — InteractiveEarth3D
 *
 * GOOGLE-MAPS-STYLE INTERACTIVE 3D VIEWER over the derived boundary
 * manifold (the v36.0 country polygons, globe-agnostic).
 *
 * Controls (maps-style mapping):
 *   • Left-drag / one-finger drag ......... pan (screen-space)
 *   • Right-drag / two-finger drag ........ orbit — vertical motion tilts
 *   • Middle-drag ......................... dolly (zoom)
 *   • Scroll / pinch ...................... smooth zoom, global → country
 *   • Double-click ........................ reset to the default view
 *   • Click ............................... country select → Truth Panel,
 *                                           or ELEVATION SAMPLING when the
 *                                           elevation toggle is ON
 *   • Hover ............................... tooltip: name + Physical
 *                                           Truth area
 *
 * Elevation-on-click: the click's WORLD intersection is converted back
 * to the solver's intrinsic frame (the parent owns the fit transform)
 * and POSTed to /api/elevation, which returns the ETOPO1 height above
 * sea level stored as a per-vertex SCALAR at ingestion time. No
 * lon/lat, no WGS84, no EPSG exists anywhere in this loop (Axioms 2-4).
 *
 * Honest scope note: smooth zoom reaches polygon vertex detail (~ km
 * scale at 1:50m source resolution); the zoom meter reports the honest
 * level rather than a fictional town-level promise.
 */

import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import * as THREE from 'three';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls, Html, Billboard, Line } from '@react-three/drei';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import { ACCENT, DIM, heatColorHex, areaColorHex, ViewportHud } from './Scene';
import { fitTransform, type Pt } from '@/lib/delaunay';
import { apiFetch } from '@/lib/api';
import CountryPolygon, { type BoundaryRing } from './CountryPolygon';
import type {
  EarthSimulation3DData,
  TerritoryRenderStats,
  BoundaryCountry,
} from './EarthSimulation3D';

const EXTENT = 24;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ElevationResult {
  elevation_m: number | null;
  coordinates?: [number, number, number];
  source?: string;
  reference?: string;
  error?: string;
}

interface PinState {
  world: [number, number, number];
  intrinsic: [number, number];
  pending: boolean;
  result: ElevationResult | null;
}

export interface InteractiveEarth3DProps {
  data: EarthSimulation3DData;
  boundaryData: BoundaryCountry[] | null;
  heatmap: 'none' | 'area' | 'deviation';
  showLabels?: boolean;
  labelDensity?: 'all' | 'major' | 'none';
  selectedRegion?: string | null;
  autoRotate?: boolean;
  viewPreset?: 'orbit' | 'planar';
  /** Elevation mode ON → clicks sample /api/elevation instead of selecting. */
  elevationEnabled: boolean;
  /** Reported on every elevation query (pending + resolved). */
  onElevationUpdate?: (r: ElevationResult | null) => void;
  onRegionClick?: (region: string) => void;
  onRenderStats?: (stats: TerritoryRenderStats) => void;
  hudSuffix?: string;
}

// ---------------------------------------------------------------------------
// Controls rig — Google-Maps-style mouse mapping + double-click reset
// ---------------------------------------------------------------------------

const DEFAULT_ORBIT: [number, number, number] = [EXTENT * 1.05, EXTENT, EXTENT * 1.45];
const DEFAULT_PLANAR: [number, number, number] = [0, EXTENT * 2.6, 0.42];
const ZOOM_REF = EXTENT * 2.6; // camera distance that frames the world

function ControlsRig({
  preset,
  resetSignal,
  autoRotate,
  onZoomLevel,
}: {
  preset: 'orbit' | 'planar';
  resetSignal: number;
  autoRotate: boolean;
  onZoomLevel?: (level: number) => void;
}) {
  const controlsRef = useRef<OrbitControlsImpl | null>(null);
  const { camera } = useThree();
  const goal = useRef<{ pos: THREE.Vector3; tgt: THREE.Vector3 } | null>(null);
  const lastZoom = useRef(-1);

  // Maps-style button mapping: left = pan, right = rotate (tilt), middle
  // = dolly. Touch: one finger pans, two fingers dolly + rotate.
  useEffect(() => {
    const c = controlsRef.current;
    if (!c) return;
    c.mouseButtons = {
      LEFT: THREE.MOUSE.PAN,
      MIDDLE: THREE.MOUSE.DOLLY,
      RIGHT: THREE.MOUSE.ROTATE,
    };
    c.touches = {
      ONE: THREE.TOUCH.PAN,
      TWO: THREE.TOUCH.DOLLY_ROTATE,
    };
    c.screenSpacePanning = true;
    c.zoomSpeed = 1.2;
    c.rotateSpeed = 0.6;
    c.panSpeed = 0.8;
  }, []);

  // Preset change → glide to the new framing.
  useEffect(() => {
    goal.current = {
      pos: new THREE.Vector3(...(preset === 'planar' ? DEFAULT_PLANAR : DEFAULT_ORBIT)),
      tgt: new THREE.Vector3(0, 0, 0),
    };
  }, [preset]);

  // Double-click reset signal → glide back to the default view.
  useEffect(() => {
    if (resetSignal === 0) return;
    goal.current = {
      pos: new THREE.Vector3(...(preset === 'planar' ? DEFAULT_PLANAR : DEFAULT_ORBIT)),
      tgt: new THREE.Vector3(0, 0, 0),
    };
  }, [resetSignal, preset]);

  useFrame(() => {
    const c = controlsRef.current;
    if (goal.current) {
      camera.position.lerp(goal.current.pos, 0.12);
      if (c) {
        c.target.lerp(goal.current.tgt, 0.12);
        c.update();
      }
      if (camera.position.distanceTo(goal.current.pos) < 0.05) goal.current = null;
    }
    if (c && onZoomLevel) {
      const dist = camera.position.distanceTo(c.target);
      const level = Math.max(1, Math.min(12, Math.round(Math.log2(ZOOM_REF / Math.max(dist, 0.4)) + 1)));
      if (level !== lastZoom.current) {
        lastZoom.current = level;
        onZoomLevel(level);
      }
    }
  });

  return (
    <OrbitControls
      ref={(r) => { controlsRef.current = r; }}
      makeDefault
      enablePan
      enableZoom
      enableRotate
      enableDamping
      dampingFactor={0.05}
      minDistance={0.5}
      maxDistance={5000}
      autoRotate={autoRotate}
      autoRotateSpeed={0.7}
    />
  );
}

// ---------------------------------------------------------------------------
// Elevation click plane — catches clicks on empty manifold space too
// ---------------------------------------------------------------------------

function ElevationPlane({ onPlaneClick }: { onPlaneClick: (p: THREE.Vector3, screen: { x: number; y: number }) => void }) {
  const down = useRef<{ x: number; y: number } | null>(null);
  return (
    <mesh
      rotation={[-Math.PI / 2, 0, 0]}
      position={[0, -0.02, 0]}
      visible={false}
      onPointerDown={(e) => {
        down.current = { x: e.nativeEvent.clientX, y: e.nativeEvent.clientY };
      }}
      onClick={(e) => {
        e.stopPropagation();
        const d = down.current;
        down.current = null;
        // Drag guard: a pan release is not a click.
        if (d) {
          const dx = e.nativeEvent.clientX - d.x;
          const dy = e.nativeEvent.clientY - d.y;
          if (Math.hypot(dx, dy) > 6) return;
        }
        onPlaneClick(e.point, { x: e.nativeEvent.clientX, y: e.nativeEvent.clientY });
      }}
    >
      <planeGeometry args={[2400, 2400]} />
    </mesh>
  );
}

// ---------------------------------------------------------------------------
// Elevation pin — marks the sampled point in the manifold
// ---------------------------------------------------------------------------

function ElevationPin({ pin }: { pin: PinState }) {
  const [x, y0, z] = pin.world;
  const elev = pin.result?.elevation_m;
  const label = pin.pending
    ? 'sampling…'
    : elev === null || elev === undefined
      ? (pin.result?.error ? 'outside known manifold' : `${elev} m`)
      : `${elev.toLocaleString()} m`;
  return (
    <group position={[x, 0, z]}>
      <Line
        points={[[0, 0.05, 0], [0, 2.4, 0]]}
        color="#38bdf8"
        lineWidth={1.6}
        transparent
        opacity={0.9}
      />
      <mesh position={[0, 0.06, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.22, 0.34, 28]} />
        <meshBasicMaterial color="#38bdf8" side={THREE.DoubleSide} transparent opacity={0.9} />
      </mesh>
      <Billboard position={[0, 2.75, 0]}>
        <Html
          center
          distanceFactor={18}
          zIndexRange={[60, 0]}
          style={{ pointerEvents: 'none' }}
        >
          <div
            style={{
              background: 'rgba(4,10,16,0.94)', border: '1px solid #38bdf8aa',
              borderRadius: 6, padding: '5px 10px', color: '#e6edf3',
              fontFamily: 'monospace', fontSize: 11, lineHeight: 1.45,
              whiteSpace: 'nowrap', pointerEvents: 'none', userSelect: 'none',
            }}
          >
            <div style={{ color: '#38bdf8', fontWeight: 700 }}>⌾ ELEVATION</div>
            <div>{label}</div>
            <div style={{ color: '#5b6b7b' }}>height above sea level · ETOPO1 scalar</div>
          </div>
        </Html>
      </Billboard>
    </group>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function InteractiveEarth3D({
  data,
  boundaryData,
  heatmap,
  showLabels = true,
  labelDensity = 'all',
  selectedRegion = null,
  autoRotate = false,
  viewPreset = 'orbit',
  elevationEnabled,
  onElevationUpdate,
  onRegionClick,
  onRenderStats,
  hudSuffix,
}: InteractiveEarth3DProps) {
  const [hover, setHover] = useState<{ name: string; area: number; position: [number, number, number] } | null>(null);
  const [resetSignal, setResetSignal] = useState(0);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [pin, setPin] = useState<PinState | null>(null);

  const colorFn =
    heatmap === 'deviation' ? heatColorHex :
    heatmap === 'area' ? areaColorHex :
    null;

  // ---- Boundary model (same fit logic as EarthSimulation3D v36.0) --------
  const model = useMemo(() => {
    if (!boundaryData || boundaryData.length < 3) return null;
    const anchored = boundaryData.filter((c) => c.anchored !== false);
    const fitSet = anchored.length >= 3 ? anchored : boundaryData;
    const bboxArea = (c: { rings: [number, number][][] }) => {
      let minx = Infinity, maxx = -Infinity, miny = Infinity, maxy = -Infinity;
      for (const r of c.rings) for (const [x, y] of r) {
        if (x < minx) minx = x; if (x > maxx) maxx = x;
        if (y < miny) miny = y; if (y > maxy) maxy = y;
      }
      return (maxx - minx) * (maxy - miny);
    };
    const areas = fitSet.map(bboxArea);
    const med = [...areas].sort((a, b) => a - b)[Math.floor(areas.length / 2)] || 1;
    const robust = fitSet.filter((c, i) => areas[i] <= med * 8);
    const useSet = robust.length >= 3 ? robust : fitSet;
    const allPts: Pt[] = [];
    for (const c of useSet) for (const r of c.rings) for (const [x, y] of r) allPts.push({ x, y });
    if (allPts.length < 3) return null;
    const tf = fitTransform(allPts, EXTENT);
    const map = (p: [number, number]): [number, number] =>
      [(p[0] - tf.cx) * tf.scale, -(p[1] - tf.cy) * tf.scale];

    const areaLogs = boundaryData.map((c) => Math.log10(Math.max(1, c.area || 1)));
    const lmin = Math.min(...areaLogs);
    const lmax = Math.max(...areaLogs);
    const heatOf = (i: number): number | null => {
      if (heatmap === 'deviation') {
        const d = boundaryData[i].deviation;
        if (d === null || !Number.isFinite(d)) return null;
        return 0.5 + Math.max(-1, Math.min(1, d / 200)) * 0.5;
      }
      if (heatmap === 'area') return (areaLogs[i] - lmin) / Math.max(1e-9, lmax - lmin);
      return null;
    };

    const majorNames = new Set(
      [...boundaryData].sort((a, b) => (b.area || 0) - (a.area || 0))
        .slice(0, 24).map((c) => c.name),
    );

    const countries = boundaryData.map((c, i) => {
      const h = heatOf(i);
      const neutral = '#12321f';
      const fill = h === null ? neutral : `rgb(${colorFn!(h).map((v) => Math.round(v * 255)).join(',')})`;
      const rings: BoundaryRing[] = c.rings
        .map((pts, ri) => ({ pts: pts.map(map), kind: c.ringKinds[ri] || 'outer' }))
        .filter((r) => r.pts.length >= 3);
      const showLabel =
        !!showLabels && labelDensity !== 'none' &&
        (labelDensity === 'all' || majorNames.has(c.name) || c.name === selectedRegion);
      return { country: c, rings, fill, showLabel, major: majorNames.has(c.name) };
    }).filter((entry) => entry.rings.some((r) => r.kind === 'outer'));

    // Transparency stats: rendered polygon area vs declared area.
    const xs: number[] = [];
    const ys: number[] = [];
    for (const c of boundaryData) {
      if (c.renderedArea && c.renderedArea > 1 && c.area > 1) {
        xs.push(Math.log10(c.renderedArea));
        ys.push(Math.log10(c.area));
      }
    }
    let borderSegments = 0;
    for (const entry of countries) borderSegments += entry.rings.length;

    return {
      tf,
      countries,
      stats: {
        cells: countries.length,
        borderSegments,
        areaCorrelation: (() => {
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
        })(),
      } as TerritoryRenderStats,
    };
  }, [boundaryData, heatmap, showLabels, labelDensity, selectedRegion, colorFn]);

  // Report boundary stats to the page (transparency panel).
  const statsRef = useRef<TerritoryRenderStats | null>(null);
  useEffect(() => {
    if (!model || !onRenderStats) return;
    const st = model.stats;
    const prev = statsRef.current;
    if (
      prev && prev.cells === st.cells && prev.borderSegments === st.borderSegments &&
      Math.abs((prev.areaCorrelation ?? -2) - (st.areaCorrelation ?? -2)) < 1e-9
    ) return;
    statsRef.current = st;
    onRenderStats(st);
  }, [model, onRenderStats]);

  // ---- Elevation-on-click ------------------------------------------------
  const handleElevationPoint = useCallback(
    (world: [number, number, number]) => {
      if (!model) return;
      const tf = model.tf;
      // world → intrinsic: worldX = (x - cx)·s ; worldZ = -(y - cy)·s
      const xi = world[0] / tf.scale + tf.cx;
      const yi = -world[2] / tf.scale + tf.cy;
      const next: PinState = {
        world,
        intrinsic: [xi, yi],
        pending: true,
        result: null,
      };
      setPin(next);
      onElevationUpdate?.(null);
      (async () => {
        try {
          const res = await apiFetch('/api/elevation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ x: xi, y: yi, z: 0 }),
          });
          const j = await res.json();
          const result: ElevationResult = res.ok && j.elevation_m !== null && j.elevation_m !== undefined
            ? {
                elevation_m: Number(j.elevation_m),
                coordinates: j.coordinates,
                source: j.source,
                reference: j.reference,
              }
            : { elevation_m: null, error: j.error || `HTTP ${res.status}` };
          setPin((p) => (p === next ? { ...p, pending: false, result } : p));
          onElevationUpdate?.(result);
        } catch (e) {
          const result: ElevationResult = { elevation_m: null, error: (e as Error)?.message || 'network error' };
          setPin((p) => (p === next ? { ...p, pending: false, result } : p));
          onElevationUpdate?.(result);
        }
      })();
    },
    [model, onElevationUpdate],
  );

  const onPlaneClick = useCallback(
    (_p: THREE.Vector3, _screen: { x: number; y: number }) => {
      // Empty-space clicks still sample elevation (ocean gaps between
      // polygons); the intersection point comes from the plane itself.
      if (_p) handleElevationPoint([_p.x, 0, _p.z]);
    },
    [handleElevationPoint],
  );

  if (!boundaryData || boundaryData.length < 3 || !model) {
    return (
      <div
        style={{
          width: '100%', height: '100%', display: 'flex', alignItems: 'center',
          justifyContent: 'center', color: '#5b6b7b', fontFamily: 'monospace', fontSize: 12,
        }}
      >
        Derived boundary geometry unavailable — check /api/boundaries/intrinsic.
      </div>
    );
  }

  const heatHud =
    heatmap === 'none' ? 'NO HEATMAP' :
    heatmap === 'area' ? 'TRUE-AREA HEATMAP (LOG SCALE)' :
    'LEGACY DEVIATION HEATMAP (RED = INFLATED, BLUE = SHRUNK)';

  return (
    <div
      style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden', borderRadius: '10px' }}
      onDoubleClick={() => setResetSignal((s) => s + 1)}
    >
      <Canvas
        dpr={[1, 2]}
        camera={{ position: DEFAULT_ORBIT, fov: 50, near: 0.05, far: 12000 }}
        gl={{ antialias: true, alpha: false }}
        style={{ width: '100%', height: '100%', background: '#040a10' }}
        onPointerMissed={() => setHover(null)}
      >
        <color attach="background" args={['#040a10']} />
        <fog attach="fog" args={['#040a10', 200, 6000]} />
        <ambientLight intensity={0.8} />
        <directionalLight position={[100, 120, 80]} intensity={0.75} />
        <pointLight position={[-60, -30, -70]} intensity={0.3} color={ACCENT} />

        <ControlsRig
          preset={viewPreset}
          resetSignal={resetSignal}
          autoRotate={autoRotate}
          onZoomLevel={setZoomLevel}
        />

        {/* Country polygons — closed derived boundaries with borders and
            centroid labels. Elevation ON → clicks sample the manifold;
            OFF → clicks select the country (Truth Panel). */}
        {model.countries.map((entry) => (
          <CountryPolygon
            key={`b-${entry.country.name}`}
            name={entry.country.name}
            rings={entry.rings}
            fillColor={entry.fill}
            borderColor="#e8fff4"
            areaKm2={entry.country.area}
            major={entry.major}
            showLabel={entry.showLabel}
            selected={entry.country.name === selectedRegion}
            accent={ACCENT}
            onPick={(nm) => { if (!elevationEnabled) onRegionClick?.(nm); }}
            onPickPoint={(_nm, worldPoint) => {
              if (elevationEnabled) handleElevationPoint(worldPoint);
            }}
            onHover={setHover}
          />
        ))}

        {/* Elevation mode: catch clicks between polygons too. */}
        {elevationEnabled && <ElevationPlane onPlaneClick={onPlaneClick} />}

        {/* Elevation pin — the last sampled point. */}
        {pin && <ElevationPin pin={pin} />}

        {/* Hover tooltip — name + Physical Truth area (mandatory). */}
        {hover && (
          <Html
            position={hover.position}
            center
            distanceFactor={16}
            zIndexRange={[50, 0]}
            style={{ pointerEvents: 'none' }}
          >
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
              <div style={{ color: '#5b6b7b' }}>
                {elevationEnabled ? 'click → sample elevation' : 'click → Physical Truth module'}
              </div>
            </div>
          </Html>
        )}
      </Canvas>

      {/* Zoom meter (maps-style, honest about source resolution). */}
      <div
        style={{
          position: 'absolute', right: 12, bottom: 10, zIndex: 5,
          background: 'rgba(4,10,16,0.85)', border: `1px solid ${DIM}`,
          borderRadius: 6, padding: '4px 10px', color: '#8b9bab',
          fontFamily: 'monospace', fontSize: 10, letterSpacing: 1,
          pointerEvents: 'none',
        }}
      >
        ZOOM L{zoomLevel}/12 · {zoomLevel <= 3 ? 'GLOBAL' : zoomLevel <= 6 ? 'CONTINENT' : zoomLevel <= 9 ? 'COUNTRY' : 'REGION DETAIL (1:50m SOURCE)'} · double-click resets
      </div>

      <ViewportHud
        text={`INTERACTIVE MANIFOLD — ${model.stats.cells} DERIVED COUNTRY BOUNDARIES · ${model.stats.borderSegments} BOUNDARY RINGS · ${elevationEnabled ? 'ELEVATION MODE: CLICK = ETOPO1 SAMPLE' : 'SELECT MODE: CLICK = TRUTH PANEL'} · ${heatHud}${hudSuffix ? ` · ${hudSuffix}` : ''}`}
      />

      {/* Hover fallback strip (non-3D text under the HUD). */}
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
