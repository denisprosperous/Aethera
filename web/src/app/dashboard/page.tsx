"use client";

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { MODULES } from '@/components/ModuleConfig';
import { Activity, Clock } from 'lucide-react';

export default function Dashboard() {
  const router = useRouter();
  const [selectedModule, setSelectedModule] = useState<string | null>(null);
  const [health, setHealth] = useState<any>(null);
  const [healthError, setHealthError] = useState<string>('');

  useEffect(() => {
    fetch('http://localhost:8765/api/health', { signal: AbortSignal.timeout(3000) })
      .then(r => r.json())
      .then(setHealth)
      .catch(() => setHealthError('Backend unreachable'));
  }, []);

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden', background: '#000' }}>
      <nav style={{ width: '240px', background: '#0a0a0a', borderRight: '1px solid #1a1a1a', display: 'flex', flexDirection: 'column', padding: '20px' }}>
        <div style={{ marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ 
            width: '28px', height: '28px', 
            background: '#06b6d4', 
            boxShadow: '0 0 12px rgba(6,182,212,0.4)',
            clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)'
          }}></div>
          <h1 style={{ fontFamily: 'monospace', fontSize: '16px', fontWeight: 600, letterSpacing: '2px', color: '#fff' }}>AETHERA</h1>
        </div>

        <div style={{ flex: 1, overflowY: 'auto' }}>
          {MODULES.map((mod) => (
            <button
              key={mod.id}
              onClick={() => { setSelectedModule(mod.id); router.push(mod.path); }}
              style={{
                display: 'flex', alignItems: 'center', gap: '10px',
                padding: '10px 12px',
                width: '100%', textAlign: 'left',
                background: selectedModule === mod.id ? 'rgba(6,182,212,0.1)' : 'transparent',
                border: 'none', borderRadius: '6px',
                color: selectedModule === mod.id ? '#06b6d4' : '#888',
                cursor: 'pointer', marginBottom: '2px',
                fontFamily: 'monospace', fontSize: '12px',
              }}
            >
              <span style={{ fontSize: '16px' }}>{mod.icon}</span>
              {mod.name}
            </button>
          ))}
        </div>
      </nav>

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '32px', overflowY: 'auto' }}>
        <header style={{ marginBottom: '32px' }}>
          <h2 style={{ fontSize: '22px', fontWeight: 300, letterSpacing: '2px', color: '#fff' }}>SYSTEM OVERVIEW</h2>
          <p style={{ color: '#444', fontFamily: 'monospace', fontSize: '12px', marginTop: '8px' }}>
            Sovereign Computational Geometry Platform — Absolute Geometric Substrate
          </p>
        </header>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '16px',
          alignContent: 'start'
        }}>
          {MODULES.map((mod) => (
            <div
              key={mod.id}
              style={{
                display: 'flex', flexDirection: 'column', gap: '12px',
                cursor: 'pointer', height: '100%',
                padding: '16px',
                background: '#0a0a0a',
                border: '1px solid #1a1a1a',
                borderRadius: '8px',
                transition: 'border-color 0.2s',
              }}
              onMouseEnter={e => (e.currentTarget.style.borderColor = '#06b6d4')}
              onMouseLeave={e => (e.currentTarget.style.borderColor = '#1a1a1a')}
              onClick={() => router.push(mod.path)}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{
                    padding: '8px',
                    background: '#111',
                    borderRadius: '6px',
                    border: '1px solid #222',
                    fontSize: '20px',
                  }}>
                    {mod.icon}
                  </div>
                  <h3 style={{ fontSize: '13px', fontWeight: 500, color: '#e2e8f0' }}>{mod.name}</h3>
                </div>
                <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10b981', boxShadow: '0 0 6px #10b981' }} />
              </div>

              <p style={{ fontSize: '11px', color: '#555', lineHeight: 1.6, flex: 1 }}>
                {mod.description}
              </p>

              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 'auto' }}>
                <button style={{ fontSize: '11px', padding: '4px 12px', background: 'transparent', border: '1px solid #222', color: '#666', borderRadius: '4px', cursor: 'pointer', fontFamily: 'monospace' }}>
                  Open →
                </button>
              </div>
            </div>
          ))}
        </div>

        <div style={{ marginTop: 'auto', paddingTop: '24px' }}>
          <div style={{
            width: '100%',
            padding: '16px',
            background: '#0a0a0a',
            border: '1px solid #1a1a1a',
            borderRadius: '8px',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Activity size={14} color="#10b981" />
                <span style={{ fontFamily: 'monospace', fontSize: '12px', color: health?.status === 'ok' ? '#10b981' : '#ef4444' }}>
                  System Status: {health?.status === 'ok' ? 'NOMINAL' : healthError ? 'ERROR' : 'CHECKING...'}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Clock size={14} color="#f59e0b" />
                <span style={{ fontFamily: 'monospace', fontSize: '12px', color: '#666' }}>v0.2.0</span>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '16px', fontFamily: 'monospace', fontSize: '11px', color: '#444' }}>
              <span>Backend: http://localhost:8765</span>
              <span>|</span>
              <span>Modules: {MODULES.length} operational</span>
              <span>|</span>
              <span>LLM: {health?.llm?.any_available ? 'Available' : 'Fallback'}</span>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
