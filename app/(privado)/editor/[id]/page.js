'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { memo, useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Modal, useApp } from '@/components/Shell';
import Icono from '@/components/Icono';
import { ApiError, api, descargar, streamSSE, subirArchivo } from '@/lib/api';
import { TIPOS, escaparHtml, fechaCompleta, haceCuanto, sanearHtml } from '@/lib/util';
import { UNIVERSIDADES_PRIVADAS_LIMA, urlLogoRespaldo, urlLogoUniversidad } from '@/lib/universidades';

const FORMATOS = [
    { clave: 'pdf', nombre: 'PDF', detalle: 'Para imprimir o subir al aula virtual' },
    { clave: 'docx', nombre: 'Word', detalle: 'Documento editable (.docx)' },
    { clave: 'xlsx', nombre: 'Excel', detalle: 'Hoja de cálculo (.xlsx)' },
    { clave: 'html', nombre: 'HTML', detalle: 'Página web' },
    { clave: 'txt', nombre: 'Texto', detalle: 'Texto plano (.txt)' },
];

const ATAJOS_BASE = ['Hazlo más breve', 'Agrega bibliografía APA', 'Traduce a inglés'];
const ATAJOS_TIPO = {
    examen: ['Agrega 10 preguntas de desarrollo'],
    caso: ['Cambia los nombres de la empresa y los personajes'],
};
const BLOQUES = 'P, LI, TD, TH, H4';
const ESPERA_GUARDADO = 1500;

// ---------------------------------------------------------------------------
// Sección editable: el HTML se escribe en el DOM solo al montar; los cambios
// externos (asistente, regeneración) remontan la sección con una nueva clave.
// ---------------------------------------------------------------------------
const CuerpoEditable = memo(function CuerpoEditable({ id, html, editable, onCambio, registrar }) {
    const ref = useRef(null);
    useLayoutEffect(() => {
        if (ref.current) ref.current.innerHTML = html || '<p></p>';
        registrar(id, ref.current);
        return () => registrar(id, null);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    function pegar(e) {
        // HU0015-2: se quita el formato que el editor no admite
        e.preventDefault();
        const html = e.clipboardData.getData('text/html');
        const texto = e.clipboardData.getData('text/plain');
        const limpio = html ? sanearHtml(html) : escaparHtml(texto).split(/\n{2,}/).map((p) => `<p>${p.replace(/\n/g, '<br>')}</p>`).join('');
        document.execCommand('insertHTML', false, limpio);
        onCambio(id, ref.current.innerHTML);
    }

    return (
        <div
            ref={ref}
            className="seccion-cuerpo"
            contentEditable={editable}
            suppressContentEditableWarning
            data-seccion={id}
            onInput={() => onCambio(id, ref.current.innerHTML)}
            onPaste={pegar}
            spellCheck
        />
    );
});

export default function EditorPage() {
    const { id } = useParams();
    const { avisar } = useApp();

    const [recurso, setRecurso] = useState(null);
    const [titulo, setTitulo] = useState('');
    const [guardandoTitulo, setGuardandoTitulo] = useState(false);
    const [versiones, setVersiones] = useState(null);
    const [mostrandoVersiones, setMostrandoVersiones] = useState(false);
    const [restaurandoVersion, setRestaurandoVersion] = useState(null);
    const [error, setError] = useState(null);
    const [secciones, setSecciones] = useState([]);
    const [revision, setRevision] = useState({});
    const [conformidad, setConformidad] = useState(null);
    const [guardado, setGuardado] = useState({ estado: 'guardado', fecha: null });
    const [, setReloj] = useState(0);
    const [avisosIniciales, setAvisosIniciales] = useState([]);
    const [mensajes, setMensajes] = useState([]);
    const [entrada, setEntrada] = useState('');
    const [adjuntos, setAdjuntos] = useState([]);
    const [subiendoAdjunto, setSubiendoAdjunto] = useState(false);
    const [respondiendo, setRespondiendo] = useState(false);
    const [menuExportar, setMenuExportar] = useState(false);
    const [opcionesExportar, setOpcionesExportar] = useState({ membrete: true, clave: true, universidad: 'upc' });
    const [exportando, setExportando] = useState(null);
    const [errorExportar, setErrorExportar] = useState(null);
    const [bloque, setBloque] = useState(null);
    const [regenerando, setRegenerando] = useState(null);
    const [aprobacion, setAprobacion] = useState(null);
    const [aprobando, setAprobando] = useState(false);
    const [clavesVisibles, setClavesVisibles] = useState({});
    const [reintentandoGeneracion, setReintentandoGeneracion] = useState(null);

    const cuerpos = useRef({});
    const seccionesRef = useRef([]);
    const sucio = useRef(false);
    const temporizador = useRef(null);
    const segundosPendientes = useRef(0);
    const ultimaActividad = useRef(Date.now());
    const documentoRef = useRef(null);
    const bloqueEl = useRef(null);
    const regenConteo = useRef({ clave: null, n: 0 });
    const chatFin = useRef(null);
    const respaldoClave = `educagen:borrador:${id}`;

    const registrar = useCallback((idSeccion, el) => {
        if (el) cuerpos.current[idSeccion] = el;
        else delete cuerpos.current[idSeccion];
    }, []);

    // ---------------------------------------------------------------- carga
    const cargar = useCallback(async () => {
        try {
            const d = await api(`/api/recursos/${id}`);
            let secs = d.contenido?.secciones || [];
            let fechaServidor = d.fecha_guardado ? new Date(d.fecha_guardado).getTime() : 0;
            // HU0016-2: si hay una copia local más reciente (sin conexión), se recupera
            try {
                const local = JSON.parse(localStorage.getItem(respaldoClave) || 'null');
                if (local && local.fecha > fechaServidor && local.secciones?.length) {
                    secs = local.secciones;
                    sucio.current = true;
                }
            } catch {
                /* copia local dañada */
            }
            setRecurso(d);
            setTitulo(d.titulo || '');
            setAdjuntos((d.adjuntos || []).map((a) => ({ ...a, texto: '' })));
            setSecciones(secs);
            seccionesRef.current = secs;
            setConformidad(d.conformidad_detalle);
            setMensajes(d.mensajes || []);
            setGuardado({ estado: sucio.current ? 'pendiente' : 'guardado', fecha: fechaServidor || null });
            const avisos = sessionStorage.getItem(`educagen:avisos:${id}`);
            if (avisos) {
                setAvisosIniciales(JSON.parse(avisos));
                sessionStorage.removeItem(`educagen:avisos:${id}`);
            }
        } catch (err) {
            setError(err instanceof ApiError ? { status: err.status, mensaje: err.message } : { mensaje: 'No se pudo abrir el recurso.' });
        }
    }, [id, respaldoClave]);

    useEffect(() => {
        cargar();
    }, [cargar]);

    // ------------------------------------------------------- guardado automático
    const guardar = useCallback(async () => {
        clearTimeout(temporizador.current);
        if (!sucio.current && segundosPendientes.current === 0) return;
        const conContenido = sucio.current;
        const segundos = segundosPendientes.current;
        const contenido = { secciones: seccionesRef.current };
        sucio.current = false;
        segundosPendientes.current = 0;
        if (conContenido) setGuardado((g) => ({ ...g, estado: 'guardando' }));
        try {
            const r = await api(`/api/recursos/${id}/borrador`, {
                method: 'PUT',
                body: { ...(conContenido && { contenido }), segundos_activos: Math.min(segundos, 3600) },
            });
            localStorage.removeItem(respaldoClave);
            setConformidad(r.conformidad);
            setRecurso((rec) => (rec ? { ...rec, estado: r.estado } : rec));
            setGuardado({ estado: 'guardado', fecha: new Date(r.fecha_guardado).getTime() });
        } catch (err) {
            if (conContenido) {
                sucio.current = true;
                // HU0016-2: copia temporal en el navegador hasta que vuelva la conexión
                localStorage.setItem(respaldoClave, JSON.stringify({ secciones: contenido.secciones, fecha: Date.now() }));
                setGuardado((g) => ({ ...g, estado: err.status === 0 ? 'sin_conexion' : 'error' }));
            }
            segundosPendientes.current += segundos;
        }
    }, [id, respaldoClave]);

    const programarGuardado = useCallback(() => {
        sucio.current = true;
        setGuardado((g) => (g.estado === 'sin_conexion' ? g : { ...g, estado: 'pendiente' }));
        clearTimeout(temporizador.current);
        temporizador.current = setTimeout(guardar, ESPERA_GUARDADO);
    }, [guardar]);

    const enviarBaliza = useCallback(() => {
        if (!sucio.current && segundosPendientes.current === 0) return;
        const cuerpo = JSON.stringify({
            ...(sucio.current && { contenido: { secciones: seccionesRef.current } }),
            segundos_activos: Math.min(segundosPendientes.current, 3600),
        });
        if (sucio.current) localStorage.setItem(respaldoClave, JSON.stringify({ secciones: seccionesRef.current, fecha: Date.now() }));
        navigator.sendBeacon?.(`/api/recursos/${id}/borrador`, new Blob([cuerpo], { type: 'application/json' }));
        sucio.current = false;
        segundosPendientes.current = 0;
    }, [id, respaldoClave]);

    useEffect(() => {
        // HU0016-1: al cerrar la pestaña o salir del editor se guarda el borrador
        const alOcultar = () => document.visibilityState === 'hidden' && enviarBaliza();
        const alVolverConexion = () => sucio.current && guardar();
        window.addEventListener('pagehide', enviarBaliza);
        document.addEventListener('visibilitychange', alOcultar);
        window.addEventListener('online', alVolverConexion);
        return () => {
            enviarBaliza();
            window.removeEventListener('pagehide', enviarBaliza);
            document.removeEventListener('visibilitychange', alOcultar);
            window.removeEventListener('online', alVolverConexion);
        };
    }, [enviarBaliza, guardar]);

    // --------------------------------------------- tiempo activo de elaboración
    useEffect(() => {
        const actividad = () => { ultimaActividad.current = Date.now(); };
        const eventos = ['keydown', 'mousedown', 'mousemove', 'wheel', 'touchstart'];
        eventos.forEach((e) => window.addEventListener(e, actividad, { passive: true }));
        const contador = setInterval(() => {
            if (document.visibilityState === 'visible' && Date.now() - ultimaActividad.current < 60000) segundosPendientes.current += 5;
        }, 5000);
        const latido = setInterval(() => { if (!sucio.current && segundosPendientes.current >= 30) guardar(); }, 30000);
        const reloj = setInterval(() => setReloj((n) => n + 1), 30000);
        return () => {
            eventos.forEach((e) => window.removeEventListener(e, actividad));
            clearInterval(contador);
            clearInterval(latido);
            clearInterval(reloj);
        };
    }, [guardar]);

    // ---------------------------------------------------------------- edición
    const alCambiarCuerpo = useCallback((idSeccion, html) => {
        seccionesRef.current = seccionesRef.current.map((s) => (s.id === idSeccion ? { ...s, html } : s));
        programarGuardado();
    }, [programarGuardado]);

    function cambiarTituloSeccion(idSeccion, titulo) {
        seccionesRef.current = seccionesRef.current.map((s) => (s.id === idSeccion ? { ...s, titulo } : s));
        setSecciones(seccionesRef.current);
        programarGuardado();
    }

    function reemplazarSecciones(nuevas) {
        seccionesRef.current = nuevas;
        setSecciones(nuevas);
        setRevision((r) => {
            const siguiente = { ...r };
            nuevas.forEach((s) => { siguiente[s.id] = (siguiente[s.id] || 0) + 1; });
            return siguiente;
        });
    }

    function sincronizarDesdeDom(idSeccion) {
        const el = cuerpos.current[idSeccion];
        if (el) alCambiarCuerpo(idSeccion, el.innerHTML);
    }

    async function guardarTitulo() {
        const nuevo = titulo.trim();
        if (!nuevo || nuevo === recurso.titulo) {
            setTitulo(recurso.titulo);
            return;
        }
        setGuardandoTitulo(true);
        try {
            const r = await api(`/api/recursos/${id}/borrador`, { method: 'PUT', body: { titulo: nuevo } });
            setRecurso((actual) => ({ ...actual, titulo: nuevo }));
            setTitulo(nuevo);
            setGuardado({ estado: 'guardado', fecha: new Date(r.fecha_guardado).getTime() });
            avisar('Título actualizado.', 'exito');
        } catch (err) {
            setTitulo(recurso.titulo);
            avisar(err.message, 'error');
        } finally {
            setGuardandoTitulo(false);
        }
    }

    async function abrirVersiones() {
        try {
            setVersiones((await api(`/api/recursos/${id}/versiones`)).versiones);
            setMostrandoVersiones(true);
        } catch (err) {
            avisar(err.message, 'error');
        }
    }

    async function restaurarVersion(version) {
        setRestaurandoVersion(version.id);
        try {
            const r = await api(`/api/recursos/${id}/versiones/${version.id}/restaurar`, { method: 'POST' });
            reemplazarSecciones(r.contenido.secciones);
            setConformidad(r.conformidad);
            setRecurso((actual) => ({ ...actual, estado: r.estado }));
            setGuardado({ estado: 'guardado', fecha: new Date(r.fecha_guardado).getTime() });
            setMostrandoVersiones(false);
            avisar(`Se restauró la versión ${version.numero}.`, 'exito');
        } catch (err) {
            avisar(err.message, 'error');
        } finally {
            setRestaurandoVersion(null);
        }
    }

    function formato(comando, valor) {
        document.execCommand(comando, false, valor);
        const sel = window.getSelection();
        const el = sel?.anchorNode && (sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentElement)?.closest('[data-seccion]');
        if (el) sincronizarDesdeDom(el.dataset.seccion);
    }

    function insertarTabla() {
        const celdas = (n, tag) => Array.from({ length: n }, () => `<${tag}>&nbsp;</${tag}>`).join('');
        formato('insertHTML', `<table><thead><tr>${celdas(3, 'th')}</tr></thead><tbody><tr>${celdas(3, 'td')}</tr><tr>${celdas(3, 'td')}</tr></tbody></table><p></p>`);
    }

    // Bloque (párrafo) donde está el cursor, para regenerarlo (HU0011)
    useEffect(() => {
        function alSeleccionar() {
            if (regenerando) return;
            const sel = window.getSelection();
            if (!sel?.anchorNode || !documentoRef.current) return;
            const nodo = sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentElement;
            const cuerpo = nodo?.closest?.('[data-seccion]');
            if (!cuerpo || !documentoRef.current.contains(cuerpo)) return;
            let el = nodo.closest(BLOQUES);
            if (!el || !cuerpo.contains(el)) el = cuerpo.firstElementChild ? null : cuerpo;
            if (!el) return;
            bloqueEl.current = el;
            posicionarBloque(el, cuerpo.dataset.seccion);
        }
        document.addEventListener('selectionchange', alSeleccionar);
        return () => document.removeEventListener('selectionchange', alSeleccionar);
    }, [regenerando]);

    function posicionarBloque(el, idSeccion) {
        const base = documentoRef.current.getBoundingClientRect();
        const r = el.getBoundingClientRect();
        setBloque({ seccion: idSeccion, top: r.top - base.top + documentoRef.current.scrollTop, left: r.left - base.left, width: r.width, height: r.height });
    }

    async function regenerarBloque() {
        const el = bloqueEl.current;
        if (!el || !bloque) return;
        const cuerpo = cuerpos.current[bloque.seccion];
        const indice = cuerpo ? Array.from(cuerpo.querySelectorAll(BLOQUES)).indexOf(el) : -1;
        const clave = `${bloque.seccion}:${indice}`;
        regenConteo.current = regenConteo.current.clave === clave ? { clave, n: regenConteo.current.n + 1 } : { clave, n: 1 };
        posicionarBloque(el, bloque.seccion);
        setRegenerando(bloque.seccion);
        await guardar();
        try {
            const r = await api(`/api/recursos/${id}/regenerar`, {
                method: 'POST',
                body: { seccion_id: bloque.seccion, bloque_html: el.outerHTML, intento: regenConteo.current.n },
            });
            let html = r.html;
            // Si el bloque es un elemento de lista o celda, se usa solo el contenido del párrafo
            if (el.tagName !== 'P') html = html.replace(/^<p>|<\/p>$/g, '');
            if (el.tagName === 'P' && /^<p>[\s\S]*<\/p>$/.test(html) && html.indexOf('<p>', 1) === -1) el.innerHTML = html.slice(3, -4);
            else if (el.tagName === 'P') el.outerHTML = html;
            else el.innerHTML = html;
            sincronizarDesdeDom(bloque.seccion);
            avisar(r.intentos_restantes > 0 ? 'Fragmento regenerado. El resto del documento no cambió.' : 'Fragmento regenerado. Llegaste al límite de nuevas redacciones para este fragmento.', 'exito');
        } catch (err) {
            avisar(err.message, err.status === 429 ? 'aviso' : 'error', 6000);
        } finally {
            setRegenerando(null);
            setBloque(null);
        }
    }

    // ---------------------------------------------------------------- asistente
    useEffect(() => {
        chatFin.current?.scrollIntoView({ block: 'end' });
    }, [mensajes]);

    async function enviarAlAsistente(texto, reintento = false) {
        const mensaje = (texto ?? entrada).trim();
        if (!mensaje || respondiendo) return; // HU0012-2
        if (!reintento) setEntrada('');
        await guardar();
        const idLocal = `tmp-${Date.now()}`;
        setMensajes((m) => [
            ...m.filter((x) => !(reintento && x.reintentable)),
            ...(reintento ? [] : [{ id: `${idLocal}-d`, emisor: 'docente', contenido: mensaje }]),
            { id: idLocal, emisor: 'asistente', contenido: '', escribiendo: true },
        ]);
        setRespondiendo(true);
        const actualizar = (cambios) => setMensajes((m) => m.map((x) => (x.id === idLocal ? { ...x, ...cambios(x) } : x)));
        try {
            await streamSSE(`/api/recursos/${id}/asistente`, { mensaje, secciones: seccionesRef.current, adjuntos }, {
                onEvento: (ev) => {
                    if (ev.tipo === 'chunk') actualizar((x) => ({ contenido: x.contenido + ev.texto }));
                    else if (ev.tipo === 'reinicio') actualizar(() => ({ contenido: '' }));
                    else if (ev.tipo === 'fin') actualizar(() => ({ id: ev.id_mensaje, contenido: ev.contenido, propuesta: ev.propuesta, escribiendo: false }));
                    else if (ev.tipo === 'error') actualizar(() => ({ contenido: ev.mensaje, escribiendo: false, error: true, reintentable: true, pedido: mensaje }));
                },
            });
        } catch (err) {
            // HU0013-2: se conserva lo que ya se mostró y se ofrece reintentar
            actualizar((x) => ({ escribiendo: false, error: true, reintentable: true, pedido: mensaje, nota: err.message, contenido: x.contenido }));
        } finally {
            setRespondiendo(false);
        }
    }

    async function seleccionarAdjuntos(e) {
        const archivos = Array.from(e.target.files || []);
        e.target.value = '';
        if (!archivos.length) return;
        if (adjuntos.length + archivos.length > 5) {
            avisar('Puedes adjuntar hasta 5 archivos por consulta.', 'aviso');
            return;
        }

        async function quitarAdjunto(adjunto) {
            try {
                await api(`/api/recursos/${id}/archivos/${adjunto.id}`, { method: 'DELETE' });
                setAdjuntos((lista) => lista.filter((a) => a.id !== adjunto.id));
                avisar(`Se quitó «${adjunto.nombre}».`, 'exito');
            } catch (err) {
                avisar(err.message, 'error');
            }
        }
        setSubiendoAdjunto(true);
        try {
            const cargados = [];
            for (const archivo of archivos) cargados.push(await subirArchivo(archivo));
            setAdjuntos((lista) => [...lista, ...cargados]);
        } catch (err) {
            avisar(err.message, 'error');
        } finally {
            setSubiendoAdjunto(false);
        }
    }

    async function aplicarCambio(m) {
        if (m.propuesta?.tipo === 'bibliografia' && !m.confirmado) {
            avisar('Marca la casilla para confirmar que revisaste las referencias.', 'aviso');
            return;
        }
        await guardar();
        try {
            const r = await api(`/api/recursos/${id}/asistente/${m.id}/aplicar`, { method: 'POST', body: { confirmado: !!m.confirmado } });
            reemplazarSecciones(r.contenido.secciones);
            setConformidad(r.conformidad);
            setRecurso((rec) => ({ ...rec, estado: r.estado }));
            setGuardado({ estado: 'guardado', fecha: new Date(r.fecha_guardado).getTime() });
            setMensajes((lista) => lista.map((x) => (x.id === m.id ? { ...x, aplicado: true } : x)));
        } catch (err) {
            avisar(err.message, 'error');
        }
    }

    // ---------------------------------------------------------------- exportar
    async function exportar(formato) {
        setExportando(formato);
        setErrorExportar(null);
        await guardar();
        try {
            const q = new URLSearchParams({
                formato,
                membrete: opcionesExportar.membrete,
                clave: opcionesExportar.clave,
                universidad: opcionesExportar.universidad,
            });
            const nombre = await descargar(`/api/recursos/${id}/exportar?${q}`);
            avisar(`Descargado: ${nombre}`, 'exito');
            setMenuExportar(false);
        } catch (err) {
            setErrorExportar({ mensaje: err.message, alternativas: err.detalle?.alternativas || [] });
        } finally {
            setExportando(null);
        }
    }

    // ---------------------------------------------------------------- aprobar
    async function abrirAprobacion() {
        await guardar();
        try {
            setAprobacion(await api(`/api/recursos/${id}/aprobacion`));
        } catch (err) {
            avisar(err.message, 'error');
        }
    }

    async function confirmarAprobacion() {
        setAprobando(true);
        try {
            const r = await api(`/api/recursos/${id}/aprobar`, { method: 'POST' });
            setRecurso((rec) => ({ ...rec, estado: 'aprobado', fecha_aprobacion: r.fecha_aprobacion, version_actual: r.version }));
            setAprobacion(null);
            avisar(`Recurso aprobado como versión ${r.version}.`, 'exito');
        } catch (err) {
            avisar(err.message, 'error');
        } finally {
            setAprobando(false);
        }
    }

    // ------------------------------------------------- reintentar generación
    async function reintentarGeneracion() {
        setReintentandoGeneracion({ mensaje: 'Reintentando la generación…' });
        try {
            let fallo = null;
            await streamSSE(`/api/recursos/${id}/generar`, {}, {
                onEvento: (ev) => {
                    if (ev.tipo === 'estado' || ev.tipo === 'reinicio') setReintentandoGeneracion({ mensaje: ev.mensaje });
                    if (ev.tipo === 'chunk') setReintentandoGeneracion({ mensaje: 'Redactando el contenido…' });
                    if (ev.tipo === 'error') fallo = ev.mensaje;
                },
            });
            if (fallo) throw new Error(fallo);
            setReintentandoGeneracion(null);
            await cargar();
            setRevision({});
        } catch (err) {
            setReintentandoGeneracion(null);
            avisar(err.message, 'error', 7000);
        }
    }

    // ---------------------------------------------------------------- render
    if (error) {
        return (
            <div className="pagina">
                <div className="vacio">
                    <h2>{error.status === 403 ? 'Acceso denegado' : 'No se pudo abrir el recurso'}</h2>
                    <p>{error.mensaje}</p>
                    <Link href="/historial" className="boton boton-amarillo">Ir a mi Historial</Link>
                </div>
            </div>
        );
    }
    if (!recurso) return <div className="cargando-pagina">Abriendo el editor…</div>;

    const tipo = recurso.tipo;
    const aprobado = recurso.estado === 'aprobado';
    const pendiente = recurso.estado === 'pendiente' || recurso.estado === 'generando' || secciones.length === 0;
    const atajos = [...ATAJOS_BASE, ...(ATAJOS_TIPO[tipo] || [])];
    const textoGuardado = {
        guardado: guardado.fecha ? `Guardado automáticamente ${haceCuanto(guardado.fecha)}` : 'Sin cambios',
        pendiente: 'Cambios sin guardar…',
        guardando: 'Guardando…',
        sin_conexion: 'Sin conexión: copia guardada en este navegador',
        error: 'No se pudo guardar. Reintentaremos en breve.',
    }[guardado.estado];

    return (
        <div className="editor">
            <header className="editor-cabecera">
                <div className="editor-titulo">
                    <div className="titulo-editable">
                        <input value={titulo} maxLength={200} onChange={(e) => setTitulo(e.target.value)}
                            onBlur={guardarTitulo} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); e.currentTarget.blur(); } }}
                            aria-label="Título del recurso" disabled={guardandoTitulo} />
                        <small>Haz clic para editar</small>
                    </div>
                    {conformidad && !pendiente && (
                        conformidad.conforme
                            ? <span className="insignia insignia-ok"><Icono nombre="checkCirculo" tam={15} /> 100 % conforme</span>
                            : <span className="insignia insignia-alerta"><Icono nombre="alerta" tam={15} /> {conformidad.presentes} de {conformidad.total} secciones</span>
                    )}
                </div>
                <div className="editor-acciones">
                    <span className={`estado-guardado estado-${guardado.estado}`}>
                        {aprobado ? `Aprobado el ${fechaCompleta(recurso.fecha_aprobacion)}` : textoGuardado}
                    </span>
                    <button type="button" className="boton boton-secundario" onClick={abrirVersiones} disabled={pendiente}>
                        Versiones
                    </button>
                    {!pendiente && (aprobado ? (
                        <span className="boton boton-aprobado" aria-live="polite"><Icono nombre="check" tam={16} /> Aprobado</span>
                    ) : (
                        <button type="button" className="boton boton-verde" onClick={abrirAprobacion}>
                            <Icono nombre="check" tam={16} /> Aprobar recurso
                        </button>
                    ))}
                    <div className="desplegable">
                        <button type="button" className="boton boton-azul" onClick={() => setMenuExportar((v) => !v)} aria-expanded={menuExportar} disabled={pendiente}>
                            Exportar <Icono nombre="flecha" tam={16} />
                        </button>
                        {menuExportar && (
                            <div className="menu-exportar" role="menu">
                                {conformidad && !conformidad.conforme && (
                                    <p className="menu-nota">Faltan secciones obligatorias: {conformidad.faltantes.join(', ')}. Corrígelas antes de entregar el documento.</p>
                                )}
                                <label className="campo campo-exportar">
                                    <span>Logo de universidad</span>
                                    <select
                                        value={opcionesExportar.universidad}
                                        onChange={(e) => setOpcionesExportar((o) => ({ ...o, universidad: e.target.value }))}
                                    >
                                        {UNIVERSIDADES_PRIVADAS_LIMA.map((universidad) => (
                                            <option key={universidad.clave} value={universidad.clave}>{universidad.nombre}</option>
                                        ))}
                                    </select>
                                    <span className="logo-seleccionado">
                                        <img
                                            src={urlLogoUniversidad(UNIVERSIDADES_PRIVADAS_LIMA.find((u) => u.clave === opcionesExportar.universidad))}
                                            alt={`Logo de ${UNIVERSIDADES_PRIVADAS_LIMA.find((u) => u.clave === opcionesExportar.universidad)?.nombre || 'la universidad seleccionada'}`}
                                            width="24"
                                            height="24"
                                            onError={(e) => {
                                                const universidad = UNIVERSIDADES_PRIVADAS_LIMA.find((u) => u.clave === opcionesExportar.universidad);
                                                e.currentTarget.onerror = null;
                                                e.currentTarget.src = urlLogoRespaldo(universidad);
                                            }}
                                        />
                                        Se incluirá en el membrete del archivo.
                                    </span>
                                </label>
                                {FORMATOS.map((f) => (
                                    <button key={f.clave} type="button" role="menuitem" className="menu-opcion" onClick={() => exportar(f.clave)} disabled={!!exportando}>
                                        <strong>{f.nombre}</strong>
                                        <small>{exportando === f.clave ? 'Preparando archivo…' : f.detalle}</small>
                                    </button>
                                ))}
                                <label className="casilla">
                                    <input type="checkbox" checked={opcionesExportar.membrete} onChange={(e) => setOpcionesExportar((o) => ({ ...o, membrete: e.target.checked }))} />
                                    Incluir membrete institucional
                                </label>
                                {tipo === 'examen' && (
                                    <label className="casilla">
                                        <input type="checkbox" checked={opcionesExportar.clave} onChange={(e) => setOpcionesExportar((o) => ({ ...o, clave: e.target.checked }))} />
                                        Incluir clave de respuestas
                                    </label>
                                )}
                                {errorExportar && (
                                    <div className="menu-error" role="alert">
                                        <p>{errorExportar.mensaje}</p>
                                        <div className="fila-botones">
                                            {errorExportar.alternativas.slice(0, 3).map((f) => (
                                                <button key={f} type="button" className="boton-texto" onClick={() => exportar(f)}>Descargar en {FORMATOS.find((x) => x.clave === f)?.nombre}</button>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            </header>

            <div className="editor-cuerpo">
                <section className="documento" ref={documentoRef} onScroll={() => setBloque(null)}>
                    {pendiente ? (
                        <div className="vacio">
                            <h2>Este recurso aún no tiene contenido</h2>
                            <p>Los servicios de IA no respondieron cuando lo solicitaste. Tus datos quedaron guardados como borrador.</p>
                            <button type="button" className="boton boton-amarillo" onClick={reintentarGeneracion} disabled={!!reintentandoGeneracion}>
                                {reintentandoGeneracion ? reintentandoGeneracion.mensaje : 'Reintentar generación'}
                            </button>
                        </div>
                    ) : (
                        <>
                            <div className="pista">
                                <Icono nombre="ayuda" tam={16} />
                                {aprobado ? 'Recurso aprobado. Si lo editas se creará una nueva versión en borrador.'
                                    : 'Selecciona cualquier párrafo para regenerarlo, o pídeselo al asistente lateral.'}
                            </div>

                            {avisosIniciales.map((a) => (
                                <div key={a} className="banda banda-info">{a}</div>
                            ))}
                            {conformidad && !conformidad.conforme && (
                                <div className="banda banda-alerta" role="alert">
                                    <span>Falta {conformidad.faltantes.length === 1 ? 'la sección obligatoria' : 'las secciones obligatorias'}: <strong>{conformidad.faltantes.join(', ')}</strong>.</span>
                                    <button type="button" className="boton-texto" onClick={() => enviarAlAsistente(`Agrega las secciones obligatorias que faltan: ${conformidad.faltantes.join(', ')}`)}>
                                        Agregar con el asistente
                                    </button>
                                </div>
                            )}

                            <div className="barra-formato" role="toolbar" aria-label="Formato">
                                <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => formato('bold')} title="Negrita" aria-label="Negrita"><Icono nombre="negrita" /></button>
                                <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => formato('italic')} title="Cursiva" aria-label="Cursiva"><Icono nombre="cursiva" /></button>
                                <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => formato('insertUnorderedList')} title="Lista con viñetas" aria-label="Lista con viñetas"><Icono nombre="lista" /></button>
                                <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => formato('insertOrderedList')} title="Lista numerada" aria-label="Lista numerada"><Icono nombre="listaNum" /></button>
                                <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={insertarTabla} title="Insertar tabla" aria-label="Insertar tabla"><Icono nombre="tabla" /></button>
                                <span className="separador" />
                                <button type="button" className="con-texto" onMouseDown={(e) => e.preventDefault()} onClick={regenerarBloque} disabled={!bloque || !!regenerando}>
                                    <Icono nombre="regenerar" /> Regenerar selección
                                </button>
                            </div>

                            <p className="membrete-doc">{TIPOS[tipo]?.nombre} — {recurso.curso}</p>

                            {secciones.map((s) => (
                                <article key={s.id} className={`seccion${s.oculta ? ' seccion-oculta' : ''}`}>
                                    <input
                                        className="seccion-titulo"
                                        value={s.titulo}
                                        onChange={(e) => cambiarTituloSeccion(s.id, e.target.value)}
                                        aria-label="Título de la sección"
                                    />
                                    {s.oculta && !clavesVisibles[s.id] ? (
                                        <button type="button" className="boton-texto" onClick={() => setClavesVisibles((c) => ({ ...c, [s.id]: true }))}>
                                            <Icono nombre="ojo" tam={16} /> Mostrar clave de respuestas (oculta para los estudiantes)
                                        </button>
                                    ) : (
                                        <CuerpoEditable
                                            key={`${s.id}:${revision[s.id] || 0}`}
                                            id={s.id}
                                            html={s.html}
                                            editable={!regenerando}
                                            onCambio={alCambiarCuerpo}
                                            registrar={registrar}
                                        />
                                    )}
                                </article>
                            ))}

                            {bloque && (
                                <div className={`bloque-activo${regenerando ? ' regenerando' : ''}`}
                                    style={{ top: bloque.top - 4, left: bloque.left - 8, width: bloque.width + 16, height: bloque.height + 8 }}>
                                    {regenerando ? (
                                        <span className="bloque-estado"><span className="punto-pulso" /> Regenerando esta sección…</span>
                                    ) : (
                                        <button type="button" className="bloque-boton" onMouseDown={(e) => e.preventDefault()} onClick={regenerarBloque}>
                                            <Icono nombre="regenerar" tam={14} /> Regenerar
                                        </button>
                                    )}
                                </div>
                            )}
                        </>
                    )}
                </section>

                <aside className="asistente" aria-label="Asistente en tiempo real">
                    <div className="asistente-cabecera">
                        <span className={`punto-estado${respondiendo ? ' activo' : ''}`} />
                        <div>
                            <h2>Asistente en tiempo real</h2>
                            <small>Escribe o usa un atajo</small>
                        </div>
                    </div>
                    <div className="chat" aria-live="polite">
                        {mensajes.length === 0 && (
                            <p className="chat-vacio">Pídele cambios al documento: hacerlo más breve, agregar bibliografía, completar una sección o reescribir con otro enfoque.</p>
                        )}
                        {mensajes.map((m) => (
                            <div key={m.id} className={`burbuja ${m.emisor === 'docente' ? 'burbuja-docente' : 'burbuja-ia'}${m.error ? ' burbuja-error' : ''}`}>
                                <p>{m.contenido}{m.escribiendo && <span className="cursor-escribiendo" />}</p>
                                {m.nota && <small className="texto-suave">{m.nota}</small>}
                                {m.reintentable && (
                                    <button type="button" className="boton boton-pequeno boton-amarillo" onClick={() => enviarAlAsistente(m.pedido, true)} disabled={respondiendo}>Reintentar</button>
                                )}
                                {m.propuesta && !m.escribiendo && (
                                    <div className="propuesta">
                                        {m.propuesta.tipo === 'bibliografia' && !m.aplicado && (
                                            <label className="casilla">
                                                <input type="checkbox" checked={!!m.confirmado}
                                                    onChange={(e) => setMensajes((l) => l.map((x) => (x.id === m.id ? { ...x, confirmado: e.target.checked } : x)))} />
                                                Revisé las referencias y quiero insertarlas
                                            </label>
                                        )}
                                        {m.aplicado ? (
                                            <span className="boton boton-pequeno boton-aplicado">Aplicado <Icono nombre="check" tam={14} /></span>
                                        ) : (
                                            <button type="button" className="boton boton-pequeno boton-amarillo" onClick={() => aplicarCambio(m)}
                                                disabled={m.propuesta.tipo === 'bibliografia' && !m.confirmado}>
                                                Aplicar al texto
                                            </button>
                                        )}
                                    </div>
                                )}
                            </div>
                        ))}
                        <div ref={chatFin} />
                    </div>
                    <div className="atajos">
                        {atajos.map((a) => (
                            <button key={a} type="button" className="atajo" onClick={() => enviarAlAsistente(a)} disabled={respondiendo || pendiente}>{a}</button>
                        ))}
                    </div>
                    <form className="chat-entrada" onSubmit={(e) => { e.preventDefault(); enviarAlAsistente(); }}>
                        <input value={entrada} onChange={(e) => setEntrada(e.target.value)} placeholder="Pide un cambio por chat…" maxLength={2000} disabled={pendiente} aria-label="Mensaje para el asistente" />
                        <label className="boton-adjunto" title="Añadir archivo de referencia">
                            <span aria-hidden="true">+</span>
                            <input type="file" className="solo-lector" multiple onChange={seleccionarAdjuntos} disabled={subiendoAdjunto || pendiente || adjuntos.length >= 5} />
                        </label>
                        <button type="submit" className="boton-enviar" disabled={!entrada.trim() || respondiendo} aria-label="Enviar">
                            <Icono nombre="enviar" tam={16} />
                        </button>
                    </form>
                    {adjuntos.length > 0 && <ul className="lista-adjuntos lista-adjuntos-chat">
                        {adjuntos.map((archivo) => (
                            <li key={archivo.id}><span title={archivo.nombre}>{archivo.nombre}</span>
                                <button type="button" className="boton-texto" onClick={() => quitarAdjunto(archivo)}>Quitar</button>
                            </li>
                        ))}
                    </ul>}
                </aside>
            </div>

            {aprobacion && (
                <Modal
                    titulo="Aprobar recurso"
                    subtitulo="Revisa la validación automática antes de confirmar la aprobación."
                    onCerrar={() => setAprobacion(null)}
                    pie={
                        <>
                            <button type="button" className="boton boton-secundario" onClick={() => setAprobacion(null)}>Cancelar</button>
                            <button type="button" className="boton boton-verde" onClick={confirmarAprobacion} disabled={aprobando}>
                                {aprobando ? 'Aprobando…' : 'Confirmar aprobación'}
                            </button>
                        </>
                    }
                >
                    <ul className="verificaciones">
                        <li className={aprobacion.conformidad.conforme ? 'ok' : 'falla'}>
                            <Icono nombre={aprobacion.conformidad.conforme ? 'checkCirculo' : 'alerta'} tam={20} />
                            <div>
                                <strong>{aprobacion.conformidad.conforme ? 'Estructura institucional completa' : 'Estructura institucional incompleta'}</strong>
                                <small>
                                    {aprobacion.conformidad.presentes} de {aprobacion.conformidad.total} secciones obligatorias presentes
                                    {aprobacion.conformidad.faltantes.length > 0 && `. Falta: ${aprobacion.conformidad.faltantes.join(', ')}`}
                                </small>
                            </div>
                        </li>
                        <li className={aprobacion.materiales.cantidad ? 'ok' : 'neutro'}>
                            <Icono nombre={aprobacion.materiales.cantidad ? 'checkCirculo' : 'ayuda'} tam={20} />
                            <div>
                                <strong>{aprobacion.materiales.cantidad ? 'Conforme con los materiales modelo (RAG)' : 'Formato estándar de la universidad'}</strong>
                                <small>{aprobacion.materiales.descripcion}</small>
                            </div>
                        </li>
                        <li className={aprobacion.alertas_activas ? 'falla' : 'ok'}>
                            <Icono nombre={aprobacion.alertas_activas ? 'alerta' : 'checkCirculo'} tam={20} />
                            <div>
                                <strong>{aprobacion.alertas_activas ? `${aprobacion.alertas_activas} alerta(s) activa(s)` : 'Sin alertas activas'}</strong>
                                <small>{aprobacion.alertas_activas ? 'Revísalas en el Panel de calidad.' : 'No se detectaron inconsistencias en la última versión.'}</small>
                            </div>
                        </li>
                    </ul>
                    <div className="cifras">
                        <div><strong>Versión {aprobacion.version_a_aprobar}</strong><small>Versión a aprobar</small></div>
                        <div><strong>{aprobacion.minutos_activos} min</strong><small>Tiempo activo de elaboración</small></div>
                        <div><strong>{aprobacion.porcentaje_editado} %</strong><small>Contenido editado por ti</small></div>
                    </div>
                    <p className="nota-amarilla">
                        Al confirmar, el recurso pasa al estado <strong>Aprobado</strong>, se registra la fecha de aprobación y se detiene la medición del tiempo de elaboración.
                        Podrás seguir exportándolo; cualquier cambio posterior generará una nueva versión.
                    </p>
                </Modal>
            )}

            {mostrandoVersiones && (
                <Modal
                    titulo="Historial de versiones"
                    subtitulo="Puedes recuperar una versión anterior; el documento quedará como borrador para revisarlo."
                    onCerrar={() => setMostrandoVersiones(false)}
                    ancho={620}
                >
                    {versiones?.length ? (
                        <ul className="lista-versiones">
                            {versiones.map((version) => (
                                <li key={version.id}>
                                    <div>
                                        <strong>Versión {version.numero}</strong>
                                        <small>{version.origen === 'docente' ? 'Aprobada por ti' : 'Generada por IA'} · {fechaCompleta(version.fecha)}</small>
                                    </div>
                                    <button type="button" className="boton boton-secundario boton-pequeno"
                                        onClick={() => restaurarVersion(version)} disabled={restaurandoVersion !== null}>
                                        {restaurandoVersion === version.id ? 'Restaurando…' : 'Restaurar'}
                                    </button>
                                </li>
                            ))}
                        </ul>
                    ) : <p className="texto-suave">Todavía no hay versiones guardadas.</p>}
                </Modal>
            )}
        </div>
    );
}
