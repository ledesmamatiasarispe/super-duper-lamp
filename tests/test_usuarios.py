"""Usuarios (del núcleo) vistos desde mantenimiento: se entra con el legajo, y cada usuario tiene su ficha en Personal.
Las reglas generales (siempre un administrador, la baja cierra la sesión...) las prueba appbase; acá, lo que hace
mantenimiento con ellas y que sigan valiendo en esta app."""
from tests.test_api import api, error  # noqa: F401  (fixture con el admin ya logueado)


def entrar(api, usuario, password):
    return api.post("/api/auth/login", json={"usuario": str(usuario), "password": password}, headers={"Authorization": ""})


def como(token):
    return {"Authorization": f"Bearer {token}"}


def alta(api, legajo, nombre, password="123456", es_admin=False):
    return api.post("/api/usuarios", json={"usuario": str(legajo), "nombre": nombre, "password": password, "es_admin": es_admin})


def test_alta_con_contrasena_provisoria(api):
    assert "6 caracteres" in error(alta(api, 20, "Juan", "123"))
    u = alta(api, 20, "Juan").json()
    assert (u["usuario"], u["es_admin"], u["debe_cambiar"]) == ("20", 0, 1)
    assert "Ya existe" in error(alta(api, 20, "Otro"))
    tok = entrar(api, 20, "123456").json()["token"]
    # con la provisoria puede usar todo; /api/auth/yo la informa para mostrar el aviso
    assert api.get("/api/auth/yo", headers=como(tok)).json()["debe_cambiar"] is True
    assert api.get("/api/equipos", headers=como(tok)).status_code == 200
    assert api.post("/api/auth/password", json={"actual": "123456", "nueva": "propia1"}, headers=como(tok)).status_code == 200
    # un usuario común registra pero no configura ni maneja usuarios
    assert api.get("/api/usuarios", headers=como(tok)).status_code == 403
    assert api.post("/api/equipos", json={"nombre": "X"}, headers=como(tok)).status_code == 403


def test_baja_cierra_la_sesion_y_siempre_queda_un_administrador(api):
    u = alta(api, 21, "Ana").json()
    tok = entrar(api, 21, "123456").json()["token"]
    api.post(f"/api/usuarios/{u['id']}/baja")
    assert api.get("/api/auth/yo", headers=como(tok)).status_code == 401
    assert entrar(api, 21, "123456").status_code == 401
    yo = api.get("/api/auth/yo").json()
    assert "a vos mismo" in error(api.post(f"/api/usuarios/{yo['id']}/baja"))
    assert "único administrador" in error(api.put(f"/api/usuarios/{yo['id']}", json={"nombre": "Administrador", "es_admin": False}))


def ficha(api, uid):
    return next((p for p in api.get("/api/opciones").json()["personas"] if p["usuario_legajo"] == uid), None)


def test_cada_usuario_tiene_su_ficha_en_personal(api):
    assert ficha(api, api.get("/api/auth/yo").json()["id"])["nombre"] == "Administrador"   # el de fábrica también
    u = alta(api, 40, "Carlos Díaz").json()
    f = ficha(api, u["id"])
    assert (f["nombre"], f["categoria"], f["activo"]) == ("Carlos Díaz", "interno", 1)
    # el nombre y la baja siguen al usuario
    api.put(f"/api/usuarios/{u['id']}", json={"nombre": "Carlos A. Díaz", "es_admin": False})
    api.post(f"/api/usuarios/{u['id']}/baja")
    f = ficha(api, u["id"])
    assert (f["nombre"], f["activo"]) == ("Carlos A. Díaz", 0)
    api.post(f"/api/usuarios/{u['id']}/alta")
    assert ficha(api, u["id"])["activo"] == 1
    # desde Personal se edita el contacto, pero no el nombre ni el alta
    assert api.put(f"/api/personas/{f['id']}", json={"nombre": "Carlos A. Díaz", "contacto": "int. 214"}).json()["contacto"] == "int. 214"
    assert "Usuarios" in error(api.put(f"/api/personas/{f['id']}", json={"nombre": "Otro nombre"}))
    assert "Usuarios" in error(api.post(f"/api/personas/{f['id']}/baja"))


def test_operario_ya_cargado_se_vincula_sin_duplicarse(api):
    op = api.post("/api/personas", json={"nombre": "Martín López", "categoria": "interno"}).json()
    u = alta(api, 41, "Martín López").json()
    assert ficha(api, u["id"])["id"] == op["id"]
    assert sum(p["nombre"] == "Martín López" for p in api.get("/api/opciones").json()["personas"]) == 1
    # el mismo nombre que un proveedor es otra persona: no se mezclan (y el usuario no se crea)
    api.post("/api/personas", json={"nombre": "Frío Sur", "categoria": "externo"})
    assert "Personal ya hay otro" in error(alta(api, 42, "Frío Sur"))
    assert not any(x["usuario"] == "42" for x in api.get("/api/usuarios").json())
