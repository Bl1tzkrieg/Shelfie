from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/api/v1/serials", tags=["Publicaciones Seriadas"])


def _ahora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _serializar_suscripcion(db: Session, s: models.Suscripcion) -> dict:
    fasciculos = db.query(models.Fasciculo).filter(
        models.Fasciculo.suscripcion_id == s.id).all()
    return {
        "id": s.id,
        "titulo": s.titulo,
        "issn": s.issn,
        "proveedor_id": s.proveedor_id,
        "periodicidad": s.periodicidad,
        "fecha_inicio": s.fecha_inicio,
        "fecha_fin": s.fecha_fin,
        "estado": s.estado,
        "fasciculos_recibidos": len([f for f in fasciculos if f.recibido]),
        "fasciculos_esperados": len(fasciculos),
    }


@router.get("/subscriptions", response_model=List[schemas.SuscripcionResponse])
def listar_suscripciones(db: Session = Depends(get_db)):
    suscripciones = db.query(models.Suscripcion).order_by(
        models.Suscripcion.titulo).all()
    return [_serializar_suscripcion(db, s) for s in suscripciones]


@router.post("/subscriptions", response_model=schemas.SuscripcionResponse, status_code=201)
def crear_suscripcion(payload: schemas.SuscripcionRequest, db: Session = Depends(get_db)):
    if payload.proveedor_id:
        proveedor = db.query(models.Proveedor).filter(
            models.Proveedor.id == payload.proveedor_id).first()
        if not proveedor:
            raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    suscripcion = models.Suscripcion(
        titulo=payload.titulo,
        issn=payload.issn,
        proveedor_id=payload.proveedor_id,
        periodicidad=payload.periodicidad,
        fecha_inicio=payload.fecha_inicio,
        fecha_fin=payload.fecha_fin,
        estado="Activa",
    )
    db.add(suscripcion)
    db.commit()
    db.refresh(suscripcion)
    return _serializar_suscripcion(db, suscripcion)


@router.get("/subscriptions/{suscripcion_id}", response_model=schemas.SuscripcionResponse)
def get_suscripcion(suscripcion_id: int, db: Session = Depends(get_db)):
    s = db.query(models.Suscripcion).filter(
        models.Suscripcion.id == suscripcion_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")
    return _serializar_suscripcion(db, s)


@router.post("/subscriptions/{suscripcion_id}/cancel",
             response_model=schemas.SuscripcionResponse)
def cancelar_suscripcion(suscripcion_id: int, db: Session = Depends(get_db)):
    s = db.query(models.Suscripcion).filter(
        models.Suscripcion.id == suscripcion_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")
    s.estado = "Cancelada"
    db.commit()
    db.refresh(s)
    return _serializar_suscripcion(db, s)


# --- Fascículos ------------------------------------------------------------

@router.get("/subscriptions/{suscripcion_id}/issues",
            response_model=List[schemas.FasciculoResponse])
def listar_fasciculos(suscripcion_id: int, db: Session = Depends(get_db)):
    if not db.query(models.Suscripcion).filter(
            models.Suscripcion.id == suscripcion_id).first():
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")
    return db.query(models.Fasciculo).filter(
        models.Fasciculo.suscripcion_id == suscripcion_id).order_by(
        models.Fasciculo.id).all()


@router.post("/subscriptions/{suscripcion_id}/issues",
             response_model=schemas.FasciculoResponse, status_code=201)
def registrar_fasciculo(
    suscripcion_id: int,
    payload: schemas.FasciculoRequest,
    db: Session = Depends(get_db),
):
    """Registra un fascículo esperado dentro del calendario de la suscripción."""
    if not db.query(models.Suscripcion).filter(
            models.Suscripcion.id == suscripcion_id).first():
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")

    duplicado = db.query(models.Fasciculo).filter(
        models.Fasciculo.suscripcion_id == suscripcion_id,
        models.Fasciculo.numero == payload.numero).first()
    if duplicado:
        raise HTTPException(
            status_code=400,
            detail=f"El fascículo {payload.numero} ya está registrado")

    fasciculo = models.Fasciculo(
        suscripcion_id=suscripcion_id,
        numero=payload.numero,
        fecha_esperada=payload.fecha_esperada,
        recibido=False,
    )
    db.add(fasciculo)
    db.commit()
    db.refresh(fasciculo)
    return fasciculo


@router.post("/issues/{fasciculo_id}/receive", response_model=schemas.FasciculoResponse)
def recibir_fasciculo(fasciculo_id: int, db: Session = Depends(get_db)):
    """Acusa recibo de un fascículo (kardex de publicaciones seriadas)."""
    fasciculo = db.query(models.Fasciculo).filter(
        models.Fasciculo.id == fasciculo_id).first()
    if not fasciculo:
        raise HTTPException(status_code=404, detail="Fascículo no encontrado")
    if fasciculo.recibido:
        raise HTTPException(status_code=400, detail="El fascículo ya figura como recibido")

    fasciculo.recibido = True
    fasciculo.fecha_recepcion = _ahora()
    db.commit()
    db.refresh(fasciculo)
    return fasciculo


@router.get("/issues/pending", response_model=List[schemas.FasciculoResponse])
def fasciculos_pendientes(db: Session = Depends(get_db)):
    """Fascículos aún no recibidos: el reclamo típico a proveedores."""
    return db.query(models.Fasciculo).filter(
        models.Fasciculo.recibido == False).order_by(
        models.Fasciculo.fecha_esperada).all()
