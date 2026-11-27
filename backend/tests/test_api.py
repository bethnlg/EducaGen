"""Pruebas de integración de la API REST (requiere instalar requirements.txt)."""
import json
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models import Usuario


def eventos(respuesta):
    return [json.loads(l[5:]) for l in respuesta.text.splitlines() if l.startswith("data:")]


@pytest.fixture(scope="module")
def cliente():
    with TestClient(app) as c:
        r = c.post("/api/auth/register", json={"nombre": "Andrea Cabanillas", "correo": "andrea@universidad.edu.pe", "contrasena": "clave-segura-1"})
        assert r.status_code == 201
        with SessionLocal() as db:
            db.query(Usuario).filter(Usuario.correo_institucional == "andrea@universidad.edu.pe").update({"estado": "activo"})
            db.commit()
        c.post("/api/auth/login", json={"correo": "andrea@universidad.edu.pe", "contrasena": "clave-segura-1"})
        yield c


def test_correo_duplicado(cliente):  # HU0001-2
    r = cliente.post("/api/auth/register", json={"nombre": "Otra", "correo": "andrea@universidad.edu.pe", "contrasena": "clave-segura-1"})
    assert r.status_code == 409


def test_registro_requiere_correo_institucional():
    with TestClient(app) as c:
        r = c.post("/api/auth/register", json={"nombre": "Docente", "correo": "docente@gmail.com", "contrasena": "clave-segura-1"})
        assert r.status_code == 400
        assert r.json()["detail"]["campos"] == ["correo"]


def test_verificacion_de_correo(monkeypatch):
    enlace = {}

    def capturar(_para, _nombre, url):
        enlace["url"] = url
        return True

    monkeypatch.setattr("app.routers.auth.correo.enviar_verificacion", capturar)
    with TestClient(app) as c:
        r = c.post("/api/auth/register", json={"nombre": "Verificado", "correo": "verificado@universidad.edu.pe", "contrasena": "clave-segura-1"})
        assert r.status_code == 201 and r.json()["requiere_verificacion"]
        url = urlparse(enlace["url"])
        resultado = c.post("/api/auth/verify", params={"token": parse_qs(url.query)["token"][0]},
                           json={"correo": parse_qs(url.query)["correo"][0]})
        assert resultado.status_code == 200
        assert c.post("/api/auth/login", json={"correo": "verificado@universidad.edu.pe", "contrasena": "clave-segura-1"}).status_code == 200


def test_login_mensaje_general():  # HU0002-2
    with TestClient(app) as c:
        r = c.post("/api/auth/login", json={"correo": "nadie@universidad.edu.pe", "contrasena": "x"})
        assert r.status_code == 401
        assert "correo o la contraseña" in r.json()["detail"]["mensaje"]


def test_recuperacion_misma_respuesta(cliente):  # HU0003-2
    a = cliente.post("/api/auth/forgot", json={"correo": "andrea@universidad.edu.pe"}).json()
    b = cliente.post("/api/auth/forgot", json={"correo": "no-existe@universidad.edu.pe"}).json()
    assert a == b


def test_datos_obligatorios(cliente):  # HU0005-2
    r = cliente.post("/api/recursos/generar", json={"tipo": "silabo", "curso": "", "temas": ""})
    assert r.status_code == 422 and set(r.json()["detail"]["campos"]) == {"curso", "temas"}


def test_cargar_archivo_de_referencia(cliente, monkeypatch, tmp_path):
    monkeypatch.setattr("app.routers.recursos.config.STORAGE_DIR", tmp_path)
    r = cliente.post("/api/recursos/archivos", files={"archivo": ("guia.txt", b"Regla de evaluacion", "text/plain")})
    assert r.status_code == 200
    assert r.json()["nombre"] == "guia.txt"
    assert "Regla de evaluacion" in r.json()["texto"]


def test_pesos_rubrica(cliente):  # HU0007-2
    r = cliente.post("/api/recursos/generar", json={"tipo": "rubrica", "curso": "Comunicación", "temas": "Redacción 30, Análisis 30"})
    assert r.status_code == 409 and r.json()["detail"]["codigo"] == "pesos_no_suman"


def test_flujo_completo(cliente):
    r = cliente.post("/api/recursos/generar", json={
        "tipo": "silabo", "curso": "Algoritmos y Estructuras de Datos",
        "temas": "Diseña algoritmos eficientes usando recursividad, árboles y grafos", "carrera": "Ingeniería de Software", "ciclo": 4,
    })
    assert r.status_code == 200
    ev = eventos(r)
    fin = ev[-1]
    assert fin["tipo"] == "fin", ev[-1]
    rid = fin["id_recurso"]

    detalle = cliente.get(f"/api/recursos/{rid}").json()
    assert detalle["conformidad_detalle"]["conforme"]

    # Asistente + aplicar al texto (HU0012)
    r = cliente.post(f"/api/recursos/{rid}/asistente", json={"mensaje": "Hazlo más breve"})
    fin_chat = eventos(r)[-1]
    assert fin_chat["tipo"] == "fin" and fin_chat["propuesta"]
    r = cliente.post(f"/api/recursos/{rid}/asistente/{fin_chat['id_mensaje']}/aplicar", json={})
    assert r.status_code == 200

    # Aprobación (HU0027, HU0025)
    vista = cliente.get(f"/api/recursos/{rid}/aprobacion").json()
    assert vista["porcentaje_editado"] > 0
    assert cliente.post(f"/api/recursos/{rid}/aprobar").json()["estado"] == "aprobado"
    versiones = cliente.get(f"/api/recursos/{rid}/versiones").json()["versiones"]
    assert versiones and versiones[0]["origen"] in ("ia", "docente")
    assert cliente.post(f"/api/recursos/{rid}/versiones/{versiones[0]['id']}/restaurar").status_code == 200

    # Exportación (HU0021)
    r = cliente.get(f"/api/recursos/{rid}/exportar", params={"formato": "docx", "membrete": True})
    assert r.status_code == 200 and len(r.content) > 1000

    # Historial, duplicar y eliminar (HU0017-HU0020)
    copia = cliente.post(f"/api/recursos/{rid}/duplicar").json()
    assert copia["titulo"].endswith("(Copia)")
    assert cliente.delete(f"/api/recursos/{copia['id']}").status_code == 200
    lista = cliente.get("/api/recursos", params={"q": "Algoritmos"}).json()
    assert [x["id"] for x in lista["recursos"]] == [rid]
    assert cliente.get("/api/recursos", params={"q": "zzz"}).json()["recursos"] == []

    # Panel de calidad (HU0032)
    panel = cliente.get("/api/calidad").json()
    assert panel["indicadores"]["recursos_auditados"] >= 1


def test_recurso_ajeno_403(cliente):  # HU0004-2
    rid = cliente.get("/api/recursos").json()["recursos"][0]["id"]
    with TestClient(app) as otro:
        otro.post("/api/auth/register", json={"nombre": "Beth Oneglio", "correo": "beth@universidad.edu.pe", "contrasena": "clave-segura-2"})
        with SessionLocal() as db:
            db.query(Usuario).filter(Usuario.correo_institucional == "beth@universidad.edu.pe").update({"estado": "activo"})
            db.commit()
        otro.post("/api/auth/login", json={"correo": "beth@universidad.edu.pe", "contrasena": "clave-segura-2"})
        assert otro.get(f"/api/recursos/{rid}").status_code == 403


def test_usuario_demo_activo():
    with TestClient(app) as c:
        r = c.post("/api/auth/login", json={"correo": "demo@universidad.edu.pe", "contrasena": "EducaGenDemo2026!"})
        assert r.status_code == 200
        assert r.json()["usuario"]["correo"] == "demo@universidad.edu.pe"


def test_eliminar_adjunto_antes_de_vincular(cliente, monkeypatch, tmp_path):
    monkeypatch.setattr("app.routers.recursos.config.STORAGE_DIR", tmp_path)
    rid = cliente.get("/api/recursos").json()["recursos"][0]["id"]
    subido = cliente.post("/api/recursos/archivos", files={"archivo": ("borrador.txt", b"Contexto temporal", "text/plain")}).json()
    assert cliente.delete(f"/api/recursos/{rid}/archivos/{subido['id']}").status_code == 200

    subido2 = cliente.post("/api/recursos/archivos", files={"archivo": ("suelto.txt", b"Otro contexto", "text/plain")}).json()
    assert cliente.delete(f"/api/recursos/archivos/{subido2['id']}").status_code == 200
