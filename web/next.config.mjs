/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Proxy /api/* to the FastAPI backend.
  // In development: localhost:8000
  // In production: set NEXT_PUBLIC_API_URL to the deployed backend URL.
  async rewrites() {
    const api_url = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    // If NEXT_PUBLIC_API_URL is set, we use client-side fetch directly.
    // Only proxy in development.
    if (process.env.NODE_ENV === 'production' && process.env.NEXT_PUBLIC_API_URL) {
      return [];
    }
    return [
      {
        source: '/api/:path*',
        destination: `${api_url}/api/:path*`,
      },
    ];
  },
};
export default nextConfig;
