import Icono from '@/components/Icono';

export default function PanelMarca() {
    return (
        <section className="auth-marca">
            <span className="auth-logo">EducaGen</span>
            <div className="auth-mensaje">
                <h1>
                    Crea recursos académicos <span className="resaltado">en minutos</span>, no en horas.
                </h1>
                <ul>
                    <li><Icono nombre="checkCirculo" tam={20} /> Sílabos, rúbricas, exámenes y casos de estudio desde una sola pantalla</li>
                    <li><Icono nombre="checkCirculo" tam={20} /> Asistente en tiempo real para ajustar cualquier sección al instante</li>
                    <li><Icono nombre="checkCirculo" tam={20} /> Exporta con el membrete de tu universidad en un clic</li>
                </ul>
            </div>
            <small className="auth-pie">EducaGen, hecho para docentes universitarios</small>
        </section>
    );
}
