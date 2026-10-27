'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { EtiquetaTipo, Modal, useApp } from '@/components/Shell';
import Icono from '@/components/Icono';
import { api } from '@/lib/api';
import { fechaRelativa } from '@/lib/util';

const VACIO = { id_recurso: '', nota_ia: '', nota_final: '', observaciones: '' };

function cifra(valor, sufijo = '') {
    return valor === null || valor === undefined ? '—' : `${valor}${sufijo}`;
}

export default function PanelCalidad() {
    const { avisar } = useApp();
    const [datos, setDatos] = useState(null);
    const [form, setForm] = useState(VACIO);
    const [guardando, setGuardando] = useState(false);
    const [sugerir, setSugerir] = useState(null); // { respuesta, cargando, justificacion }

    const cargar = useCallback(async () => {
        try {
            setDatos(await api('/api/calidad'));
        } catch (err) {
            avisar(err.message, 'error');
        }
    }, [avisar]);

    useEffect(() => {
        cargar();
    }, [cargar]);

    async function atender(a) {
        try {
            await api(`/api/calidad/alertas/${a.id}`, { method: 'PATCH' });
            await cargar();
        } catch (err) {
            avisar(err.message, 'error');
        }
    }

    async function registrar(e) {
        e.preventDefault();
        if (!form.id_recurso || form.nota_ia === '' || form.nota_final === '') {
            avisar('Elige un recurso y completa ambas notas.', 'aviso');
            return;
        }
        setGuardando(true);
        try {
            await api('/api/calidad/evaluaciones', {
                method: 'POST',
                body: { id_recurso: Number(form.id_recurso), nota_ia: Number(form.nota_ia), nota_final: Number(form.nota_final), observaciones: form.observaciones },
            });
            avisar('Evaluación registrada.', 'exito');
            setForm(VACIO);
            await cargar();
        } catch (err) {
            avisar(err.message, 'error');
        } finally {
            setGuardando(false);
        }
    }

    async function pedirNota() {
        setSugerir((s) => ({ ...s, cargando: true }));
        try {
            const r = await api('/api/calidad/sugerir-nota', { method: 'POST', body: { id_recurso: Number(form.id_recurso), respuesta: sugerir.respuesta } });
            setForm((f) => ({ ...f, nota_ia: String(r.nota) }));
            setSugerir({ respuesta: sugerir.respuesta, cargando: false, justificacion: r.justificacion, nota: r.nota });
        } catch (err) {
            avisar(err.message, 'error');
            setSugerir((s) => ({ ...s, cargando: false }));
        }
    }

    if (!datos) return <div className="cargando-pagina">Calculando indicadores…</div>;
    const ind = datos.indicadores;

    return (
        <div className="pagina">
            <header className="cabecera-pagina">
                <div>
                    <h1>Panel de calidad</h1>
                    <p className="texto-suave">Conformidad, auditoría automática de IA y alertas de tus recursos.</p>
                </div>
            </header>

            <div className="indicadores">
                <div className="indicador"><strong>{cifra(ind.conformidad, '%')}</strong><span>Conformidad de mis recursos</span></div>
                <div className="indicador"><strong>{ind.recursos_auditados}</strong><span>Recursos auditados</span></div>
                <div className="indicador"><strong className={ind.alertas_activas ? 'rojo' : ''}>{ind.alertas_activas}</strong><span>Alertas activas</span></div>
                <div className="indicador"><strong>{cifra(ind.tiempo_medio_ia_seg, 's')}</strong><span>Tiempo medio de respuesta IA</span></div>
            </div>

            <div className="indicadores secundarios">
                <div className="indicador"><strong>{ind.recursos_aprobados}</strong><span>Recursos aprobados</span></div>
                <div className="indicador"><strong>{cifra(ind.minutos_medios_elaboracion, ' min')}</strong><span>Tiempo medio de elaboración</span></div>
                <div className="indicador"><strong>{cifra(ind.porcentaje_medio_editado, '%')}</strong><span>Contenido editado en promedio</span></div>
                <div className="indicador"><strong>{ind.consultas_ia}</strong><span>Consultas a la IA ({ind.consultas_conmutadas} con respaldo)</span></div>
            </div>

            <section className="bloque-panel">
                <h2>Alertas recientes</h2>
                {datos.alertas.length === 0 ? (
                    <p className="texto-suave">No hay alertas. Tus recursos cumplen con la estructura institucional.</p>
                ) : (
                    <ul className="alertas">
                        {datos.alertas.map((a) => (
                            <li key={a.id} className={`alerta sev-${a.severidad}${a.atendida ? ' atendida' : ''}`}>
                                <Icono nombre="alerta" tam={18} />
                                <div>
                                    <strong>{a.titulo}</strong>
                                    <p>{a.descripcion}</p>
                                    <small className="texto-suave">{fechaRelativa(a.fecha)}{a.atendida ? ', atendida' : ''}</small>
                                </div>
                                <div className="alerta-acciones">
                                    {a.id_recurso && <Link href={`/editor/${a.id_recurso}`} className="boton-texto">Abrir recurso</Link>}
                                    {!a.atendida && <button type="button" className="boton-texto" onClick={() => atender(a)}>Marcar como atendida</button>}
                                </div>
                            </li>
                        ))}
                    </ul>
                )}
            </section>

            <section className="bloque-panel">
                <h2>Diferencias entre la nota sugerida por la IA y tu nota final</h2>
                {datos.notas.length === 0 ? (
                    <p className="texto-suave">Aún no hay datos para comparar. Registra tus notas finales abajo para saber qué tan confiable es la IA en tus evaluaciones.</p>
                ) : (
                    <div className="tabla-contenedor">
                        <table className="tabla">
                            <thead><tr><th>Recurso</th><th>Tipo</th><th>Nota IA</th><th>Nota final</th><th>Diferencia</th></tr></thead>
                            <tbody>
                                {datos.notas.map((n) => (
                                    <tr key={n.id}>
                                        <td>{n.recurso}</td>
                                        <td><EtiquetaTipo tipo={n.tipo} nombre={n.tipo_nombre} /></td>
                                        <td>{n.nota_ia?.toFixed(1)}</td>
                                        <td>{n.nota_final.toFixed(1)}</td>
                                        <td className={n.diferencia > 0 ? 'verde' : n.diferencia < 0 ? 'rojo' : ''}>
                                            {n.diferencia > 0 ? '+' : ''}{n.diferencia?.toFixed(1)}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}

                <form className="form-evaluacion" onSubmit={registrar}>
                    <h3>Registrar una evaluación</h3>
                    {datos.recursos_evaluables.length === 0 ? (
                        <p className="texto-suave">Genera una rúbrica, un examen o un caso de estudio para registrar notas.</p>
                    ) : (
                        <div className="fila-campos">
                            <label className="campo">
                                <span>Recurso aplicado</span>
                                <select value={form.id_recurso} onChange={(e) => setForm({ ...form, id_recurso: e.target.value })}>
                                    <option value="">Elige un recurso…</option>
                                    {datos.recursos_evaluables.map((r) => <option key={r.id} value={r.id}>{r.titulo}</option>)}
                                </select>
                            </label>
                            <label className="campo corto">
                                <span>Nota IA</span>
                                <input type="number" min={0} max={20} step={0.5} value={form.nota_ia} onChange={(e) => setForm({ ...form, nota_ia: e.target.value })} />
                            </label>
                            <label className="campo corto">
                                <span>Nota final</span>
                                <input type="number" min={0} max={20} step={0.5} value={form.nota_final} onChange={(e) => setForm({ ...form, nota_final: e.target.value })} />
                            </label>
                            <div className="fila-botones">
                                <button type="button" className="boton boton-secundario" disabled={!form.id_recurso} onClick={() => setSugerir({ respuesta: '', cargando: false })}>
                                    <Icono nombre="chispa" tam={16} /> Sugerir nota con IA
                                </button>
                                <button type="submit" className="boton boton-amarillo" disabled={guardando}>Registrar</button>
                            </div>
                        </div>
                    )}
                </form>
            </section>

            <p className="texto-suave pie-ia">
                Servicio de IA principal: {datos.ia.principal || 'ninguno'}. Respaldo: {datos.ia.respaldo || 'ninguno'}. Interruptor de circuito: {datos.ia.circuito}.
            </p>

            {sugerir && (
                <Modal
                    titulo="Sugerir nota con IA"
                    subtitulo="Pega la respuesta del estudiante sin datos personales. La IA aplicará el recurso elegido."
                    onCerrar={() => setSugerir(null)}
                    pie={
                        <>
                            <button type="button" className="boton boton-secundario" onClick={() => setSugerir(null)}>Cerrar</button>
                            <button type="button" className="boton boton-amarillo" onClick={pedirNota} disabled={sugerir.cargando || (sugerir.respuesta || '').trim().length < 20}>
                                {sugerir.cargando ? 'Calificando…' : 'Sugerir nota'}
                            </button>
                        </>
                    }
                >
                    <textarea className="area" rows={8} value={sugerir.respuesta} onChange={(e) => setSugerir({ ...sugerir, respuesta: e.target.value })}
                        placeholder="Respuesta o trabajo del estudiante (mínimo 20 caracteres)…" />
                    {sugerir.nota !== undefined && (
                        <p className="nota-amarilla"><strong>Nota sugerida: {sugerir.nota}</strong>. {sugerir.justificacion}</p>
                    )}
                </Modal>
            )}
        </div>
    );
}
