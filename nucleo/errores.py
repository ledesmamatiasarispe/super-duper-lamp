"""Los dos errores que una regla de negocio puede lanzar. aplicacion.py los traduce a HTTP (400 y 404) con su mensaje:
las rutas no llevan try/except."""


class ErrorDeNegocio(Exception):
    """Una regla no se cumple. El mensaje lo lee el usuario: tiene que decir qué pasó y qué hacer."""


class NoEncontrado(Exception):
    """Lo pedido no existe (un id que no está)."""
