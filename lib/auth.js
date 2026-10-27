import { jwtVerify } from 'jose';

// La cookie la emite la API (FastAPI). Next.js solo la verifica para proteger las páginas.
export const SESSION_COOKIE = 'session';

function getSecret() {
    const secret = process.env.JWT_SECRET || 'clave-temporal-solo-para-desarrollo-123456';
    return new TextEncoder().encode(secret);
}

export async function verifySession(token) {
    if (!token) return null;
    try {
        const { payload } = await jwtVerify(token, getSecret(), { algorithms: ['HS256'] });
        return payload;
    } catch {
        return null;
    }
}
