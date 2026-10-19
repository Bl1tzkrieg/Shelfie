"""Publicaciones seriadas: suscripciones, predicción, recepción y reclamos."""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.permisos import Permiso
from app.database import get_db
from app.security import requiere
from app.services import seriadas

SERIADAS = requiere(Permiso.SERIADAS)

router = APIRouter(prefix="/api/v1/serials", tags=["Publicaciones Seriadas"],
                   dependencies=[Depends(SERIADAS)])


@router.get("/suppliers")
def proveedores(db: Session = Depends(get_db)):
    """Proveedores activos para elegir en una suscripción (sin exigir el permiso de adquisiciones)."""
    return [{"id": p.id, "nombre": p.nombre, "email": p.email}
            for p in db.query(models.Proveedor).filter(models.Proveedor.activo == True)  # noqa: E712
            .order_by(models.Proveedor.nombre)]


@router.get("/subscriptions")
def listar_suscripciones(estado: Optional[str] = None, db: Session = Depends(get_db)):
    return seriadas.listar(db, estado)


@router.post("/subscriptions", status_code=201)
def crear_suscripcion(payload: schemas.SuscripcionRequest, db: Session = Depends(get_db)):
    return seriadas.crear(db, payload.model_dump(exclude_unset=True))


@router.post("/prediction")
def vista_previa(payload: schemas.PrediccionRequest):
    """Los próximos números que produciría el patrón (antes de guardar la suscripción)."""
    return seriadas.predecir(payload.frecuencia_unidad, payload.frecuencia_cada,
                             payload.numeracion, payload.numeros_por_volumen,
                             payload.volumen_inicial, payload.numero_inicial,
                             payload.primer_fasciculo, payload.cantidad)


@router.get("/subscriptions/{suscripcion_id}")
def get_suscripcion(suscripcion_id: int, db: Session = Depends(get_db)):
    """La suscripción con su kardex de fascículos."""
    return seriadas.obtener(db, suscripcion_id)


@router.put("/subscriptions/{suscripcion_id}")
def actualizar_suscripcion(suscripcion_id: int, payload: schemas.SuscripcionRequest,
                           db: Session = Depends(get_db)):
    return seriadas.actualizar(db, suscripcion_id, payload.model_dump(exclude_unset=True))


@router.post("/subscriptions/{suscripcion_id}/cancel")
def cancelar_suscripcion(suscripcion_id: int, db: Session = Depends(get_db)):
    return seriadas.cancelar(db, suscripcion_id)


@router.post("/subscriptions/{suscripcion_id}/renew")
def renovar_suscripcion(suscripcion_id: int, payload: schemas.RenovarSuscripcionRequest,
                        db: Session = Depends(get_db)):
    return seriadas.reactivar(db, suscripcion_id, payload.fecha_fin)


@router.post("/subscriptions/{suscripcion_id}/issues", status_code=201)
def registrar_fasciculo(suscripcion_id: int, payload: schemas.FasciculoRequest,
                        db: Session = Depends(get_db)):
    """Un número fuera del patrón (especial, suplemento) o de una suscripción irregular."""
    return seriadas.registrar_fasciculo(db, suscripcion_id, payload.model_dump())


@router.post("/issues/{fasciculo_id}/receive")
def recibir_fasciculo(fasciculo_id: int, payload: Optional[schemas.RecibirFasciculoRequest] = None,
                      db: Session = Depends(get_db), actor: models.Usuario = Depends(SERIADAS)):
    """Acusa recibo, da de alta el ejemplar y predice el siguiente número."""
    datos = payload.model_dump(exclude_unset=True) if payload else {}
    return seriadas.recibir_fasciculo(db, fasciculo_id, datos, actor.id)


@router.post("/issues/{fasciculo_id}/missing")
def marcar_faltante(fasciculo_id: int, payload: Optional[schemas.NotaRequest] = None,
                    db: Session = Depends(get_db)):
    return seriadas.marcar_faltante(db, fasciculo_id, payload.notas if payload else None)


@router.post("/issues/{fasciculo_id}/claim")
def reclamar(fasciculo_id: int, db: Session = Depends(get_db)):
    return seriadas.reclamar(db, fasciculo_id)


@router.post("/suppliers/{proveedor_id}/claim")
def reclamar_al_proveedor(proveedor_id: int, suscripcion_id: Optional[int] = None,
                          db: Session = Depends(get_db)):
    """Un correo al proveedor con sus números atrasados (de una suscripción, o de todas)."""
    return seriadas.reclamar_por_correo(db, proveedor_id, suscripcion_id=suscripcion_id)


@router.get("/issues/expected")
def por_recibir(db: Session = Depends(get_db)):
    """Lo que se espera de todas las suscripciones activas."""
    return seriadas.por_recibir(db)


@router.get("/issues/late")
def atrasados(db: Session = Depends(get_db)):
    """Fascículos atrasados (pasaron los días de gracia): lo que hay que reclamar."""
    return seriadas.atrasados(db)


@router.get("/issues/pending")
def fasciculos_pendientes(db: Session = Depends(get_db)):
    """Compatibilidad: lo mismo que /issues/expected."""
    return seriadas.por_recibir(db)
