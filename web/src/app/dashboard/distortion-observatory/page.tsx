'use client';
import { useState, useEffect, useRef } from 'react';
import * as THREE from 'three';

export default function DistortionObservatoryPage() {
  const [globalData, setGlobalData] = useState<any>(null);
  const [ranking, setRanking] = useState<any[]>([]);
  const [projection, setProjection] = useState('Mercator');
  const [loading, setLoading] = useState(true);
  const [view2D, setView2D] = useState(true);
  const [manifoldCoords, setManifoldCoords] = useState<Record<string, number[]> | null>(null);

  useEffect(() => {
    Promise.all([
      fetch('/api/distortion/global').then(r => r.json()).catch(() => null),
      fetch(`/api/distortion/ranking?projection=${projection}&limit=30`).then(r => r.json()).catch(() => null),
    ]).then(([g, r]) => {
      setGlobalData(g);
      setRanking(r?.ranking || []);
      setLoading(false);
    });
  }, [projection]);

  const solveManifold = async () => {
    setManifoldCoords(null);
    const res = await fetch('/api/solve/manifold', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        edges: [
          { source: 'A', target: 'B', length: 1.0 },
          { source: 'B', target: 'C', length: 1.0 },
          { source: 'C', target: 'D', length: 1.0 },
          { source: 'A', target: 'D', length: 1.0 },
          { source: 'A', target: 'C', length: 1.41421356 },
          { source: 'B', target: 'D', length: 1.41421356 },
          { source: 'A', target: 'E', length: 1.0 },
          { source: 'E', target: 'F', length: 1.0 },
          { source: 'F', target: 'C', length: 1.0 },
          { source: 'B', target: 'E', length: 1.0 },
          { source: 'D', target: 'E', length: 1.0 },
          { source: 'B', target: 'F', length: 1.41421356 },
        ],
        max_iter: 500,
        tol: 1e-10,
        embedding: view2D ? '2d' : '3d',
      }),
    }).then(r => r.json()).catch(() => null);
    setManifoldCoords(res?.coordinates || null);
  };

  return (
    <main className="min-h-screen bg-black text-white p-8">
      <h1 className="text-3xl font-bold mb-2">Projection Distortion Observatory</h1>
      <p className="text-sm text-white/60 mb-6">
        Transparent, verifiable metrics quantifying how legacy cartographic projections
        deviate from physical truth.
      </p>

      <div className="bg-yellow-500/10 border border-yellow-500/30 rounded p-3 mb-6 text-sm text-yellow-200">
        <strong>Scientific Disclaimer:</strong> These metrics compare legacy cartographic
        projection areas against a physical baseline derived from measured geographic survey
        data. Deviations represent the systematic bias introduced by map projections, not errors
        in the original data sources.
      </div>

      {loading ? (
        <p className="text-white/40">Loading metrics...</p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-6 mb-8">
            <div className="border border-white/10 rounded p-4">
              <h2 className="text-sm uppercase text-white/40 mb-3">Global Distortion Index</h2>
              {globalData?.projections?.map((p: any) => (
                <div key={p.projection} className="mb-3">
                  <div className="flex justify-between items-baseline">
                    <span className="font-semibold">{p.projection}</span>
                    <span className={`font-mono text-2xl ${p.global_distortion_percent > 50 ? 'text-red-400' : p.global_distortion_percent > 20 ? 'text-yellow-400' : 'text-green-400'}`}>
                      {p.global_distortion_percent.toFixed(1)}%
                    </span>
                  </div>
                  <div className="w-full bg-white/10 rounded h-2 mt-1">
                    <div
                      className={`h-2 rounded ${p.global_distortion_percent > 50 ? 'bg-red-500' : p.global_distortion_percent > 20 ? 'bg-yellow-500' : 'bg-green-500'}`}
                      style={{ width: `${Math.min(p.global_distortion_percent, 100)}%` }}
                    />
                  </div>
                  <div className="text-xs text-white/40 mt-1">{p.region_count} regions analyzed</div>
                </div>
              ))}
            </div>

            <div className="border border-white/10 rounded p-4">
              <h2 className="text-sm uppercase text-white/40 mb-3">Projection Selector</h2>
              <div className="space-y-2">
                {['Mercator', 'Robinson', 'AuthaGraph', 'Equirectangular'].map(p => (
                  <button key={p} onClick={() => setProjection(p)}
                    className={`block w-full text-left px-3 py-2 rounded text-sm ${
                      projection === p ? 'bg-cyan-500 text-black font-semibold' : 'bg-white/5 hover:bg-white/10'
                    }`}>
                    {p}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-6">
            <div className="col-span-2 border border-white/10 rounded p-4">
              <h2 className="text-sm uppercase text-white/40 mb-3">
                Top Deviations ({projection})
              </h2>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-white/40 text-left">
                    <th className="p-2">#</th>
                    <th className="p-2">Region</th>
                    <th className="p-2 text-right">Physical (km²)</th>
                    <th className="p-2 text-right">Legacy (km²)</th>
                    <th className="p-2 text-right">Error %</th>
                    <th className="p-2">Category</th>
                  </tr>
                </thead>
                <tbody>
                  {ranking.map((r, i) => (
                    <tr key={i} className="border-t border-white/10 hover:bg-white/5">
                      <td className="p-2 text-white/40">{i + 1}</td>
                      <td className="p-2 font-semibold">{r.region}</td>
                      <td className="p-2 text-right font-mono">{(r.area_physical_m2 / 1e6).toLocaleString()}</td>
                      <td className="p-2 text-right font-mono">{(r.area_legacy_m2 / 1e6).toLocaleString()}</td>
                      <td className={`p-2 text-right font-mono ${
                        r.relative_error_percent < 0 ? 'text-red-400' : 'text-blue-400'
                      }`}>
                        {r.relative_error_percent > 0 ? '+' : ''}{r.relative_error_percent.toFixed(1)}%
                      </td>
                      <td className="p-2 text-xs">
                        <span className={`px-2 py-0.5 rounded ${
                          r.distortion_category === 'overreported' ? 'bg-red-500/20 text-red-400' :
                          r.distortion_category === 'underreported' ? 'bg-blue-500/20 text-blue-400' :
                          'bg-green-500/20 text-green-400'
                        }`}>
                          {r.distortion_category}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="border border-white/10 rounded p-4">
              <h2 className="text-sm uppercase text-white/40 mb-3">Data-Guided Manifold</h2>
              <p className="text-xs text-white/40 mb-3">
                The shape below is reconstructed purely from edge lengths.
                No forced shape bias — the data determines the geometry.
              </p>
              <button onClick={solveManifold}
                className="px-4 py-2 bg-cyan-500 text-black rounded font-semibold mb-3 text-sm">
                Solve Manifold ({view2D ? '2D' : '3D'})
              </button>
              <button onClick={() => setView2D(!view2D)}
                className="px-4 py-2 bg-white/10 rounded text-sm ml-2">
                Switch to {view2D ? '3D' : '2D'}
              </button>
              {manifoldCoords && (
                <ManifoldView coords={manifoldCoords} is3D={!view2D} />
              )}
            </div>
          </div>
        </>
      )}
    </main>
  );
}

function ManifoldView({ coords, is3D }: { coords: Record<string, number[]>; is3D: boolean }) {
  const mountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const width = mount.clientWidth;
    const height = 300;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a0a);

    const camera = is3D
      ? new THREE.PerspectiveCamera(50, width / height, 0.1, 100)
      : new THREE.OrthographicCamera(-3, 3, 1.5, -1.5, 0.1, 100);
    camera.position.set(0, 0, 5);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    mount.appendChild(renderer.domElement);

    // Add points
    const points = Object.entries(coords);
    const positions = new Float32Array(points.length * 3);
    points.forEach(([name, coord], i) => {
      positions[i * 3] = coord[0];
      positions[i * 3 + 1] = coord[1] || 0;
      positions[i * 3 + 2] = coord[2] || 0;
    });

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    const material = new THREE.PointsMaterial({ color: 0x00ffff, size: 0.1 });
    const pointsMesh = new THREE.Points(geometry, material);
    scene.add(pointsMesh);

    // Connect edges
    const edges = [
      ['A', 'B'], ['B', 'C'], ['C', 'D'], ['A', 'D'],
      ['A', 'C'], ['B', 'D'], ['A', 'E'], ['E', 'F'],
      ['F', 'C'], ['B', 'E'], ['D', 'E'], ['B', 'F'],
    ];
    const edgePositions: number[] = [];
    for (const [a, b] of edges) {
      if (coords[a] && coords[b]) {
        edgePositions.push(coords[a][0], coords[a][1] || 0, coords[a][2] || 0);
        edgePositions.push(coords[b][0], coords[b][1] || 0, coords[b][2] || 0);
      }
    }
    const edgeGeo = new THREE.BufferGeometry();
    edgeGeo.setAttribute('position', new THREE.Float32BufferAttribute(edgePositions, 3));
    const edgeMat = new THREE.LineBasicMaterial({ color: 0x444444 });
    scene.add(new THREE.LineSegments(edgeGeo, edgeMat));

    let frame = 0;
    const animate = () => {
      requestAnimationFrame(animate);
      if (is3D) {
        pointsMesh.rotation.y = frame * 0.01;
        scene.children.forEach(c => { if (c instanceof THREE.LineSegments) c.rotation.y = frame * 0.01; });
      }
      frame++;
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      mount.removeChild(renderer.domElement);
      renderer.dispose();
    };
  }, [coords, is3D]);

  return <div ref={mountRef} className="w-full" />;
}
