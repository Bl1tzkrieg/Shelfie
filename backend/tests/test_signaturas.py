"""Cotas (signaturas topográficas): normalización y orden del estante."""

from app.core.signaturas import clave_signatura, normalizar_cota


def test_normalizar_cota():
    assert normalizar_cota(" 616.39  h37 ") == "616.39 H37"
    assert normalizar_cota("  ") is None
    assert normalizar_cota("") is None
    assert normalizar_cota(None) is None


def test_clave_signatura_ordena_como_el_estante():
    assert clave_signatura("92 B") < clave_signatura("630 R6") < clave_signatura("863 G2")
    assert clave_signatura(" 630   r6 ") == clave_signatura("630 R6")
