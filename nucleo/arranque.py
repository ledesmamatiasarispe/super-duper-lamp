"""correr(app): lo que hace `python -m app` o el .exe compilado.

El puerto se elige en Opciones (ver puerto.py). Si la app ya estaba abierta, abrirla de nuevo solo abre el navegador;
si el puerto lo usa otro programa, arranca en el siguiente libre y lo avisa. La versión compilada abre el navegador al
arrancar (<PREFIJO>_NAVEGADOR=0 lo evita, para pruebas o un servidor sin pantalla). Atiende en toda la red (0.0.0.0)
para que entren otras PCs y tablets.
"""
import os
import sys
import threading
import webbrowser

from . import ajustes
from . import puerto as pto


def correr(app) -> None:
    import uvicorn
    # redirigida a un archivo (logs, accesos directos), la salida usaría la página de códigos de Windows y los acentos
    # saldrían mal; en una consola de verdad Python ya escribe Unicode
    if sys.stdout and not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    abrir = ajustes.COMPILADA and ajustes.env("NAVEGADOR", "1") != "0"
    puerto, ya_abierta = pto.al_arrancar()
    url = f"http://localhost:{puerto}"
    if ya_abierta:
        print(f"{ajustes.NOMBRE} ya está funcionando: {url}")
        if abrir:
            webbrowser.open(url)
        return
    if puerto != pto.configurado():
        print(f"El puerto {pto.configurado()} lo está usando otro programa: esta vez la app arranca en el {puerto}. "
              "Se puede elegir otro en Opciones.")
    os.environ[pto.VARIABLE_ACTUAL] = str(puerto)
    print(f"{ajustes.NOMBRE} {ajustes.VERSION} - {url}  (cerrar esta ventana apaga la app)")
    if abrir:
        threading.Timer(2, webbrowser.open, [url]).start()
    # el objeto app directo (no "app.main:app"): compilada, uvicorn no puede importar el módulo por nombre
    uvicorn.run(app, host="0.0.0.0", port=puerto)
