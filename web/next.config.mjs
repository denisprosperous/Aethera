/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Production: unmatched /api/* paths are rewritten to the FastAPI
  // serverless function at web/api/index.py (afterFiles => Next.js
  // filesystem routes such as src/app/api/llm/route.ts win first).
  // Development: proxy to a local uvicorn on :8765.
  async rewrites() {
    if (process.env.NODE_ENV === 'production') {
      return {
        beforeFiles: [],
        afterFiles: [
          { source: '/api/:path*', destination: '/api/index' },
        ],
        fallback: [],
      };
    }
    return {
      beforeFiles: [],
      afterFiles: [
        { source: '/api/:path*', destination: 'http://localhost:8765/api/:path*' },
      ],
      fallback: [],
    };
  },
};
export default nextConfig;
