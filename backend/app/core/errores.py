"""Errores de negocio.

Los servicios no conocen HTTP: lanzan estas excepciones y `main.py` las traduce a
la respuesta `{"detail": "..."}` con el código que corresponde. Así la misma
regla sirve igual desde un endpoint, un script o una tarea programada.
"""


class ErrorDeNegocio(Exception):
    status_code = 400

    def __init__(self, mensaje: str):
        super().__init__(mensaje)
        self.mensaje = mensaje


class ReglaIncumplida(ErrorDeNegocio):
    """La operación viola una regla del dominio (400)."""
    status_code = 400


class NoEncontrado(ErrorDeNegocio):
    """El recurso pedido no existe (404)."""
    status_code = 404


class CredencialesInvalidas(ErrorDeNegocio):
    status_code = 401


class AccesoDenegado(ErrorDeNegocio):
    status_code = 403


class DemasiadosIntentos(ErrorDeNegocio):
    """Demasiados intentos fallidos de entrar: hay que esperar (429)."""
    status_code = 429


class ErroresDeValidacion(ErrorDeNegocio):
    """Varios errores de datos a la vez, cada uno con su ubicación (422).

    `errores` va en el `detail` con la misma forma que usa FastAPI para los
    errores de validación: [{"loc": [...], "msg": "..."}], que el frontend ya sabe
    mostrar y que permite marcar cada error junto a su campo.
    """
    status_code = 422

    def __init__(self, errores: list):
        super().__init__(" · ".join(e["msg"] for e in errores))
        self.errores = errores
