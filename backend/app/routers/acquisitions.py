from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/api/v1/acquisitions", tags=["Adquisiciones"])


def _ahora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _serializar_orden(db: Session, orden: models.OrdenCompra) -> dict:
    lineas = db.query(models.LineaOrden).filter(
        models.LineaOrden.orden_id == orden.id).all()
    proveedor = db.query(models.Proveedor).filter(
        models.Proveedor.id == orden.proveedor_id).first()

    total = sum(float(l.precio_unitario) * l.cantidad for l in lineas)

    return {
        "id": orden.id,
        "proveedor_id": orden.proveedor_id,
        "proveedor_nombre": proveedor.nombre if proveedor else None,
        "fecha_emision": orden.fecha_emision,
        "fecha_recepcion": orden.fecha_recepcion,
        "estado": orden.estado,
        "observaciones": orden.observaciones,
        "total": round(total, 2),
        "lineas": [
            {
                "id": l.id,
                "titulo": l.titulo,
                "autor": l.autor,
                "isbn": l.isbn,
                "cantidad": l.cantidad,
                "precio_unitario": float(l.precio_unitario),
            }
            for l in lineas
        ],
    }


# --- Proveedores -----------------------------------------------------------

@router.get("/suppliers", response_model=List[schemas.ProveedorResponse])
def listar_proveedores(db: Session = Depends(get_db)):
    return db.query(models.Proveedor).order_by(models.Proveedor.nombre).all()


@router.post("/suppliers", response_model=schemas.ProveedorResponse, status_code=201)
def crear_proveedor(payload: schemas.ProveedorRequest, db: Session = Depends(get_db)):
    proveedor = models.Proveedor(
        nombre=payload.nombre,
        contacto=payload.contacto,
        email=payload.email,
        telefono=payload.telefono,
        activo=True,
    )
    db.add(proveedor)
    db.commit()
    db.refresh(proveedor)
    return proveedor


# --- Órdenes de compra -----------------------------------------------------

@router.get("/orders", response_model=List[schemas.OrdenCompraResponse])
def listar_ordenes(db: Session = Depends(get_db)):
    ordenes = db.query(models.OrdenCompra).order_by(
        models.OrdenCompra.id.desc()).all()
    return [_serializar_orden(db, o) for o in ordenes]


@router.post("/orders", response_model=schemas.OrdenCompraResponse, status_code=201)
def crear_orden(payload: schemas.OrdenCompraRequest, db: Session = Depends(get_db)):
    proveedor = db.query(models.Proveedor).filter(
        models.Proveedor.id == payload.proveedor_id).first()
    if not proveedor:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    orden = models.OrdenCompra(
        proveedor_id=proveedor.id,
        fecha_emision=_ahora(),
        estado="Pendiente",
        observaciones=payload.observaciones,
    )
    db.add(orden)
    db.flush()

    for linea in payload.lineas:
        db.add(models.LineaOrden(
            orden_id=orden.id,
            titulo=linea.titulo,
            autor=linea.autor,
            isbn=linea.isbn,
            cantidad=linea.cantidad,
            precio_unitario=linea.precio_unitario,
        ))

    db.commit()
    db.refresh(orden)
    return _serializar_orden(db, orden)


@router.get("/orders/{orden_id}", response_model=schemas.OrdenCompraResponse)
def get_orden(orden_id: int, db: Session = Depends(get_db)):
    orden = db.query(models.OrdenCompra).filter(
        models.OrdenCompra.id == orden_id).first()
    if not orden:
        raise HTTPException(status_code=404, detail="Orden de compra no encontrada")
    return _serializar_orden(db, orden)


@router.post("/orders/{orden_id}/receive", response_model=schemas.OrdenCompraResponse)
def recibir_orden(orden_id: int, db: Session = Depends(get_db)):
    """Marca la orden como recibida y da de alta los ejemplares en el catálogo."""
    orden = db.query(models.OrdenCompra).filter(
        models.OrdenCompra.id == orden_id).first()
    if not orden:
        raise HTTPException(status_code=404, detail="Orden de compra no encontrada")
    if orden.estado == "Recibida":
        raise HTTPException(status_code=400, detail="La orden ya fue recibida")
    if orden.estado == "Cancelada":
        raise HTTPException(status_code=400, detail="La orden está cancelada")

    tipo = db.query(models.TipoItem).filter(models.TipoItem.codigo == "LIB").first()
    lineas = db.query(models.LineaOrden).filter(
        models.LineaOrden.orden_id == orden.id).all()

    for linea in lineas:
        # Se reutiliza el registro bibliográfico si el ISBN ya existe.
        biblio = None
        if linea.isbn:
            biblio = db.query(models.RegistroBibliografico).filter(
                models.RegistroBibliografico.isbn == linea.isbn).first()
        if not biblio:
            biblio = models.RegistroBibliografico(
                isbn=linea.isbn,
                titulo=linea.titulo,
                autor=linea.autor,
                marc_json={
                    "leader": "00000cam a22000001a 4500",
                    "fields": [{"245": {"subfields": [{"a": linea.titulo}]}}],
                },
            )
            db.add(biblio)
            db.flush()

        # Un ejemplar por unidad comprada, con código de barras derivado de la orden.
        for n in range(linea.cantidad):
            codigo = f"OC{orden.id:04d}-L{linea.id:03d}-{n + 1:02d}"
            if db.query(models.Item).filter(models.Item.codigo_barras == codigo).first():
                continue
            db.add(models.Item(
                biblio_id=biblio.id,
                codigo_barras=codigo,
                tipo_item_id=tipo.id if tipo else None,
                estado="Disponible",
            ))

    orden.estado = "Recibida"
    orden.fecha_recepcion = _ahora()
    db.commit()
    db.refresh(orden)
    return _serializar_orden(db, orden)


@router.post("/orders/{orden_id}/cancel", response_model=schemas.OrdenCompraResponse)
def cancelar_orden(orden_id: int, db: Session = Depends(get_db)):
    orden = db.query(models.OrdenCompra).filter(
        models.OrdenCompra.id == orden_id).first()
    if not orden:
        raise HTTPException(status_code=404, detail="Orden de compra no encontrada")
    if orden.estado == "Recibida":
        raise HTTPException(
            status_code=400, detail="No se puede cancelar una orden ya recibida")
    orden.estado = "Cancelada"
    db.commit()
    db.refresh(orden)
    return _serializar_orden(db, orden)
