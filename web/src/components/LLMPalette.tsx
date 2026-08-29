"use client";

import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * AETHERA AI Palette (v25.0) — global Ctrl+K / ⌘K overlay.
 *
 * Chat with the platform LLM (NVIDIA NIM free endpoints — no API key
 * required by default) and manage NVIDIA keys:
 *   - the platform ships with a built-in key (works out of the box)
 *   - users may set their own key (stored in localStorage, sent per
 *     request) and optionally rotate the server-side key.
 */

type LLMStatus = {
  primary?: string;
  models?: string[];
  active_key_masked?: string;
  note?: string;
};

const LS_KEY = 'aethera_nvidia_key';

export function getUserNvidiaKey(): string {
  if (typeof window === 'undefined') return '';
  try {
    return window.localStorage.getItem(LS_KEY) || '';
  } catch {
    return '';
  }
}

export default function LLMPalette() {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<'chat' | 'settings'>('chat');

  // chat state
  const [prompt, setPrompt] = useState('');
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState('');
  const [meta, setMeta] = useState<{ provider: string; model: string } | null>(null);
  const [chatError, setChatError] = useState('');
  const [selectedModel, setSelectedModel] = useState<string>('auto');
  const chatEndRef = useRef<HTMLDivElement>(null);

  // settings state
  const [status, setStatus] = useState<LLMStatus | null>(null);
  const [keyInput, setKeyInput] = useState('');
  const [savedKey, setSavedKey] = useState('');
  const [settingsMsg, setSettingsMsg] = useState('');

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  useEffect(() => {
    setSavedKey(getUserNvidiaKey());
    if (open) {
      fetch('/api/llm')
        .then((r) => r.json())
        .then((d) => setStatus(d))
        .catch(() => setStatus(null));
    }
  }, [open]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [answer, chatError, busy]);

  const send = useCallback(async () => {
    const text = prompt.trim();
    if (!text || busy) return;
    setBusy(true);
    setChatError('');
    setAnswer('');
    setMeta(null);
    try {
      const res = await fetch('/api/llm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: text,
          apiKey: getUserNvidiaKey() || undefined,
          model: selectedModel === 'auto' ? undefined : selectedModel,
        }),
      });
      const json = await res.json();
      if (json.success) {
        setAnswer(json.text || '(empty response)');
        setMeta({ provider: json.provider, model: json.model });
      } else {
        setChatError(json.error || json.text || 'Request failed');
      }
    } catch (e: any) {
      setChatError(e?.message || 'Request failed');
    } finally {
      setBusy(false);
    }
  }, [prompt, busy, selectedModel]);

  const saveKey = useCallback(async () => {
    const k = keyInput.trim();
    if (!k) {
      setSettingsMsg('Enter a key first.');
      return;
    }
    if (!k.startsWith('nvapi-')) {
      setSettingsMsg('NVIDIA keys start with "nvapi-".');
      return;
    }
    try {
      window.localStorage.setItem(LS_KEY, k);
      setSavedKey(k);
      setSettingsMsg('Key saved locally — it will be used for your requests.');
    } catch {
      setSettingsMsg('Could not access localStorage.');
    }
    // Best-effort server-side rotation (ignored if unreachable).
    try {
      await fetch('/api/llm/key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: k }),
      });
    } catch {
      /* per-request key still applies */
    }
    setKeyInput('');
  }, [keyInput]);

  const resetKey = useCallback(async () => {
    try {
      window.localStorage.removeItem(LS_KEY);
    } catch { /* ignore */ }
    setSavedKey('');
    setSettingsMsg('Reverted to the built-in platform key.');
    try {
      await fetch('/api/llm/key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reset: true }),
      });
    } catch { /* ignore */ }
  }, []);

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        title="AI Assistant (Ctrl+K)"
        style={{
          position: 'fixed', right: '20px', bottom: '20px', zIndex: 50,
          display: 'flex', alignItems: 'center', gap: '8px',
          padding: '10px 16px',
          background: '#0a0a0a', border: '1px solid #06b6d4', borderRadius: '8px',
          color: '#06b6d4', fontFamily: 'monospace', fontSize: '12px',
          cursor: 'pointer', boxShadow: '0 0 16px rgba(6,182,212,0.25)',
        }}
      >
        <span style={{ fontSize: '14px' }}>✦</span> AI Assistant
        <span style={{ color: '#555' }}>⌘K</span>
      </button>
    );
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 100,
        background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(2px)',
        display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
        paddingTop: '8vh',
      }}
      onClick={() => setOpen(false)}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 'min(680px, 92vw)', maxHeight: '80vh',
          background: '#0a0a0a', border: '1px solid #1e2a32', borderRadius: '12px',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
          boxShadow: '0 8px 40px rgba(0,0,0,0.6)',
        }}
      >
        {/* header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '14px 16px', borderBottom: '1px solid #161d22' }}>
          <span style={{ color: '#06b6d4', fontSize: '16px' }}>✦</span>
          <span style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: '13px', letterSpacing: '1px' }}>
            AETHERA AI — NVIDIA NIM (free, no key required)
          </span>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: '6px' }}>
            {(['chat', 'settings'] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                style={{
                  padding: '5px 12px', fontSize: '11px', fontFamily: 'monospace',
                  background: tab === t ? 'rgba(6,182,212,0.12)' : 'transparent',
                  color: tab === t ? '#06b6d4' : '#667',
                  border: `1px solid ${tab === t ? '#06b6d4' : '#1e2a32'}`,
                  borderRadius: '6px', cursor: 'pointer', textTransform: 'uppercase',
                }}
              >
                {t}
              </button>
            ))}
            <button
              onClick={() => setOpen(false)}
              style={{ padding: '5px 12px', fontSize: '11px', background: 'transparent', color: '#667', border: '1px solid #1e2a32', borderRadius: '6px', cursor: 'pointer', fontFamily: 'monospace' }}
            >
              ESC
            </button>
          </div>
        </div>

        {tab === 'chat' && (
          <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
            <div style={{ flex: 1, overflowY: 'auto', padding: '16px', minHeight: '220px' }}>
              {!answer && !chatError && !busy && (
                <p style={{ color: '#556', fontFamily: 'monospace', fontSize: '12px', lineHeight: 1.7 }}>
                  Ask anything about the AETHERA geometric substrate — modules,
                  endpoints, axioms, or general geometry. Powered by NVIDIA free
                  models with automatic fallback: deepseek-v4-flash →
                  nemotron-3.5-lightning → kimi-k3.
                </p>
              )}
              {busy && (
                <p style={{ color: '#06b6d4', fontFamily: 'monospace', fontSize: '12px' }}>
                  Thinking… (reasoning models may take up to a minute)
                </p>
              )}
              {answer && (
                <div>
                  <pre style={{ whiteSpace: 'pre-wrap', color: '#d7e2ea', fontFamily: 'monospace', fontSize: '12.5px', lineHeight: 1.7, margin: 0 }}>
                    {answer}
                  </pre>
                  {meta && (
                    <p style={{ color: '#10b981', fontFamily: 'monospace', fontSize: '11px', marginTop: '10px' }}>
                      {meta.provider} · {meta.model}
                    </p>
                  )}
                </div>
              )}
              {chatError && (
                <p style={{ color: '#f87171', fontFamily: 'monospace', fontSize: '12px' }}>{chatError}</p>
              )}
              <div ref={chatEndRef} />
            </div>

            <div style={{ padding: '12px 16px', borderTop: '1px solid #161d22' }}>
              <div style={{ display: 'flex', gap: '8px', marginBottom: '8px', alignItems: 'center' }}>
                <select
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  style={{
                    background: '#0f1417', color: '#89a', border: '1px solid #1e2a32',
                    borderRadius: '6px', fontSize: '11px', fontFamily: 'monospace', padding: '6px 8px',
                  }}
                >
                  <option value="auto">auto (fallback chain)</option>
                  <option value="deepseek-ai/deepseek-v4-flash-0731">deepseek-v4-flash-0731</option>
                  <option value="nvidia/nemotron-3.5-lightning-30b-a3b">nemotron-3.5-lightning-30b</option>
                  <option value="moonshotai/kimi-k3">kimi-k3</option>
                </select>
                {savedKey && (
                  <span style={{ color: '#10b981', fontSize: '11px', fontFamily: 'monospace' }}>
                    using your key ({savedKey.slice(0, 9)}****)
                  </span>
                )}
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
                  }}
                  placeholder="Ask AETHERA… (Enter to send)"
                  rows={2}
                  style={{
                    flex: 1, resize: 'none', background: '#0f1417', color: '#d7e2ea',
                    border: '1px solid #1e2a32', borderRadius: '8px', padding: '10px',
                    fontFamily: 'monospace', fontSize: '12.5px', outline: 'none',
                  }}
                />
                <button
                  onClick={send}
                  disabled={busy || !prompt.trim()}
                  style={{
                    padding: '0 18px', borderRadius: '8px', cursor: busy ? 'wait' : 'pointer',
                    background: busy ? '#0d2229' : '#06b6d4', color: busy ? '#456' : '#00232b',
                    border: 'none', fontFamily: 'monospace', fontSize: '12px', fontWeight: 600,
                  }}
                >
                  {busy ? '…' : 'Send'}
                </button>
              </div>
            </div>
          </div>
        )}

        {tab === 'settings' && (
          <div style={{ padding: '16px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <h3 style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: '12px', margin: '0 0 6px' }}>
                PROVIDER STATUS
              </h3>
              <p style={{ color: '#89a', fontFamily: 'monospace', fontSize: '11.5px', lineHeight: 1.7, margin: 0 }}>
                {status?.primary || 'NVIDIA NIM (free) — no API key required'}
                <br />
                Models: {(status?.models || ['deepseek-ai/deepseek-v4-flash-0731', 'nvidia/nemotron-3.5-lightning-30b-a3b', 'moonshotai/kimi-k3']).join(' → ')}
                {status?.active_key_masked && (
                  <>
                    <br />
                    Active server key: <span style={{ color: '#06b6d4' }}>{status.active_key_masked}</span>
                  </>
                )}
              </p>
            </div>

            <div style={{ borderTop: '1px solid #161d22', paddingTop: '14px' }}>
              <h3 style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: '12px', margin: '0 0 6px' }}>
                SET A NEW NVIDIA API KEY
              </h3>
              <p style={{ color: '#667', fontFamily: 'monospace', fontSize: '11px', lineHeight: 1.7, margin: '0 0 10px' }}>
                Optional — the platform works without it. Your key is stored in
                this browser and sent with each request; it also rotates the
                server-side key when the backend is reachable.
              </p>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="password"
                  value={keyInput}
                  onChange={(e) => setKeyInput(e.target.value)}
                  placeholder="nvapi-…"
                  style={{
                    flex: 1, background: '#0f1417', color: '#d7e2ea',
                    border: '1px solid #1e2a32', borderRadius: '8px', padding: '10px',
                    fontFamily: 'monospace', fontSize: '12px', outline: 'none',
                  }}
                />
                <button
                  onClick={saveKey}
                  style={{
                    padding: '0 16px', borderRadius: '8px', cursor: 'pointer',
                    background: '#06b6d4', color: '#00232b', border: 'none',
                    fontFamily: 'monospace', fontSize: '12px', fontWeight: 600,
                  }}
                >
                  Save
                </button>
                <button
                  onClick={resetKey}
                  style={{
                    padding: '0 16px', borderRadius: '8px', cursor: 'pointer',
                    background: 'transparent', color: '#89a', border: '1px solid #1e2a32',
                    fontFamily: 'monospace', fontSize: '12px',
                  }}
                >
                  Reset
                </button>
              </div>
              {settingsMsg && (
                <p style={{ color: '#10b981', fontFamily: 'monospace', fontSize: '11px', marginTop: '8px' }}>
                  {settingsMsg}
                </p>
              )}
            </div>

            <div style={{ borderTop: '1px solid #161d22', paddingTop: '14px' }}>
              <h3 style={{ color: '#e2e8f0', fontFamily: 'monospace', fontSize: '12px', margin: '0 0 6px' }}>
                FALLBACK CHAIN
              </h3>
              <p style={{ color: '#667', fontFamily: 'monospace', fontSize: '11px', lineHeight: 1.7, margin: 0 }}>
                NVIDIA NIM → GLM-5.2 (Z.ai) → DeepSeek → ChatGPT → Gemini → Mistral → Local (Ollama).
                Fallback providers activate automatically when configured via environment variables.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
