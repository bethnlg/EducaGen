'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';

// "Espacio de trabajo": abre el recurso editado más recientemente
export default function EspacioDeTrabajo() {
    const router = useRouter();
    const [vacio, setVacio] = useState(false);

    useEffect(() => {
        api('/api/recursos?limite=1')
            .then((d) => (d.recursos.length ? router.replace(`/editor/${d.recursos[0].id}`) : setVacio(true)))
            .catch(() => setVacio(true));
    }, [router]);

    if (!vacio) return <div className="cargando-pagina">Abriendo tu último recurso…</div>;
    return (
        <div className="pagina">
            <div className="vacio">
                <h2>Tu espacio de trabajo está vacío</h2>
                <p>Genera tu primer recurso desde el Dashboard y aquí podrás editarlo con el asistente.</p>
                <Link href="/dashboard" className="boton boton-amarillo">Crear mi primer recurso</Link>
            </div>
        </div>
    );
}
