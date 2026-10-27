import { NextResponse } from 'next/server';
import { verifySession, SESSION_COOKIE } from '@/lib/auth';

const PRIVADAS = ['/dashboard', '/editor', '/historial', '/calidad'];

export async function middleware(request) {
    const { pathname } = request.nextUrl;
    const session = await verifySession(request.cookies.get(SESSION_COOKIE)?.value);

    // Sin sesión no se puede entrar a las páginas privadas
    if (PRIVADAS.some((ruta) => pathname.startsWith(ruta)) && !session) {
        const url = new URL('/login', request.url);
        url.searchParams.set('volver', pathname);
        return NextResponse.redirect(url);
    }
    // Si ya inició sesión, no vuelve a ver el login
    if (pathname === '/login' && session) {
        return NextResponse.redirect(new URL('/dashboard', request.url));
    }
    return NextResponse.next();
}

export const config = {
    matcher: ['/dashboard/:path*', '/editor/:path*', '/historial/:path*', '/calidad/:path*', '/login'],
};
