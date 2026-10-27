'use client';

import Link from 'next/link';
import { Suspense, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { api } from '@/lib/api';
import PanelMarca from '../login/PanelMarca';

function Formulario() {
    const params = useSearchParams();
    const correo = params.get('correo') || '';
    const token = params.get('token') || '';
    const [contrasena, setContrasena] = useState('');
    const [confirmar, setConfirmar] = useState('');
    const [error, setError] = useState('');
    const [cargando, setCargando] = useState(false);
    const [listo, setListo] = useState(false);

    async function onSubmit(e) {
        e.preventDefault();
        setError('');
        if (contrasena.length < 8) return setError('La contraseña debe tener al menos 8 caracteres.');
        if (contrasena !== confirmar) return setError('Las contraseñas no coinciden.');
        setCargando(true);
        try {
            await api('/api/auth/reset', { method: 'POST', body: { correo, token, contrasena } });
            setListo(true);
        } catch (err) {
            setError(err.message);
        } finally {
            setCargando(false);
        }
    }

    if (!correo || !token) {
        return (
            <div className="auth-tarjeta">
                <h2>Enlace incompleto</h2>
                <p className="texto-suave">Abre de nuevo el enlace que recibiste por correo o solicita uno nuevo.</p>
                <Link href="/login" className="boton boton-amarillo boton-ancho">Ir a iniciar sesión</Link>
            </div>
        );
    }

    return (
        <div className="auth-tarjeta">
            <h2>Crea una nueva contraseña</h2>
            <p className="texto-suave">Para la cuenta {correo}</p>
            {listo ? (
                <>
                    <div className="exito">Tu contraseña se cambió correctamente. Ya puedes ingresar con ella.</div>
                    <Link href="/login" className="boton boton-amarillo boton-ancho">Iniciar sesión</Link>
                </>
            ) : (
                <form onSubmit={onSubmit} className="auth-form" noValidate>
                    <label className="campo">
                        <span>Nueva contraseña</span>
                        <input type="password" autoComplete="new-password" placeholder="Mínimo 8 caracteres" value={contrasena} onChange={(e) => setContrasena(e.target.value)} />
                    </label>
                    <label className="campo">
                        <span>Confirma la contraseña</span>
                        <input type="password" autoComplete="new-password" value={confirmar} onChange={(e) => setConfirmar(e.target.value)} />
                    </label>
                    {error && <p className="error" role="alert">{error}</p>}
                    <button type="submit" className="boton boton-amarillo boton-ancho" disabled={cargando}>
                        {cargando ? 'Guardando…' : 'Guardar contraseña'}
                    </button>
                </form>
            )}
        </div>
    );
}

export default function RestablecerPage() {
    return (
        <main className="auth">
            <PanelMarca />
            <section className="auth-formulario">
                <Suspense fallback={null}>
                    <Formulario />
                </Suspense>
            </section>
        </main>
    );
}
