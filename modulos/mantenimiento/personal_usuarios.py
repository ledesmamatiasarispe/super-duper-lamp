"""Todo usuario del sistema tiene su ficha en Personal (Mantenimiento interno), con el mismo nombre y la misma alta.

El núcleo maneja los usuarios; este módulo se entera de cada alta o cambio por nucleo.usuarios.AL_GUARDAR (dentro de
la misma transacción) y mantiene la ficha. personas.usuario_legajo guarda el id del usuario (que en las bases de antes
del núcleo es su legajo)."""
from nucleo import usuarios
from nucleo.db import transaccion
from nucleo.errores import ErrorDeNegocio


def sincronizar_persona(c, uid: int) -> None:
    """Deja la ficha de Personal igual al usuario. Si todavía no tiene ficha y hay un operario interno suelto con ese
    nombre, es la misma persona: se vincula. El mismo nombre en un proveedor o en la fila "Otro" es otra cosa, y se
    avisa en vez de mezclarlos."""
    u = c.execute("SELECT id, nombre, activo FROM usuarios WHERE id=?", (uid,)).fetchone()
    ficha = c.execute("SELECT id FROM personas WHERE usuario_legajo=?", (uid,)).fetchone()
    mismo_nombre = c.execute("SELECT id, categoria, pide_nombre, usuario_legajo FROM personas WHERE lower(nombre)=lower(?)",
                             (u["nombre"],)).fetchone()
    if mismo_nombre and (not ficha or mismo_nombre["id"] != ficha["id"]):
        if ficha or mismo_nombre["categoria"] != "interno" or mismo_nombre["pide_nombre"] or mismo_nombre["usuario_legajo"]:
            raise ErrorDeNegocio(f"En Personal ya hay otro '{u['nombre']}'. Usar un nombre que lo distinga (por ejemplo, con el apellido).")
        c.execute("UPDATE personas SET usuario_legajo=?, activo=? WHERE id=?", (uid, u["activo"], mismo_nombre["id"]))
        return
    if ficha:
        c.execute("UPDATE personas SET nombre=?, activo=? WHERE id=?", (u["nombre"], u["activo"], ficha["id"]))
    else:
        c.execute("INSERT INTO personas (nombre, categoria, activo, usuario_legajo) VALUES (?, 'interno', ?, ?)",
                  (u["nombre"], u["activo"], uid))


def sincronizar_todos() -> None:
    """Al arrancar: los usuarios sin ficha (el administrador de fábrica de una base nueva, o los de antes)."""
    with transaccion() as c:
        for u in c.execute("SELECT id FROM usuarios WHERE id NOT IN "
                           "(SELECT usuario_legajo FROM personas WHERE usuario_legajo IS NOT NULL)").fetchall():
            sincronizar_persona(c, u["id"])


if sincronizar_persona not in usuarios.AL_GUARDAR:
    usuarios.AL_GUARDAR.append(sincronizar_persona)
