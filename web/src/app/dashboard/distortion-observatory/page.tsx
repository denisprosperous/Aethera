'use client';
import { useState, useEffect, useRef, useCallback } from 'react';
import * as THREE from 'three';

interface RegionNode {
  name: string;
  coords: number[];
  area_km2: number;
}

export default function DistortionObservatoryPage() {
  const [globalData, setGlobalData] = useState<any>(null);
  const [ranking, setRanking] = useState<any[]>([]);
  const [projection, setProjection] = useState('Mercator');
  const [loading, setLoading] = useState(true);
  const [regions, setRegions] = useState<RegionNode[]>([]);
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null);
  const [regionDetail, setRegionDetail] = useState<any>(null);
  const [manifoldLoading, setManifoldLoading] = useState(false);
  const [uploadResult, setUploadResult] = useState<any>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch distortion data.
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

  // Fetch Physical Truth manifold.
  const fetchManifold = useCallback(async () => {
    setManifoldLoading(true);
    const res = await fetch('/api/solve/physical-truth').then(r => r.json()).catch(() => null);
    if (res?.regions) {
      setRegions(res.regions);
    }
    setManifoldLoading(false);
  }, []);

  useEffect(() => {
    fetchManifold();
  }, [fetchManifold]);

  // Fetch region detail on selection.
  useEffect(() => {
    if (!selectedRegion) return;
    Promise.all([
      fetch(`/api/distortion/region/${encodeURIComponent(selectedRegion)}?projection=${projection}`).then(r => r.json()).catch(() => null),
      fetch(`/api/aics/coordinates/${encodeURIComponent(selectedRegion)}`).then(r => r.json()).catch(() => null),
    ]).then(([dist, aics]) => {
      const region = regions.find(r => r.name === selectedRegion);
      setRegionDetail({
        name: selectedRegion,
        physical_area_km2: region?.area_km2 || 0,
        distortion: dist?.metrics?.[0] || null,
        aics: aics || null,
      });
    });
  }, [selectedRegion, projection, regions]);

  // Handle file upload.
  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploadResult(null);
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch('/api/upload/survey', {
      method: 'POST',
      body: formData,
    }).then(r => r.json()).catch(() => null);
    setUploadResult(res);
    if (res?.coordinates) {
      // Convert uploaded coords to region-like format for display.
      const uploadedRegions = Object.entries(res.coordinates).map(([name, coords]) => ({
        name,
        coords: coords as number[],
        area_km2: 0,
      }));
      setRegions(uploadedRegions);
    }
  };

  return (
    <main className="min-h-screen bg-black text-white p-8">
      <h1 className="text-3xl font-bold mb-2">Projection Distortion Observatory</h1>
      <p className="text-sm text-white/60 mb-6">
        Transparent, verifiable metrics quantifying how legacy cartographic projections
        deviate from physical truth. The manifold below is solved from real Physical Truth data.
      </p>

      <div className="bg-yellow-500/10 border border-yellow-500/30 rounded p-3 mb-6 text-sm text-yellow-200">
        <strong>Scientific Disclaimer:</strong> These metrics compare legacy cartographic
        projection areas against a physical baseline. The manifold shape is reconstructed
        purely from area-derived edge lengths — no coordinates, no projections, no forced bias.
      </div>

      {/* Global Distortion Index */}
      <div className="grid grid-cols-2 gap-6 mb-6">
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
                <div className={`h-2 rounded ${p.global_distortion_percent > 50 ? 'bg-red-500' : p.global_distortion_percent > 20 ? 'bg-yellow-500' : 'bg-green-500'}`}
                  style={{ width: `${Math.min(p.global_distortion_percent, 100)}%` }} />
              </div>
            </div>
          ))}
        </div>

        <div className="border border-white/10 rounded p-4">
          <h2 className="text-sm uppercase text-white/40 mb-3">Projection Selector</h2>
          <div className="space-y-2">
            {['Mercator', 'Robinson', 'AuthaGraph', 'Equirectangular'].map(p => (
              <button key={p} onClick={() => setProjection(p)}
                className={`block w-full text-left px-3 py-2 rounded text-sm ${projection === p ? 'bg-cyan-500 text-black font-semibold' : 'bg-white/5 hover:bg-white/10'}`}>
                {p}
              </button>
            ))}
          </div>
          <button onClick={fetchManifold} disabled={manifoldLoading}
            className="mt-3 px-4 py-2 bg-cyan-500 text-black rounded font-semibold text-sm w-full">
            {manifoldLoading ? 'Re-solving...' : 'Re-solve Physical Truth Manifold'}
          </button>
        </div>
      </div>

      {/* Main grid: manifold viewer + sidebar */}
      <div className="grid grid-cols-3 gap-6">
        {/* Manifold Viewer */}
        <div className="col-span-2 border border-white/10 rounded p-4">
          <h2 className="text-sm uppercase text-white/40 mb-3">
            Data-Guided Manifold ({regions.length} regions)
          </h2>
          {manifoldLoading ? (
            <div className="h-[400px] flex items-center justify-center text-white/40">
              Solving manifold from Physical Truth data...
            </div>
          ) : regions.length > 0 ? (
            <ManifoldView regions={regions} selected={selectedRegion} onSelect={setSelectedRegion} />
          ) : (
            <div className="h-[400px] flex items-center justify-center text-white/40">
              No manifold data. Click "Re-solve" above.
            </div>
          )}
        </div>

        {/* Sidebar: Region Detail */}
        <div className="border border-white/10 rounded p-4">
          <h2 className="text-sm uppercase text-white/40 mb-3">Region Detail</h2>
          {selectedRegion && regionDetail ? (
            <div className="space-y-3 text-sm">
              <div>
                <div className="text-white/40 text-xs uppercase">Region</div>
                <div className="font-semibold text-lg">{selectedRegion}</div>
              </div>
              <div>
                <div className="text-white/40 text-xs uppercase">Physical Area</div>
                <div className="font-mono">{regionDetail.physical_area_km2.toLocaleString()} km²</div>
              </div>
              {regionDetail.distortion && (
                <>
                  <div>
                    <div className="text-white/40 text-xs uppercase">Legacy Area ({projection})</div>
                    <div className="font-mono">{(regionDetail.distortion.area_legacy_m2 / 1e6).toLocaleString()} km²</div>
                  </div>
                  <div>
                    <div className="text-white/40 text-xs uppercase">Deviation</div>
                    <div className={`font-mono ${regionDetail.distortion.relative_error_percent < 0 ? 'text-red-400' : 'text-blue-400'}`}>
                      {regionDetail.distortion.relative_error_percent > 0 ? '+' : ''}{regionDetail.distortion.relative_error_percent.toFixed(2)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-white/40 text-xs uppercase">Category</div>
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      regionDetail.distortion.distortion_category === 'overreported' ? 'bg-red-500/20 text-red-400' :
                      regionDetail.distortion.distortion_category === 'underreported' ? 'bg-blue-500/20 text-blue-400' :
                      'bg-green-500/20 text-green-400'
                    }`}>
                      {regionDetail.distortion.distortion_category}
                    </span>
                  </div>
                </>
              )}
              {regionDetail.aics && (
                <div className="border-t border-white/10 pt-3">
                  <div className="text-white/40 text-xs uppercase mb-1">AICS Coordinates</div>
                  <div className="font-mono text-xs space-y-1">
                    <div>X: {regionDetail.aics.aics_coordinates?.barycentric_x?.toFixed(3)}</div>
                    <div>Y: {regionDetail.aics.aics_coordinates?.barycentric_y?.toFixed(3)}</div>
                    <div>Z: {regionDetail.aics.aics_coordinates?.scale_z?.toFixed(3)}</div>
                    <div>Azimuth: {regionDetail.aics.intrinsic_direction?.azimuth_deg?.toFixed(1)}°</div>
                    <div>Distance: {regionDetail.aics.intrinsic_direction?.distance_from_origin?.toFixed(3)}</div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p className="text-white/40 text-sm">Click a region in the manifold to see its details.</p>
          )}
        </div>
      </div>

      {/* Upload section */}
      <div className="mt-6 border border-white/10 rounded p-4">
        <h2 className="text-sm uppercase text-white/40 mb-3">Upload Survey Data (Mode A)</h2>
        <p className="text-xs text-white/40 mb-3">
          Upload a CSV with columns: point_A, point_B, distance_meters.
          The manifold will re-solve from your custom edge lengths.
        </p>
        <input type="file" accept=".csv,.txt" onChange={handleUpload} ref={fileInputRef}
          className="text-sm text-white/60 file:mr-3 file:py-1 file:px-3 file:rounded file:border-0 file:bg-cyan-500 file:text-black file:font-semibold" />
        {uploadResult && (
          <div className="mt-3 text-sm">
            {uploadResult.error ? (
              <p className="text-red-400">Error: {uploadResult.error}</p>
            ) : (
              <p className="text-green-400">
                Solved {uploadResult.edges_uploaded} edges → {uploadResult.node_count} nodes.
                Residual: {uploadResult.residual?.toFixed(6)}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Ranking table */}
      <div className="mt-6 border border-white/10 rounded p-4">
        <h2 className="text-sm uppercase text-white/40 mb-3">Top Deviations ({projection}) — click to select</h2>
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
              <tr key={i} className={`border-t border-white/10 cursor-pointer hover:bg-white/10 ${selectedRegion === r.region ? 'bg-cyan-500/10' : ''}`}
                onClick={() => setSelectedRegion(r.region)}>
                <td className="p-2 text-white/40">{i + 1}</td>
                <td className="p-2 font-semibold">{r.region}</td>
                <td className="p-2 text-right font-mono">{(r.area_physical_m2 / 1e6).toLocaleString()}</td>
                <td className="p-2 text-right font-mono">{(r.area_legacy_m2 / 1e6).toLocaleString()}</td>
                <td className={`p-2 text-right font-mono ${r.relative_error_percent < 0 ? 'text-red-400' : 'text-blue-400'}`}>
                  {r.relative_error_percent > 0 ? '+' : ''}{r.relative_error_percent.toFixed(1)}%
                </td>
                <td className="p-2 text-xs">
                  <span className={`px-2 py-0.5 rounded ${
                    r.distortion_category === 'overreported' ? 'bg-red-500/20 text-red-400' :
                    r.distortion_category === 'underreported' ? 'bg-blue-500/20 text-blue-400' :
                    'bg-green-500/20 text-green-400'
                  }`}>{r.distortion_category}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}

function ManifoldView({ regions, selected, onSelect }: { regions: RegionNode[]; selected: string | null; onSelect: (name: string) => void }) {
  const mountRef = useRef<HTMLDivElement>(null);
  const pointsRef = useRef<THREE.Points | null>(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || regions.length === 0) return;

    const width = mount.clientWidth;
    const height = 400;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a0a);

    const camera = new THREE.OrthographicCamera(-3000, 3000, 1500, -1500, 0.1, 1000);
    camera.position.set(0, 0, 100);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    mount.appendChild(renderer.domElement);

    // Normalise coordinates.
    const coords = regions.map(r => r.coords);
    const xs = coords.map(c => c[0]);
    const ys = coords.map(c => c[1]);
    const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
    const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
    const range = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));

    // Points.
    const positions = new Float32Array(regions.length * 3);
    const colors = new Float32Array(regions.length * 3);
    regions.forEach((r, i) => {
      positions[i * 3] = r.coords[0] - cx;
      positions[i * 3 + 1] = r.coords[1] - cy;
      positions[i * 3 + 2] = 0;
      // Colour by area (larger = warmer).
      const t = Math.min(1, Math.sqrt(r.area_km2) / 5000);
      colors[i * 3] = 0.2 + t * 0.8;
      colors[i * 3 + 1] = 0.8 - t * 0.3;
      colors[i * 3 + 2] = 1.0 - t * 0.5;
    });

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    const material = new THREE.PointsMaterial({ vertexColors: true, size: 15, sizeAttenuation: false });
    const pointsMesh = new THREE.Points(geometry, material);
    scene.add(pointsMesh);
    pointsRef.current = pointsMesh;

    // Raycaster for click selection.
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    raycaster.params.Points = { threshold: 20 };

    const onClick = (event: MouseEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObject(pointsMesh);
      if (intersects.length > 0) {
        const idx = intersects[0].index;
        if (idx !== undefined && regions[idx]) {
          onSelect(regions[idx].name);
        }
      }
    };
    renderer.domElement.addEventListener('click', onClick);

    // Highlight selected.
    const updateColors = () => {
      const colors = geometry.attributes.color.array as Float32Array;
      regions.forEach((r, i) => {
        if (r.name === selected) {
          colors[i * 3] = 0; colors[i * 3 + 1] = 1; colors[i * 3 + 2] = 1; // cyan
        } else {
          const t = Math.min(1, Math.sqrt(r.area_km2) / 5000);
          colors[i * 3] = 0.2 + t * 0.8;
          colors[i * 3 + 1] = 0.8 - t * 0.3;
          colors[i * 3 + 2] = 1.0 - t * 0.5;
        }
      });
      geometry.attributes.color.needsUpdate = true;
    };
    updateColors();

    const animate = () => {
      requestAnimationFrame(animate);
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      renderer.domElement.removeEventListener('click', onClick);
      if (mount.contains(renderer.domElement)) mount.removeChild(renderer.domElement);
      renderer.dispose();
    };
  }, [regions, selected, onSelect]);

  return <div ref={mountRef} className="w-full" />;
}
