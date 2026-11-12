// Cliente de la API REST (I-01) y lector de Server-Sent Events (I-02).
// Todas las rutas /api/* se reenvían a FastAPI desde next.config.mjs.

const BASE = process.env.NEXT_PUBLIC_API_URL || '';

export class ApiError extends Error {
    constructor(status, detalle) {
        const mensaje =
            (detalle && typeof detalle === 'object' ? detalle.mensaje : detalle) ||
            (status === 0 ? 'No hay conexión con el servidor. Revisa tu internet.' : 'Ocurrió un error. Inténtalo de nuevo.');
        super(mensaje);
        this.status = status;
        this.detalle = detalle && typeof detalle === 'object' ? detalle : { mensaje };
    }
}

function irAlLogin() {
    if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
        window.location.href = `/login?volver=${encodeURIComponent(window.location.pathname)}`;
    }
}

async function leerError(res) {
    let datos = null;
    try {
        datos = await res.json();
    } catch {
        /* respuesta sin JSON */
    }
    return new ApiError(res.status, datos?.detail ?? datos?.error ?? null);
}

export async function api(ruta, { method = 'GET', body, signal } = {}) {
    let res;
    try {
        res = await fetch(BASE + ruta, {
            method,
            credentials: 'include',
            headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
            body: body !== undefined ? JSON.stringify(body) : undefined,
            signal,
        });
    } catch (err) {
        if (err.name === 'AbortError') throw err;
        throw new ApiError(0, null);
    }

    if (res.status === 401 && !ruta.startsWith('/api/auth/')) {
        irAlLogin();
    }
    if (!res.ok) throw await leerError(res);
    if (res.status === 204) return null;
    return res.json();
}

/** Carga un archivo de referencia para incorporarlo a un prompt. */
export async function subirArchivo(archivo, signal) {
    let res;
    const datos = new FormData();
    datos.append('archivo', archivo);
    try {
        res = await fetch(BASE + '/api/recursos/archivos', {
            method: 'POST',
            credentials: 'include',
            body: datos,
            signal,
        });
    } catch (err) {
        if (err.name === 'AbortError') throw err;
        throw new ApiError(0, null);
    }
    if (res.status === 401) irAlLogin();
    if (!res.ok) throw await leerError(res);
    return res.json();
}

/**
 * Envía un POST y lee la respuesta como flujo SSE.
 * onEvento recibe cada objeto JSON enviado por el servidor.
 */
export async function streamSSE(ruta, body, { onEvento, signal } = {}) {
    let res;
    try {
        res = await fetch(BASE + ruta, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
            body: JSON.stringify(body ?? {}),
            signal,
        });
    } catch (err) {
        if (err.name === 'AbortError') throw err;
        throw new ApiError(0, null);
    }
    if (res.status === 401) irAlLogin();
    if (!res.ok) throw await leerError(res);

    const lector = res.body.getReader();
    const decodificador = new TextDecoder();
    let buffer = '';
    try {
        for (;;) {
            const { value, done } = await lector.read();
            if (done) break;
            buffer += decodificador.decode(value, { stream: true });
            let corte;
            while ((corte = buffer.indexOf('\n\n')) !== -1) {
                const bloque = buffer.slice(0, corte);
                buffer = buffer.slice(corte + 2);
                const datos = bloque
                    .split('\n')
                    .filter((l) => l.startsWith('data:'))
                    .map((l) => l.slice(5).trimStart())
                    .join('\n');
                if (!datos) continue;
                try {
                    onEvento?.(JSON.parse(datos));
                } catch {
                    /* evento incompleto */
                }
            }
        }
    } catch (err) {
        if (err.name === 'AbortError') throw err;
        // HU0013-2: la conexión se cortó a mitad de la respuesta
        throw new ApiError(0, { mensaje: 'Se perdió la conexión mientras llegaba la respuesta.', codigo: 'conexion_cortada' });
    }
}

/** Descarga un archivo generado por la API. */
export async function descargar(ruta) {
    let res;
    try {
        res = await fetch(BASE + ruta, { credentials: 'include' });
    } catch {
        throw new ApiError(0, null);
    }
    if (!res.ok) throw await leerError(res);
    const blob = await res.blob();
    const disposicion = res.headers.get('Content-Disposition') || '';
    const nombre = /filename="([^"]+)"/.exec(disposicion)?.[1] || 'recurso';
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = nombre;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    return nombre;
}
