from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/v1/circulation", tags=["Circulación"])

@router.post("/checkout", response_model=schemas.PrestamoResponse)
def checkout_item(payload: schemas.CheckoutRequest, db: Session = Depends(get_db)):
    # 1. Validar existencia del usuario
    usuario = db.query(models.Usuario).filter(models.Usuario.nro_carnet == payload.nro_carnet, models.Usuario.activo == True).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado o inactivo")
    
    # 2. Validar existencia y disponibilidad del ítem
    item = db.query(models.Item).filter(models.Item.codigo_barras == payload.codigo_barras).first()
    if not item:
        raise HTTPException(status_code=404, detail="Ejemplar de biblioteca no encontrado")
    if item.estado != "Disponible":
        raise HTTPException(status_code=400, detail=f"El ítem no puede ser prestado. Estado actual: {item.estado}")
    
    # 3. Obtener políticas de préstamo basadas en la categoría de usuario
    categoria = db.query(models.CategoriaUsuario).filter(models.CategoriaUsuario.id == usuario.categoria_id).first()
    
    # 4. Calcular fechas límite transaccionales
    fecha_actual = datetime.utcnow()
    fecha_vence = fecha_actual + timedelta(days=categoria.dias_prestamo)
    
    # 5. Generar transacción de préstamo y actualizar inventario
    nuevo_prestamo = models.Prestamo(
        item_id=item.id,
        usuario_id=usuario.id,
        fecha_prestamo=fecha_actual,
        fecha_vencimiento=fecha_vence
    )
    item.estado = "Prestado"
    
    db.add(nuevo_prestamo)
    db.commit()
    db.refresh(nuevo_prestamo)
    return nuevo_prestamo


@router.post("/checkin", response_model=schemas.ReturnResponse)
def checkin_item(payload: schemas.CheckinRequest, db: Session = Depends(get_db)):
    # 1. Localizar el ítem mediante su identificador físico
    item = db.query(models.Item).filter(models.Item.codigo_barras == payload.codigo_barras).first()
    if not item or item.estado != "Prestado":
        raise HTTPException(status_code=400, detail="El ítem no está registrado como prestado en este momento")
    
    # 2. Recuperar el préstamo activo asociado
    prestamo = db.query(models.Prestamo).filter(models.Prestamo.item_id == item.id, models.Prestamo.fecha_devolucion == None).first()
    
    # 3. Traer datos del usuario y sus políticas punitivas por mora
    usuario = db.query(models.Usuario).filter(models.Usuario.id == prestamo.usuario_id).first()
    categoria = db.query(models.CategoriaUsuario).filter(models.CategoriaUsuario.id == usuario.categoria_id).first()
    
    fecha_actual = datetime.utcnow()
    multa_total = 0.0
    
    # 4. Algoritmo automático de penalización por retraso
    if fecha_actual > prestamo.fecha_vencimiento:
        dias_retraso = (fecha_actual - prestamo.fecha_vencimiento).days
        multa_total = dias_retraso * float(categoria.multa_por_dia)
        
        # Guardar registro oficial de la multa
        nueva_multa = models.Multa(prestamo_id=prestamo.id, usuario_id=usuario.id, monto=multa_total)
        db.add(nueva_multa)
        # Aplicar el balance negativo directamente a la cuenta del lector
        usuario.saldo_multas = float(usuario.saldo_multas) + multa_total

    # 5. Registrar devolución física
    prestamo.fecha_devolucion = fecha_actual
    
    # 6. Comprobar colas de reservas pendientes (Si alguien más lo esperaba en la cola)
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
        "nuevo_estado_item": nuevo_estado
    }