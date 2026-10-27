'use client';

import { Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { api } from '@/lib/api';
import PanelMarca from './PanelMarca';

const VACIO = { nombre: '', correo: '', contrasena: '' };
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function Formulario() {
    const router = useRouter();
    const volver = useSearchParams().get('volver');
    const [modo, setModo] = useState('login'); // login | registro | recuperar
    const [form, setForm] = useState(VACIO);
    const [error, setError] = useState('');
    const [invalidos, setInvalidos] = useState([]);
    const [cargando, setCargando] = useState(false);
    const [verPass, setVerPass] = useState(false);
    const [enviado, setEnviado] = useState(false);

    const esLogin = modo === 'login';

    function cambiarModo(nuevo) {
        setModo(nuevo);
        setError('');
        setInvalidos([]);
        setEnviado(false);
        setForm((f) => ({ ...VACIO, correo: f.correo }));
    }

    function onChange(e) {
        setForm({ ...form, [e.target.name]: e.target.value });
        setInvalidos((v) => v.filter((c) => c !== e.target.name));
    }

    async function onSubmit(e) {
        e.preventDefault();
        setError('');
        const requeridos = modo === 'recuperar' ? ['correo'] : esLogin ? ['correo', 'contrasena'] : ['nombre', 'correo', 'contrasena'];
        const faltan = requeridos.filter((c) => !form[c].trim());
        if (faltan.length) {
            setInvalidos(faltan);
            setError('Completa todos los campos.');
            return;
        }
        if (!EMAIL_RE.test(form.correo.trim())) {
            setInvalidos(['correo']);
            setError('Ingresa un correo institucional válido.');
            return;
        }
        if (modo === 'registro' && form.contrasena.length < 8) {
            setInvalidos(['contrasena']);
            setError('La contraseña debe tener al menos 8 caracteres.');
            return;
        }

        setCargando(true);
        try {
            if (modo === 'recuperar') {
                await api('/api/auth/forgot', { method: 'POST', body: { correo: form.correo } });
                setEnviado(true);
                return;
            }
            await api(esLogin ? '/api/auth/login' : '/api/auth/register', { method: 'POST', body: form });
            router.push(volver && volver.startsWith('/') ? volver : '/dashboard');
            router.refresh();
        } catch (err) {
            setError(err.message);
            if (err.detalle?.campos) setInvalidos(err.detalle.campos);
        } finally {
            setCargando(false);
        }
    }

    const campo = (nombre) => `campo${invalidos.includes(nombre) ? ' invalido' : ''}`;

    if (modo === 'recuperar') {
        return (
            <div className="auth-tarjeta">
                <button type="button" className="boton-texto" onClick={() => cambiarModo('login')}>Volver a iniciar sesión</button>
                <h2>Recupera tu contraseña</h2>
                <p className="texto-suave">Escribe tu correo institucional y te enviaremos un enlace para crear una nueva.</p>
                {enviado ? (
                    <div className="exito">
                        Si existe una cuenta con <strong>{form.correo}</strong>, recibirás un correo con el enlace en unos minutos. Revisa también tu carpeta de spam.
                    </div>
                ) : (
                    <form onSubmit={onSubmit} className="auth-form" noValidate>
                        <label className={campo('correo')}>
                            <span>Correo institucional</span>
                            <input name="correo" type="email" autoComplete="email" placeholder="nombre@universidad.edu.pe" value={form.correo} onChange={onChange} />
                        </label>
                        {error && <p className="error" role="alert">{error}</p>}
                        <button type="submit" className="boton boton-amarillo boton-ancho" disabled={cargando}>
                            {cargando ? 'Enviando…' : 'Recuperar contraseña'}
                        </button>
                    </form>
                )}
            </div>
        );
    }

    return (
        <div className="auth-tarjeta">
            <div className="tabs" role="tablist">
                <button type="button" role="tab" aria-selected={esLogin} className={`tab${esLogin ? ' tab-activo' : ''}`} onClick={() => cambiarModo('login')}>Iniciar sesión</button>
                <button type="button" role="tab" aria-selected={!esLogin} className={`tab${!esLogin ? ' tab-activo' : ''}`} onClick={() => cambiarModo('registro')}>Crear cuenta</button>
            </div>

            <h2>{esLogin ? 'Te damos la bienvenida' : 'Crea tu cuenta docente'}</h2>
            <p className="texto-suave">{esLogin ? 'Ingresa con tu correo institucional para continuar.' : 'Solo necesitas tu nombre, tu correo institucional y una contraseña.'}</p>

            <form onSubmit={onSubmit} className="auth-form" noValidate>
                {!esLogin && (
                    <label className={campo('nombre')}>
                        <span>Nombre completo</span>
                        <input name="nombre" autoComplete="name" placeholder="Ej. María Pérez Rojas" value={form.nombre} onChange={onChange} />
                    </label>
                )}
                <label className={campo('correo')}>
                    <span>Correo institucional</span>
                    <input name="correo" type="email" autoComplete="email" placeholder="nombre@universidad.edu.pe" value={form.correo} onChange={onChange} />
                </label>
                <label className={campo('contrasena')}>
                    <span>Contraseña</span>
                    <div className="pass">
                        <input name="contrasena" type={verPass ? 'text' : 'password'} autoComplete={esLogin ? 'current-password' : 'new-password'}
                            placeholder={esLogin ? '••••••••' : 'Mínimo 8 caracteres'} value={form.contrasena} onChange={onChange} />
                        <button type="button" className="boton-texto" onClick={() => setVerPass(!verPass)}>{verPass ? 'Ocultar' : 'Mostrar'}</button>
                    </div>
                </label>

                {error && <p className="error" role="alert">{error}</p>}

                <button type="submit" className="boton boton-amarillo boton-ancho" disabled={cargando}>
                    {cargando ? 'Un momento…' : esLogin ? 'Ingresar' : 'Crear cuenta'}
                </button>
            </form>

            {esLogin && (
                <p className="auth-alterno">
                    ¿Olvidaste tu contraseña?{' '}
                    <button type="button" className="enlace" onClick={() => cambiarModo('recuperar')}>Recupérala aquí</button>
                </p>
            )}
        </div>
    );
}

export default function LoginPage() {
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
