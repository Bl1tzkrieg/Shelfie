from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/api/v1/catalog", tags=["Catálogo"])


def _ahora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _serializar_registro(db: Session, biblio: models.RegistroBibliografico) -> dict:
    """Vista de un título con la disponibilidad agregada de sus ejemplares."""
    items = db.query(models.Item).filter(models.Item.biblio_id == biblio.id).all()
    disponibles = [i for i in items if i.estado == "Disponible"]

    tipo = None
    if items and items[0].tipo_item_id:
        tipo = db.query(models.TipoItem).filter(
            models.TipoItem.id == items[0].tipo_item_id).first()

    return {
        "id": str(biblio.id),
        "title": biblio.titulo or "Sin título",
        "author": biblio.autor or "Autor desconocido",
        "year": biblio.ano_publicacion,
        "category": biblio.materia or "Sin clasificar",
        "type": tipo.descripcion if tipo else "Sin tipo",
        "isbn": biblio.isbn or "N/A",
        "location": items[0].signatura_topografica if items else None,
        "copies": len(items),
        "available": len(disponibles),
        # El código de barras del primer ejemplar libre es lo que necesita
        # /circulation/checkout para poder prestar desde la tarjeta.
        "availableBarcode": disponibles[0].codigo_barras if disponibles else None,
    }


@router.get("/items", response_model=List[schemas.MaterialResponse])
def get_all_items(db: Session = Depends(get_db)):
    # El catálogo se presenta por título (registro bibliográfico), no por ejemplar:
    # cada tarjeta agrupa sus items y reporta cuántos hay y cuántos están libres.
    registros = db.query(models.RegistroBibliografico).order_by(
        models.RegistroBibliografico.titulo).all()
    return [_serializar_registro(db, b) for b in registros]


@router.post("/items", response_model=schemas.MaterialResponse, status_code=201)
def crear_material(payload: schemas.NuevoMaterialRequest, db: Session = Depends(get_db)):
    """Da de alta un registro bibliográfico junto con su primer ejemplar."""
    existente = db.query(models.Item).filter(
        models.Item.codigo_barras == payload.codigo_barras).first()
    if existente:
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe un ejemplar con el código de barras {payload.codigo_barras}")

    tipo = db.query(models.TipoItem).filter(
        models.TipoItem.codigo == payload.tipo_item_codigo).first()
    if not tipo:
        raise HTTPException(
            status_code=400,
            detail=f"No existe el tipo de ítem '{payload.tipo_item_codigo}'")

    # Se reutiliza el registro bibliográfico si ya hay uno con el mismo ISBN:
    # así un segundo ejemplar suma copias en lugar de duplicar el título.
    biblio = None
    if payload.isbn:
        biblio = db.query(models.RegistroBibliografico).filter(
            models.RegistroBibliografico.isbn == payload.isbn).first()

    if not biblio:
        biblio = models.RegistroBibliografico(
            isbn=payload.isbn,
            titulo=payload.titulo,
            autor=payload.autor,
            ano_publicacion=payload.ano_publicacion,
            materia=payload.materia,
            marc_json=_marc_minimo(payload),
        )
        db.add(biblio)
        db.flush()

    item = models.Item(
        biblio_id=biblio.id,
        codigo_barras=payload.codigo_barras,
        tipo_item_id=tipo.id,
        signatura_topografica=payload.signatura_topografica,
        estado="Disponible",
    )
    db.add(item)
    db.commit()
    db.refresh(biblio)

    return _serializar_registro(db, biblio)


def _marc_minimo(payload: schemas.NuevoMaterialRequest) -> dict:
    """Estructura MARC21 mínima: 020 (ISBN), 100 (autor), 245 (título)."""
    fields = []
    if payload.isbn:
        fields.append({"020": {"subfields": [{"a": payload.isbn}]}})
    if payload.autor:
        fields.append({"100": {"subfields": [{"a": payload.autor}]}})
    fields.append({"245": {"subfields": [{"a": payload.titulo}]}})
    return {"leader": "00000cam a22000001a 4500", "fields": fields}


@router.get("/items/{biblio_id}", response_model=schemas.MaterialResponse)
def get_item(biblio_id: int, db: Session = Depends(get_db)):
    biblio = db.query(models.RegistroBibliografico).filter(
        models.RegistroBibliografico.id == biblio_id).first()
    if not biblio:
        raise HTTPException(status_code=404, detail="Título no encontrado en el catálogo")
    return _serializar_registro(db, biblio)


@router.get("/items/{biblio_id}/ejemplares")
def get_ejemplares(biblio_id: int, db: Session = Depends(get_db)):
    """Lista los ejemplares físicos de un título, con su estado individual."""
    biblio = db.query(models.RegistroBibliografico).filter(
        models.RegistroBibliografico.id == biblio_id).first()
    if not biblio:
        raise HTTPException(status_code=404, detail="Título no encontrado en el catálogo")

    items = db.query(models.Item).filter(models.Item.biblio_id == biblio_id).all()
    resultado = []
    for item in items:
        prestamo = db.query(models.Prestamo).filter(
            models.Prestamo.item_id == item.id,
            models.Prestamo.fecha_devolucion == None).first()
        lector = None
        if prestamo:
            usuario = db.query(models.Usuario).filter(
                models.Usuario.id == prestamo.usuario_id).first()
            lector = f"{usuario.nombre} {usuario.apellido}" if usuario else None

        resultado.append({
            "id": str(item.id),
            "barcode": item.codigo_barras,
            "location": item.signatura_topografica,
            "status": item.estado,
            "dueDate": prestamo.fecha_vencimiento.strftime("%d %b %Y") if prestamo else None,
            "borrowedBy": lector,
        })
    return resultado


@router.post("/reservations", response_model=schemas.ReservaResponse, status_code=201)
def crear_reserva(payload: schemas.ReservaRequest, db: Session = Depends(get_db)):
    """Encola una reserva sobre un título cuando no hay ejemplares libres."""
    usuario = db.query(models.Usuario).filter(
        models.Usuario.nro_carnet == payload.nro_carnet,
        models.Usuario.activo == True).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado o inactivo")

    biblio = db.query(models.RegistroBibliografico).filter(
        models.RegistroBibliografico.id == payload.biblio_id).first()
    if not biblio:
        raise HTTPException(status_code=404, detail="Título no encontrado en el catálogo")

    ya_reservado = db.query(models.Reserva).filter(
        models.Reserva.biblio_id == biblio.id,
        models.Reserva.usuario_id == usuario.id,
        models.Reserva.estado == "Pendiente").first()
    if ya_reservado:
        raise HTTPException(
            status_code=400, detail="El usuario ya tiene una reserva pendiente sobre este título")

    # La prioridad es el turno en la cola: el siguiente número libre.
    en_cola = db.query(models.Reserva).filter(
        models.Reserva.biblio_id == biblio.id,
        models.Reserva.estado == "Pendiente").count()

    reserva = models.Reserva(
        biblio_id=biblio.id,
        usuario_id=usuario.id,
        prioridad=en_cola + 1,
        estado="Pendiente",
    )
    db.add(reserva)
    db.commit()
    db.refresh(reserva)

    return {
        "mensaje": f"Reserva registrada. Turno número {reserva.prioridad} en la cola.",
        "reserva_id": reserva.id,
        "prioridad": reserva.prioridad,
    }


@router.get("/reservations")
def listar_reservas(db: Session = Depends(get_db)):
    reservas = db.query(models.Reserva).order_by(
        models.Reserva.biblio_id, models.Reserva.prioridad).all()
    resultado = []
    for r in reservas:
        biblio = db.query(models.RegistroBibliografico).filter(
            models.RegistroBibliografico.id == r.biblio_id).first()
        usuario = db.query(models.Usuario).filter(
            models.Usuario.id == r.usuario_id).first()
        resultado.append({
            "id": str(r.id),
            "title": biblio.titulo if biblio else "Desconocido",
            "userName": f"{usuario.nombre} {usuario.apellido}" if usuario else "Desconocido",
            "userId": usuario.nro_carnet if usuario else "N/A",
            "priority": r.prioridad,
            "status": r.estado,
        })
    return resultado


@router.delete("/reservations/{reserva_id}")
def cancelar_reserva(reserva_id: int, db: Session = Depends(get_db)):
    reserva = db.query(models.Reserva).filter(models.Reserva.id == reserva_id).first()
    if not reserva:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    reserva.estado = "Cancelada"
    db.commit()
    return {"mensaje": "Reserva cancelada"}


@router.get("/dashboard-stats", tags=["Métricas"])
def get_dashboard_stats(db: Session = Depends(get_db)):
    ahora = _ahora()

    total_libros = db.query(models.Item).count()
    total_usuarios = db.query(models.Usuario).filter(models.Usuario.activo == True).count()

    activos = db.query(models.Prestamo).filter(
        models.Prestamo.fecha_devolucion == None).count()

    # Vencidos: activos cuya fecha de vencimiento ya pasó.
    vencidos = db.query(models.Prestamo).filter(
        models.Prestamo.fecha_devolucion == None,
        models.Prestamo.fecha_vencimiento < ahora).count()

    return {
        "totalItems": total_libros,
        "totalUsers": total_usuarios,
        "activeLoans": activos,
        "overdueLoans": vencidos,
    }
