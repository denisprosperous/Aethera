'use client';

/**
 * AETHERA v27.0 — GlobeControls
 *
 * Control deck for the True-Area Globe: camera presets (3D orbit ↔ 2D
 * planar), heatmap mode (true area ↔ legacy deviation ↔ plain wireframe),
 * labels, mesh, auto-rotate, and the legacy projection selector used by
 * the deviation heatmap. Pure presentation + callbacks.
 */

import type { GlobeHeatMode } from '@/components/three/TrueGlobe';
import { PROJECTION_TYPES } from '@/lib/samples';

export interface GlobeControlState {
  heatMode: GlobeHeatMode;
  showLabels: boolean;
  showMesh: boolean;
  autoRotate: boolean;
  viewPreset: 'orbit' | 'planar';
  projection: string;
}

interface GlobeControlsProps {
  state: GlobeControlState;
  onChange: (patch: Partial<GlobeControlState>) => void;
  disabled?: boolean;
}

const chip = (active: boolean) => ({
  background: active ? 'rgba(0,255,136,0.12)' : '#0d1117',
  border: `1px solid ${active ? '#00ff88' : '#1c2a38'}`,
  color: active ? '#00ff88' : '#8b9bab',
  borderRadius: '6px',
  padding: '7px 13px',
  cursor: 'pointer',
  fontFamily: 'monospace',
  fontSize: '11px',
} as React.CSSProperties);

export default function GlobeControls({ state, onChange, disabled }: GlobeControlsProps) {
  return (
    <div
      style={{
        display: 'flex', flexWrap: 'wrap', gap: '10px 14px', alignItems: 'center',
        background: '#0d1117', border: '1px solid #1c2a38', borderRadius: '10px',
        padding: '12px 14px', opacity: disabled ? 0.5 : 1, pointerEvents: disabled ? 'none' : 'auto',
      }}
    >
      <Group label="VIEW">
        <button style={chip(state.viewPreset === 'orbit')} onClick={() => onChange({ viewPreset: 'orbit' })}>
          🛰 3D Orbit
        </button>
        <button style={chip(state.viewPreset === 'planar')} onClick={() => onChange({ viewPreset: 'planar' })}>
          🗺 2D Planar
        </button>
      </Group>

      <Group label="HEATMAP">
        <button style={chip(state.heatMode === 'area')} onClick={() => onChange({ heatMode: 'area' })}>
          🌡 True Area
        </button>
        <button style={chip(state.heatMode === 'legacy')} onClick={() => onChange({ heatMode: 'legacy' })}>
          📕 Legacy Deviation
        </button>
        <button style={chip(state.heatMode === 'plain')} onClick={() => onChange({ heatMode: 'plain' })}>
          ◻ Plain Mesh
        </button>
      </Group>

      {state.heatMode === 'legacy' && (
        <Group label="LEGACY SOURCE">
          <select
            value={state.projection}
            onChange={(e) => onChange({ projection: e.target.value })}
            style={{
              background: '#040a10', color: '#e6edf3', border: '1px solid #1c2a38',
              borderRadius: 6, padding: '7px 9px', fontFamily: 'monospace', fontSize: 12,
            }}
            aria-label="Legacy projection"
          >
            {PROJECTION_TYPES.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </Group>
      )}

      <Group label="LAYERS">
        <button style={chip(state.showMesh)} onClick={() => onChange({ showMesh: !state.showMesh })}>
          ▦ Mesh
        </button>
        <button style={chip(state.showLabels)} onClick={() => onChange({ showLabels: !state.showLabels })}>
          🏷 Labels
        </button>
        <button style={chip(state.autoRotate)} onClick={() => onChange({ autoRotate: !state.autoRotate })}>
          ⟳ Auto-rotate
        </button>
      </Group>
    </div>
  );
}

function Group({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span
        style={{
          color: '#5b6b7b', fontFamily: 'monospace', fontSize: '10px',
          letterSpacing: '1px', marginRight: 2,
        }}
      >
        {label}
      </span>
      {children}
    </div>
  );
}
