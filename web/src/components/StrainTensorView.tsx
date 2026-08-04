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
