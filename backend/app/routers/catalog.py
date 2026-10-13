from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app import schemas
from app.core.errores import NoEncontrado, ReglaIncumplida
from app.core.permisos import Permiso
from app.database import get_db
from app.security import requiere, requiere_personal, sede_de_trabajo
from app.core import marc_plantillas
from app.services import busqueda, catalogo, intercambio_marc, reservas

router = APIRouter(prefix="/api/v1/catalog", tags=["Catálogo"],
                   dependencies=[Depends(requiere_personal)])

CATALOGA = [Depends(requiere(Permiso.CATALOGO))]


@router.get("/items", response_model=List[schemas.MaterialResponse])
def get_all_items(db: Session = Depends(get_db)):
    """Catálogo por título: cada fila agrupa sus ejemplares y su disponibilidad."""
    return catalogo.listar_titulos(db)


@router.get("/search", response_model=schemas.BusquedaCatalogoResponse)
def buscar(
    q: str = Query("", description="Título, autor, materia, ISBN o código de barras"),
    materia: Optional[str] = None,
    autor: Optional[str] = None,
    tipo: Optional[str] = Query(None, description="Código del tipo de ítem"),
    disponible: Optional[bool] = Query(None, description="true: con ejemplares libres"),
    ano_desde: Optional[int] = None,
    ano_hasta: Optional[int] = None,
    orden: str = Query("relevancia", pattern="^(relevancia|titulo|ano_desc|ano_asc)$"),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Búsqueda de texto completo (sin acentos, por raíz) con facetas y paginación."""
    filtros = busqueda.Filtros(q=q, materia=materia, autor=autor, tipo=tipo,
                               disponible=disponible, ano_desde=ano_desde, ano_hasta=ano_hasta)
    return catalogo.buscar_titulos(db, filtros, pagina=pagina, por_pagina=por_pagina,
                                   orden=orden)


@router.get("/export")
def exportar(
    formato: str = Query("marc", pattern="^(marc|marcxml)$"),
    ejemplares: bool = Query(True, description="Incluir los ejemplares en 952, como Koha"),
    q: str = "",
    materia: Optional[str] = None,
    autor: Optional[str] = None,
    tipo: Optional[str] = None,
    disponible: Optional[bool] = None,
    ano_desde: Optional[int] = None,
    ano_hasta: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Descarga en MARC (ISO 2709) o MARCXML los registros que cumplen la búsqueda."""
    filtros = busqueda.Filtros(q=q, materia=materia, autor=autor, tipo=tipo,
                               disponible=disponible, ano_desde=ano_desde, ano_hasta=ano_hasta)
    contenido, tipo_mime, nombre = intercambio_marc.exportar(db, filtros, formato, ejemplares)
    return Response(content=contenido, media_type=tipo_mime,
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


MAX_IMPORTACION = 20 * 1024 * 1024


@router.post("/import", dependencies=CATALOGA)
async def importar(
    request: Request,
    modo: str = Query("vista", pattern="^(vista|aplicar)$"),
    duplicados: str = Query("omitir", pattern="^(omitir|reemplazar|agregar)$"),
    plantilla: str = Query("auto", description="auto, o el código de una plantilla"),
    db: Session = Depends(get_db),
):
    """Importa un archivo MARC (ISO 2709) o MARCXML enviado como cuerpo de la petición.

    `modo=vista` no escribe nada y dice qué pasaría con cada registro; `modo=aplicar`
    importa. Los ejemplares en 952 (formato Koha) se crean junto con su registro.
    """
    contenido = await request.body()
    if len(contenido) > MAX_IMPORTACION:
        raise ReglaIncumplida("El archivo supera los 20 MB: divídelo en partes")
    return intercambio_marc.importar(db, contenido, aplicar=modo == "aplicar",
                                     duplicados=duplicados, plantilla=plantilla)


@router.post("/items", response_model=schemas.MaterialResponse, status_code=201,
             dependencies=[Depends(requiere(Permiso.CATALOGO))])
def crear_material(payload: schemas.NuevoMaterialRequest, db: Session = Depends(get_db)):
    return catalogo.dar_de_alta(db, payload)


@router.get("/items/{biblio_id}", response_model=schemas.MaterialResponse)
def get_item(biblio_id: int, db: Session = Depends(get_db)):
    return catalogo.obtener_titulo(db, biblio_id)


@router.delete("/items/{biblio_id}", status_code=204, dependencies=CATALOGA)
def eliminar_registro(biblio_id: int, db: Session = Depends(get_db)):
    """Borra un registro sin ejemplares ni reservas activas."""
    catalogo.eliminar_registro(db, biblio_id)


@router.get("/items/{biblio_id}/ejemplares")
def get_ejemplares(biblio_id: int, db: Session = Depends(get_db)):
    return catalogo.listar_ejemplares(db, biblio_id)


@router.post("/items/{biblio_id}/ejemplares", response_model=schemas.MaterialResponse,
             status_code=201, dependencies=CATALOGA)
def agregar_ejemplar(biblio_id: int, payload: schemas.NuevoEjemplarRequest,
                     db: Session = Depends(get_db)):
    return catalogo.agregar_ejemplar(db, biblio_id, payload)


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


@router.post("/reservations", response_model=schemas.ReservaResponse, status_code=201,
             dependencies=[Depends(requiere(Permiso.CIRCULACION))])
def crear_reserva(payload: schemas.ReservaRequest, db: Session = Depends(get_db),
                  sede: Optional[int] = Depends(sede_de_trabajo)):
    return reservas.reservar(db, payload.biblio_id, payload.nro_carnet,
                             biblioteca_retiro_id=payload.biblioteca_retiro_id,
                             fecha_limite=payload.fecha_limite, notas=payload.notas,
                             sede_trabajo=sede)


@router.get("/reservations")
def listar_reservas(db: Session = Depends(get_db)):
    """Todas las reservas, incluidas las cerradas (ver también /circulation/holds)."""
    return reservas.listar(db)


@router.delete("/reservations/{reserva_id}", dependencies=[Depends(requiere(Permiso.CIRCULACION))])
def cancelar_reserva(reserva_id: int, db: Session = Depends(get_db)):
    reservas.cancelar(db, reserva_id)
    return {"mensaje": "Reserva cancelada"}


@router.get("/dashboard-stats", tags=["Métricas"])
def get_dashboard_stats(db: Session = Depends(get_db)):
    return catalogo.estadisticas_dashboard(db)
