"""¿El núcleo de esta app es el mismo que salió de appbase? Compara cada archivo con MANIFIESTO.json (su SHA-256).

Las apps NO modifican nucleo/: si hace falta un cambio, se hace en appbase y se trae con herramientas/sincronizar.py.
Cada app tiene tests/test_nucleo_intacto.py, que falla si alguien lo tocó a mano (así no se pierde en la próxima
sincronización ni se separa de las otras apps)."""
import hashlib
import json
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
MANIFIESTO = CARPETA / "MANIFIESTO.json"


def _archivos() -> dict[str, str]:
    salida = {}
    for f in sorted(CARPETA.rglob("*")):
        if f.is_file() and f != MANIFIESTO and "__pycache__" not in f.parts and f.suffix != ".pyc":
            # sin \r: el mismo archivo con fin de línea de Windows o de Linux es el mismo archivo
            salida[f.relative_to(CARPETA).as_posix()] = hashlib.sha256(f.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    return salida


def generar() -> dict:
    """Lo usa appbase al cambiar el núcleo (herramientas/manifiesto.py)."""
    from . import VERSION_NUCLEO
    datos = {"version": VERSION_NUCLEO, "archivos": _archivos()}
    MANIFIESTO.write_text(json.dumps(datos, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return datos


def cambios() -> list[str]:
    """Lo que difiere del manifiesto: 'cambiado: x', 'falta: x', 'sobra: x'. Vacío = intacto."""
    esperado = json.loads(MANIFIESTO.read_text(encoding="utf-8"))["archivos"]
    actual = _archivos()
    return ([f"cambiado: {k}" for k in esperado if k in actual and actual[k] != esperado[k]]
            + [f"falta: {k}" for k in esperado if k not in actual] + [f"sobra: {k}" for k in actual if k not in esperado])
