// Iconos de trazo (24x24) usados en la interfaz
const RUTAS = {
    dashboard: 'M4 4h7v7H4zM13 4h7v4h-7zM13 10h7v10h-7zM4 13h7v7H4z',
    editor: 'M4 20h4l10.5-10.5a2.1 2.1 0 0 0-3-3L5 17v3zM13.5 6.5l3 3',
    historial: 'M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 2',
    calidad: 'M3 12h4l3-8 4 16 3-8h4',
    salir: 'M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 17l5-5-5-5M15 12H4',
    enviar: 'M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z',
    buscar: 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM21 21l-4.3-4.3',
    abrir: 'M14 4h6v6M20 4 10 14M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5',
    duplicar: 'M9 9h11v11H9zM5 15H4V4h11v1',
    eliminar: 'M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3',
    documento: 'M6 3h8l4 4v14H6zM14 3v4h4M9 12h6M9 16h6',
    check: 'M5 12.5 10 17l9-10',
    checkCirculo: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM8 12.5l3 3 5-6',
    alerta: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 8v5M12 16h.01',
    ayuda: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM9.5 9.5a2.5 2.5 0 0 1 4.8 1c0 1.7-2.3 2-2.3 3.5M12 17h.01',
    flecha: 'M6 9l6 6 6-6',
    cerrar: 'M6 6l12 12M18 6 6 18',
    regenerar: 'M20 11a8 8 0 0 0-14.3-4.9L4 8M4 4v4h4M4 13a8 8 0 0 0 14.3 4.9L20 16M20 20v-4h-4',
    negrita: 'M7 4h6a4 4 0 0 1 0 8H7zM7 12h7a4 4 0 0 1 0 8H7z',
    cursiva: 'M10 4h8M6 20h8M14 4l-4 16',
    lista: 'M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01',
    listaNum: 'M10 6h10M10 12h10M10 18h10M4 5l1.5-1v5M3.5 14.5c0-1 2.5-1 2.5.5L3.5 19H6',
    tabla: 'M3 5h18v14H3zM3 10h18M3 15h18M9 5v14M15 5v14',
    papelera: 'M4 7h16M6 7l1 13h10l1-13M9 7V4h6v3',
    restaurar: 'M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5',
    ojo: 'M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
    chispa: 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z',
    mas: 'M12 5v14M5 12h14',
};

export default function Icono({ nombre, tam = 18, grosor = 1.8, className, titulo }) {
    return (
        <svg
            width={tam}
            height={tam}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={grosor}
            strokeLinecap="round"
            strokeLinejoin="round"
            className={className}
            aria-hidden={titulo ? undefined : true}
            role={titulo ? 'img' : undefined}
        >
            {titulo && <title>{titulo}</title>}
            <path d={RUTAS[nombre] || ''} />
        </svg>
    );
}
