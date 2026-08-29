// AETHERA v26.0 — Railway-aware dual-mode API resolver with runtime failover.
//
// MODE A (Railway connected):  NEXT_PUBLIC_RAILWAY_URL is set to the Railway
//   public URL (e.g. https://aethera-backend.up.railway.app). All fetches go
//   to that absolute URL: `${RAILWAY_URL}/api/...`
//
// MODE B (Vercel serverless fallback): no env var set — fetches use the
//   same-origin relative path `/api/...`, served by the bundled FastAPI
//   serverless function (web/api/index.py). Works with zero configuration.
//
// SEAMLESS FAILOVER: when NEXT_PUBLIC_RAILWAY_URL is configured, the first
// request probes Railway's /api/health (2.5 s timeout). If Railway is
// unreachable — or dies mid-session — apiFetch() transparently retries the
// same request against the same-origin serverless function. The platform
// therefore works identically whether Railway is up, down, or unconfigured.

const RAILWAY_URL = (process.env.NEXT_PUBLIC_RAILWAY_URL || '').replace(/\/+$/, '');

export const RAILWAY_ENABLED = RAILWAY_URL.length > 0;

export const API_MODE = RAILWAY_ENABLED ? 'railway' : 'vercel-serverless';

let cachedRailwayUp: boolean | null = null;

/**
 * Resolve an API path (starting with "/") to a full URL depending on the
 * deployment mode. Example: apiUrl('/api/health'). Static resolution only —
 * no failover. Prefer apiFetch() for data fetching.
 */
export function apiUrl(path: string): string {
  const clean = path.startsWith('/') ? path : `/${path}`;
  return RAILWAY_ENABLED ? `${RAILWAY_URL}${clean}` : clean;
}

/**
 * Probe Railway once per session (cached). Returns true if Railway answered
 * /api/health with a 2xx within the timeout window.
 */
export async function isRailwayUp(timeoutMs = 2500): Promise<boolean> {
  if (!RAILWAY_ENABLED) return false;
  if (cachedRailwayUp !== null) return cachedRailwayUp;
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    const res = await fetch(`${RAILWAY_URL}/api/health`, {
      signal: ctrl.signal,
      cache: 'no-store',
    });
    clearTimeout(timer);
    cachedRailwayUp = res.ok;
  } catch {
    cachedRailwayUp = false;
  }
  return cachedRailwayUp;
}

/**
 * Fetch an API path with automatic Railway -> same-origin failover.
 * Signature matches the global fetch.
 */
export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const clean = path.startsWith('/') ? path : `/${path}`;

  if (!RAILWAY_ENABLED) return fetch(clean, init);

  const railwayUp = await isRailwayUp();
  const target = railwayUp ? `${RAILWAY_URL}${clean}` : clean;
  try {
    return await fetch(target, init);
  } catch (err) {
    // Network failure mid-session: degrade to same-origin and retry once.
    if (railwayUp) {
      cachedRailwayUp = false;
      return fetch(clean, init);
    }
    throw err;
  }
}
