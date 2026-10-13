"""Cuenta del lector en el OPAC. Todo lo de aquí es del lector que inició sesión."""

from typing import Optional

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import abrir_sesion_opac, get_lector
from app.services import autenticacion, cuenta_opac, listas

router = APIRouter(prefix="/api/v1/opac/account", tags=["OPAC: cuenta del lector"])

Lector = models.Usuario


@router.get("")
def resumen(lector: Lector = Depends(get_lector), db: Session = Depends(get_db)):
    return cuenta_opac.resumen(db, lector)


@router.post("/password", status_code=204)
def cambiar_clave(payload: schemas.CambiarClaveRequest, response: Response,
                  lector: Lector = Depends(get_lector), db: Session = Depends(get_db)):
    """Cambia la contraseña. Cierra las demás sesiones (también las de la intranet)."""
    autenticacion.cambiar_clave(db, lector, payload.actual, payload.nueva)
    abrir_sesion_opac(response, lector)


# --- Préstamos ---------------------------------------------------------------------------

@router.get("/loans")
def prestamos(lector: Lector = Depends(get_lector), db: Session = Depends(get_db)):
    return cuenta_opac.prestamos(db, lector)


@router.post("/loans/renew-all")
def renovar_todos(lector: Lector = Depends(get_lector), db: Session = Depends(get_db)):
    return cuenta_opac.renovar_todos(db, lector)


@router.post("/loans/{prestamo_id}/renew")
def renovar(prestamo_id: int, payload: Optional[schemas.RenovarOpacRequest] = None,
            lector: Lector = Depends(get_lector), db: Session = Depends(get_db)):
    """Un préstamo vencido solo se renueva con `aceptar_cargo`: renovar cobra el atraso."""
    return cuenta_opac.renovar(db, lector, prestamo_id,
                               aceptar_cargo=bool(payload and payload.aceptar_cargo))


@router.get("/history")
def historial(lector: Lector = Depends(get_lector), db: Session = Depends(get_db)):
    return cuenta_opac.historial(db, lector)


# --- Reservas ----------------------------------------------------------------------------

@router.get("/holds")
def reservas(lector: Lector = Depends(get_lector), db: Session = Depends(get_db)):
    return cuenta_opac.mis_reservas(db, lector)


@router.post("/holds", status_code=201)
def reservar(payload: schemas.ReservaOpacRequest, lector: Lector = Depends(get_lector),
             db: Session = Depends(get_db)):
    return cuenta_opac.reservar(db, lector, payload.model_dump())


@router.patch("/holds/{reserva_id}")
def modificar_reserva(reserva_id: int, payload: schemas.ModificarReservaOpacRequest,
                      lector: Lector = Depends(get_lector), db: Session = Depends(get_db)):
    return cuenta_opac.modificar_reserva(db, lector, reserva_id,
                                         payload.model_dump(exclude_unset=True))


@router.delete("/holds/{reserva_id}", status_code=204)
def cancelar_reserva(reserva_id: int, lector: Lector = Depends(get_lector),
                     db: Session = Depends(get_db)):
    cuenta_opac.cancelar_reserva(db, lector, reserva_id)


# --- Multas y sugerencias -------------------------------------------------------------------

@router.get("/charges")
def multas(lector: Lector = Depends(get_lector), db: Session = Depends(get_db)):
    return cuenta_opac.multas(db, lector)


@router.get("/suggestions")
def sugerencias(lector: Lector = Depends(get_lector), db: Session = Depends(get_db)):
    return cuenta_opac.mis_sugerencias(db, lector)


@router.post("/suggestions", status_code=201)
def sugerir(payload: schemas.SugerenciaOpacRequest, lector: Lector = Depends(get_lector),
            db: Session = Depends(get_db)):
    return cuenta_opac.sugerir(db, lector, payload.model_dump())


# --- Listas ------------------------------------------------------------------------------

@router.get("/lists")
def mis_listas(biblio_id: Optional[int] = None, lector: Lector = Depends(get_lector),
               db: Session = Depends(get_db)):
    """Con `biblio_id`, cada lista dice además si ya tiene ese título."""
    return listas.mis_listas(db, lector, biblio_id)


@router.post("/lists", status_code=201)
def crear_lista(payload: schemas.ListaRequest, lector: Lector = Depends(get_lector),
                db: Session = Depends(get_db)):
    return listas.crear(db, lector, payload.nombre, payload.publica)


@router.patch("/lists/{lista_id}")
def editar_lista(lista_id: int, payload: schemas.EditarListaRequest,
                 lector: Lector = Depends(get_lector), db: Session = Depends(get_db)):
    return listas.editar(db, lector, lista_id, payload.model_dump(exclude_unset=True))


@router.delete("/lists/{lista_id}", status_code=204)
def eliminar_lista(lista_id: int, lector: Lector = Depends(get_lector),
                   db: Session = Depends(get_db)):
    listas.eliminar(db, lector, lista_id)


@router.post("/lists/{lista_id}/titles")
def agregar_a_lista(lista_id: int, payload: schemas.ListaRegistroRequest,
                    lector: Lector = Depends(get_lector), db: Session = Depends(get_db)):
    return listas.agregar(db, lector, lista_id, payload.biblio_id)


@router.delete("/lists/{lista_id}/titles/{biblio_id}", status_code=204)
def quitar_de_lista(lista_id: int, biblio_id: int, lector: Lector = Depends(get_lector),
                    db: Session = Depends(get_db)):
    listas.quitar(db, lector, lista_id, biblio_id)
