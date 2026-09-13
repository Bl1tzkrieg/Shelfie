import csv
import io
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import hash_password

router = APIRouter(prefix="/api/v1", tags=["Usuarios"])


def _ahora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _serializar_usuario(db: Session, u: models.Usuario) -> dict:
    activos = db.query(models.Prestamo).filter(
        models.Prestamo.usuario_id == u.id,
        models.Prestamo.fecha_devolucion == None).count()

    total = db.query(models.Prestamo).filter(
        models.Prestamo.usuario_id == u.id).count()

    categoria = None
    if u.categoria_id:
        categoria = db.query(models.CategoriaUsuario).filter(
            models.CategoriaUsuario.id == u.categoria_id).first()

    return {
        "nro_carnet": u.nro_carnet,
        "nombre": u.nombre,
        "apellido": u.apellido,
        "email": u.email,
        "activo": u.activo,
        "saldo_multas": float(u.saldo_multas or 0),
        "departamento": u.departamento,
        "fecha_creacion": u.fecha_creacion,
        "categoria": categoria,
        "prestamos_activos_count": activos,
        "total_prestamos_count": total,
    }


@router.get("/users", response_model=List[schemas.UserResponse])
def get_users(db: Session = Depends(get_db)):
    usuarios = db.query(models.Usuario).order_by(models.Usuario.id).all()
    return [_serializar_usuario(db, u) for u in usuarios]


@router.post("/users", response_model=schemas.UserResponse, status_code=201)
def crear_usuario(payload: schemas.NuevoUsuarioRequest, db: Session = Depends(get_db)):
    if db.query(models.Usuario).filter(
            models.Usuario.nro_carnet == payload.nro_carnet).first():
        raise HTTPException(
            status_code=400, detail=f"Ya existe un usuario con el carnet {payload.nro_carnet}")

    if db.query(models.Usuario).filter(models.Usuario.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Ese email ya está registrado")

    # Si no se indica username se deriva del carnet, que es único.
    username = payload.username or f"u{payload.nro_carnet}"
    if db.query(models.Usuario).filter(models.Usuario.username == username).first():
        raise HTTPException(status_code=400, detail=f"El username '{username}' ya está tomado")

    categoria = db.query(models.CategoriaUsuario).filter(
        models.CategoriaUsuario.codigo == payload.categoria_codigo).first()
    if not categoria:
        raise HTTPException(
            status_code=400,
            detail=f"No existe la categoría de usuario '{payload.categoria_codigo}'")

    # Sin contraseña explícita se usa el carnet como clave inicial.
    password_inicial = payload.password or payload.nro_carnet

    usuario = models.Usuario(
        nro_carnet=payload.nro_carnet,
        username=username,
        password_hash=hash_password(password_inicial),
        nombre=payload.nombre,
        apellido=payload.apellido,
        email=payload.email,
        departamento=payload.departamento,
        categoria_id=categoria.id,
        saldo_multas=0,
        activo=True,
        fecha_creacion=_ahora(),
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)

    return _serializar_usuario(db, usuario)


@router.get("/users/{nro_carnet}", response_model=schemas.UserResponse)
def get_usuario(nro_carnet: str, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(
        models.Usuario.nro_carnet == nro_carnet).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return _serializar_usuario(db, usuario)


@router.get("/users/{nro_carnet}/loans")
def get_prestamos_usuario(nro_carnet: str, db: Session = Depends(get_db)):
    """Historial de préstamos de un lector, para su ficha de perfil."""
    usuario = db.query(models.Usuario).filter(
        models.Usuario.nro_carnet == nro_carnet).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    ahora = _ahora()
    prestamos = db.query(models.Prestamo).filter(
        models.Prestamo.usuario_id == usuario.id).order_by(
        models.Prestamo.fecha_prestamo.desc()).all()

    resultado = []
    for p in prestamos:
        item = db.query(models.Item).filter(models.Item.id == p.item_id).first()
        biblio = db.query(models.RegistroBibliografico).filter(
            models.RegistroBibliografico.id == item.biblio_id).first() if item else None
        resultado.append({
            "id": str(p.id),
            "bookTitle": biblio.titulo if biblio else "Desconocido",
            "bookCode": item.codigo_barras if item else "N/A",
            "loanDate": p.fecha_prestamo.strftime("%d %b %Y"),
            "dueDate": p.fecha_vencimiento.strftime("%d %b %Y"),
            "returnDate": p.fecha_devolucion.strftime("%d %b %Y") if p.fecha_devolucion else None,
            "renewals": p.renovaciones_realizadas or 0,
            "status": "returned" if p.fecha_devolucion else (
                "overdue" if ahora > p.fecha_vencimiento else "active"),
        })
    return resultado


@router.put("/users/{nro_carnet}", response_model=schemas.UserResponse)
def editar_usuario(
    nro_carnet: str,
    payload: schemas.EditarUsuarioRequest,
    db: Session = Depends(get_db),
):
    usuario = db.query(models.Usuario).filter(
        models.Usuario.nro_carnet == nro_carnet).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if payload.email and payload.email != usuario.email:
        if db.query(models.Usuario).filter(models.Usuario.email == payload.email).first():
            raise HTTPException(status_code=400, detail="Ese email ya está registrado")
        usuario.email = payload.email

    if payload.nombre:
        usuario.nombre = payload.nombre
    if payload.apellido:
        usuario.apellido = payload.apellido
    if payload.departamento is not None:
        usuario.departamento = payload.departamento

    if payload.categoria_codigo:
        categoria = db.query(models.CategoriaUsuario).filter(
            models.CategoriaUsuario.codigo == payload.categoria_codigo).first()
        if not categoria:
            raise HTTPException(
                status_code=400,
                detail=f"No existe la categoría '{payload.categoria_codigo}'")
        usuario.categoria_id = categoria.id

    db.commit()
    db.refresh(usuario)
    return _serializar_usuario(db, usuario)


@router.patch("/users/{nro_carnet}/status", response_model=schemas.UserResponse)
def cambiar_estado_usuario(
    nro_carnet: str,
    payload: schemas.EstadoUsuarioRequest,
    db: Session = Depends(get_db),
):
    """Suspende o reactiva a un lector."""
    usuario = db.query(models.Usuario).filter(
        models.Usuario.nro_carnet == nro_carnet).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if not payload.activo:
        activos = db.query(models.Prestamo).filter(
            models.Prestamo.usuario_id == usuario.id,
            models.Prestamo.fecha_devolucion == None).count()
        if activos:
            raise HTTPException(
                status_code=400,
                detail=f"No se puede suspender: el usuario tiene {activos} préstamo(s) sin devolver")

    usuario.activo = payload.activo
    db.commit()
    db.refresh(usuario)
    return _serializar_usuario(db, usuario)


@router.get("/users-export")
def export_users(db: Session = Depends(get_db)):
    """Descarga el padrón de usuarios en CSV."""
    usuarios = db.query(models.Usuario).order_by(models.Usuario.id).all()
    filas = []
    for u in usuarios:
        d = _serializar_usuario(db, u)
        filas.append({
            "nro_carnet": d["nro_carnet"],
            "nombre": d["nombre"],
            "apellido": d["apellido"],
            "email": d["email"],
            "departamento": d["departamento"] or "",
            "categoria": d["categoria"].descripcion if d["categoria"] else "",
            "activo": "Sí" if d["activo"] else "No",
            "saldo_multas": f"{d['saldo_multas']:.2f}",
            "prestamos_activos": d["prestamos_activos_count"],
            "total_prestamos": d["total_prestamos_count"],
        })

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(filas[0].keys()) if filas else ["nro_carnet"])
    writer.writeheader()
    writer.writerows(filas)

    contenido = "﻿" + buffer.getvalue()
    nombre = f"usuarios-{_ahora().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([contenido]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.post("/users-import")
def import_users(filas: List[schemas.NuevoUsuarioRequest], db: Session = Depends(get_db)):
    """Alta masiva de lectores. Informa fila por fila qué se creó y qué se omitió."""
    creados, omitidos = 0, []

    for i, fila in enumerate(filas, start=1):
        try:
            crear_usuario(fila, db)
            creados += 1
        except HTTPException as e:
            db.rollback()
            omitidos.append({"fila": i, "carnet": fila.nro_carnet, "motivo": e.detail})

    return {"creados": creados, "omitidos": omitidos, "total": len(filas)}


@router.get("/categories", response_model=List[schemas.CategoriaSchema])
def get_categorias(db: Session = Depends(get_db)):
    """Categorías disponibles, para poblar los selectores del frontend."""
    return db.query(models.CategoriaUsuario).order_by(models.CategoriaUsuario.codigo).all()
