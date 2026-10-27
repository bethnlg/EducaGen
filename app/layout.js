import './globals.css';

export const metadata = {
    title: 'EducaGen',
    description: 'Crea sílabos, rúbricas, exámenes y casos de estudio con IA en minutos.',
};

export default function RootLayout({ children }) {
    return (
        <html lang="es">
            <head>
                <link rel="preconnect" href="https://fonts.googleapis.com" />
                <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
                {/* eslint-disable-next-line @next/next/no-page-custom-font */}
                <link
                    rel="stylesheet"
                    href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&display=swap"
                />
            </head>
            <body>{children}</body>
        </html>
    );
}
