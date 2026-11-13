"""La base común: nombre y logo, puerto y /api/version (app/marca.py, app/puerto.py, app/rutas_base.py).

MISMO ARCHIVO en UltraMantenimiento, Gestión Automotor y Edificios de Mamá. La fixture `admin` es el cliente con el
administrador ya logueado de cada app: `api` (tests/test_api.py) o `cliente` (conftest.py de Edificios de Mamá)."""
import socket

import pytest

from app import db, puerto as pto
from app import version as v

try:
    from tests.test_api import api  # noqa: F401  (UltraMantenimiento y Gestión Automotor)
    _FIXTURE = "api"
except ImportError:
    _FIXTURE = "cliente"   # Edificios de Mamá: la define conftest.py

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture()
def admin(request):
    return request.getfixturevalue(_FIXTURE)


def error(r, status=400):
    assert r.status_code == status, r.text
    return r.json()["detail"]


def ocupar():
    s = socket.socket()
    s.bind(("0.0.0.0", 0))
    s.listen()
    return s, s.getsockname()[1]


def test_version_dice_que_app_es(admin):
    r = admin.get("/api/version", headers={"Authorization": ""})   # sin sesión
    assert r.json() == {"version": v.VERSION, "app": v.APP}


def test_la_pagina_pide_sus_archivos_con_la_version(admin):
    pagina = admin.get("/").text
    assert f'.js?v={v.VERSION}"' in pagina and f'.css?v={v.VERSION}"' in pagina and "/static/comun.js" in pagina


def test_nombre_y_logo_de_la_app(admin):
    sin_sesion = {"Authorization": ""}
    fabrica = {"nombre": v.NOMBRE, "propio": False, "logo": None, "defecto": v.NOMBRE}
    assert admin.get("/api/marca").json() == fabrica
    assert f"<title>{v.NOMBRE}</title>" in admin.get("/").text
    # el nombre se ve también en el login (sin sesión) y va escapado
    assert admin.put("/api/marca/nombre", json={"nombre": "  Taller   <Romero> "}).json()["nombre"] == "Taller <Romero>"
    pagina = admin.get("/", headers=sin_sesion).text
    assert "<title>Taller &lt;Romero&gt;</title>" in pagina and "<Romero>" not in pagina
    assert "40 caracteres" in error(admin.put("/api/marca/nombre", json={"nombre": "x" * 41}))
    # el logo: solo imágenes de verdad
    assert "imagen" in error(admin.post("/api/marca/logo", files={"archivo": ("logo.exe", b"MZ", "image/png")}))
    assert "no es un .png" in error(admin.post("/api/marca/logo", files={"archivo": ("logo.png", b"MZ\x00", "image/png")}))
    logo = admin.post("/api/marca/logo", files={"archivo": ("logo.png", PNG, "image/png")}).json()["logo"]
    pagina = admin.get("/", headers=sin_sesion).text
    assert f"/api/marca/logo?v={logo}" in pagina and "/static/icono.svg" not in pagina and 'type="image/png"' in pagina
    r = admin.get("/api/marca/logo", headers=sin_sesion)
    assert r.content == PNG and "default-src 'none'" in r.headers["content-security-policy"]
    # uno nuevo reemplaza al anterior (y borra su archivo); volver a los de fábrica
    otro = admin.post("/api/marca/logo", files={"archivo": ("logo.svg", b'<svg xmlns="http://www.w3.org/2000/svg"/>',
                                                            "image/svg+xml")}).json()["logo"]
    assert otro != logo and not (db.DB_PATH.parent / "marca" / logo).exists()
    assert admin.delete("/api/marca/logo").json()["logo"] is None and not (db.DB_PATH.parent / "marca" / otro).exists()
    assert admin.put("/api/marca/nombre", json={"nombre": ""}).json() == fabrica
    assert "/static/icono.svg" in admin.get("/").text
    assert admin.get("/api/marca/logo").status_code == 404


def test_elegir_el_puerto_en_opciones(admin, monkeypatch):
    monkeypatch.delenv(pto.VARIABLE, raising=False)
    monkeypatch.delenv(pto.VARIABLE_ACTUAL, raising=False)
    assert admin.get("/api/puerto").json()["elegido"] == v.PUERTO
    assert "entre" in error(admin.put("/api/puerto", json={"puerto": 80}))
    s, ocupado = ocupar()
    with s:
        assert "otro programa" in error(admin.put("/api/puerto", json={"puerto": ocupado}))
    libre = ocupar()
    libre[0].close()
    assert admin.put("/api/puerto", json={"puerto": libre[1]}).json()["elegido"] == libre[1]
    assert pto.configurado() == libre[1]
    # la variable manda sobre lo elegido, y entonces no se cambia desde la app
    monkeypatch.setenv(pto.VARIABLE, "9999")
    assert pto.configurado() == 9999 and "variable" in error(admin.put("/api/puerto", json={"puerto": 9100}))


def test_al_arrancar_esquiva_un_puerto_ocupado(monkeypatch):
    s, ocupado = ocupar()
    with s:
        monkeypatch.delenv(pto.VARIABLE, raising=False)
        monkeypatch.setattr(pto, "configurado", lambda: ocupado)
        monkeypatch.setattr(pto, "quien_atiende", lambda p: None)   # lo ocupa otro programa
        puerto, ya_abierta = pto.al_arrancar()
        assert puerto > ocupado and not ya_abierta
        monkeypatch.setattr(pto, "quien_atiende", lambda p: v.APP)   # lo ocupa esta misma app: se reusa
        assert pto.al_arrancar() == (ocupado, True)
