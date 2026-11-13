"""Instructivos enriquecidos: bloques de contenido, detalle por actividad y adjuntos (imágenes y archivos)."""
from nucleo import db
from tests.test_api import api, error  # noqa: F401  (fixture con el admin ya logueado)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.4\n%prueba\n"


def it01(api):
    return next(i for i in api.get("/api/instructivos").json() if i["codigo"] == "IT01")["id"]


def subir(api, it_id, nombre, datos):
    return api.post(f"/api/instructivos/{it_id}/adjuntos", files={"archivo": (nombre, datos)})


def contenido(api, it_id, **cambios):
    """El contenido actual listo para mandar como revisión, con los cambios pedidos."""
    c = api.get(f"/api/instructivos/{it_id}").json()
    base = {k: c[k] for k in ("titulo", "descripcion", "seguridad", "repuestos", "bloques")}
    base["archivos"] = [a["id"] for a in c["archivos"]]
    base["secciones"] = [{"letra": s["letra"], "actividades": s["actividades"]} for s in c["secciones"]]
    return {**base, "motivo": "prueba", **cambios}


def test_subida_valida_queda_en_la_carpeta_de_la_app(api):
    a = subir(api, it01(api), "foto compresor.png", PNG).json()
    assert (a["nombre"], a["es_imagen"], a["tamanio"]) == ("foto compresor.png", 1, len(PNG))
    guardados = list((db.DB_PATH.parent / "adjuntos" / "IT01").iterdir())
    assert len(guardados) == 1 and guardados[0].name != "foto compresor.png" and guardados[0].read_bytes() == PNG
    r = api.get(f"/api/adjuntos/{a['id']}")
    assert r.status_code == 200 and r.content == PNG and r.headers["content-type"] == "image/png"
    assert r.headers["x-content-type-options"] == "nosniff"


def test_subidas_invalidas(api):
    it = it01(api)
    assert "no admitido" in error(subir(api, it, "virus.exe", b"MZ\x90\x00"))
    assert "no admitido" in error(subir(api, it, "sin_extension", PNG))
    assert "no es un .png" in error(subir(api, it, "trucho.png", b"MZ ejecutable renombrado"))
    assert "no es un .pdf" in error(subir(api, it, "manual.pdf", PNG))
    assert "vacío" in error(subir(api, it, "vacio.pdf", b""))
    from modulos.mantenimiento import servicios
    grande = b"%PDF" + b"0" * servicios.MAX_ADJUNTO
    assert "máximo" in error(subir(api, it, "enorme.pdf", grande))
    # un nombre con carpetas no sale de data/adjuntos: se usa solo para mostrar
    a = subir(api, it, "..\\..\\..\\app\\main.png", PNG).json()
    assert a["nombre"] == "main.png"
    a = subir(api, it, "../../etc/passwd.txt", b"hola").json()
    assert a["nombre"] == "passwd.txt"
    assert all(p.parent.name == "IT01" for p in (db.DB_PATH.parent / "adjuntos").rglob("*") if p.is_file())


def test_descarga_sin_sesion_rechazada(api):
    a = subir(api, it01(api), "plano.pdf", PDF).json()
    assert api.get(f"/api/adjuntos/{a['id']}", headers={"Authorization": ""}).status_code == 401
    assert api.get(f"/api/adjuntos/{a['id']}", headers={"Authorization": "Bearer inventado"}).status_code == 401
    assert api.get("/api/adjuntos/9999").status_code == 404


def test_bloques_y_detalle_por_actividad(api):
    it = it01(api)
    img = subir(api, it, "esquema.png", PNG).json()
    pdf = subir(api, it, "manual.pdf", PDF).json()
    c = contenido(api, it)
    c["secciones"][0]["actividades"][0]["detalle"] = "Soplar con aire seco\nNo usar solvente"
    c["bloques"] = [
        {"tipo": "tabla", "ubicacion": "general", "datos": {"encabezado": True, "filas": [["Dato", "Valor"], ["Presión", "8 bar"]]}},
        {"tipo": "nota", "ubicacion": "B", "datos": {"nivel": "peligro", "texto": "Aceite caliente"}},
        {"tipo": "imagen", "ubicacion": "A", "datos": {"adjunto_id": img["id"], "epigrafe": "Filtro de aire"}},
        {"tipo": "grafico", "ubicacion": "general", "datos": {"forma": "barras", "filas": [["Ene", "1,5"], ["Feb", 2]]}},
    ]
    c["archivos"] = [pdf["id"]]
    nuevo = api.put(f"/api/instructivos/{it}", json=c).json()
    assert nuevo["secciones"][0]["actividades"][0]["detalle"] == "Soplar con aire seco\nNo usar solvente"
    assert [b["tipo"] for b in nuevo["bloques"]] == ["tabla", "nota", "imagen", "grafico"]
    assert nuevo["bloques"][3]["datos"]["filas"] == [["Ene", 1.5], ["Feb", 2.0]]
    assert [a["nombre"] for a in nuevo["archivos"]] == ["manual.pdf"]
    # validaciones de forma
    malo = dict(c, bloques=[{"tipo": "imagen", "ubicacion": "Z", "datos": {"adjunto_id": img["id"]}}])
    assert "sección Z" in error(api.put(f"/api/instructivos/{it}", json=malo))
    malo = dict(c, bloques=[{"tipo": "imagen", "datos": {"adjunto_id": pdf["id"]}}])
    assert "tiene que usar una imagen" in error(api.put(f"/api/instructivos/{it}", json=malo))
    malo = dict(c, bloques=[{"tipo": "grafico", "datos": {"filas": [["Ene", "mucho"]]}}])
    assert "no es un número" in error(api.put(f"/api/instructivos/{it}", json=malo))
    malo = dict(c, bloques=[{"tipo": "script", "datos": {}}])
    assert "tipo desconocido" in error(api.put(f"/api/instructivos/{it}", json=malo))
    # un adjunto de otro instructivo no se puede usar
    it2 = next(i for i in api.get("/api/instructivos").json() if i["codigo"] == "IT02")["id"]
    ajeno = subir(api, it2, "otra.png", PNG).json()
    assert "no es de este instructivo" in error(api.put(f"/api/instructivos/{it}", json=dict(c, archivos=[ajeno["id"]])))


def test_revision_vieja_conserva_sus_imagenes_y_no_se_borran(api):
    it = it01(api)
    img = subir(api, it, "antes.png", PNG).json()
    con_imagen = contenido(api, it, bloques=[{"tipo": "imagen", "ubicacion": "general", "datos": {"adjunto_id": img["id"]}}])
    rev = api.put(f"/api/instructivos/{it}", json=con_imagen).json()["revision"]            # rev 1: con la imagen
    sin_imagen = contenido(api, it, bloques=[])
    api.put(f"/api/instructivos/{it}", json=sin_imagen)                                    # rev 2: se la sacó
    actual = api.get(f"/api/instructivos/{it}").json()
    assert actual["bloques"] == [] and next(a for a in actual["adjuntos"] if a["id"] == img["id"])["en_uso"] is True
    vieja = api.get(f"/api/instructivos/{it}/revisiones/{rev}").json()
    assert vieja["bloques"][0]["datos"]["adjunto_id"] == img["id"]
    assert api.get(f"/api/adjuntos/{img['id']}").status_code == 200                         # la imagen sigue
    assert "revisión anterior" in error(api.delete(f"/api/adjuntos/{img['id']}"))
    # uno subido de más, que ninguna revisión usó, sí se borra (y desaparece de la carpeta)
    sobra = subir(api, it, "sobra.pdf", PDF).json()
    assert api.delete(f"/api/adjuntos/{sobra['id']}").status_code == 200
    assert api.get(f"/api/adjuntos/{sobra['id']}").status_code == 404
    assert len(list((db.DB_PATH.parent / "adjuntos" / "IT01").iterdir())) == 1


def test_solo_admin_sube_y_borra(api):
    api.post("/api/usuarios", json={"usuario": "50", "nombre": "Operario", "password": "123456"})
    tok = api.post("/api/auth/login", json={"usuario": "50", "password": "123456"}, headers={"Authorization": ""}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    api.post("/api/auth/password", json={"actual": "123456", "nueva": "propia1"}, headers=h)
    it = it01(api)
    assert api.post(f"/api/instructivos/{it}/adjuntos", files={"archivo": ("a.png", PNG)}, headers=h).status_code == 403
    a = subir(api, it, "a.png", PNG).json()
    assert api.get(f"/api/adjuntos/{a['id']}", headers=h).status_code == 200      # ver, sí
    assert api.delete(f"/api/adjuntos/{a['id']}", headers=h).status_code == 403


def test_crear_con_imagen_pide_crear_primero_y_eliminar_borra_archivos(api):
    nuevo = api.post("/api/instructivos", json={"titulo": "Prueba", "secciones": [{"letra": "A", "actividades": [{"texto": "Algo"}]}],
                                                "archivos": [1]})
    assert "Primero hay que crear" in error(nuevo)
    nuevo = api.post("/api/instructivos", json={"titulo": "Prueba", "secciones": [{"letra": "A", "actividades": [{"texto": "Algo"}]}]}).json()
    subir(api, nuevo["id"], "x.png", PNG)
    carpeta = db.DB_PATH.parent / "adjuntos" / nuevo["codigo"]
    assert carpeta.exists()
    assert api.delete(f"/api/instructivos/{nuevo['id']}").status_code == 200
    assert not carpeta.exists()
