"use client";

import { Canvas } from '@react-three/fiber';
import { OrbitControls, Line, Text } from '@react-three/drei';
import { useMemo } from 'react';

interface ManifoldViewerProps {
  vertices: number[][];
  edges: number[][];
  colors?: string[];
}

export default function ManifoldViewer({ vertices, edges, colors }: ManifoldViewerProps) {
  const geometry = useMemo(() => {
    return { vertices, edges };
  }, [vertices, edges]);

  if (vertices.length === 0) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '400px', background: '#0a0a0a', borderRadius: '8px' }}>
        <span style={{ color: '#666', fontFamily: 'monospace' }}>No data to visualize</span>
      </div>
    );
  }

  return (
    <div style={{ height: '400px', background: '#0a0a0a', borderRadius: '8px', overflow: 'hidden' }}>
      <Canvas camera={{ position: [10, 10, 10], fov: 50 }}>
        <ambientLight intensity={0.5} />
        <directionalLight position={[10, 10, 5]} />
        
        {/* Render edges as lines */}
        {edges.map((edge, i) => {
          const start = (vertices[edge[0]] || [0, 0, 0]) as [number, number, number];
          const end = (vertices[edge[1]] || [0, 0, 0]) as [number, number, number];
          return (
            <Line
              key={i}
              points={[start, end]}
              color={colors?.[i] || '#06b6d4'}
              lineWidth={1}
            />
          );
        })}
        
        {/* Render vertices as spheres */}
        {vertices.map((v, i) => (
          <mesh key={i} position={v as [number, number, number]}>
            <sphereGeometry args={[0.15]} />
            <meshStandardMaterial color={colors?.[i] || '#a78bfa'} />
          </mesh>
        ))}
        
        <OrbitControls enablePan={false} enableZoom={true} />
      </Canvas>
    </div>
  );
}
