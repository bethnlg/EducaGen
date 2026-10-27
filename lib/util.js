export const TIPOS = {
    silabo: { nombre: 'Sílabo', plural: 'Sílabos', corto: 'Sílabo' },
    rubrica: { nombre: 'Rúbrica', plural: 'Rúbricas', corto: 'Rúbrica' },
    examen: { nombre: 'Examen', plural: 'Exámenes', corto: 'Examen' },
    caso: { nombre: 'Caso de estudio', plural: 'Casos', corto: 'Caso' },
};

export const ESTADOS = {
    aprobado: 'Aprobado',
    borrador: 'Borrador',
    pendiente: 'Pendiente de IA',
    generando: 'Generando',
};

export function iniciales(nombre = '') {
    return (
        nombre
            .split(/\s+/)
            .filter(Boolean)
            .slice(0, 2)
            .map((p) => p[0].toUpperCase())
            .join('') || 'D'
    );
}

const DIA = 24 * 60 * 60 * 1000;

function inicioDelDia(fecha) {
    const d = new Date(fecha);
    d.setHours(0, 0, 0, 0);
    return d.getTime();
}

/** "Hoy", "Ayer", "Hace 3 días"... */
export function fechaRelativa(iso) {
    if (!iso) return '';
    const dias = Math.round((inicioDelDia(Date.now()) - inicioDelDia(iso)) / DIA);
    if (dias <= 0) return 'Hoy';
    if (dias === 1) return 'Ayer';
    if (dias < 7) return `Hace ${dias} días`;
    if (dias < 14) return 'Hace 1 semana';
    if (dias < 31) return `Hace ${Math.floor(dias / 7)} semanas`;
    return new Date(iso).toLocaleDateString('es-PE', { day: '2-digit', month: 'short', year: 'numeric' });
}

/** "Hoy, 09:40", "Ayer, 18:12", "Hace 3 días" */
export function fechaConHora(iso) {
    if (!iso) return '';
    const rel = fechaRelativa(iso);
    const hora = new Date(iso).toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit', hour12: false });
    return rel === 'Hoy' || rel === 'Ayer' ? `${rel}, ${hora}` : rel;
}

export function fechaCompleta(iso) {
    if (!iso) return '';
    return new Date(iso).toLocaleString('es-PE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false });
}

/** "hace unos segundos", "hace 1 min", "hace 12 min" */
export function haceCuanto(ms) {
    if (!ms) return '';
    const seg = Math.max(0, Math.round((Date.now() - ms) / 1000));
    if (seg < 45) return 'hace unos segundos';
    const min = Math.round(seg / 60);
    if (min < 60) return `hace ${min} min`;
    const h = Math.round(min / 60);
    return `hace ${h} h`;
}

// ---------------------------------------------------------------------------
// Saneamiento de HTML pegado en el editor (HU0015-2)
// ---------------------------------------------------------------------------
const PERMITIDAS = new Set(['P', 'BR', 'STRONG', 'EM', 'U', 'UL', 'OL', 'LI', 'TABLE', 'THEAD', 'TBODY', 'TR', 'TH', 'TD', 'H4']);
const EQUIVALENTES = { B: 'STRONG', I: 'EM', H1: 'H4', H2: 'H4', H3: 'H4', H5: 'H4', H6: 'H4', DIV: 'P', SECTION: 'P', ARTICLE: 'P', BLOCKQUOTE: 'P' };
const DESCARTAR = new Set(['SCRIPT', 'STYLE', 'META', 'LINK', 'TITLE', 'IFRAME', 'OBJECT', 'SVG', 'IMG', 'VIDEO', 'NOSCRIPT']);

export function sanearHtml(html) {
    const doc = new DOMParser().parseFromString(`<div>${html}</div>`, 'text/html');
    const salida = document.createElement('div');

    function copiar(origen, destino) {
        origen.childNodes.forEach((nodo) => {
            if (nodo.nodeType === Node.TEXT_NODE) {
                destino.appendChild(document.createTextNode(nodo.textContent));
                return;
            }
            if (nodo.nodeType !== Node.ELEMENT_NODE) return;
            const tag = EQUIVALENTES[nodo.tagName] || nodo.tagName;
            if (DESCARTAR.has(nodo.tagName)) return;
            if (PERMITIDAS.has(tag)) {
                const nuevo = document.createElement(tag);
                copiar(nodo, nuevo);
                destino.appendChild(nuevo);
            } else {
                copiar(nodo, destino); // se conserva el texto, se quita la etiqueta
            }
        });
    }
    copiar(doc.body.firstChild, salida);
    return salida.innerHTML;
}

export function escaparHtml(texto) {
    return String(texto ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}
