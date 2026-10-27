import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import Shell from '@/components/Shell';
import { verifySession, SESSION_COOKIE } from '@/lib/auth';

export default async function LayoutPrivado({ children }) {
    const sesion = await verifySession(cookies().get(SESSION_COOKIE)?.value);
    if (!sesion) redirect('/login');
    const usuario = { id: sesion.id, nombre: sesion.nombre, correo: sesion.correo, rol: sesion.rol };
    return <Shell usuario={usuario}>{children}</Shell>;
}
