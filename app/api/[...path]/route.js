// Proxy de mismo origen hacia FastAPI sin buffering para Server-Sent Events (SSE),
// cookies de sesión HttpOnly, carga de archivos multipart y descargas binarias.

export const dynamic = 'force-dynamic';
export const fetchCache = 'force-no-store';
export const runtime = 'nodejs';
export const maxDuration = 300;

const CABECERAS_ENTRADA = ['cookie', 'authorization', 'content-type', 'accept', 'user-agent'];
const CABECERAS_SALIDA = ['content-type', 'content-disposition', 'cache-control', 'x-accel-buffering'];

function urlDestino(request, params) {
    const base = (process.env.API_URL || 'http://localhost:8000').replace(/\/+$/, '');
    const segmentos = (params?.path || []).map((s) => encodeURIComponent(s)).join('/');
    return `${base}/api/${segmentos}${request.nextUrl.search}`;
}

async function reenviar(request, context) {
    const params = await context.params;
    const destino = urlDestino(request, params);

    const cabeceras = new Headers();
    for (const nombre of CABECERAS_ENTRADA) {
        const valor = request.headers.get(nombre);
        if (valor) cabeceras.set(nombre, valor);
    }
    // Evita compresión intermedia para transmitir flujos SSE y archivos binarios intactos
    cabeceras.set('accept-encoding', 'identity');

    const ip = request.headers.get('x-forwarded-for');
    if (ip) cabeceras.set('x-forwarded-for', ip);
    cabeceras.set('x-forwarded-proto', request.nextUrl.protocol.replace(':', ''));

    let body;
    if (request.method !== 'GET' && request.method !== 'HEAD') {
        const buffer = await request.arrayBuffer();
        if (buffer.byteLength > 0) body = buffer;
    }

    let upstream;
    try {
        upstream = await fetch(destino, {
            method: request.method,
            headers: cabeceras,
            body,
            redirect: 'manual',
            cache: 'no-store',
        });
    } catch {
        return Response.json(
            { detail: { mensaje: 'No se pudo conectar con el servidor de EducaGen. Inténtalo de nuevo en unos segundos.' } },
            { status: 502 },
        );
    }

    const respuestaCabeceras = new Headers();
    for (const nombre of CABECERAS_SALIDA) {
        const valor = upstream.headers.get(nombre);
        if (valor) respuestaCabeceras.set(nombre, valor);
    }

    const cookies =
        typeof upstream.headers.getSetCookie === 'function'
            ? upstream.headers.getSetCookie()
            : upstream.headers.get('set-cookie')
              ? [upstream.headers.get('set-cookie')]
              : [];
    for (const cookie of cookies) {
        if (cookie) respuestaCabeceras.append('set-cookie', cookie);
    }

    if ((upstream.headers.get('content-type') || '').includes('text/event-stream')) {
        respuestaCabeceras.set('content-type', 'text/event-stream; charset=utf-8');
        respuestaCabeceras.set('cache-control', 'no-cache, no-transform');
        respuestaCabeceras.set('connection', 'keep-alive');
        respuestaCabeceras.set('x-accel-buffering', 'no');
    }

    const sinCuerpo = upstream.status === 204 || upstream.status === 205 || upstream.status === 304;
    return new Response(sinCuerpo ? null : upstream.body, {
        status: upstream.status,
        headers: respuestaCabeceras,
    });
}

export const GET = reenviar;
export const POST = reenviar;
export const PUT = reenviar;
export const PATCH = reenviar;
export const DELETE = reenviar;
