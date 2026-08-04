/**
 * AETHERA Keep-Alive Worker
 *
 * Pings the Render backend every 10 minutes to prevent cold starts.
 * Render free tier spins down after 15 minutes of inactivity.
 */

export default {
  async scheduled(event, env, ctx) {
    const url = env.RENDER_APP_URL + '/api/health';
    try {
      const resp = await fetch(url, {
        method: 'GET',
        headers: { 'User-Agent': 'aethera-keepalive/1.0' },
      });
      const data = await resp.json();
      console.log(`[keep-alive] ${new Date().toISOString()} — status: ${resp.status}, solver: ${data.solver || 'unknown'}`);
    } catch (e) {
      console.error(`[keep-alive] ${new Date().toISOString()} — error: ${e.message}`);
    }
  },

  async fetch(request, env) {
    // Manual trigger endpoint for testing.
    const url = env.RENDER_APP_URL + '/api/health';
    try {
      const resp = await fetch(url);
      const data = await resp.json();
      return new Response(JSON.stringify({
        status: 'ok',
        timestamp: new Date().toISOString(),
        backend: data,
      }), {
          headers: { 'Content-Type': 'application/json' },
      });
    } catch (e) {
      return new Response(JSON.stringify({
        status: 'error',
        error: e.message,
        timestamp: new Date().toISOString(),
      }), {
          status: 502,
          headers: { 'Content-Type': 'application/json' },
      });
    }
  },
};
