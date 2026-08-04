/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Proxy /api/* to the FastAPI backend during development.
  // In production, set NEXT_PUBLIC_API_URL to the deployed API URL.
  async rewrites() {
    const api_url = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${api_url}/api/:path*`,
      },
    ];
  },
};
export default nextConfig;
