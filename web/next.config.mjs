/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // In production: API is served by Vercel serverless functions (api/index.py)
  // In development: proxy to localhost:8000
  async rewrites() {
    if (process.env.NODE_ENV === 'production') {
      return []; // API served by Vercel directly
    }
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
    ];
  },
};
export default nextConfig;
