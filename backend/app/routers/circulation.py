import csv
import io
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/api/v1/circulation", tags=["Circulación"])

# El frontend clasifica a los lectores en tres grupos; los códigos de categoría
# de la base de datos se normalizan contra ese vocabulario.
USER_TYPE_POR_CATEGORIA = {
    "doc": "teacher",
    "docente": "teacher",
    "adm": "staff",
    "staff": "staff",
}

# Tope por defecto cuando la configuración del sistema no dice otra cosa.
RENOVACIONES_POR_DEFECTO = 2


def _ahora() -> datetime:
    """Fecha/hora naive en UTC, para comparar con las columnas TIMESTAMP sin zona."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _resolver_user_type(categoria):
    if not categoria or not categoria.codigo:
        return "student"
    return USER_TYPE_POR_CATEGORIA.get(categoria.codigo.lower(), "student")


def _max_renovaciones(db: Session) -> int:
    """Lee el tope de renovaciones de la configuración del sistema."""
    config = db.query(models.Configuracion).filter(
        models.Configuracion.clave == "politicas_prestamo").first()
    if config and isinstance(config.valor, dict):
        return int(config.valor.get("renovaciones_permitidas", RENOVACIONES_POR_DEFECTO))
    return RENOVACIONES_POR_DEFECTO


@router.post("/checkout", response_model=schemas.PrestamoResponse)
def checkout_item(payload: schemas.CheckoutRequest, db: Session = Depends(get_db)):
    # 1. Validar existencia del usuario
    usuario = db.query(models.Usuario).filter(
        models.Usuario.nro_carnet == payload.nro_carnet,
        models.Usuario.activo == True).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado o inactivo")

    # 2. Validar existencia y disponibilidad del ítem
    item = db.query(models.Item).filter(
        models.Item.codigo_barras == payload.codigo_barras).first()
    if not item:
        raise HTTPException(status_code=404, detail="Ejemplar de biblioteca no encontrado")
    if item.estado != "Disponible":
        raise HTTPException(
            status_code=400,
            detail=f"El ítem no puede ser prestado. Estado actual: {item.estado}")

    # 3. Obtener políticas de préstamo basadas en la categoría de usuario
    categoria = db.query(models.CategoriaUsuario).filter(
        models.CategoriaUsuario.id == usuario.categoria_id).first()
    if not categoria:
        raise HTTPException(
            status_code=400,
            detail="El usuario no tiene una categoría asignada, no se pueden aplicar políticas")

    # 4. Verificar que no exceda el tope de préstamos simultáneos de su categoría
    activos = db.query(models.Prestamo).filter(
        models.Prestamo.usuario_id == usuario.id,
        models.Prestamo.fecha_devolucion == None).count()
    if activos >= categoria.max_prestamos:
        raise HTTPException(
            status_code=400,
            detail=f"El usuario alcanzó su límite de {categoria.max_prestamos} préstamos simultáneos")

    # 5. Bloquear a quien tenga multas pendientes
    if usuario.saldo_multas and float(usuario.saldo_multas) > 0:
        raise HTTPException(
            status_code=400,
            detail=f"El usuario tiene multas pendientes por Bs. {float(usuario.saldo_multas):.2f}")

    # 6. Calcular fechas límite transaccionales
    fecha_actual = _ahora()
    fecha_vence = fecha_actual + timedelta(days=categoria.dias_prestamo)

    # 7. Generar transacción de préstamo y actualizar inventario
    nuevo_prestamo = models.Prestamo(
        item_id=item.id,
        usuario_id=usuario.id,
        fecha_prestamo=fecha_actual,
        fecha_vencimiento=fecha_vence,
        renovaciones_realizadas=0,
    )
    item.estado = "Prestado"

    db.add(nuevo_prestamo)
    db.commit()
    db.refresh(nuevo_prestamo)
    return nuevo_prestamo


@router.post("/checkin", response_model=schemas.ReturnResponse)
def checkin_item(payload: schemas.CheckinRequest, db: Session = Depends(get_db)):
    # 1. Localizar el ítem mediante su identificador físico
    item = db.query(models.Item).filter(
        models.Item.codigo_barras == payload.codigo_barras).first()
    if not item or item.estado != "Prestado":
        raise HTTPException(
            status_code=400,
            detail="El ítem no está registrado como prestado en este momento")

    # 2. Recuperar el préstamo activo asociado
    prestamo = db.query(models.Prestamo).filter(
        models.Prestamo.item_id == item.id,
        models.Prestamo.fecha_devolucion == None).first()
    if not prestamo:
        raise HTTPException(
            status_code=400,
            detail="El ejemplar figura prestado pero no tiene un préstamo activo asociado")

    # 3. Traer datos del usuario y sus políticas punitivas por mora
    usuario = db.query(models.Usuario).filter(
        models.Usuario.id == prestamo.usuario_id).first()
    categoria = db.query(models.CategoriaUsuario).filter(
        models.CategoriaUsuario.id == usuario.categoria_id).first() if usuario else None

    fecha_actual = _ahora()
    multa_total = 0.0

    # 4. Algoritmo automático de penalización por retraso
    if categoria and fecha_actual > prestamo.fecha_vencimiento:
        dias_retraso = (fecha_actual - prestamo.fecha_vencimiento).days
        multa_total = dias_retraso * float(categoria.multa_por_dia)

        # Guardar registro oficial de la multa
        nueva_multa = models.Multa(
            prestamo_id=prestamo.id, usuario_id=usuario.id, monto=multa_total)
        db.add(nueva_multa)
        # Aplicar el balance negativo directamente a la cuenta del lector
        usuario.saldo_multas = float(usuario.saldo_multas or 0) + multa_total

    # 5. Registrar devolución física
    prestamo.fecha_devolucion = fecha_actual

    # 6. Comprobar colas de reservas pendientes (si alguien más lo esperaba en la cola)
    reserva_pendiente = db.query(models.Reserva).filter(
        models.Reserva.biblio_id == item.biblio_id,
        models.Reserva.estado == "Pendiente"
    ).order_by(models.Reserva.prioridad.asc()).first()

    nuevo_estado = "Reservado" if reserva_pendiente else "Disponible"
    item.estado = nuevo_estado

    db.commit()

    return {
        "mensaje": "Devolución registrada correctamente en el inventario",
        "multa_aplicada": multa_total,
        "nuevo_estado_item": nuevo_estado,
    }


@router.post("/renew", response_model=schemas.RenewResponse)
def renew_loan(payload: schemas.RenewRequest, db: Session = Depends(get_db)):
    """Extiende la fecha de vencimiento de un préstamo activo."""
    prestamo = db.query(models.Prestamo).filter(
        models.Prestamo.id == payload.prestamo_id).first()
    if not prestamo:
        raise HTTPException(status_code=404, detail="Préstamo no encontrado")
    if prestamo.fecha_devolucion:
        raise HTTPException(
            status_code=400, detail="El préstamo ya fue devuelto, no puede renovarse")

    tope = _max_renovaciones(db)
    realizadas = prestamo.renovaciones_realizadas or 0
    if realizadas >= tope:
        raise HTTPException(
            status_code=400,
            detail=f"El préstamo agotó sus {tope} renovaciones permitidas")

    usuario = db.query(models.Usuario).filter(
        models.Usuario.id == prestamo.usuario_id).first()
    categoria = db.query(models.CategoriaUsuario).filter(
        models.CategoriaUsuario.id == usuario.categoria_id).first() if usuario else None
    dias = categoria.dias_prestamo if categoria else 7

    # No se renueva un ejemplar que otro lector está esperando en la cola de reservas.
    item = db.query(models.Item).filter(models.Item.id == prestamo.item_id).first()
    if item:
        hay_cola = db.query(models.Reserva).filter(
            models.Reserva.biblio_id == item.biblio_id,
            models.Reserva.estado == "Pendiente").count()
        if hay_cola:
            raise HTTPException(
                status_code=400,
                detail="No se puede renovar: hay reservas pendientes sobre este título")

    # La extensión corre desde el vencimiento original si aún no venció,
    # y desde hoy si ya está atrasado.
    base = max(prestamo.fecha_vencimiento, _ahora())
    prestamo.fecha_vencimiento = base + timedelta(days=dias)
    prestamo.renovaciones_realizadas = realizadas + 1

    db.commit()
    db.refresh(prestamo)

    return {
        "mensaje": "Préstamo renovado correctamente",
        "nueva_fecha_vencimiento": prestamo.fecha_vencimiento,
        "renovaciones_realizadas": prestamo.renovaciones_realizadas,
        "renovaciones_restantes": tope - prestamo.renovaciones_realizadas,
    }


def _serializar_prestamos(db: Session):
    """Arma la vista de préstamos que consume la tabla de circulación."""
    prestamos = db.query(models.Prestamo).order_by(models.Prestamo.id.desc()).all()
    ahora = _ahora()
    resultado = []

    for p in prestamos:
        usuario = db.query(models.Usuario).filter(models.Usuario.id == p.usuario_id).first()
        item = db.query(models.Item).filter(models.Item.id == p.item_id).first()
        biblio = db.query(models.RegistroBibliografico).filter(
            models.RegistroBibliografico.id == item.biblio_id).first() if item else None
        categoria = db.query(models.CategoriaUsuario).filter(
            models.CategoriaUsuario.id == usuario.categoria_id).first() if usuario else None

        resultado.append({
            "id": str(p.id),
            "bookTitle": biblio.titulo if biblio else "Desconocido",
            "bookCode": item.codigo_barras if item else "N/A",
            "userName": f"{usuario.nombre} {usuario.apellido}" if usuario else "Desconocido",
            "userId": usuario.nro_carnet if usuario else "N/A",
            "userType": _resolver_user_type(categoria),
            "loanDate": p.fecha_prestamo.strftime("%d %b %Y"),
            "dueDate": p.fecha_vencimiento.strftime("%d %b %Y"),
            "returnDate": p.fecha_devolucion.strftime("%d %b %Y") if p.fecha_devolucion else None,
            "renewals": p.renovaciones_realizadas or 0,
            "status": "returned" if p.fecha_devolucion else (
                "overdue" if ahora > p.fecha_vencimiento else "active"),
        })

    return resultado


@router.get("/loans")
def get_all_loans(db: Session = Depends(get_db)):
    return _serializar_prestamos(db)


@router.get("/loans/export")
def export_loans(db: Session = Depends(get_db)):
    """Descarga el listado de préstamos en CSV."""
    filas = _serializar_prestamos(db)

    buffer = io.StringIO()
    columnas = ["id", "bookTitle", "bookCode", "userName", "userId", "userType",
                "loanDate", "dueDate", "returnDate", "renewals", "status"]
    writer = csv.DictWriter(buffer, fieldnames=columnas, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(filas)

    # El BOM hace que Excel abra el archivo en UTF-8 sin romper los acentos.
    contenido = "﻿" + buffer.getvalue()
    nombre = f"prestamos-{_ahora().strftime('%Y%m%d')}.csv"

    return StreamingResponse(
        iter([contenido]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )
