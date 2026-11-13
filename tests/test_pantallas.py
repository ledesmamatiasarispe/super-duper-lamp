"""Las pantallas cargan sin errores: carga los scripts del núcleo y de los módulos (sin navegador) y detecta nombres
globales repetidos, errores al cargar y pestañas sin pantalla, que en el navegador fallan en silencio. Lo trae
herramientas/sincronizar.py de appbase; se saltea si la PC no tiene Node."""
import pytest

import app.main
from nucleo import chequeo


def test_las_pantallas_cargan_sin_errores():
    errores = chequeo.pantallas(app.main.MODULOS)
    if errores is None:
        pytest.skip("No hay Node en esta PC.")
    assert errores == []
