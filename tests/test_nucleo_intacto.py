"""El núcleo de esta app es el de appbase, sin cambios a mano. Si falla: el cambio va en appbase y se trae con
herramientas/sincronizar.py (así no se pierde en la próxima sincronización ni se separa de las otras apps)."""
from nucleo import intacto


def test_nucleo_sin_cambios_a_mano():
    assert intacto.cambios() == []
