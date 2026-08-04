#!/bin/bash
set -e
ROOT=/home/z/my-project/aethera-core

# ============================================================
# Next.js frontend (Hall of Shame)
# ============================================================

cat > $ROOT/web/package.json << 'JSON'
{
  "name": "aethera-web",
  "version": "0.2.0",
  "private": true,
  "scripts": {
    "dev": "next dev -p 3000",
    "build": "next build",
    "start": "next start -p 3000"
  },
  "dependencies": {
    "next": "16.0.0",
    "react": "19.0.0",
    "react-dom": "19.0.0",
    "three": "0.180.0"
  },
  "devDependencies": {
    "@types/node": "^22.10.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@types/three": "^0.180.0",
    "typescript": "^5.7.0"
  }
}
JSON

cat > $ROOT/web/tsconfig.json << 'JSON'
{
  "compilerOptions": {
    "target": "ES2022", "lib": ["dom","dom.iterable","esnext"],
    "skipLibCheck": true, "strict": true, "noEmit": true,
    "esModuleInterop": true, "module": "esnext",
    "moduleResolution": "bundler", "resolveJsonModule": true,
    "isolatedModules": true, "jsx": "preserve", "incremental": true,
    "plugins": [{"name": "next"}], "paths": {"@/*": ["./src/*"]}
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx"]
}
JSON

cat > $ROOT/web/next.config.mjs << 'JS'
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // For Cloudflare R2 deployment: set assetPrefix to your R2 public URL.
  // assetPrefix: process.env.NEXT_PUBLIC_R2_URL || undefined,
};
export default nextConfig;
JS

cat > $ROOT/web/vercel.json << 'JSON'
{
  "buildCommand": "npm run build",
  "outputDirectory": ".next",
  "framework": "nextjs",
  "regions": ["iad1"]
}
JSON

mkdir -p $ROOT/web/src/{app,components,lib}

cat > $ROOT/web/src/app/globals.css << 'CSS'
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; height: 100%; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: #000; color: #fff;
}
button { cursor: pointer; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
CSS

cat > $ROOT/web/src/app/layout.tsx << 'TSX'
import './globals.css';
export const metadata = {
  title: 'AETHERA — Consensus Hall of Shame',
  description: 'Strain tensor overlay of scholarly map projections. Pure geometric substrate — no radius, no G, no ephemeris.',
};
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (<html lang="en"><body>{children}</body></html>);
}
TSX

cat > $ROOT/web/src/lib/projections.ts << 'TS'
export type Projection = (lon: number, lat: number) => [number, number];

export const mercator: Projection = (lon, lat) => {
  const lr = Math.max(-89.999, Math.min(89.999, lat)) * Math.PI / 180;
  return [lon * Math.PI / 180, Math.log(Math.tan(Math.PI/4 + lr/2))];
};
export const robinson: Projection = (lon, lat) => {
  const lr = lat * Math.PI / 180;
  return [lon * Math.PI / 180 * Math.cos(lr * 0.7), lr * (1.0 - 0.1 * lr * lr)];
};
export const authagraph: Projection = (lon, lat) => {
  const lr = lat * Math.PI / 180;
  return [lon * Math.PI / 180 * Math.cos(lr), Math.sin(lr)];
};
export const equirectangular: Projection = (lon, lat) => [lon * Math.PI / 180, lat * Math.PI / 180];

export const PROJECTIONS: Record<string, Projection> = {
  Mercator: mercator, Robinson: robinson,
  AuthaGraph: authagraph, Equirectangular: equirectangular,
};

export interface Polygon {
  name: string;
  vertices: [number, number][];
  areaTrue: number;
  coloniser: boolean;
}

export interface StrainField {
  polygonName: string;
  centroid: [number, number];
  areaProjected: number;
  areaTrue: number;
  scaleFactor: number;
  logStrain: number;
  colour: [number, number, number];
}

export interface DistortionScore {
  projection: string;
  meanLogStrain: number;
  stdLogStrain: number;
  maxInflation: number;
  maxDeflation: number;
  colonialDistortionScore: number;
  note: string;
}

function shoelaceArea(verts: [number, number][]): number {
  if (verts.length < 3) return 0;
  let s = 0;
  for (let i = 0; i < verts.length; i++) {
    const [x1, y1] = verts[i];
    const [x2, y2] = verts[(i + 1) % verts.length];
    s += x1 * y2 - x2 * y1;
  }
  return Math.abs(s) / 2;
}

function centroid2d(verts: [number, number][]): [number, number] {
  const n = verts.length;
  return [verts.reduce((s, v) => s + v[0], 0) / n, verts.reduce((s, v) => s + v[1], 0) / n];
}

export function strainField(polygons: Polygon[], proj: Projection, projName: string): StrainField[] {
  return polygons.map((poly) => {
    const projected = poly.vertices.map(([lon, lat]) => proj(lon, lat));
    const areaProj = shoelaceArea(projected);
    const scale = areaProj / Math.max(poly.areaTrue, 1e-12);
    const logStrain = Math.log(Math.max(scale, 1e-12));
    const cent = centroid2d(projected);
    let colour: [number, number, number];
    if (logStrain > 0) { const t = Math.min(1, logStrain / 2); colour = [1.0, 1.0-t, 1.0-t]; }
    else { const t = Math.min(1, -logStrain / 2); colour = [1.0-t, 1.0-t, 1.0]; }
    return { polygonName: poly.name, centroid: cent, areaProjected: areaProj,
             areaTrue: poly.areaTrue, scaleFactor: scale, logStrain, colour };
  });
}

export function colonialDistortionScore(polygons: Polygon[], proj: Projection, projName: string): DistortionScore {
  const strains = strainField(polygons, proj, projName);
  const cs = strains.filter((_, i) => polygons[i].coloniser).map((s) => s.logStrain);
  const ds = strains.filter((_, i) => !polygons[i].coloniser).map((s) => s.logStrain);
  const mean = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / Math.max(xs.length, 1);
  const mc = mean(cs); const md = mean(ds);
  const allS = strains.map((s) => s.logStrain);
  const ma = mean(allS);
  const std = allS.length > 0 ? Math.sqrt(allS.reduce((s, x) => s + (x-ma)**2, 0) / allS.length) : 0;
  const score = mc - md;
  return {
    projection: projName, meanLogStrain: ma, stdLogStrain: std,
    maxInflation: Math.max(...allS, 0), maxDeflation: Math.min(...allS, 0),
    colonialDistortionScore: score,
    note: `${projName}: coloniser mean ${mc.toFixed(3)}, colonised mean ${md.toFixed(3)}. Score ${score.toFixed(3)}.`,
  };
}

export function allScores(polygons: Polygon[]): DistortionScore[] {
  return Object.entries(PROJECTIONS).map(([name, p]) => colonialDistortionScore(polygons, p, name));
}
TS

cat > $ROOT/web/src/lib/polygons.ts << 'TS'
import type { Polygon } from './projections';

export const CONTINENT_POLYGONS: Polygon[] = [
  { name: 'Africa', vertices: [[-20,-35],[50,-35],[50,37],[-20,37]],
    areaTrue: 30_370_000, coloniser: false }, // AETHERA-GUARD: ALLOW DOCUMENTATION (measured area)
  { name: 'Europe', vertices: [[-10,36],[40,36],[40,71],[-10,71]],
    areaTrue: 10_180_000, coloniser: true }, // AETHERA-GUARD: ALLOW DOCUMENTATION (measured area)
  { name: 'Asia', vertices: [[26,0],[180,0],[180,77],[26,77]],
    areaTrue: 44_579_000, coloniser: true }, // AETHERA-GUARD: ALLOW DOCUMENTATION (measured area)
  { name: 'North America', vertices: [[-168,7],[-52,7],[-52,83],[-168,83]],
    areaTrue: 24_709_000, coloniser: true }, // AETHERA-GUARD: ALLOW DOCUMENTATION (measured area)
  { name: 'South America', vertices: [[-82,-56],[-35,-56],[-35,13],[-82,13]],
    areaTrue: 17_840_000, coloniser: false }, // AETHERA-GUARD: ALLOW DOCUMENTATION (measured area)
  { name: 'Australia', vertices: [[113,-44],[154,-44],[154,-10],[113,-10]],
    areaTrue: 8_600_000, coloniser: true }, // AETHERA-GUARD: ALLOW DOCUMENTATION (measured area)
  { name: 'Greenland', vertices: [[-50,60],[-20,60],[-20,80],[-50,80]],
    areaTrue: 2_166_086, coloniser: false }, // AETHERA-GUARD: ALLOW DOCUMENTATION (measured area)
  { name: 'Antarctica', vertices: [[-180,-90],[180,-90],[180,-60],[-180,-60]],
    areaTrue: 14_000_000, coloniser: false }, // AETHERA-GUARD: ALLOW DOCUMENTATION (measured area)
];
TS

cat > $ROOT/web/src/components/StrainTensorView.tsx << 'TSX'
'use client';
import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { PROJECTIONS, strainField, type Polygon, type StrainField } from '@/lib/projections';

interface Props {
  polygons: Polygon[];
  projection: string;
}

export default function StrainTensorView({ polygons, projection }: Props) {
  const mountRef = useRef<HTMLDivElement>(null);
  const [hovered, setHovered] = useState<StrainField | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.OrthographicCamera | null>(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;
    const width = mount.clientWidth;
    const height = mount.clientHeight;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a0a);
    sceneRef.current = scene;
    const camera = new THREE.OrthographicCamera(-4, 4, 2, -2, 0.1, 100);
    camera.position.set(0, 0, 10);
    cameraRef.current = camera;
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);
    mount.appendChild(renderer.domElement);
    rendererRef.current = renderer;
    const animate = () => { requestAnimationFrame(animate); renderer.render(scene, camera); };
    animate();
    const handleResize = () => {
      if (!mount) return;
      const w = mount.clientWidth; const h = mount.clientHeight;
      renderer.setSize(w, h);
      const aspect = w / h;
      camera.left = -4 * aspect; camera.right = 4 * aspect;
      camera.top = 2; camera.bottom = -2;
      camera.updateProjectionMatrix();
    };
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      if (mount.contains(renderer.domElement)) mount.removeChild(renderer.domElement);
      renderer.dispose();
    };
  }, []);

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;
    while (scene.children.length > 0) {
      const obj = scene.children[0];
      scene.remove(obj);
      if (obj instanceof THREE.Mesh || obj instanceof THREE.LineSegments) {
        obj.geometry?.dispose();
        const mat = (obj as THREE.Mesh).material;
        if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
        else if (mat) (mat as THREE.Material).dispose();
      }
    }
    const proj = PROJECTIONS[projection];
    if (!proj) return;
    const strains = strainField(polygons, proj, projection);
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const poly of polygons) {
      for (const [lon, lat] of poly.vertices) {
        const [x, y] = proj(lon, lat);
        minX = Math.min(minX, x); maxX = Math.max(maxX, x);
        minY = Math.min(minY, y); maxY = Math.max(maxY, y);
      }
    }
    const cx = (minX + maxX) / 2; const cy = (minY + maxY) / 2;
    const scale = 3.5 / Math.max(maxX - minX, maxY - minY);
    for (let i = 0; i < polygons.length; i++) {
      const poly = polygons[i];
      const strain = strains[i];
      const verts = poly.vertices.map(([lon, lat]) => {
        const [x, y] = proj(lon, lat);
        return [(x - cx) * scale, (y - cy) * scale] as [number, number];
      });
      const cent = verts.reduce((acc, v) => [acc[0] + v[0], acc[1] + v[1]] as [number, number], [0, 0] as [number, number]);
      cent[0] /= verts.length; cent[1] /= verts.length;
      const positions: number[] = []; const colours: number[] = [];
      const [r, g, b] = strain.colour;
      for (let k = 0; k < verts.length; k++) {
        const v1 = verts[k]; const v2 = verts[(k + 1) % verts.length];
        positions.push(cent[0], cent[1], 0, v1[0], v1[1], 0, v2[0], v2[1], 0);
        colours.push(r, g, b, r, g, b, r, g, b);
      }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
      geo.setAttribute('color', new THREE.Float32BufferAttribute(colours, 3));
      const mat = new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.DoubleSide, transparent: true, opacity: 0.85 });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.userData = { strain, polygon: poly };
      scene.add(mesh);
    }
  }, [polygons, projection]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || !rendererRef.current) return;
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    const handler = (e: MouseEvent) => {
      const rect = mount.getBoundingClientRect();
      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(mouse, cameraRef.current!);
      const intersects = raycaster.intersectObjects(sceneRef.current!.children);
      for (const it of intersects) {
        const ud = it.object.userData;
        if (ud && ud.strain) { setHovered(ud.strain as StrainField); return; }
      }
      setHovered(null);
    };
    mount.addEventListener('mousemove', handler);
    return () => mount.removeEventListener('mousemove', handler);
  }, []);

  return (
    <div className="relative w-full h-full">
      <div ref={mountRef} className="w-full h-full" />
      {hovered && (
        <div className="absolute top-2 left-2 bg-black/80 text-white p-2 rounded text-xs font-mono pointer-events-none">
          <div className="text-cyan-300 font-bold">{hovered.polygonName}</div>
          <div>scale: {hovered.scaleFactor.toFixed(4)}</div>
          <div>log strain: {hovered.logStrain.toFixed(4)}</div>
          <div>area: {hovered.areaTrue.toLocaleString()} km²</div>
        </div>
      )}
    </div>
  );
}
TSX

cat > $ROOT/web/src/app/page.tsx << 'TSX'
'use client';
import { useMemo, useState } from 'react';
import StrainTensorView from '@/components/StrainTensorView';
import { CONTINENT_POLYGONS } from '@/lib/polygons';
import { allScores, PROJECTIONS } from '@/lib/projections';

export default function Home() {
  const [projection, setProjection] = useState('Mercator');
  const scores = useMemo(() => allScores(CONTINENT_POLYGONS), []);

  return (
    <main className="min-h-screen bg-black text-white">
      <header className="border-b border-white/10 px-8 py-6">
        <div className="flex items-baseline justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">AETHERA — Consensus Hall of Shame</h1>
            <p className="text-sm text-white/60 mt-1">
              Strain tensor overlay of scholarly map projections. Pure geometric substrate — no radius, no G, no ephemeris.
            </p>
          </div>
          <div className="text-xs text-white/40 font-mono">v0.2.0 · geometry provider · not a weapons controller</div>
        </div>
      </header>
      <div className="grid grid-cols-12 gap-0">
        <aside className="col-span-2 border-r border-white/10 p-4 space-y-2">
          <h2 className="text-xs uppercase tracking-wider text-white/40 mb-2">Projection</h2>
          {Object.keys(PROJECTIONS).map((name) => (
            <button key={name} onClick={() => setProjection(name)}
              className={`block w-full text-left px-3 py-2 rounded text-sm transition ${
                projection === name ? 'bg-cyan-500 text-black font-semibold' : 'bg-white/5 hover:bg-white/10 text-white/80'
              }`}>{name}</button>
          ))}
        </aside>
        <section className="col-span-7 border-r border-white/10 h-[80vh]">
          <StrainTensorView polygons={CONTINENT_POLYGONS} projection={projection} />
        </section>
        <aside className="col-span-3 p-4 space-y-4 overflow-y-auto h-[80vh]">
          <h2 className="text-xs uppercase tracking-wider text-white/40 mb-2">Colonial Distortion Scores</h2>
          <p className="text-xs text-white/60">Positive = inflates historically colonising nations. Pure geometric scalar.</p>
          <div className="space-y-2">
            {scores.map((s) => (
              <div key={s.projection}
                onClick={() => setProjection(s.projection)}
                className={`p-3 rounded border cursor-pointer transition ${
                  projection === s.projection ? 'border-cyan-500 bg-cyan-500/10' : 'border-white/10 bg-white/5'
                }`}>
                <div className="flex justify-between items-baseline">
                  <div className="font-semibold text-sm">{s.projection}</div>
                  <div className={`font-mono text-xs ${
                    s.colonialDistortionScore > 0 ? 'text-red-400' : 'text-blue-400'
                  }`}>{s.colonialDistortionScore > 0 ? '+' : ''}{s.colonialDistortionScore.toFixed(3)}</div>
                </div>
                <div className="text-xs text-white/50 mt-1">
                  max infl: {s.maxInflation.toFixed(2)} · max defl: {s.maxDeflation.toFixed(2)}
                </div>
              </div>
            ))}
          </div>
        </aside>
      </div>
      <footer className="border-t border-white/10 px-8 py-6 bg-white/[0.02]">
        <h2 className="text-xs uppercase tracking-wider text-white/40 mb-3">AETHERA Substrate — Agents & Modules (v6.0)</h2>
        <div className="grid grid-cols-4 gap-3 text-xs">
          <Card name="Agent 0 — Ghost Resolver" desc="Residual closure, 5% threshold, rationale log" ok />
          <Card name="Agent 2 — Intrinsic Geometer" desc="Weighted SMACOF + curvature" ok />
          <Card name="Agent 6 — ACIF Navigator" desc="Atomic-interferometry + VLBI" ok />
          <Card name="Agent 8 — Alien Geometer" desc="Topology-agnostic shape reconstruction" ok />
          <Card name="Agent 7 — Dynamics (reformed)" desc="Dual-mode: geodesic + user-force-field. No targeting." ok />
          <Card name="Module 5A — Transparency" desc="Range-vs-chord comparator" ok />
          <Card name="Module 5B — Strain Visualizer" desc="Seismic strain (not a predictor)" ok />
          <Card name="Module 5C — Anomaly Daemon" desc="Civil-scientific: groundwater, glacial, volcanic" ok />
          <Card name="Module 5D — Maritime" desc="Chokepoint navigability" ok />
          <Card name="Module 5E — Hall of Shame" desc="Strain tensor overlay (this view)" ok />
          <Card name="Module 5F — Terraformation" desc="Volume-transfer coastline" ok />
          <Card name="Module 5G — Stellar" desc="Deep-space probe VLBI" ok />
        </div>
        <p className="text-xs text-white/40 mt-4">
          AETHERA v6.0 — hardened physics, transparent ethics. The platform is a geometry provider, not a weapons controller.
        </p>
      </footer>
    </main>
  );
}

function Card({ name, desc, ok }: { name: string; desc: string; ok: boolean }) {
  return (
    <div className={`p-3 rounded border ${ok ? 'border-cyan-500/30 bg-cyan-500/5' : 'border-red-500/30 bg-red-500/5'}`}>
      <div className="flex items-center gap-2 mb-1">
        <span className={ok ? 'text-cyan-400' : 'text-red-400'}>{ok ? '✓' : '✗'}</span>
        <span className="font-semibold text-white/90">{name}</span>
      </div>
      <div className="text-white/50 leading-relaxed">{desc}</div>
    </div>
  );
}
TSX

echo "Next.js frontend written"
