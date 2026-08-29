"use client";

import { useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { MODULES } from '@/components/ModuleConfig';
import { ChevronLeft, Loader2, AlertCircle } from 'lucide-react';
import LLMPalette from '@/components/LLMPalette';
import { apiUrl } from '@/lib/api';

export default function ModulePage() {
  const params = useParams();
  const router = useRouter();
  const moduleId = params.moduleId as string;
  
  const module = MODULES.find(m => m.id === moduleId);
  
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [loadTime, setLoadTime] = useState<number>(0);

  const runTest = async () => {
    if (!module) return;
    setLoading(true);
    setError('');
    const start = Date.now();
    
    try {
      const isPost = !!module.testPayload;
      const res = await fetch(apiUrl(`/api${module.apiEndpoint}`), {
        method: isPost ? 'POST' : 'GET',
        headers: { 'Content-Type': 'application/json' },
        body: isPost ? JSON.stringify(module.testPayload) : undefined,
      });
      
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      
      const json = await res.json();
      setLoadTime(Date.now() - start);
      setResult(json);
    } catch (e: any) {
      setError(e.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  if (!module) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', background: '#000', color: '#fff' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 300, marginBottom: '24px' }}>Module not found</h1>
        <button onClick={() => router.push('/dashboard')} style={{ padding: '8px 16px', background: 'transparent', border: '1px solid #333', color: '#666', borderRadius: '4px', cursor: 'pointer' }}>
          Back to Dashboard
        </button>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden', background: '#000' }}>
      {/* Sidebar */}
      <nav style={{ width: '240px', background: '#0a0a0a', borderRight: '1px solid #1a1a1a', display: 'flex', flexDirection: 'column', padding: '20px' }}>
        <button onClick={() => router.push('/dashboard')} style={{ marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', background: 'transparent', border: 'none', color: '#666', cursor: 'pointer', fontSize: '13px' }}>
          <ChevronLeft size={16} /> Dashboard
        </button>
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {MODULES.map(m => {
            const isActive = m.id === moduleId;
            return (
              <button
                key={m.id}
                onClick={() => router.push(m.path)}
                style={{
                  display: 'flex', alignItems: 'center', gap: '10px',
                  padding: '10px 12px',
                  width: '100%', textAlign: 'left',
                  background: isActive ? 'rgba(6,182,212,0.1)' : 'transparent',
                  border: 'none', borderRadius: '6px',
                  color: isActive ? '#06b6d4' : '#888',
                  cursor: 'pointer', marginBottom: '2px',
                  fontFamily: 'monospace', fontSize: '12px',
                }}
              >
                <span style={{ fontSize: '16px' }}>{m.icon}</span>
                {m.name}
              </button>
            );
          })}
        </div>
      </nav>

      {/* Main Content */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '32px', overflowY: 'auto' }}>
        {/* Header */}
        <header style={{ marginBottom: '32px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '8px' }}>
            <div style={{ padding: '10px', background: '#111', borderRadius: '8px', border: '1px solid #222', fontSize: '24px' }}>
              {module.icon}
            </div>
            <div>
              <h1 style={{ fontSize: '22px', fontWeight: 400, letterSpacing: '1px', color: '#fff' }}>{module.name}</h1>
              <p style={{ fontSize: '12px', color: '#444', marginTop: '4px' }}>{module.description}</p>
            </div>
          </div>
        </header>

        {/* Run Button */}
        <div style={{ marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ fontSize: '12px', fontWeight: 500, letterSpacing: '1px', textTransform: 'uppercase', color: '#333' }}>
            {module.testPayload ? 'Run Test' : 'Load Data'}
          </h3>
          <button 
            onClick={runTest} 
            disabled={loading}
            style={{
              padding: '8px 20px',
              background: loading ? '#222' : '#06b6d4',
              color: loading ? '#555' : '#000',
              border: 'none', borderRadius: '6px',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontSize: '13px', fontWeight: 600,
              display: 'flex', alignItems: 'center', gap: '8px',
            }}
          >
            {loading ? <><Loader2 size={14} /> Computing...</> : module.testPayload ? 'Execute' : 'Load'}
          </button>
        </div>

        {error && (
          <div style={{ padding: '12px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '6px', color: '#ef4444', fontSize: '12px', fontFamily: 'monospace', marginBottom: '16px' }}>
            <AlertCircle size={14} style={{ verticalAlign: 'middle', marginRight: '8px' }} />
            {error}
          </div>
        )}

        {/* Results */}
        {result && (
          <div style={{ background: '#0a0a0a', border: '1px solid #1a1a1a', borderRadius: '8px', padding: '20px' }}>
            {/* Metrics Row */}
            <div style={{ display: 'flex', gap: '32px', marginBottom: '20px', paddingBottom: '16px', borderBottom: '1px solid #1a1a1a' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '11px', color: '#333', textTransform: 'uppercase' }}>Status</span>
                <span style={{ fontSize: '12px', color: '#10b981', fontFamily: 'monospace' }}>complete</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '11px', color: '#333', textTransform: 'uppercase' }}>Load Time</span>
                <span style={{ fontSize: '12px', fontFamily: 'monospace', color: loadTime < 1000 ? '#10b981' : '#f59e0b' }}>
                  {loadTime}ms
                </span>
              </div>
            </div>

            {/* Rationale */}
            {result.rationale && (
              <div style={{ marginBottom: '16px' }}>
                <div style={{ fontSize: '11px', color: '#333', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>Rationale</div>
                <p style={{ fontSize: '13px', color: '#888', fontFamily: 'monospace', lineHeight: 1.6 }}>
                  {result.rationale}
                </p>
              </div>
            )}

            {/* Metrics Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '16px', marginBottom: '16px' }}>
              {result.stress !== undefined && (
                <div>
                  <div style={{ fontSize: '11px', color: '#333', textTransform: 'uppercase', letterSpacing: '1px' }}>Stress</div>
                  <div style={{ fontSize: '18px', color: '#e2e8f0', fontWeight: 600, fontFamily: 'monospace' }}>
                    {typeof result.stress === 'number' ? result.stress.toExponential(4) : result.stress}
                  </div>
                </div>
              )}
              {result.iterations !== undefined && (
                <div>
                  <div style={{ fontSize: '11px', color: '#333', textTransform: 'uppercase', letterSpacing: '1px' }}>Iterations</div>
                  <div style={{ fontSize: '18px', color: '#e2e8f0', fontWeight: 600, fontFamily: 'monospace' }}>{result.iterations}</div>
                </div>
              )}
              {result.converged !== undefined && (
                <div>
                  <div style={{ fontSize: '11px', color: '#333', textTransform: 'uppercase', letterSpacing: '1px' }}>Converged</div>
                  <div style={{ fontSize: '18px', color: result.converged ? '#10b981' : '#ef4444', fontWeight: 600 }}>
                    {result.converged ? '✓ yes' : '✗ no'}
                  </div>
                </div>
              )}
              {result.confidence !== undefined && (
                <div>
                  <div style={{ fontSize: '11px', color: '#333', textTransform: 'uppercase', letterSpacing: '1px' }}>Confidence</div>
                  <div style={{ fontSize: '18px', color: '#06b6d4', fontWeight: 600, fontFamily: 'monospace' }}>
                    {(result.confidence * 100).toFixed(1)}%
                  </div>
                </div>
              )}
              {result.error !== undefined && (
                <div>
                  <div style={{ fontSize: '11px', color: '#333', textTransform: 'uppercase', letterSpacing: '1px' }}>Residual</div>
                  <div style={{ fontSize: '18px', color: '#e2e8f0', fontWeight: 600, fontFamily: 'monospace' }}>
                    {typeof result.error === 'number' ? result.error.toExponential(4) : result.error}
                  </div>
                </div>
              )}
              {result.shape !== undefined && (
                <div>
                  <div style={{ fontSize: '11px', color: '#333', textTransform: 'uppercase', letterSpacing: '1px' }}>Shape</div>
                  <div style={{ fontSize: '18px', color: '#a78bfa', fontWeight: 600 }}>{result.shape}</div>
                </div>
              )}
              {result.total_path_length !== undefined && (
                <div>
                  <div style={{ fontSize: '11px', color: '#333', textTransform: 'uppercase', letterSpacing: '1px' }}>Path Length</div>
                  <div style={{ fontSize: '18px', color: '#e2e8f0', fontWeight: 600, fontFamily: 'monospace' }}>
                    {result.total_path_length.toFixed(4)}
                  </div>
                </div>
              )}
            </div>

            {/* Data Display */}
            <div style={{ marginTop: '16px' }}>
              <div style={{ fontSize: '11px', color: '#333', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>
                Raw Response
              </div>
              <pre style={{ fontSize: '11px', color: '#555', fontFamily: 'monospace', background: '#0a0a0a', padding: '12px', borderRadius: '6px', overflowX: 'auto', maxHeight: '400px', overflowY: 'auto', border: '1px solid #1a1a1a' }}>
                {JSON.stringify(result, null, 2)}
              </pre>
            </div>

            {/* Note */}
            {result.note && (
              <div style={{ marginTop: '16px', padding: '12px', background: '#0a0a0a', borderRadius: '6px', border: '1px solid #1a1a1a', fontFamily: 'monospace', fontSize: '12px', color: '#444' }}>
                {result.note}
              </div>
            )}
          </div>
        )}

        {/* Loading State */}
        {loading && !result && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '20px', background: '#0a0a0a', border: '1px solid #1a1a1a', borderRadius: '8px' }}>
            <Loader2 size={20} color="#06b6d4" />
            <span style={{ color: '#555', fontFamily: 'monospace', fontSize: '13px' }}>Computing...</span>
          </div>
        )}

        {/* Empty State */}
        {!result && !loading && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '60px', background: '#0a0a0a', border: '1px solid #1a1a1a', borderRadius: '8px', color: '#333', fontFamily: 'monospace', fontSize: '13px' }}>
            Click "Execute" to run the module test
          </div>
        )}
      </main>

      <LLMPalette />
    </div>
  );
}
