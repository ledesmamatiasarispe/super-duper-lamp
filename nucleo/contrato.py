"""El CONTRATO del núcleo: todo lo que un módulo o una app pueden usar. Se extrae del código (no se escribe a mano):

  python    los nombres públicos (sin _) de cada archivo del núcleo, con la firma de funciones y clases
  modulo    los campos de Modulo y Menu, y los parámetros de configurar()
  api       las rutas HTTP del núcleo (método + camino)
  base      las tablas del núcleo y sus columnas
  js        lo global de nucleo.js, las claves de Nucleo y de Ayuda (y Ayuda.h)
  css       las variables (--azul...) y las clases de nucleo.css

herramientas/contrato.py lo guarda en docs/contrato.json y tests/test_contrato.py exige que esté al día. Sacar o
cambiar algo del contrato es un cambio INCOMPATIBLE: sube la versión mayor (2.0) y lleva una nota en NOVEDADES.md
con lo que cada app tiene que cambiar (ver docs/reglas.md)."""
import dataclasses
import importlib
import inspect
import re
import sqlite3
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
MODULOS_PY = ("ajustes", "errores", "validar", "db", "auth", "usuarios", "adjuntos", "marca", "puerto", "actualizador",
              "modulo", "aplicacion", "arranque", "intacto", "chequeo")


def _firma(obj) -> str:
    if dataclasses.is_dataclass(obj):
        return "campos(" + ", ".join(f.name + ("=" if f.default is not dataclasses.MISSING
                                               or f.default_factory is not dataclasses.MISSING else "")
                                     for f in dataclasses.fields(obj)) + ")"
    if inspect.isclass(obj):
        return "clase"
    try:
        params = inspect.signature(obj).parameters.values()
    except (TypeError, ValueError):
        return "función"
    partes = []
    for p in params:
        pref = "*" if p.kind == p.VAR_POSITIONAL else "**" if p.kind == p.VAR_KEYWORD else ""
        partes.append(pref + p.name + ("=" if p.default is not p.empty else ""))
    return "(" + ", ".join(partes) + ")"


def _python() -> dict:
    salida = {}
    for nombre in MODULOS_PY:
        m = importlib.import_module(f"nucleo.{nombre}")
        nombres = {}
        for k, v in vars(m).items():
            if k.startswith("_") or inspect.ismodule(v):
                continue
            if (inspect.isfunction(v) or inspect.isclass(v)) and getattr(v, "__module__", "") != m.__name__:
                continue   # importado de otro lado: es del contrato de ese otro archivo
            if inspect.isfunction(v) or inspect.isclass(v):
                nombres[k] = _firma(v)
            elif k.isupper():
                nombres[k] = "constante"
        salida[nombre] = dict(sorted(nombres.items()))
    return salida


def _api() -> list[str]:
    from .aplicacion import crear_app
    rutas = []
    for r in crear_app([]).routes:
        for metodo in sorted(getattr(r, "methods", None) or ["MOUNT"]):
            if metodo != "HEAD":
                rutas.append(f"{metodo} {r.path}")
    return sorted(set(rutas))


def _base() -> dict:
    from .db import ESQUEMA
    c = sqlite3.connect(":memory:")
    c.executescript(ESQUEMA)
    tablas = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    return {t: [r[1] for r in c.execute(f"PRAGMA table_info({t})")] for t in sorted(tablas)}


def _claves(objeto: str) -> list[str]:
    """Las claves de un objeto literal de JavaScript ({ a, b: x, c: () => f(1, 2) }): se vacía lo anidado y se toma
    lo que va antes de cada ':' (o el nombre solo, si es abreviado)."""
    while True:
        nuevo = re.sub(r"\([^()]*\)|\{[^{}]*\}|\[[^\[\]]*\]", "", objeto)
        if nuevo == objeto:
            break
        objeto = nuevo
    return sorted({p.split(":")[0].strip() for p in objeto.split(",") if p.strip()})


def _js() -> dict:
    nucleo = (CARPETA / "frontend" / "nucleo.js").read_text(encoding="utf-8")
    ayuda = (CARPETA / "frontend" / "ayuda.js").read_text(encoding="utf-8")
    globales = sorted(n for n in set(re.findall(r"^(?:const|let|var|function|async function)\s+([A-Za-z_$][\w$]*)", nucleo, re.M))
                      if not n.startswith("_"))   # con _ es interno (regla del contrato)
    obj_ayuda = re.search(r"window\.Ayuda = \{(.*?)\};", ayuda, re.S).group(1)
    return {"globales": globales, "Nucleo": _claves(re.search(r"const Nucleo = \{([^}]*)\}", nucleo).group(1)),
            "Ayuda": _claves(obj_ayuda), "Ayuda.h": _claves(re.search(r"h: \{([^}]*)\}", obj_ayuda).group(1))}


def _css() -> dict:
    css = (CARPETA / "frontend" / "nucleo.css").read_text(encoding="utf-8")
    sin_comentarios = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return {"variables": sorted(set(re.findall(r"(--[\w-]+)\s*:", sin_comentarios))),
            "clases": sorted(set(re.findall(r"\.([a-zA-Z][\w-]*)", re.sub(r"\{[^}]*\}", "{}", sin_comentarios))))}


def extraer() -> dict:
    from . import VERSION_NUCLEO
    from .modulo import Menu, Modulo
    from .ajustes import configurar
    return {"version": VERSION_NUCLEO, "python": _python(),
            "modulo": {"Modulo": _firma(Modulo), "Menu": _firma(Menu), "configurar": _firma(configurar)},
            "api": _api(), "base": _base(), "js": _js(), "css": _css()}


def _planos(d, prefijo="") -> dict:
    """{"python.db.transaccion": "()", "api.GET /api/version": True, ...} para comparar dos contratos."""
    salida = {}
    if isinstance(d, dict):
        for k, v in d.items():
            if k == "version":
                continue
            salida.update(_planos(v, f"{prefijo}{k}."))
    elif isinstance(d, list):
        for v in d:
            salida[f"{prefijo}{v}"] = True
    else:
        salida[prefijo.rstrip(".")] = d
    return salida


def _compatible(viejo, nuevo) -> bool:
    """Una firma nueva es compatible si conserva cada parámetro (o campo) viejo en el mismo orden y lo que agrega tiene
    valor por defecto."""
    if not (isinstance(viejo, str) and isinstance(nuevo, str) and viejo.endswith(")") and nuevo.endswith(")")):
        return viejo == nuevo
    lista = lambda f: [p.strip() for p in f[f.index("(") + 1:-1].split(",") if p.strip()]  # noqa: E731
    v, n = lista(viejo), lista(nuevo)
    return n[:len(v)] == v and all(p.endswith("=") or p.startswith("*") for p in n[len(v):])


def comparar(viejo: dict, nuevo: dict) -> dict:
    """agregado / quitado / cambiado (incompatible) / ampliado (compatible: parámetros nuevos con valor por defecto)."""
    a, b = _planos(viejo), _planos(nuevo)
    cambiados = [k for k in a if k in b and a[k] != b[k]]
    return {"agregado": sorted(k for k in b if k not in a), "quitado": sorted(k for k in a if k not in b),
            "cambiado": sorted(k for k in cambiados if not _compatible(a[k], b[k])),
            "ampliado": sorted(k for k in cambiados if _compatible(a[k], b[k]))}
