"""NÚCLEO: la base común de las apps (UltraMantenimiento, Gestión Automotor APB, Edificios de Mamá...).

LAS APPS NO MODIFICAN ESTA CARPETA. La reciben tal cual (herramientas/sincronizar.py) y construyen encima con MÓDULOS
(ver nucleo/modulo.py). Una mejora del núcleo se hace en el repositorio appbase y se lleva a todas las apps.
Como todo lo propio de un negocio vive en módulos, dos apps se pueden fusionar activando los módulos de las dos sobre el
mismo núcleo.

Qué trae:
  ajustes      identidad de la app (APP, NOMBRE, PREFIJO, PUERTO, VERSION, REPO): la pone la app con configurar()
  errores      ErrorDeNegocio (400 con su mensaje) y NoEncontrado (404)
  validar      texto, numero, fecha, opcion... (el texto crudo del formulario entra acá, nunca convertido en la ruta)
  db           SQLite: transaccion() con BEGIN IMMEDIATE (varios usuarios escriben de a uno), reentrante con SAVEPOINT;
               el esquema de cada módulo y sus columnas nuevas se aplican al arrancar
  auth         sesiones con token Bearer, contraseñas con PBKDF2; la provisoria NO bloquea (la pantalla avisa)
  usuarios     alta, rol, baja, restablecer y cambiar contraseña; siempre queda un administrador
  adjuntos     archivos subidos validados por su contenido (firma), guardados con nombre aleatorio
  marca        nombre y logo de la app, editables desde Opciones
  puerto       puerto editable; al arrancar esquiva uno ocupado y si la app ya estaba abierta solo abre el navegador
  actualizador releases de GitHub (Windows, versión compilada): SHA-256, certificados, copia de la base, vuelta atrás
  modulo       el contrato de un módulo (esquema, rutas, pantallas, menú, ayuda)
  aplicacion   crear_app(modulos) -> la app FastAPI con todo lo anterior y los módulos enchufados
  arranque     correr(app): el python -m app / el .exe

Uso mínimo (ver app/ en appbase, la app de ejemplo):
    import nucleo
    nucleo.configurar(app="MiApp", nombre="Mi App", prefijo="MIAPP", puerto=8095, version="1.0.0", repo="usuario/repo",
                      raiz=Path(__file__).resolve().parent.parent)
    from nucleo.aplicacion import crear_app
    app = crear_app([mi_modulo.MODULO])
"""
from .ajustes import configurar  # noqa: F401

VERSION_NUCLEO = "1.0.1"
