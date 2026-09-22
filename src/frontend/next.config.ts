import type { NextConfig } from 'next';

const backendOrigin =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  process.env.BACKEND_URL;

if (!backendOrigin) {
  throw new Error(
    'Missing backend URL. Start the whole stack with ./scripts/start.sh (it exports ' +
      'API_URL/NEXT_PUBLIC_API_URL), or run the dashboard standalone with ' +
      '`API_URL=http://127.0.0.1:8000 npm run dev`. Do not add an .env.local at the ' +
      'repo root: the backend only reads src/backend/.env.local, and Next.js only ' +
      'reads env files inside src/frontend/.'
  );
}

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: '/api/:path*', destination: `${backendOrigin}/api/:path*` },
      { source: '/report/:path*', destination: `${backendOrigin}/report/:path*` },
      { source: '/dossier/:path*/download-pdf', destination: `${backendOrigin}/dossier/:path*/download-pdf` },
    ];
  },
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
          {
            key: 'Permissions-Policy',
            value: 'camera=(), microphone=(), geolocation=()',
          },
        ],
      },
    ];
  },
};

export default nextConfig;
