"""Cotas (signaturas topográficas): cómo se guardan y cómo se ordenan en el estante."""

import re
from typing import Optional


def normalizar_cota(texto: Optional[str]) -> Optional[str]:
    """Espacios simples y mayúsculas («616.39  h37» → «616.39 H37»); vacía, None."""
    limpia = re.sub(r"\s+", " ", (texto or "").strip()).upper()
    return limpia or None


def clave_signatura(cota: Optional[str]) -> str:
    """Para ordenar y comparar signaturas: mayúsculas, espacios simples y la parte numérica
    inicial con ceros a la izquierda (así «92 B» va antes de «630 R6», como en el estante)."""
    texto = re.sub(r"\s+", " ", (cota or "").strip().upper())
    inicio = re.match(r"^(\d+)", texto)
    if inicio:
        texto = inicio.group(1).zfill(6) + texto[inicio.end():]
    return texto
