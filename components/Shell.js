'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { api } from '@/lib/api';
import { iniciales } from '@/lib/util';
import Icono from './Icono';

const MENU = [
    { nombre: 'Dashboard', icono: 'dashboard', href: '/dashboard' },
    { nombre: 'Espacio de trabajo', icono: 'editor', href: '/editor' },
    { nombre: 'Historial', icono: 'historial', href: '/historial' },
    { nombre: 'Panel de calidad', icono: 'calidad', href: '/calidad' },
];

const ContextoApp = createContext({ usuario: null, avisar: () => {} });
export const useApp = () => useContext(ContextoApp);

export default function Shell({ usuario, children }) {
    const ruta = usePathname();
    const router = useRouter();
    const [avisos, setAvisos] = useState([]);
    const contador = useRef(0);

    const avisar = useCallback((texto, tipo = 'info', duracion = 4500) => {
        const id = ++contador.current;
        setAvisos((a) => [...a, { id, texto, tipo }]);
        setTimeout(() => setAvisos((a) => a.filter((x) => x.id !== id)), duracion);
    }, []);

    async function salir() {
        try {
            await api('/api/auth/logout', { method: 'POST' });
        } finally {
            router.push('/login');
            router.refresh();
        }
    }

    return (
        <ContextoApp.Provider value={{ usuario, avisar }}>
            <div className="app">
                <aside className="lateral">
                    <Link href="/dashboard" className="marca">
                        <span className="marca-icono" aria-hidden>E</span>
                        EducaGen
                    </Link>
                    <nav className="menu" aria-label="Navegación principal">
                        {MENU.map((item) => {
                            const activo = ruta.startsWith(item.href);
                            return (
                                <Link key={item.href} href={item.href} className={`menu-item${activo ? ' activo' : ''}`} aria-current={activo ? 'page' : undefined}>
                                    <Icono nombre={item.icono} />
                                    <span>{item.nombre}</span>
                                </Link>
                            );
                        })}
                    </nav>
                    <div className="perfil">
                        <span className="avatar">{iniciales(usuario?.nombre)}</span>
                        <div className="perfil-texto">
                            <strong>{usuario?.nombre || 'Docente'}</strong>
                            <small>Docente universitario</small>
                        </div>
                        <button type="button" className="boton-icono claro" onClick={salir} title="Cerrar sesión" aria-label="Cerrar sesión">
                            <Icono nombre="salir" />
                        </button>
                    </div>
                </aside>
                <main className="contenido">{children}</main>
            </div>
            <div className="avisos" role="status" aria-live="polite">
                {avisos.map((a) => (
                    <div key={a.id} className={`aviso aviso-${a.tipo}`}>
                        {a.texto}
                    </div>
                ))}
            </div>
        </ContextoApp.Provider>
    );
}

export function Modal({ titulo, subtitulo, children, onCerrar, ancho = 520, pie }) {
    useEffect(() => {
        const tecla = (e) => e.key === 'Escape' && onCerrar?.();
        window.addEventListener('keydown', tecla);
        return () => window.removeEventListener('keydown', tecla);
    }, [onCerrar]);

    return (
        <div className="modal-fondo" onMouseDown={(e) => e.target === e.currentTarget && onCerrar?.()}>
            <div className="modal" role="dialog" aria-modal="true" aria-label={titulo} style={{ maxWidth: ancho }}>
                <div className="modal-cabecera">
                    <div>
                        <h2>{titulo}</h2>
                        {subtitulo && <p className="texto-suave">{subtitulo}</p>}
                    </div>
                    {onCerrar && (
                        <button type="button" className="boton-icono" onClick={onCerrar} aria-label="Cerrar">
                            <Icono nombre="cerrar" />
                        </button>
                    )}
                </div>
                <div className="modal-cuerpo">{children}</div>
                {pie && <div className="modal-pie">{pie}</div>}
            </div>
        </div>
    );
}

export function EtiquetaTipo({ tipo, nombre }) {
    return <span className={`etiqueta tipo-${tipo}`}>{nombre}</span>;
}
