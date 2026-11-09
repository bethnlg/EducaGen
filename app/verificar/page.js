'use client';

import Link from 'next/link';
import { Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { api } from '@/lib/api';
import PanelMarca from '../login/PanelMarca';

function Verificacion() {
    const params = useSearchParams();
    const correo = params.get('correo') || '';
    const token = params.get('token') || '';
    const [estado, setEstado] = useState('cargando');
    const [mensaje, setMensaje] = useState('');

    useEffect(() => {
        if (!correo || !token) {
            setEstado('error');
            setMensaje('El enlace está incompleto.');
            return;
        }
        api(`/api/auth/verify?token=${encodeURIComponent(token)}`, {
            method: 'POST',
            body: { correo },
        }).then((respuesta) => {
            setEstado('listo');
            setMensaje(respuesta.mensaje);
        }).catch((err) => {
            setEstado('error');
            setMensaje(err.message);
        });
    }, [correo, token]);

    return (
        <div className="auth-tarjeta">
            <h2>{estado === 'cargando' ? 'Confirmando tu correo…' : estado === 'listo' ? 'Correo confirmado' : 'No se pudo confirmar'}</h2>
            <p className={estado === 'error' ? 'error' : 'texto-suave'} role={estado === 'error' ? 'alert' : undefined}>
                {estado === 'cargando' ? 'Estamos activando tu cuenta de EducaGen.' : mensaje}
            </p>
            {estado !== 'cargando' && <Link href="/login" className="boton boton-amarillo boton-ancho">Ir a iniciar sesión</Link>}
        </div>
    );
}

export default function VerificarPage() {
    return (
        <main className="auth">
            <PanelMarca />
            <section className="auth-formulario">
                <Suspense fallback={null}><Verificacion /></Suspense>
            </section>
        </main>
    );
}
