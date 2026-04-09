/** @type {import('next').NextConfig} */
const backendOrigin =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  'http://127.0.0.1:8500';

const nextConfig = {
  async rewrites() {
    return [
      { source: '/api/:path*', destination: `${backendOrigin}/api/:path*` },
      { source: '/report/:path*', destination: `${backendOrigin}/report/:path*` },
    ];
  },
};

module.exports = nextConfig;
