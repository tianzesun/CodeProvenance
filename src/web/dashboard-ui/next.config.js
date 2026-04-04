/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      { source: '/api/:path*', destination: 'http://localhost:8500/api/:path*' },
      { source: '/report/:path*', destination: 'http://localhost:8500/report/:path*' },
    ];
  },
};

module.exports = nextConfig;
