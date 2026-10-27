/** @type {import('next').NextConfig} */
const API_URL = process.env.API_URL || 'http://localhost:8000';

const nextConfig = {
    // Sin compresión para que las respuestas en streaming (SSE) lleguen al instante
    compress: false,
    async rewrites() {
        // El navegador solo habla con Next.js; las rutas /api/* se reenvían a la API REST (FastAPI)
        return [{ source: '/api/:path*', destination: `${API_URL}/api/:path*` }];
    },
};

export default nextConfig;
