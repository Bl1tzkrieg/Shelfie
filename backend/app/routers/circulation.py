from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.csv import respuesta_csv
from app.core.permisos import Permiso
from app.core.tiempo import sello_archivo
from app.database import get_db
from app.security import requiere, requiere_personal, sede_de_trabajo
from app.services import circulacion, reservas, traslados

router = APIRouter(prefix="/api/v1/circulation", tags=["Circulación"],
                   dependencies=[Depends(requiere_personal)])

CIRCULA = requiere(Permiso.CIRCULACION)


@router.post("/checkout", response_model=schemas.PrestamoResponse)
def checkout_item(payload: schemas.CheckoutRequest, db: Session = Depends(get_db),
                  actor: models.Usuario = Depends(CIRCULA),
                  sede: Optional[int] = Depends(sede_de_trabajo)):
    return circulacion.prestar(db, payload.codigo_barras, payload.nro_carnet, actor.id, sede)


@router.post("/checkin", response_model=schemas.ReturnResponse)
def checkin_item(payload: schemas.CheckinRequest, db: Session = Depends(get_db),
                 actor: models.Usuario = Depends(CIRCULA),
                 sede: Optional[int] = Depends(sede_de_trabajo)):
    """Devolución y todo lo que pasa por ese mostrador: recibe traslados y aparta reservas."""
    return circulacion.devolver(db, payload.codigo_barras, actor.id, sede)


@router.post("/renew", response_model=schemas.RenewResponse)
def renew_loan(payload: schemas.RenewRequest, db: Session = Depends(get_db),
               actor: models.Usuario = Depends(CIRCULA)):
    return circulacion.renovar(db, payload.prestamo_id, actor.id)


@router.post("/loans/{prestamo_id}/lost")
def declarar_perdido(prestamo_id: int, db: Session = Depends(get_db),
                     actor: models.Usuario = Depends(CIRCULA)):
    """Cierra el préstamo, marca el ejemplar como perdido y cobra la reposición."""
    return circulacion.declarar_perdido(db, prestamo_id, actor.id)


@router.get("/loans")
def get_all_loans(estado: Optional[str] = Query(None, pattern="^(activos|vencidos)$"),
                  limite: Optional[int] = Query(None, ge=1, le=500),
                  db: Session = Depends(get_db)):
    """Préstamos, del más reciente al más viejo. `estado=vencidos` para las alertas."""
    return circulacion.listar_prestamos(db, estado, limite)


@router.get("/loans/export")
def export_loans(db: Session = Depends(get_db)):
    """Descarga el listado de préstamos en CSV."""
    return respuesta_csv(
        circulacion.listar_prestamos(db),
        f"prestamos-{sello_archivo()}.csv",
        columnas=circulacion.COLUMNAS_EXPORTACION,
    )


@router.get("/holds")
def listar_reservas(activas: bool = True, biblio_id: Optional[int] = None,
                    db: Session = Depends(get_db)):
    """Reservas: por defecto solo las activas (pendientes, en tránsito y en espera)."""
    return reservas.listar(db, solo_activas=activas, biblio_id=biblio_id)


@router.get("/holds/to-pull")
def reservas_por_sacar(todas_las_sedes: bool = False, db: Session = Depends(get_db),
                       sede: Optional[int] = Depends(sede_de_trabajo)):
    """Ejemplares disponibles que hay que sacar del estante para reservas que esperan."""
    return reservas.por_sacar(db, None if todas_las_sedes else sede)


@router.patch("/holds/{reserva_id}", dependencies=[Depends(CIRCULA)])
def modificar_reserva(reserva_id: int, payload: schemas.ModificarReservaRequest,
                      db: Session = Depends(get_db)):
    return reservas.modificar(db, reserva_id, payload.model_dump(exclude_unset=True))


@router.delete("/holds/{reserva_id}", dependencies=[Depends(CIRCULA)])
def cancelar_reserva(reserva_id: int, db: Session = Depends(get_db)):
    reservas.cancelar(db, reserva_id)
    return {"mensaje": "Reserva cancelada"}


@router.post("/holds/expire", dependencies=[Depends(CIRCULA)])
def expirar_reservas(db: Session = Depends(get_db)):
    """Mantenimiento de la cola. También ocurre solo al prestar, devolver o listar."""
    return reservas.ejecutar_expiracion(db)


# --- Traslados entre sedes ------------------------------------------------------------

@router.get("/transfers")
def listar_traslados(vista: str = "por_recibir", todas_las_sedes: bool = False,
                     db: Session = Depends(get_db),
                     sede: Optional[int] = Depends(sede_de_trabajo)):
    """por_enviar | por_recibir | enviados | historial, vistos desde la sede de trabajo."""
    return traslados.listar(db, vista, None if todas_las_sedes else sede)


@router.get("/transfers/summary")
def resumen_traslados(db: Session = Depends(get_db),
                      sede: Optional[int] = Depends(sede_de_trabajo)):
    return {"sede_id": sede, **traslados.resumen(db, sede)}


@router.post("/transfers", status_code=201)
def crear_traslado(payload: schemas.TrasladoRequest, db: Session = Depends(get_db),
                   actor: models.Usuario = Depends(CIRCULA),
                   sede: Optional[int] = Depends(sede_de_trabajo)):
    return traslados.crear(db, payload.codigo_barras, payload.hacia_id,
                           comentario=payload.comentario, sede_trabajo=sede, personal_id=actor.id)


@router.post("/transfers/{traslado_id}/send")
def enviar_traslado(traslado_id: int, db: Session = Depends(get_db),
                    actor: models.Usuario = Depends(CIRCULA)):
    return traslados.enviar(db, traslado_id, actor.id)


@router.post("/transfers/{traslado_id}/receive")
def recibir_traslado(traslado_id: int, db: Session = Depends(get_db),
                     actor: models.Usuario = Depends(CIRCULA),
                     sede: Optional[int] = Depends(sede_de_trabajo)):
    return traslados.recibir(db, traslado_id, actor.id, sede_trabajo=sede)


@router.post("/transfers/{traslado_id}/cancel", dependencies=[Depends(CIRCULA)])
def cancelar_traslado(traslado_id: int, db: Session = Depends(get_db),
                      sede: Optional[int] = Depends(sede_de_trabajo)):
    return traslados.cancelar(db, traslado_id, sede_trabajo=sede)
