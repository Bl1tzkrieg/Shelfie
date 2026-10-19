"""M6: la clave de firma débil no se acepta en producción."""

import pytest

from app.config import Settings, comprobar_clave_de_firma

FUERTE = "x" * 40


def _ajustes(**campos):
    return Settings(DATABASE_URL="postgresql://x@localhost/x", _env_file=None, **campos)


@pytest.mark.parametrize("clave", ["cambiar-esta-clave", "shelfie-dev-only-cambiar-en-produccion", "corta"])
def test_produccion_no_arranca_con_una_clave_debil(clave):
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        comprobar_clave_de_firma(_ajustes(SECRET_KEY=clave, ENTORNO="produccion"))
    with pytest.raises(RuntimeError):
        comprobar_clave_de_firma(_ajustes(SECRET_KEY=clave, COOKIE_SECURE=True))


def test_en_desarrollo_solo_advierte():
    with pytest.warns(UserWarning, match="valor de ejemplo"):
        comprobar_clave_de_firma(_ajustes(SECRET_KEY="cambiar-esta-clave"))


def test_una_clave_fuerte_pasa():
    comprobar_clave_de_firma(_ajustes(SECRET_KEY=FUERTE, ENTORNO="produccion", COOKIE_SECURE=True))
