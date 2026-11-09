// Cada logo se solicita al sitio oficial de la universidad. Google solo se usa
// como respaldo cuando el sitio no publica su favicon.
export const UNIVERSIDADES_PRIVADAS_LIMA = [
    { clave: 'upc', nombre: 'Universidad Peruana de Ciencias Aplicadas', dominio: 'upc.edu.pe' },
    { clave: 'pucp', nombre: 'Pontificia Universidad Católica del Perú', dominio: 'pucp.edu.pe' },
    { clave: 'ulima', nombre: 'Universidad de Lima', dominio: 'ulima.edu.pe' },
    { clave: 'up', nombre: 'Universidad del Pacífico', dominio: 'up.edu.pe' },
    { clave: 'usil', nombre: 'Universidad San Ignacio de Loyola', dominio: 'usil.edu.pe' },
    { clave: 'usmp', nombre: 'Universidad de San Martín de Porres', dominio: 'usmp.edu.pe' },
    { clave: 'urp', nombre: 'Universidad Ricardo Palma', dominio: 'urp.edu.pe' },
    { clave: 'upch', nombre: 'Universidad Peruana Cayetano Heredia', dominio: 'upch.edu.pe' },
    { clave: 'esan', nombre: 'Universidad ESAN', dominio: 'esan.edu.pe' },
    { clave: 'cientifica', nombre: 'Universidad Científica del Sur', dominio: 'cientifica.edu.pe' },
    { clave: 'upn', nombre: 'Universidad Privada del Norte', dominio: 'upn.edu.pe' },
    { clave: 'utp', nombre: 'Universidad Tecnológica del Perú', dominio: 'utp.edu.pe' },
    { clave: 'wiener', nombre: 'Universidad Norbert Wiener', dominio: 'uwiener.edu.pe' },
    { clave: 'autonoma', nombre: 'Universidad Autónoma del Perú', dominio: 'autonoma.edu.pe' },
    { clave: 'ucv', nombre: 'Universidad César Vallejo', dominio: 'ucv.edu.pe' },
    { clave: 'uarm', nombre: 'Universidad Antonio Ruiz de Montoya', dominio: 'uarm.edu.pe' },
    { clave: 'unife', nombre: 'Universidad Femenina del Sagrado Corazón', dominio: 'unife.edu.pe' },
    { clave: 'umch', nombre: 'Universidad Marcelino Champagnat', dominio: 'umch.edu.pe' },
    { clave: 'ucss', nombre: 'Universidad Católica Sedes Sapientiae', dominio: 'ucss.edu.pe' },
    { clave: 'upsjb', nombre: 'Universidad Privada San Juan Bautista', dominio: 'upsjb.edu.pe' },
];

export const universidadPorClave = (clave) =>
    UNIVERSIDADES_PRIVADAS_LIMA.find((universidad) => universidad.clave === clave);

export const urlLogoUniversidad = (universidad) =>
    universidad ? `https://${universidad.dominio}/favicon.ico` : '';

export const urlLogoRespaldo = (universidad) =>
    universidad ? `https://www.google.com/s2/favicons?domain=${universidad.dominio}&sz=128` : '';
