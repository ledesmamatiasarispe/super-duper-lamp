"""Actualizaciones desde los releases de GitHub (GitHub simulado: nunca se sale a internet en los tests)."""
import hashlib
import io
import json
import zipfile
from datetime import date, timedelta

import pytest

from app import actualizador as act
from tests.test_api import api, error  # noqa: F401  (fixture con el admin ya logueado)


def zip_con(archivos: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for nombre, datos in archivos.items():
            z.writestr(nombre, datos)
    return buf.getvalue()


@pytest.fixture()
def github(monkeypatch):
    """Un release v9.0.0 con su .zip y .sha256. Devuelve el dict de respuestas por URL, para cambiarlas en cada test."""
    paquete = zip_con({"MantenimientoRomero/MantenimientoRomero.exe": b"MZ nuevo", "MantenimientoRomero/_internal/x.txt": b"x"})
    respuestas = {
        act.API.format(repo="romero/mantenimiento"): json.dumps({
            "tag_name": "v9.0.0", "body": "- Novedad 1\n- Novedad 2", "html_url": "https://github.com/romero/mantenimiento/releases/v9.0.0",
            "assets": [{"name": "MantenimientoRomero-v9.0.0-win64.zip", "browser_download_url": "https://x/zip"},
                       {"name": "MantenimientoRomero-v9.0.0-win64.zip.sha256", "browser_download_url": "https://x/sha"}]}).encode(),
        "https://x/zip": paquete,
        "https://x/sha": (hashlib.sha256(paquete).hexdigest() + "  MantenimientoRomero-v9.0.0-win64.zip\n").encode(),
    }

    def pedir(url, timeout=10):
        if isinstance(respuestas.get(url), Exception):
            raise respuestas[url]
        return respuestas[url]

    monkeypatch.setattr(act, "_pedir", pedir)
    monkeypatch.setattr(act.v, "REPO", "romero/mantenimiento")
    act._estado.clear()
    yield respuestas
    act._estado.clear()


def test_comparar_versiones():
    assert act.es_mas_nueva("v1.0.1", "1.0.0") and act.es_mas_nueva("v1.10.0", "1.9.9") and act.es_mas_nueva("2.0", "1.9.9")
    assert not act.es_mas_nueva("v1.0.0", "1.0.0") and not act.es_mas_nueva("v0.9.9", "1.0.0")
    assert not act.es_mas_nueva("v1.0.0-beta", "1.0.0")


def test_sin_repositorio_no_busca(api, monkeypatch):
    monkeypatch.setattr(act.v, "REPO", "")
    act._estado.clear()
    a = api.get("/api/actualizacion").json()
    assert a["repo"] == "" and not a["disponible"] and not a["preguntar"] and "repositorio" in a["error"]


def test_hay_version_nueva_y_se_pregunta_solo_compilada(api, github, monkeypatch):
    a = api.get("/api/actualizacion").json()
    assert a["disponible"] and a["nueva"] == "v9.0.0" and a["instalable"] and "Novedad 1" in a["notas"]
    assert not a["preguntar"]   # en desarrollo no se pregunta: no se puede instalar sola
    monkeypatch.setattr(act.v, "COMPILADA", True)
    assert api.get("/api/actualizacion").json()["preguntar"]
    # "Ahora no": una semana sin preguntar
    hasta = api.post("/api/actualizacion/posponer").json()["pospuesta_hasta"]
    assert hasta == (date.today() + timedelta(days=7)).isoformat()
    a = api.get("/api/actualizacion").json()
    assert not a["preguntar"] and a["pospuesta_hasta"] == hasta and a["disponible"]


def test_pasada_la_semana_vuelve_a_preguntar(api, github, monkeypatch):
    from app.db import transaccion
    monkeypatch.setattr(act.v, "COMPILADA", True)
    with transaccion() as c:
        c.execute("INSERT INTO config VALUES ('actualizacion_pospuesta_hasta', ?)", ((date.today()).isoformat(),))
    assert api.get("/api/actualizacion").json()["preguntar"]


def test_sin_sha256_no_es_instalable_y_sin_internet_no_rompe(api, github):
    rel = json.loads(github[act.API.format(repo="romero/mantenimiento")])
    rel["assets"] = rel["assets"][:1]
    github[act.API.format(repo="romero/mantenimiento")] = json.dumps(rel).encode()
    assert not api.post("/api/actualizacion/buscar").json()["instalable"]
    github[act.API.format(repo="romero/mantenimiento")] = OSError("sin red")
    a = api.post("/api/actualizacion/buscar").json()
    assert "No se pudo consultar GitHub" in a["error"] and not a["disponible"]
    # un repositorio sin ningún release todavía no es un error: simplemente no hay versión nueva
    github[act.API.format(repo="romero/mantenimiento")] = act.urllib.error.HTTPError("u", 404, "Not Found", {}, None)
    a = api.post("/api/actualizacion/buscar").json()
    assert a["error"] is None and not a["disponible"]


def test_preparar_controla_el_hash_y_descomprime(github, tmp_path):
    info = act.buscar(forzar=True)
    carpeta = act.preparar(info, tmp_path / "actualizacion")
    assert (carpeta / "MantenimientoRomero.exe").read_bytes() == b"MZ nuevo"
    github["https://x/sha"] = b"0" * 64
    with pytest.raises(act.ErrorDeNegocio, match="SHA-256"):
        act.preparar(info, tmp_path / "actualizacion")


def test_un_zip_con_rutas_peligrosas_no_se_instala(tmp_path):
    malo = tmp_path / "malo.zip"
    malo.write_bytes(zip_con({"../../fuera.txt": b"x", "MantenimientoRomero.exe": b"MZ"}))
    with pytest.raises(act.ErrorDeNegocio, match="rutas inválidas"):
        act._extraer(malo, tmp_path / "nueva")
    assert not (tmp_path.parent / "fuera.txt").exists()
    sin_exe = tmp_path / "sin_exe.zip"
    sin_exe.write_bytes(zip_con({"otro.txt": b"x"}))
    with pytest.raises(act.ErrorDeNegocio, match="no trae"):
        act._extraer(sin_exe, tmp_path / "nueva2")


def test_instalar_y_permisos(api, github):
    assert "versión compilada" in error(api.post("/api/actualizacion/instalar"))   # en desarrollo, no
    assert api.get("/api/version").json()["version"] == act.v.VERSION
    assert api.get("/api/version", headers={"Authorization": ""}).status_code == 200   # sin sesión: se usa al reiniciar
    # un usuario común ve si hay versión nueva, pero no se le pregunta ni puede instalar
    api.post("/api/usuarios", json={"legajo": 50, "nombre": "Operario", "password": "provisoria", "es_admin": False})
    otro = api.post("/api/auth/login", json={"legajo": 50, "password": "provisoria"}).json()["token"]
    h = {"Authorization": f"Bearer {otro}"}
    api.post("/api/auth/password", json={"actual": "provisoria", "nueva": "propia-123"}, headers=h)
    assert api.get("/api/actualizacion", headers=h).json()["preguntar"] is False
    assert api.post("/api/actualizacion/instalar", headers=h).status_code == 403
    assert api.post("/api/actualizacion/posponer", headers=h).status_code == 403
