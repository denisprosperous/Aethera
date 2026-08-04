/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // For Cloudflare R2 deployment: set assetPrefix to your R2 public URL.
  // assetPrefix: process.env.NEXT_PUBLIC_R2_URL || undefined,
};
export default nextConfig;
