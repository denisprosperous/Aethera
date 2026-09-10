'use client';

/**
 * AETHERA v37.1 — ElevationToggle
 *
 * Top-right toggle for elevation-on-click. When ON, clicking any point
 * of the Intrinsic Manifold samples the ETOPO1 height above sea level
 * stored as a per-vertex physical scalar at ingestion time (no
 * coordinates leave the solver's intrinsic frame — Axioms 3-4). When
 * OFF, clicks select the country and open the Truth Panel.
 */

export interface ElevationResult {
  elevation_m: number | null;
  coordinates?: [number, number, number];
  source?: string;
  reference?: string;
  error?: string;
}

export function ElevationToggle({
  enabled,
  onToggle,
  elevation,
}: {
  enabled: boolean;
  onToggle: (next: boolean) => void;
  elevation: ElevationResult | null;
}) {
  return (
    <div style={{ position: 'absolute', top: 12, right: 12, zIndex: 10, display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end' }}>
      <button
        onClick={() => onToggle(!enabled)}
        style={{
          padding: '8px 14px',
          borderRadius: 6,
          border: `1px solid ${enabled ? '#10b981' : '#1c2a38'}`,
          background: enabled ? 'rgba(16,185,129,0.16)' : 'rgba(13,17,23,0.92)',
          color: enabled ? '#10b981' : '#8b9bab',
          fontFamily: 'monospace',
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: 1,
          cursor: 'pointer',
          backdropFilter: 'blur(4px)',
        }}
        title="Toggle elevation sampling: when ON, clicking the manifold returns the ETOPO1 height above sea level at that point"
      >
        {enabled ? '▲ Elevation: ON' : '▲ Elevation: OFF'}
      </button>

      {enabled && elevation && (
        <div
          style={{
            background: 'rgba(4,10,16,0.94)',
            border: '1px solid #38bdf8aa',
            borderRadius: 6,
            padding: '7px 11px',
            color: '#e6edf3',
            fontFamily: 'monospace',
            fontSize: 11,
            lineHeight: 1.55,
            pointerEvents: 'none',
            whiteSpace: 'nowrap',
          }}
        >
          {elevation.elevation_m !== null && elevation.elevation_m !== undefined ? (
            <>
              <div style={{ color: '#38bdf8', fontWeight: 700 }}>
                Elevation: {elevation.elevation_m.toLocaleString()} m
              </div>
              <div style={{ color: '#5b6b7b' }}>
                {elevation.source || 'ETOPO1_GLOBAL'} · {elevation.reference || 'sea_level'}
              </div>
            </>
          ) : (
            <div style={{ color: '#f59e0b' }}>
              {elevation.error || 'Point outside known manifold'}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default ElevationToggle;
