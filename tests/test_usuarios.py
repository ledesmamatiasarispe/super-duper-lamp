"""Usuarios: alta, roles, baja, contraseñas, y que nunca quede el sistema sin administrador."""
from tests.test_api import api, error  # noqa: F401  (fixture con el admin ya logueado)


def entrar(api, legajo, password):
    r = api.post("/api/auth/login", json={"legajo": legajo, "password": password}, headers={"Authorization": ""})
    return r


def como(api, token):
    return {"Authorization": f"Bearer {token}"}


def test_alta_con_contrasena_provisoria(api):
    assert "6 caracteres" in error(api.post("/api/usuarios", json={"legajo": 20, "nombre": "Juan", "password": "123"}))
    assert "legajo" in error(api.post("/api/usuarios", json={"legajo": "abc", "nombre": "Juan", "password": "123456"}))
    u = api.post("/api/usuarios", json={"legajo": 20, "nombre": "Juan", "password": "123456"}).json()
    assert (u["es_admin"], u["debe_cambiar"]) == (0, 1)
    assert "Ya existe" in error(api.post("/api/usuarios", json={"legajo": 20, "nombre": "Otro", "password": "123456"}))
    tok = entrar(api, 20, "123456").json()["token"]
    # con la provisoria solo puede ver quién es y cambiarla
    assert api.get("/api/auth/yo", headers=como(api, tok)).json()["debe_cambiar"] is True
    assert api.get("/api/equipos", headers=como(api, tok)).status_code == 403
    assert "actual no es correcta" in error(api.post("/api/auth/password", json={"actual": "mal", "nueva": "propia1"}, headers=como(api, tok)))
    assert "distinta" in error(api.post("/api/auth/password", json={"actual": "123456", "nueva": "123456"}, headers=como(api, tok)))
    assert api.post("/api/auth/password", json={"actual": "123456", "nueva": "propia1"}, headers=como(api, tok)).status_code == 200
    assert api.get("/api/equipos", headers=como(api, tok)).status_code == 200
    # un usuario común registra pero no configura ni maneja usuarios
    assert api.get("/api/usuarios", headers=como(api, tok)).status_code == 403
    assert api.post("/api/equipos", json={"nombre": "X"}, headers=como(api, tok)).status_code == 403


def test_baja_cierra_la_sesion_y_reactivar_la_devuelve(api):
    api.post("/api/usuarios", json={"legajo": 21, "nombre": "Ana", "password": "123456"})
    tok = entrar(api, 21, "123456").json()["token"]
    api.post("/api/usuarios/21/baja")
    assert api.get("/api/auth/yo", headers=como(api, tok)).status_code == 401
    assert entrar(api, 21, "123456").status_code == 401
    api.post("/api/usuarios/21/alta")
    assert entrar(api, 21, "123456").status_code == 200


def test_siempre_queda_un_administrador(api):
    assert "a vos mismo" in error(api.post("/api/usuarios/1/baja"))
    assert "único administrador" in error(api.put("/api/usuarios/1", json={"nombre": "Administrador", "es_admin": False}))
    # con un segundo administrador, el primero sí puede dejar de serlo
    api.post("/api/usuarios", json={"legajo": 30, "nombre": "Jefa", "password": "123456", "es_admin": True})
    assert api.put("/api/usuarios/1", json={"nombre": "Administrador", "es_admin": False}).json()["es_admin"] == 0
    # y el cambio de rol vale al instante: ya no puede manejar usuarios
    assert api.get("/api/usuarios").status_code == 403


def test_restablecer_contrasena(api):
    api.post("/api/usuarios", json={"legajo": 22, "nombre": "Luis", "password": "123456"})
    tok = entrar(api, 22, "123456").json()["token"]
    assert "Cambiar contraseña" in error(api.post("/api/usuarios/1/password", json={"password": "nueva123"}))
    assert api.post("/api/usuarios/22/password", json={"password": "olvido1"}).json()["debe_cambiar"] == 1
    assert api.get("/api/auth/yo", headers=como(api, tok)).status_code == 401   # sesión vieja cerrada
    assert entrar(api, 22, "123456").status_code == 401
    assert entrar(api, 22, "olvido1").json()["usuario"]["debe_cambiar"] is True


def ficha(api, legajo):
    return next((p for p in api.get("/api/opciones").json()["personas"] if p["usuario_legajo"] == legajo), None)


def test_cada_usuario_tiene_su_ficha_en_personal(api):
    assert ficha(api, 1)["nombre"] == "Administrador"   # el que ya existía también
    api.post("/api/usuarios", json={"legajo": 40, "nombre": "Carlos Díaz", "password": "123456"})
    f = ficha(api, 40)
    assert (f["nombre"], f["categoria"], f["activo"]) == ("Carlos Díaz", "interno", 1)
    # el nombre y la baja siguen al usuario
    api.put("/api/usuarios/40", json={"nombre": "Carlos A. Díaz", "es_admin": False})
    api.post("/api/usuarios/40/baja")
    f = ficha(api, 40)
    assert (f["nombre"], f["activo"]) == ("Carlos A. Díaz", 0)
    api.post("/api/usuarios/40/alta")
    assert ficha(api, 40)["activo"] == 1
    # desde Personal se edita el contacto, pero no el nombre ni el alta
    assert api.put(f"/api/personas/{f['id']}", json={"nombre": "Carlos A. Díaz", "contacto": "int. 214"}).json()["contacto"] == "int. 214"
    assert "Usuarios" in error(api.put(f"/api/personas/{f['id']}", json={"nombre": "Otro nombre"}))
    assert "Usuarios" in error(api.post(f"/api/personas/{f['id']}/baja"))


def test_operario_ya_cargado_se_vincula_sin_duplicarse(api):
    op = api.post("/api/personas", json={"nombre": "Martín López", "categoria": "interno"}).json()
    api.post("/api/usuarios", json={"legajo": 41, "nombre": "Martín López", "password": "123456"})
    assert ficha(api, 41)["id"] == op["id"]
    assert sum(p["nombre"] == "Martín López" for p in api.get("/api/opciones").json()["personas"]) == 1
    # el mismo nombre que un proveedor es otra persona: no se mezclan
    api.post("/api/personas", json={"nombre": "Frío Sur", "categoria": "externo"})
    assert "Personal ya hay otro" in error(api.post("/api/usuarios", json={"legajo": 42, "nombre": "Frío Sur", "password": "123456"}))
    assert api.get("/api/usuarios").json() and not any(u["legajo"] == 42 for u in api.get("/api/usuarios").json())
