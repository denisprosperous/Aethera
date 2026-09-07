'use client';

/**
 * AETHERA v27.0 — Ghost3D
 *
 * Ghost Resolver adjacency graph in 3D: regions are nodes (sized by
 * resolved area), shared boundaries are edges, and red-flagged / unresolved
 * regions glow red with their rationale. Layout is a deterministic 3D
 * force-directed spring embedder — no projection anywhere.
 */

import { useMemo, useState } from 'react';
import { Line } from '@react-three/drei';
import { Scene, ACCENT, springLayout3d, ViewportHud } from './Scene';

interface GhostPolygon {
  name: string;
  area?: number | null;
  claimed_area?: number | null;
  neighbours?: string[];
  [k: string]: unknown;
}

interface Ghost3DProps {
  resolvedAreas: Record<string, number>;
  redFlags: Record<string, unknown>[];
  payload: { polygons?: GhostPolygon[]; [k: string]: unknown };
  onRegionClick?: (region: string) => void;
}

function flagName(flag: Record<string, unknown>): string {
  for (const k of ['name', 'polygon', 'region', 'zone']) {
    if (typeof flag[k] === 'string') return flag[k];
  }
  return '';
}

function flagReason(flag: Record<string, unknown>): string {
  for (const k of ['reason', 'note', 'detail', 'message', 'issue']) {
    if (typeof flag[k] === 'string') return flag[k];
  }
  return JSON.stringify(flag).slice(0, 140);
}

export default function Ghost3D({
  resolvedAreas,
  redFlags,
  payload,
  onRegionClick,
}: Ghost3DProps) {
  const [hover, setHover] = useState<string | null>(null);

  const model = useMemo(() => {
    const polys: GhostPolygon[] = payload?.polygons || [];
    const names = Array.from(
      new Set<string>([
        ...Object.keys(resolvedAreas || {}),
        ...polys.map((p) => p.name),
      ].filter(Boolean)),
    );
    if (names.length === 0) return null;

    // Unique adjacency edges (both directions declared in payload).
    const edges: [string, string][] = [];
    const seen = new Set<string>();
    for (const p of polys) {
      for (const nb of p.neighbours || []) {
        if (!names.includes(nb)) continue;
        const key = [p.name, nb].sort().join('||');
        if (!seen.has(key) && p.name !== nb) {
          seen.add(key);
          edges.push([p.name, nb]);
        }
      }
    }

    const layout = springLayout3d(names, edges, 140, 4.6);
    const flagged = new Map<string, string>();
    for (const f of redFlags || []) {
      const n = flagName(f);
      if (n) flagged.set(n, flagReason(f));
    }

    const areas = names.map((n) => Math.abs(Number(resolvedAreas?.[n]) || 1));
    const maxLog = Math.max(...areas.map((a) => Math.log10(a)), 1);
    const nodes = names.map((n) => {
      const a = Math.abs(Number(resolvedAreas?.[n]) || 1);
      const r = 0.28 + (Math.log10(a) / maxLog) * 0.5;
      return {
        name: n,
        area: Number(resolvedAreas?.[n] ?? NaN),
        claimed: polys.find((p) => p.name === n)?.claimed_area ?? null,
        position: layout[n],
        radius: r,
        flagged: flagged.has(n) || Number.isNaN(Number(resolvedAreas?.[n])),
        reason: flagged.get(n) || 'unresolved / red-flagged',
      };
    });
    return { nodes, edges };
  }, [resolvedAreas, redFlags, payload]);

  if (!model) {
    return (
      <div
        style={{
          width: '100%', height: '100%', display: 'flex', alignItems: 'center',
          justifyContent: 'center', color: '#5b6b7b', fontFamily: 'monospace', fontSize: 12,
        }}
      >
        Run the Ghost Resolver to derive the adjacency graph.
      </div>
    );
  }

  const nodeByName = new Map(model.nodes.map((n) => [n.name, n]));

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <Scene camera={[7.5, 6.4, 9.8]}>
        <gridHelper args={[16, 16, '#0f2436', '#0a1826']} />
        {model.edges.map(([a, b], i) => {
          const pa = nodeByName.get(a)?.position;
          const pb = nodeByName.get(b)?.position;
          if (!pa || !pb) return null;
          const hot = nodeByName.get(a)?.flagged || nodeByName.get(b)?.flagged;
          return (
            <Line
              key={i}
              points={[pa, pb]}
              color={hot ? '#ff3b3b' : '#06b6d4'}
              lineWidth={hot ? 1.8 : 1.1}
              transparent
              opacity={0.8}
            />
          );
        })}
        {model.nodes.map((n) => {
          const claimTxt =
            n.claimed !== null && n.claimed !== undefined
              ? ` | claimed ${Number(n.claimed).toLocaleString()} km²`
              : '';
          return (
            <mesh
              key={n.name}
              position={n.position}
              onPointerOver={(e) => {
                e.stopPropagation();
                setHover(
                  n.flagged
                    ? `⚠ ${n.name} — ${n.reason}${claimTxt}`
                    : `${n.name} — ${Number.isNaN(n.area) ? 'unknown' : n.area.toLocaleString() + ' km²'}`,
                );
              }}
              onPointerOut={() => setHover(null)}
              onClick={() => onRegionClick?.(n.name)}
            >
              <sphereGeometry args={[n.radius, 22, 22]} />
              <meshStandardMaterial
                color={n.flagged ? '#ff3b3b' : ACCENT}
                emissive={n.flagged ? '#ff3b3b' : ACCENT}
                emissiveIntensity={n.flagged ? 1.4 : 0.5}
                roughness={0.35}
              />
            </mesh>
          );
        })}
      </Scene>

      <ViewportHud text={`GHOST RESOLVER — ${model.nodes.length} REGIONS · ${model.edges.length} SHARED BOUNDARIES · RED = UNRESOLVED / FLAGGED`} />

      {hover && (
        <div
          style={{
            position: 'absolute', bottom: 12, left: 12, right: 12, zIndex: 6, maxWidth: 480,
            background: 'rgba(4,10,16,0.94)',
            border: `1px solid ${hover.startsWith('⚠') ? '#ff3b3b66' : ACCENT + '55'}`,
            borderRadius: 6, padding: '8px 12px', color: '#e6edf3',
            fontFamily: 'monospace', fontSize: 11, lineHeight: 1.55,
          }}
        >
          {hover}
        </div>
      )}
    </div>
  );
}
