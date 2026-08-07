"use client";

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { MODULES } from '@/components/ModuleConfig';
import { Activity, Clock } from 'lucide-react';

export default function Dashboard() {
  const router = useRouter();
  const [selectedModule, setSelectedModule] = useState<string | null>(null);

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden' }}>
      <nav style={{ width: '240px', background: 'var(--bg-surface)', borderRight: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', padding: 'var(--space-lg)' }}>
        <div style={{ marginBottom: 'var(--space-xl)', display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
          <div style={{ 
            width: '32px', height: '32px', 
            background: 'var(--accent-cyan)', 
            boxShadow: '0 0 16px hsla(186, 100%, 50%, 0.5)',
            clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)'
          }}></div>
          <h1 style={{ fontFamily: 'var(--font-mono)', fontSize: '18px', fontWeight: 600, letterSpacing: '1px' }}>AETHERA</h1>
        </div>

        <div style={{ flex: 1, overflowY: 'auto' }}>
          {MODULES.map((mod, i) => (
            <button
              key={mod.id}
              onClick={() => router.push(mod.path)}
              style={{
                display: 'flex', alignItems: 'center', gap: 'var(--space-sm)',
                padding: 'var(--space-sm) var(--space-md)',
                width: '100%', textAlign: 'left',
                background: selectedModule === mod.id ? 'hsla(186,100%,50%,0.1)' : 'transparent',
                border: 'none', borderRadius: 'var(--radius-sm)',
                color: selectedModule === mod.id ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                cursor: 'pointer', marginBottom: '2px',
                fontFamily: 'var(--font-mono)', fontSize: '12px',
              }}
            >
              <span style={{ fontSize: '16px' }}>{mod.icon}</span>
              {mod.name}
            </button>
          ))}
        </div>
      </nav>

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 'var(--space-2xl)', overflowY: 'auto' }}>
        <header style={{ marginBottom: 'var(--space-2xl)' }}>
          <h2 style={{ fontSize: '24px', fontWeight: 300, letterSpacing: '2px' }}>SYSTEM OVERVIEW</h2>
          <p style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: '13px', marginTop: 'var(--space-xs)' }}>
            Sovereign Computational Geometry Platform — Absolute Geometric Substrate
          </p>
        </header>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: 'var(--space-lg)',
          alignContent: 'start'
        }}>
          {MODULES.map((mod, i) => (
            <motion.div
              key={mod.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05, duration: 0.4, ease: 'easeOut' }}
              className="card"
              style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)', cursor: 'pointer', height: '100%' }}
              onClick={() => router.push(mod.path)}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
                  <div style={{
                    padding: 'var(--space-sm)',
                    background: 'var(--bg-app)',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border-subtle)'
                  }}>
                    <span style={{ fontSize: '20px' }}>{mod.icon}</span>
                  </div>
                  <h3 style={{ fontSize: '14px', fontWeight: 500 }}>{mod.name}</h3>
                </div>
                <div className="status-dot active" title="Operational" />
              </div>

              <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.5, flex: 1 }}>
                {mod.description}
              </p>

              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 'auto' }}>
                <button className="btn-ghost" style={{ fontSize: '11px', padding: 'var(--space-xs) var(--space-sm)' }}>
                  Open →
                </button>
              </div>
            </motion.div>
          ))}
        </div>

        <div style={{ marginTop: 'auto', paddingTop: 'var(--space-xl)' }}>
          <div style={{
            width: '100%',
            padding: 'var(--space-md)',
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--space-sm)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
                <Activity size={14} color="var(--accent-emerald)" />
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--text-mono)' }}>
                  System Status: NOMINAL
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
                <Clock size={14} color="var(--accent-amber)" />
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--text-secondary)' }}>
                  v0.2.0
                </span>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 'var(--space-md)', fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-muted)' }}>
              <span>Backend: http://localhost:8765</span>
              <span>|</span>
              <span>API: 9 modules operational</span>
              <span>|</span>
              <span>LLM: Agnes-AI (no key)</span>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
