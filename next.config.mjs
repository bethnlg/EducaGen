/** @type {import('next').NextConfig} */
const nextConfig = {
    // Sin compresión para que las respuestas en streaming (SSE) lleguen al instante.
    // El reenvío /api/* hacia FastAPI lo gestiona app/api/[...path]/route.js sin buffering.
    compress: false,
};

export default nextConfig;
