"""Exportación CSV compartida por el catálogo, el respaldo y el registro de acciones."""

import csv
import io
from typing import Iterable, List, Optional

from fastapi.responses import StreamingResponse

# El BOM hace que Excel abra el archivo en UTF-8 sin romper los acentos.
BOM = "﻿"
# Punto y coma: con la configuración regional de Venezuela (coma decimal) Excel no separa
# las columnas de un CSV con comas.
SEPARADOR = ";"


# Una celda que empieza así se interpreta como fórmula en Excel y LibreOffice.
_INICIO_DE_FORMULA = ("=", "+", "-", "@", "\t", "\r")


class Texto(str):
    """Valor que Excel debe abrir como texto (ISBN, cota «025.32»): sin esto lo convierte en
    número y pierde ceros y dígitos."""


def celda_segura(valor):
    """Neutraliza la inyección de fórmulas: un nombre como «=HYPERLINK(...)» se exporta
    con un apóstrofo delante, que la hoja de cálculo muestra como texto. Los números
    (incluidos los negativos) se dejan tal cual. Un `Texto` también: se escribe como literal
    de cadena (`="..."`), así que su contenido nunca se ejecuta como fórmula."""
    if isinstance(valor, Texto):
        return valor
    if isinstance(valor, str) and valor.startswith(_INICIO_DE_FORMULA):
        try:
            float(valor)
            return valor
        except ValueError:
            return "'" + valor
    return valor


def _celda(valor):
    valor = celda_segura(valor)
    if isinstance(valor, Texto) and valor:
        return '="' + valor.replace('"', '""') + '"'
    return valor


def texto_csv(
    filas: List[dict],
    columnas: Optional[Iterable[str]] = None,
    texto_si_vacio: Optional[str] = None,
) -> str:
    """Las filas como texto CSV (con BOM para Excel); cada celda pasa por `celda_segura`."""
    buffer = io.StringIO()
    if not filas and texto_si_vacio is not None:
        buffer.write(texto_si_vacio)
    else:
        campos = list(columnas) if columnas else (list(filas[0].keys()) if filas else [])
        writer = csv.DictWriter(buffer, fieldnames=campos, extrasaction="ignore",
                            delimiter=SEPARADOR)
        writer.writeheader()
        writer.writerows({k: _celda(v) for k, v in fila.items()} for fila in filas)
    return BOM + buffer.getvalue()


def respuesta_csv(
    filas: List[dict],
    nombre_archivo: str,
    columnas: Optional[Iterable[str]] = None,
    texto_si_vacio: Optional[str] = None,
) -> StreamingResponse:
    return StreamingResponse(
        iter([texto_csv(filas, columnas, texto_si_vacio)]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )
