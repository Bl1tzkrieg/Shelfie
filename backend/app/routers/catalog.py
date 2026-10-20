from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app import schemas
from app.core.errores import NoEncontrado, ReglaIncumplida
from app.core.permisos import Permiso
from app.database import get_db
from app.security import requiere, requiere_personal
from app.core import marc_plantillas
from app.services import busqueda, catalogo, intercambio_marc

# Solo el registro MARC: editor, plantillas, importación y exportación. El alta y la edición
# simple de libros y sus ejemplares están en /api/v1/books (routers/libros.py).
router = APIRouter(prefix="/api/v1/catalog", tags=["Catálogo"],
                   dependencies=[Depends(requiere_personal)])

CATALOGA = [Depends(requiere(Permiso.CATALOGO))]


@router.get("/export")
def exportar(
    formato: str = Query("marc", pattern="^(marc|marcxml)$"),
    ejemplares: bool = Query(True, description="Incluir los ejemplares en 952, como Koha"),
    q: str = "",
    db: Session = Depends(get_db),
):
    """Descarga en MARC (ISO 2709) o MARCXML los registros que cumplen la búsqueda."""
    contenido, tipo_mime, nombre = intercambio_marc.exportar(db, busqueda.Filtros(q=q), formato, ejemplares)
    return Response(content=contenido, media_type=tipo_mime,
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


MAX_IMPORTACION = 20 * 1024 * 1024


@router.post("/import", dependencies=CATALOGA)
async def importar(
    request: Request,
    modo: str = Query("vista", pattern="^(vista|aplicar)$"),
    duplicados: str = Query("omitir", pattern="^(omitir|reemplazar|agregar)$"),
    plantilla: str = Query("auto", description="auto, o el código de una plantilla"),
    codificacion: str = Query("auto", pattern="^(auto|utf8|marc8|latin1)$",
                              description="Solo ISO 2709: cómo leer el texto si el líder no dice UTF-8"),
    db: Session = Depends(get_db),
):
    """Importa un archivo MARC (ISO 2709) o MARCXML enviado como cuerpo de la petición.

    `modo=vista` no escribe nada y dice qué pasaría con cada registro; `modo=aplicar`
    importa. Los ejemplares en 952 (formato Koha) se crean junto con su registro.
    """
    # Se mira el tamaño declarado antes de leer: así un archivo enorme no se carga en memoria.
    declarado = request.headers.get("content-length", "")
    if declarado.isdigit() and int(declarado) > MAX_IMPORTACION:
        raise ReglaIncumplida("El archivo supera los 20 MB: divídelo en partes")
    contenido = bytearray()
    async for parte in request.stream():
        contenido += parte
        if len(contenido) > MAX_IMPORTACION:
            raise ReglaIncumplida("El archivo supera los 20 MB: divídelo en partes")
    contenido = bytes(contenido)
    return intercambio_marc.importar(db, contenido, aplicar=modo == "aplicar",
                                     duplicados=duplicados, plantilla=plantilla,
                                     codificacion=codificacion)


# --- MARC ------------------------------------------------------------------------

@router.get("/frameworks")
def listar_plantillas():
    """Plantillas de catalogación disponibles (frameworks de Koha)."""
    return marc_plantillas.listar()


@router.get("/frameworks/{codigo}")
def obtener_plantilla(codigo: str):
    if codigo not in marc_plantillas.PLANTILLAS:
        raise NoEncontrado(f"No existe la plantilla {codigo}")
    return marc_plantillas.como_dict(marc_plantillas.PLANTILLAS[codigo])


@router.get("/items/{biblio_id}/marc", response_model=schemas.RegistroMarcResponse)
def obtener_marc(biblio_id: int, db: Session = Depends(get_db)):
    return catalogo.obtener_marc(db, biblio_id)


@router.put("/items/{biblio_id}/marc", response_model=schemas.RegistroMarcResponse,
            dependencies=CATALOGA)
def guardar_marc(biblio_id: int, payload: schemas.RegistroMarcRequest,
                 db: Session = Depends(get_db)):
    """Guarda el registro MARC y deriva de él título, autor, materia, año e ISBN."""
    return catalogo.guardar_marc(db, biblio_id, payload)


@router.post("/records", response_model=schemas.RegistroMarcResponse, status_code=201,
             dependencies=CATALOGA)
def crear_registro(payload: schemas.RegistroMarcRequest, db: Session = Depends(get_db)):
    """Catalogación completa con el editor MARC; los ejemplares se agregan después."""
    return catalogo.crear_registro(db, payload)
