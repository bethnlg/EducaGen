'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { EtiquetaTipo, Modal, useApp } from '@/components/Shell';
import Icono from '@/components/Icono';
import { api, streamSSE, subirArchivo } from '@/lib/api';
import { ESTADOS, TIPOS, fechaRelativa } from '@/lib/util';

const CONFIG = {
    silabo: {
        etiquetaTemas: 'Competencias o temas clave',
        ejemploTemas: 'Ej. Diseña algoritmos eficientes usando recursividad, complejidad, árboles y grafos',
    },
    rubrica: {
        etiquetaTemas: 'Criterios de evaluación (peso opcional)',
        ejemploTemas: 'Ej. Argumentación 40, Uso de fuentes 30, Redacción 30',
    },
    examen: {
        etiquetaTemas: 'Temas del examen',
        ejemploTemas: 'Ej. Normalización, consultas SQL, transacciones',
    },
    caso: {
        etiquetaTemas: 'Problema académico, tema y datos clave del caso real',
        ejemploTemas: 'Ej. Crisis ágil en Distribuciones Andinas: riesgos de entrega, zonas con retrasos, seguimiento y priorización con un MVP',
    },
};

const CARRERAS = ['Ingeniería de Software', 'Ingeniería de Sistemas de Información', 'Ciencias de la Computación', 'Administración y Marketing', 'Comunicación y Periodismo'];
const SECTORES = ['Retail', 'Banca y finanzas', 'Salud', 'Tecnología', 'Educación', 'Manufactura', 'Minería', 'Turismo', 'Telecomunicaciones', 'Sector público'];

const INICIAL = { curso: '', temas: '', carrera: '', ciclo: '', semanas: 16, niveles: 'Excelente, Bueno, En proceso, Inicial', num_preguntas: 10, num_caso_preguntas: 4, sector: 'Retail' };

function vistaPrevia(texto) {
    // Muestra el contenido que va llegando sin la sintaxis JSON
    return texto
        .replace(/"[a-z_]+"\s*:/g, ' ')
        .replace(/[{}[\]",]+/g, ' ')
        .replace(/\s+/g, ' ')
        .slice(-320);
}

export default function Dashboard() {
    const router = useRouter();
    const { usuario, avisar } = useApp();
    const [tipo, setTipo] = useState('silabo');
    const [form, setForm] = useState(INICIAL);
    const [invalidos, setInvalidos] = useState([]);
    const [advertencia, setAdvertencia] = useState(null); // competencias breves
    const [propuesta, setPropuesta] = useState(null); // pesos de rúbrica
    const [generacion, setGeneracion] = useState(null);
    const [adjuntos, setAdjuntos] = useState([]);
    const [subiendo, setSubiendo] = useState(false);
    const [recientes, setRecientes] = useState(null);
    const [resumen, setResumen] = useState(null);
    const abortar = useRef(null);

    useEffect(() => {
        api('/api/recursos?limite=4')
            .then((d) => {
                setRecientes(d.recursos);
                setResumen(d);
            })
            .catch(() => setRecientes([]));
        return () => abortar.current?.abort();
    }, []);

    function cambiar(e) {
        const { name, value } = e.target;
        setForm((f) => ({ ...f, [name]: value }));
        setInvalidos((v) => v.filter((c) => c !== name));
        if (name === 'temas') setAdvertencia(null);
    }

    function elegirTipo(t) {
        setTipo(t);
        setInvalidos([]);
        setAdvertencia(null);
    }

    async function generar(extra = {}) {
        // HU0005-2: se resaltan los datos faltantes sin cambiar de vista
        const faltan = ['curso', 'temas'].filter((c) => !String(form[c]).trim());
        if (faltan.length) {
            setInvalidos(faltan);
            return;
        }
        const cuerpo = {
            tipo,
            curso: form.curso,
            temas: form.temas,
            carrera: form.carrera || null,
            ciclo: form.ciclo ? Number(form.ciclo) : null,
            ...(tipo === 'silabo' && { semanas: Number(form.semanas) || 16 }),
            ...(tipo === 'rubrica' && { niveles: form.niveles }),
            ...(tipo === 'examen' && { num_preguntas: Number(form.num_preguntas) || 10 }),
            ...(tipo === 'caso' && { sector: form.sector, num_preguntas: Number(form.num_caso_preguntas) || 4 }),
            adjuntos,
            ...extra,
        };

        setGeneracion({ estado: 'generando', mensaje: `Preparando tu ${TIPOS[tipo].nombre.toLowerCase()}…`, texto: '' });
        abortar.current = new AbortController();
        let avisos = [];
        try {
            await streamSSE('/api/recursos/generar', cuerpo, {
                signal: abortar.current.signal,
                onEvento: (ev) => {
                    if (ev.tipo === 'inicio') {
                        avisos = ev.avisos || [];
                        setGeneracion((g) => ({ ...g, id: ev.id_recurso, mensaje: 'Consultando el banco de materiales modelo…' }));
                    } else if (ev.tipo === 'estado') {
                        setGeneracion((g) => ({ ...g, mensaje: ev.mensaje }));
                    } else if (ev.tipo === 'chunk') {
                        setGeneracion((g) => ({ ...g, mensaje: 'Redactando el contenido…', texto: g.texto + ev.texto }));
                    } else if (ev.tipo === 'reinicio') {
                        setGeneracion((g) => ({ ...g, mensaje: ev.mensaje, texto: '' }));
                    } else if (ev.tipo === 'fin') {
                        sessionStorage.setItem(`educagen:avisos:${ev.id_recurso}`, JSON.stringify(ev.avisos || avisos));
                        setGeneracion((g) => ({ ...g, estado: 'listo', mensaje: 'Listo. Abriendo el editor…' }));
                        router.push(`/editor/${ev.id_recurso}`);
                    } else if (ev.tipo === 'error') {
                        setGeneracion((g) => ({ ...g, estado: 'error', mensaje: ev.mensaje, id: ev.id_recurso }));
                    }

                },
            });
        } catch (err) {
            if (err.name === 'AbortError') return;
            setGeneracion(null);
            const d = err.detalle || {};
            if (d.codigo === 'competencias_breves') setAdvertencia(d.mensaje);
            else if (d.codigo === 'pesos_no_suman') setPropuesta(d);
            else if (d.campos?.length) {
                setInvalidos(d.campos);
                avisar(err.message, 'error');
            } else avisar(err.message, 'error');
        }
    }

    async function seleccionarArchivos(e) {
        const archivos = Array.from(e.target.files || []);
        e.target.value = '';
        if (!archivos.length) return;
        if (adjuntos.length + archivos.length > 5) {
            avisar('Puedes adjuntar hasta 5 archivos por prompt.', 'aviso');
            return;
        }
        setSubiendo(true);
        try {
            const cargados = [];
            for (const archivo of archivos) cargados.push(await subirArchivo(archivo));
            setAdjuntos((lista) => [...lista, ...cargados]);
        } catch (err) {
            avisar(err.message, 'error');
        } finally {
            setSubiendo(false);
        }
    }

    const cfg = CONFIG[tipo];
    const nombre = usuario?.nombre?.split(' ')[0] || '';

    return (
        <div className="pagina">
            <header className="saludo">
                <h1>Hola{nombre ? `, ${nombre}` : ''}</h1>
                {resumen && resumen.total > 0 && (
                    <p className="texto-suave">
                        Tienes {resumen.total} {resumen.total === 1 ? 'recurso' : 'recursos'} en tu biblioteca: {resumen.conteos.silabo} sílabos, {resumen.conteos.rubrica} rúbricas, {resumen.conteos.examen} exámenes y {resumen.conteos.caso} casos.
                    </p>
                )}
            </header>

            <section className="crear" aria-labelledby="titulo-crear">
                <h2 id="titulo-crear">{tipo === 'caso' ? 'Zona de casos de estudio' : 'Crear un recurso en un paso'}</h2>
                <p className="crear-sub">
                    {tipo === 'caso'
                        ? 'Indica el tema y los datos clave; EducaGen generará un caso amplio, sus preguntas y una estructura exportable.'
                        : 'Elige el tipo, completa lo esencial y genera tu material sin salir de esta pantalla.'}
                </p>

                <div className="chips" role="radiogroup" aria-label="Tipo de recurso">
                    {Object.entries(TIPOS).map(([clave, t]) => (
                        <button key={clave} type="button" role="radio" aria-checked={tipo === clave}
                            className={`chip${tipo === clave ? ' chip-activo' : ''}`} onClick={() => elegirTipo(clave)}>
                            {t.nombre}
                        </button>
                    ))}
                </div>

                <form className="crear-form" noValidate onSubmit={(e) => { e.preventDefault(); generar(); }}>
                    <label className={`campo-claro${invalidos.includes('curso') ? ' invalido' : ''}`}>
                        <span>Materia / curso</span>
                        <input name="curso" value={form.curso} onChange={cambiar} placeholder="Ej. Algoritmos y Estructuras de Datos" maxLength={150} />
                        {invalidos.includes('curso') && <small className="error-campo">Escribe el nombre del curso.</small>}
                    </label>
                    <label className={`campo-claro${invalidos.includes('temas') ? ' invalido' : ''}`}>
                        <span>{cfg.etiquetaTemas}</span>
                        <textarea name="temas" value={form.temas} onChange={cambiar} placeholder={cfg.ejemploTemas} rows={2} maxLength={2000} />
                        {invalidos.includes('temas') && <small className="error-campo">Este dato es obligatorio.</small>}
                    </label>

                    <div className="crear-extra">
                        {tipo === 'silabo' && (
                            <label className="campo-claro corto">
                                <span>Semanas</span>
                                <input name="semanas" type="number" min={1} max={24} value={form.semanas} onChange={cambiar} />
                            </label>
                        )}
                        {tipo === 'rubrica' && (
                            <label className="campo-claro">
                                <span>Niveles de desempeño</span>
                                <input name="niveles" value={form.niveles} onChange={cambiar} />
                            </label>
                        )}
                        {tipo === 'examen' && (
                            <label className="campo-claro corto">
                                <span>N.º de preguntas</span>
                                <input name="num_preguntas" type="number" min={1} max={20} value={form.num_preguntas} onChange={cambiar} />
                            </label>
                        )}
                        {tipo === 'caso' && (
                            <>
                                <label className="campo-claro">
                                    <span>Sector</span>
                                    <input name="sector" list="sectores" value={form.sector} onChange={cambiar} />
                                    <datalist id="sectores">{SECTORES.map((s) => <option key={s} value={s} />)}</datalist>
                                </label>
                                <label className="campo-claro corto">
                                    <span>N.º de preguntas</span>
                                    <input name="num_caso_preguntas" type="number" min={1} max={20} value={form.num_caso_preguntas} onChange={cambiar} />
                                </label>
                            </>
                        )}
                        <label className="campo-claro">
                            <span>Carrera (opcional)</span>
                            <input name="carrera" list="carreras" value={form.carrera} onChange={cambiar} placeholder="Ej. Ingeniería de Software" />
                            <datalist id="carreras">{CARRERAS.map((c) => <option key={c} value={c} />)}</datalist>
                        </label>
                        <label className="campo-claro corto">
                            <span>Ciclo</span>
                            <select name="ciclo" value={form.ciclo} onChange={cambiar}>
                                <option value="">—</option>
                                {Array.from({ length: 10 }, (_, i) => <option key={i + 1} value={i + 1}>{i + 1}</option>)}
                            </select>
                        </label>
                    </div>

                    <div className="adjuntos">
                        <div className="adjuntos-cabecera">
                            <span>Archivos de referencia (opcional)</span>
                            <label className="boton boton-secundario boton-pequeno">
                                {subiendo ? 'Cargando…' : 'Añadir archivo'}
                                <input type="file" className="solo-lector" multiple onChange={seleccionarArchivos} disabled={subiendo || adjuntos.length >= 5} />
                            </label>
                        </div>
                        <small className="texto-suave">Se admite cualquier formato. Se extrae texto de PDF, Word, Excel y archivos de texto para orientar a la IA (máximo 10 MB por archivo).</small>
                        {adjuntos.length > 0 && <ul className="lista-adjuntos">
                            {adjuntos.map((archivo) => (
                                <li key={archivo.id}><span title={archivo.nombre}>{archivo.nombre}</span>
                                    <button type="button" className="boton-texto" onClick={() => setAdjuntos((lista) => lista.filter((a) => a.id !== archivo.id))}>Quitar</button>
                                </li>
                            ))}
                        </ul>}
                    </div>

                    {advertencia && (
                        <div className="nota-hero" role="alert">
                            <Icono nombre="ayuda" />
                            <p>{advertencia}</p>
                            <button type="button" className="boton-texto claro" onClick={() => { setAdvertencia(null); generar({ forzar: true }); }}>
                                Generar de todos modos
                            </button>
                        </div>
                    )}

                    <button type="submit" className="boton boton-amarillo boton-grande" disabled={!!generacion}>
                        Generar ahora
                    </button>
                </form>
            </section>

            <section className="recientes">
                <div className="fila-titulo">
                    <h2>Recientes</h2>
                    <Link href="/historial" className="enlace">Ver historial completo</Link>
                </div>
                {recientes === null ? (
                    <div className="tarjetas">{[0, 1, 2, 3].map((i) => <div key={i} className="tarjeta-reciente esqueleto" />)}</div>
                ) : recientes.length === 0 ? (
                    <p className="texto-suave">Aún no tienes recursos. Completa el formulario de arriba para crear el primero.</p>
                ) : (
                    <div className="tarjetas">
                        {recientes.map((r) => (
                            <Link key={r.id} href={`/editor/${r.id}`} className="tarjeta-reciente">
                                <div className="tarjeta-cabeza">
                                    <EtiquetaTipo tipo={r.tipo} nombre={r.tipo_nombre} />
                                    <small>{fechaRelativa(r.fecha_actualizacion)}</small>
                                </div>
                                <h3 title={r.titulo}>{r.titulo}</h3>
                                <p className="texto-suave">{r.curso}</p>
                                <div className="tarjeta-pie">
                                    {r.estado === 'aprobado' ? <span className="estado-ok">Aprobado</span>
                                        : r.conforme ? <span className="estado-ok">100 % conforme</span>
                                            : <span className="estado-neutro">{r.estado === 'borrador' && r.conformidad != null ? `Borrador, ${r.conformidad} % conforme` : ESTADOS[r.estado]}</span>}
                                </div>
                            </Link>
                        ))}
                    </div>
                )}
            </section>

            {generacion && (
                <Modal
                    titulo={generacion.estado === 'error' ? 'No se pudo generar el recurso' : `Generando tu ${TIPOS[tipo].nombre.toLowerCase()}`}
                    onCerrar={generacion.estado === 'generando' ? undefined : () => setGeneracion(null)}
                    pie={generacion.estado === 'error' ? (
                        <>
                            {generacion.id && <Link href="/historial" className="boton boton-secundario">Ver en el Historial</Link>}
                            <button type="button" className="boton boton-amarillo" onClick={() => { setGeneracion(null); generar(); }}>Reintentar</button>
                        </>
                    ) : null}
                >
                    {generacion.estado === 'error' ? (
                        <p>{generacion.mensaje}</p>
                    ) : (
                        <div className="progreso">
                            <div className="barra-progreso"><span /></div>
                            <p className="progreso-estado">{generacion.mensaje}</p>
                            {generacion.texto && <p className="progreso-vista" aria-hidden>{vistaPrevia(generacion.texto)}</p>}
                            <button type="button" className="boton-texto" onClick={() => { abortar.current?.abort(); setGeneracion(null); }}>
                                Cancelar
                            </button>
                        </div>
                    )}
                </Modal>
            )}

            {propuesta && (
                <Modal
                    titulo="Los pesos no suman 100 %"
                    subtitulo={propuesta.mensaje}
                    onCerrar={() => setPropuesta(null)}
                    pie={
                        <>
                            <button type="button" className="boton boton-secundario" onClick={() => setPropuesta(null)}>Ajustar yo mismo</button>
                            <button type="button" className="boton boton-amarillo" onClick={() => {
                                setForm((f) => ({ ...f, temas: propuesta.propuesta.map((p) => `${p.nombre} ${p.peso}`).join(', ') }));
                                setPropuesta(null);
                                generar({ aceptar_propuesta: true });
                            }}>Usar esta distribución</button>
                        </>
                    }
                >
                    <table className="tabla tabla-compacta">
                        <thead><tr><th>Criterio</th><th>Peso propuesto</th></tr></thead>
                        <tbody>
                            {propuesta.propuesta.map((p) => <tr key={p.nombre}><td>{p.nombre}</td><td>{p.peso} %</td></tr>)}
                        </tbody>
                    </table>
                </Modal>
            )}
        </div>
    );
}
