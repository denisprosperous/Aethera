/**
 * AETHERA LLM Route (v25.0) — NVIDIA NIM free endpoints, zero configuration.
 *
 * The platform ships with a built-in NVIDIA API key so end users never need
 * to enter one. Users may still provide their own key:
 *   - header:  x-nvidia-key: nvapi-...
 *   - body:    { apiKey: "nvapi-..." }
 *   - palette: Ctrl+K → Settings (stored in localStorage, sent per request)
 *
 * POST /api/llm  { prompt, systemPrompt?, apiKey?, model? }
 * GET  /api/llm  → provider status
 */

import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const maxDuration = 60;

const NVIDIA_BASE_URL = process.env.NVIDIA_BASE_URL || 'https://integrate.api.nvidia.com/v1';

// Built-in keys: seamless default, no user entry required.
const DEFAULT_KEY = process.env.NVIDIA_API_KEY || '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';
const BACKUP_KEY = process.env.NVIDIA_API_KEY_BACKUP || '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';

const MODEL_CHAIN = [
  'deepseek-ai/deepseek-v4-flash-0731',
  'nvidia/nemotron-3.5-lightning-30b-a3b',
  'moonshotai/kimi-k3',
];

// Function budget on Vercel Hobby is 60s — keep deepseek's share small so
// the fast fallback models always fit within the window.
const DEFAULT_TIMEOUT_MS = 45_000;
const MODEL_TIMEOUT_MS: Record<string, number> = {
  'deepseek-ai/deepseek-v4-flash-0731': 30_000,
};

function maskKey(key: string): string {
  if (!key) return '(none)';
  if (key.length <= 12) return key.slice(0, 4) + '****';
  return `${key.slice(0, 9)}****${key.slice(-4)}`;
}

async function callNvidia(
  model: string,
  messages: Array<{ role: string; content: string }>,
  key: string,
  timeoutMs: number,
): Promise<{ ok: boolean; text?: string; reasoning?: string; status?: number; error?: string }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const resp = await fetch(`${NVIDIA_BASE_URL}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        Authorization: `Bearer ${key}`,
      },
      body: JSON.stringify({
        model,
        messages,
        temperature: 0.6,
        top_p: 0.95,
        max_tokens: 4096,
        stream: false,
      }),
      signal: controller.signal,
    });
    if (resp.status === 401 || resp.status === 403 || resp.status === 429) {
      return { ok: false, status: resp.status, error: `HTTP ${resp.status} (key rejected)` };
    }
    if (!resp.ok) {
      return { ok: false, status: resp.status, error: `HTTP ${resp.status}` };
    }
    const data = await resp.json();
    const msg = data?.choices?.[0]?.message ?? {};
    let text: string = msg.content || '';
    const reasoning: string | undefined = msg.reasoning_content || msg.reasoning || undefined;
    if (!text && reasoning) text = reasoning;
    return { ok: true, text, reasoning };
  } catch (e: any) {
    const aborted = e?.name === 'AbortError';
    return { ok: false, error: aborted ? `timeout after ${timeoutMs / 1000}s` : String(e?.message || e) };
  } finally {
    clearTimeout(timer);
  }
}

export async function POST(req: NextRequest) {
  try {
    const { prompt, systemPrompt, apiKey, model } = await req.json();
    if (!prompt) {
      return NextResponse.json({ error: 'prompt is required' }, { status: 400 });
    }

    const headerKey = req.headers.get('x-nvidia-key');
    const userKey = (apiKey || headerKey || '').trim();

    const messages: Array<{ role: string; content: string }> = [];
    messages.push({
      role: 'system',
      content:
        systemPrompt ||
        'You are AETHERA, the assistant of a sovereign geometric analysis platform. Answer clearly and concisely.',
    });
    messages.push({ role: 'user', content: prompt });

    // Key order: user key (if any) → built-in default → built-in backup.
    const keys = Array.from(new Set([userKey, DEFAULT_KEY, BACKUP_KEY].filter(Boolean))) as string[];
    const models = model ? [model] : MODEL_CHAIN;

    let lastError = 'no models attempted';
    for (const m of models) {
      const timeoutMs = MODEL_TIMEOUT_MS[m] ?? DEFAULT_TIMEOUT_MS;
      for (const key of keys) {
        const res = await callNvidia(m, messages, key, timeoutMs);
        if (res.ok) {
          return NextResponse.json({
            text: res.text,
            reasoning: res.reasoning,
            provider: 'NVIDIA NIM (free)',
            model: m,
            success: true,
          });
        }
        lastError = res.error || 'unknown error';
        // Key rejected → try next key immediately.
        if (res.status === 401 || res.status === 403 || res.status === 429) continue;
        break; // model-level failure → next model
      }
    }

    return NextResponse.json(
      {
        text: `All NVIDIA NIM models unreachable (${lastError}).`,
        provider: 'none',
        success: false,
        error: lastError,
      },
      { status: 502 },
    );
  } catch (error: any) {
    return NextResponse.json(
      {
        text: `LLM error: ${error?.message || error}`,
        provider: 'none',
        success: false,
        error: error?.message,
      },
      { status: 500 },
    );
  }
}

export async function GET() {
  return NextResponse.json({
    primary: 'NVIDIA NIM (free) — no API key required',
    models: MODEL_CHAIN,
    active_key_masked: maskKey(DEFAULT_KEY),
    note: 'A built-in key ships with the platform. Set your own key via the palette (Ctrl+K → Settings) or the x-nvidia-key header.',
  });
}
