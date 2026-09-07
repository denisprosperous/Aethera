'use client';

/**
 * AETHERA v30.1 — Disclaimer
 *
 * The mandatory principle-first banner. Rendered prominently on every
 * derived-view page (3D Earth Simulation, Truth Portal). It states, in
 * plain language, that any 3D object on screen is a post-hoc extrinsic
 * embedding of the intrinsic manifold — never a pre-seeded globe model.
 */

export const DISCLAIMER_TEXT =
  'This 3D view is a derived extrinsic embedding of the intrinsic manifold. ' +
  'It is not a globe model. The shape is determined solely by the absolute ' +
  'scalar inputs. Any resemblance to a sphere is a consequence of the data, ' +
  'not an assumption.';

export default function Disclaimer({ compact = false }: { compact?: boolean }) {
  return (
    <div
      style={{
        display: 'flex',
        gap: 12,
        alignItems: 'flex-start',
        background: 'linear-gradient(90deg, rgba(0,255,136,0.08), rgba(6,182,212,0.05))',
        border: '1px solid rgba(0,255,136,0.35)',
        borderLeft: '4px solid #00ff88',
        borderRadius: 8,
        padding: compact ? '8px 12px' : '12px 16px',
        marginBottom: 14,
      }}
      role="note"
      aria-label="Derived view disclaimer"
    >
      <span style={{ fontSize: compact ? 14 : 18, lineHeight: 1.2 }}>⚠️</span>
      <div>
        <div
          style={{
            color: '#00ff88',
            fontFamily: 'monospace',
            fontSize: 10,
            letterSpacing: 2,
            marginBottom: 4,
          }}
        >
          DERIVED VIEW — NOT A GLOBE MODEL
        </div>
        <p
          style={{
            color: '#c9d1d9',
            fontFamily: 'monospace',
            fontSize: compact ? 10.5 : 12,
            lineHeight: 1.65,
            margin: 0,
            maxWidth: 980,
          }}
        >
          {DISCLAIMER_TEXT}
        </p>
      </div>
    </div>
  );
}
