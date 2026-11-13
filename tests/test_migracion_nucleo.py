"""Una base de UltraMantenimiento 1.0.x (usuarios por legajo) pasa al núcleo sin perder nada: cada uno sigue entrando
con su legajo y con su contraseña, su ficha de Personal sigue vinculada, y antes se copia la base."""
import sqlite3

from fastapi.testclient import TestClient

from modulos.mantenimiento import esquema
from nucleo import db
from nucleo.auth import hash_password

ESQUEMA_VIEJO = """
CREATE TABLE usuarios (legajo INTEGER PRIMARY KEY, nombre TEXT NOT NULL, password_hash TEXT NOT NULL, salt TEXT NOT NULL,
    es_admin INTEGER NOT NULL DEFAULT 0, activo INTEGER NOT NULL DEFAULT 1, debe_cambiar INTEGER NOT NULL DEFAULT 0);
CREATE TABLE sesiones (token TEXT PRIMARY KEY, legajo INTEGER NOT NULL REFERENCES usuarios(legajo), vence_en TEXT NOT NULL,
    activa INTEGER NOT NULL DEFAULT 1);
CREATE TABLE config (clave TEXT PRIMARY KEY, valor TEXT NOT NULL);
"""


def test_base_vieja_pasa_al_nucleo(tmp_path, monkeypatch):
    base = tmp_path / "mantenimiento.db"
    viejo = esquema.ESQUEMA.replace("REFERENCES usuarios(id)", "REFERENCES usuarios(legajo)")
    con = sqlite3.connect(base)
    con.executescript(ESQUEMA_VIEJO + viejo)
    for legajo, nombre, clave, admin in ((1, "Administrador", "clave-admin", 1), (57, "Matías", "propia-57", 0)):
        salt, h = hash_password(clave)
        con.execute("INSERT INTO usuarios (legajo, nombre, password_hash, salt, es_admin) VALUES (?,?,?,?,?)", (legajo, nombre, h, salt, admin))
        con.execute("INSERT INTO personas (nombre, categoria, usuario_legajo) VALUES (?, 'interno', ?)", (nombre, legajo))
    con.execute("INSERT INTO personas (nombre, categoria, pide_nombre) VALUES ('Mantenimiento interno', 'interno', 1)")
    con.execute("INSERT INTO equipos (codigo, nombre) VALUES ('EQ-001', 'Compresor')")
    con.execute("INSERT INTO config VALUES ('ejemplos_cargados', '1')")
    con.commit()
    con.close()

    monkeypatch.setattr(db, "DB_PATH", base)
    from app.main import app
    with TestClient(app) as api:
        r = api.post("/api/auth/login", json={"usuario": "57", "password": "propia-57"})   # con su legajo, como siempre
        assert r.status_code == 200, r.text
        assert r.json()["usuario"] == {"id": 57, "usuario": "57", "nombre": "Matías", "es_admin": False, "debe_cambiar": False}
        h = {"Authorization": "Bearer " + r.json()["token"]}
        assert api.get("/api/auth/yo", headers=h).json()["id"] == 57
        personas = api.get("/api/opciones", headers=h).json()["personas"]
        assert next(p for p in personas if p["nombre"] == "Matías")["usuario_legajo"] == 57   # la ficha sigue vinculada
        assert len([p for p in personas if p["nombre"] == "Matías"]) == 1
        assert [e["codigo"] for e in api.get("/api/equipos", headers=h).json()] == ["EQ-001"]   # no cargó ejemplos encima
        tok = api.post("/api/auth/login", json={"usuario": "1", "password": "clave-admin"}).json()["token"]
        nuevo = api.post("/api/usuarios", json={"usuario": "60", "nombre": "Nuevo", "password": "123456"},
                         headers={"Authorization": "Bearer " + tok}).json()
        assert nuevo["id"] > 57 and nuevo["usuario"] == "60"
    assert (tmp_path / "mantenimiento_antes_del_nucleo.db").exists()   # la copia de antes
    con = sqlite3.connect(base)
    assert not con.execute("PRAGMA foreign_key_check").fetchall()
    con.close()
