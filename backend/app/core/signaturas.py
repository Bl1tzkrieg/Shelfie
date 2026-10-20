"""Cotas (signaturas topográficas): cómo se guardan y cómo se ordenan en el estante."""

import re
from typing import Optional

from sqlalchemy import case, collate, func


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


def clave_signatura_sql(cota):
    """`clave_signatura` en SQL, sobre la cota ya normalizada: la parte numérica inicial con
    ceros a la izquierda. Con intercalación "C" (por código, como Python)."""
    inicio = func.substring(cota, r"^\d+")
    clave = case(
        (inicio.isnot(None),
         func.concat(func.lpad(inicio, func.greatest(6, func.length(inicio)), "0"),
                     func.substr(cota, func.length(inicio) + 1))),
        else_=cota)
    return collate(clave, "C")


def escapar_like(texto: str) -> str:
    """Para usar el texto como literal en LIKE/ILIKE con escape="\\"."""
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
