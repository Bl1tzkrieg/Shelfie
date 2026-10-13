"""Exportación CSV compartida por circulación, usuarios y reportes."""

import csv
import io
from typing import Iterable, List, Optional

from fastapi.responses import StreamingResponse

# El BOM hace que Excel abra el archivo en UTF-8 sin romper los acentos.
BOM = "﻿"


def respuesta_csv(
    filas: List[dict],
    nombre_archivo: str,
    columnas: Optional[Iterable[str]] = None,
    texto_si_vacio: Optional[str] = None,
) -> StreamingResponse:
    buffer = io.StringIO()
    if not filas and texto_si_vacio is not None:
        buffer.write(texto_si_vacio)
    else:
        campos = list(columnas) if columnas else (list(filas[0].keys()) if filas else [])
        writer = csv.DictWriter(buffer, fieldnames=campos, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(filas)

    return StreamingResponse(
        iter([BOM + buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )
