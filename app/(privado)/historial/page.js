'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import { EtiquetaTipo, Modal, useApp } from '@/components/Shell';
import Icono from '@/components/Icono';
import { api } from '@/lib/api';
import { ESTADOS, TIPOS, fechaConHora } from '@/lib/util';

export default function Historial() {
    const router = useRouter();
    const { avisar } = useApp();
    const [busqueda, setBusqueda] = useState('');
    const [termino, setTermino] = useState('');
    const [tipo, setTipo] = useState('');
    const [papelera, setPapelera] = useState(false);
    const [datos, setDatos] = useState(null);
    const [aEliminar, setAEliminar] = useState(null);
    const [ocupado, setOcupado] = useState(null);

    const cargar = useCallback(async () => {
        const q = new URLSearchParams({ q: termino, tipo, papelera });
        try {
            setDatos(await api(`/api/recursos?${q}`));
        } catch (err) {
            avisar(err.message, 'error');
            setDatos({ recursos: [], conteos: {}, total: 0 });
        }
    }, [termino, tipo, papelera, avisar]);

    useEffect(() => {
        cargar();
    }, [cargar]);

    // Búsqueda en tiempo real (con una pequeña espera mientras se escribe)
    useEffect(() => {
        const t = setTimeout(() => setTermino(busqueda.trim()), 250);
        return () => clearTimeout(t);
    }, [busqueda]);

    async function duplicar(r) {
        setOcupado(r.id);
        try {
            const res = await api(`/api/recursos/${r.id}/duplicar`, { method: 'POST' });
            avisar(`Se creó «${res.titulo}».`, 'exito');
            await cargar();
        } catch (err) {
            avisar(err.message, 'error', 7000);
        } finally {
            setOcupado(null);
        }
    }

    async function eliminar() {
        const r = aEliminar;
        setAEliminar(null);
        try {
            const res = await api(`/api/recursos/${r.id}`, { method: 'DELETE' });
            avisar(`«${r.titulo}» se movió a la papelera por ${res.dias_papelera} días.`, 'info');
            await cargar();
        } catch (err) {
            avisar(err.message, 'error');
        }
    }

    async function restaurar(r) {
        try {
            await api(`/api/recursos/${r.id}/restaurar`, { method: 'POST' });
            avisar(`«${r.titulo}» volvió a tu historial.`, 'exito');
            await cargar();
        } catch (err) {
            avisar(err.message, 'error');
        }
    }

    const filtros = [['', 'Todos', datos?.total], ...Object.entries(TIPOS).map(([k, t]) => [k, t.plural, datos?.conteos?.[k]])];
    const sinRecursos = datos && datos.total === 0 && !papelera;

    return (
        <div className="pagina">
            <header className="cabecera-pagina">
                <div>
                    <h1>{papelera ? 'Papelera' : 'Mis recursos'}</h1>
                    <p className="texto-suave">
                        {papelera ? 'Los recursos eliminados se conservan 30 días antes de borrarse definitivamente.' : 'Busca, reutiliza o limpia tu biblioteca de materiales.'}
                    </p>
                </div>
                <button type="button" className="boton-texto" onClick={() => { setPapelera((p) => !p); setTipo(''); setBusqueda(''); }}>
                    <Icono nombre={papelera ? 'historial' : 'papelera'} tam={16} /> {papelera ? 'Volver a mis recursos' : 'Ver papelera'}
                </button>
            </header>

            {sinRecursos ? (
                <div className="vacio">
                    <h2>Te damos la bienvenida a tu historial</h2>
                    <p>Aquí verás todos los sílabos, rúbricas, exámenes y casos que crees, listos para reutilizarlos en otros ciclos.</p>
                    <Link href="/dashboard" className="boton boton-amarillo">Crear mi primer recurso</Link>
                </div>
            ) : (
                <>
                    {!papelera && (
                        <div className="barra-filtros">
                            <form className="buscador" role="search" onSubmit={(e) => { e.preventDefault(); setTermino(busqueda.trim()); }}>
                                <Icono nombre="buscar" tam={17} />
                                <input type="search" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} placeholder="Buscar por materia o palabra clave…" aria-label="Buscar recursos" />
                            </form>
                            <div className="chips chips-claros" role="radiogroup" aria-label="Filtrar por tipo">
                                {filtros.map(([clave, nombre, n]) => (
                                    <button key={clave || 'todos'} type="button" role="radio" aria-checked={tipo === clave}
                                        className={`chip${tipo === clave ? ' chip-activo' : ''}`} onClick={() => setTipo(clave)}>
                                        {nombre} {clave && <span className="contador">{n ?? 0}</span>}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    <div className="tabla-contenedor">
                        <table className="tabla">
                            <thead>
                                <tr>
                                    <th>Nombre</th>
                                    <th>Tipo</th>
                                    <th>Materia</th>
                                    <th>Estado</th>
                                    <th>{papelera ? 'Eliminado' : 'Actualizado'}</th>
                                    <th><span className="solo-lector">Acciones</span></th>
                                </tr>
                            </thead>
                            <tbody>
                                {datos === null && (
                                    <tr><td colSpan={6} className="celda-vacia">Cargando tus recursos…</td></tr>
                                )}
                                {datos?.recursos.length === 0 && (
                                    <tr><td colSpan={6} className="celda-vacia">
                                        {papelera ? 'La papelera está vacía.' : 'No se encontraron recursos que coincidan con la búsqueda.'}
                                    </td></tr>
                                )}
                                {datos?.recursos.map((r) => (
                                    <tr key={r.id}>
                                        <td>
                                            {papelera ? (
                                                <span className="celda-nombre"><Icono nombre="documento" /> {r.titulo}</span>
                                            ) : (
                                                <Link href={`/editor/${r.id}`} className="celda-nombre"><Icono nombre="documento" /> {r.titulo}</Link>
                                            )}
                                        </td>
                                        <td><EtiquetaTipo tipo={r.tipo} nombre={TIPOS[r.tipo]?.corto || r.tipo_nombre} /></td>
                                        <td>{r.curso}</td>
                                        <td>
                                            <span className={`estado-celda estado-${r.estado}`}>
                                                {ESTADOS[r.estado] || r.estado}
                                                {r.estado === 'borrador' && r.conformidad != null && ` (${r.conformidad} %)`}
                                            </span>
                                        </td>
                                        <td className="texto-suave">{fechaConHora(papelera ? r.fecha_eliminacion : r.fecha_actualizacion)}</td>
                                        <td className="acciones">
                                            {papelera ? (
                                                <button type="button" className="boton-icono" onClick={() => restaurar(r)} title="Restaurar" aria-label={`Restaurar ${r.titulo}`}>
                                                    <Icono nombre="restaurar" />
                                                </button>
                                            ) : (
                                                <>
                                                    <button type="button" className="boton-icono" onClick={() => router.push(`/editor/${r.id}`)} title="Abrir" aria-label={`Abrir ${r.titulo}`}>
                                                        <Icono nombre="abrir" />
                                                    </button>
                                                    <button type="button" className="boton-icono" onClick={() => duplicar(r)} disabled={ocupado === r.id} title="Duplicar" aria-label={`Duplicar ${r.titulo}`}>
                                                        <Icono nombre="duplicar" />
                                                    </button>
                                                    <button type="button" className="boton-icono peligro" onClick={() => setAEliminar(r)} title="Eliminar" aria-label={`Eliminar ${r.titulo}`}>
                                                        <Icono nombre="eliminar" />
                                                    </button>
                                                </>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </>
            )}

            {aEliminar && (
                <Modal
                    titulo="¿Eliminar este recurso?"
                    onCerrar={() => setAEliminar(null)}
                    ancho={440}
                    pie={
                        <>
                            <button type="button" className="boton boton-secundario" onClick={() => setAEliminar(null)}>Cancelar</button>
                            <button type="button" className="boton boton-rojo" onClick={eliminar}>Eliminar</button>
                        </>
                    }
                >
                    <p>«{aEliminar.titulo}» se moverá a la papelera. Podrás restaurarlo durante 30 días.</p>
                </Modal>
            )}
        </div>
    );
}
