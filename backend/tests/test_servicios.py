"""Pruebas unitarias de los servicios (sin base de datos ni red)."""
import json

from app.services import esquemas, exportador, html_util, metricas
from app.services.llm.demo import generar_recurso, responder_asistente

PARAMS = {
    "silabo": {"curso": "Algoritmos", "temas": ["recursividad", "árboles", "grafos"], "semanas": 16},
    "rubrica": {"curso": "Comunicación", "criterios": [("Redacción", 50), ("Análisis", 50)], "niveles": ["Excelente", "Bueno", "Inicial"]},
    "examen": {"curso": "Bases de Datos", "temas": ["SQL", "normalización"], "num_preguntas": 6},
    "caso": {"curso": "Marketing", "temas": ["omnicanalidad"], "sector": "Retail"},
}


def test_recursos_generados_completos_y_conformes():
    for tipo, params in PARAMS.items():
        datos = json.loads(json.dumps(generar_recurso(tipo, params)))
        assert esquemas.validar_json(tipo, datos) == []
        secciones = esquemas.json_a_secciones(tipo, datos)
        assert esquemas.verificar_conformidad(tipo, secciones)["conforme"]


def test_seccion_faltante_detectada():  # HU0024-2
    secciones = esquemas.json_a_secciones("silabo", generar_recurso("silabo", PARAMS["silabo"]))
    sin_biblio = [s for s in secciones if s["clave"] != "bibliografia"]
    conf = esquemas.verificar_conformidad("silabo", sin_biblio)
    assert not conf["conforme"] and conf["faltantes"] == ["Bibliografía"]


def test_caso_requiere_cuatro_preguntas():  # HU0009-1
    datos = generar_recurso("caso", PARAMS["caso"])
    datos["preguntas_discusion"] = datos["preguntas_discusion"][:2]
    assert esquemas.validar_json("caso", datos)


def test_limpieza_de_html():  # HU0015-2
    limpio = html_util.limpiar_html('<div style="color:red">Hola <b>mundo</b><script>alert(1)</script></div>')
    assert limpio == "<p>Hola <strong>mundo</strong></p>"


def test_porcentaje_modificado():  # HU0025
    secciones = esquemas.json_a_secciones("caso", generar_recurso("caso", PARAMS["caso"]))
    contenido = {"secciones": secciones}
    assert metricas.porcentaje_modificado(contenido, contenido) == 0.0
    editado = {"secciones": [dict(s, html="<p>Texto totalmente nuevo</p>") for s in secciones]}
    assert metricas.porcentaje_modificado(contenido, editado) > 50


def test_exportacion_en_todos_los_formatos():  # HU0021
    secciones = esquemas.json_a_secciones("rubrica", generar_recurso("rubrica", PARAMS["rubrica"]))
    for formato in exportador.FORMATOS:
        datos, mime, ext = exportador.exportar(formato, "Rúbrica", secciones, membrete=True)
        assert len(datos) > 200 and ext


def test_bibliografia_marcada_por_verificar():  # HU0014
    secciones = esquemas.json_a_secciones("silabo", generar_recurso("silabo", PARAMS["silabo"]))
    respuesta = responder_asistente({"mensaje": "Agrega bibliografía APA", "secciones": secciones, "curso": "Algoritmos"})
    assert "por verificar" in respuesta and '"bibliografia"' in respuesta
