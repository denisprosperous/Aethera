'use client';

/**
 * AETHERA v39.0 — ElevationToggle
 *
 * Top-right toggle for elevation-on-click mode. When ON, clicking
 * anywhere on the stitched world queries /api/elevation and shows the
 * ETOPO1 elevation (metres, sea-level reference) at the intrinsic
 * point. When OFF, clicks select countries (zoom + Truth Panel).
 */

export default function ElevationToggle({
  enabled,
  onToggle,
}: {
  enabled: boolean;
  onToggle: (v: boolean) => void;
}) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
      <button
        onClick={() => onToggle(!enabled)}
        aria-pressed={enabled}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 8,
          background: enabled ? 'rgba(0,255,136,0.14)' : '#0d1117',
          border: `1px solid ${enabled ? '#00ff88' : '#1c2a38'}`,
          color: enabled ? '#00ff88' : '#8b9bab',
          borderRadius: 8,
          padding: '9px 16px',
          cursor: 'pointer',
          fontFamily: 'monospace',
          fontSize: 12,
          letterSpacing: 1,
          boxShadow: enabled ? '0 0 14px rgba(0,255,136,0.25)' : 'none',
        }}
      >
        <span style={{ fontSize: 14 }}>{enabled ? '⛰' : '○'}</span>
        ELEVATION ON CLICK · {enabled ? 'ON' : 'OFF'}
      </button>
    </div>
  );
}
