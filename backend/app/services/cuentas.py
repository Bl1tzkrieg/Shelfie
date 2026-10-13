"""Cuentas del lector: multas, reposiciones, pagos y condonaciones."""

from decimal import ROUND_HALF_UP, Decimal
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.core.errores import NoEncontrado, ReglaIncumplida
from app.core.tiempo import ahora, formatear_fecha_hora
from app.services import configuracion

DEBITOS = {"MULTA_ATRASO", "REPOSICION", "AJUSTE"}
CENTIMO = Decimal("0.01")


def _dinero(valor) -> Decimal:
    return Decimal(str(valor)).quantize(CENTIMO, rounding=ROUND_HALF_UP)


def saldo(db: Session, usuario_id: int) -> Decimal:
    total = db.query(func.coalesce(func.sum(models.MovimientoCuenta.monto), 0)).filter(
        models.MovimientoCuenta.usuario_id == usuario_id).scalar()
    return _dinero(total)


def umbral_de_bloqueo(db: Session) -> Decimal:
    return _dinero(configuracion.leer(db, "circulacion")["umbral_bloqueo"])


def esta_bloqueado(saldo_actual, umbral) -> bool:
    """Bloquea préstamos, renovaciones y reservas cuando la deuda SUPERA el umbral."""
    return _dinero(saldo_actual) > _dinero(umbral)


def registrar(db: Session, usuario: models.Usuario, tipo: str, monto, *,
              prestamo_id: Optional[int] = None, descripcion: Optional[str] = None,
              personal_id: Optional[int] = None,
              cargo_id: Optional[int] = None) -> models.MovimientoCuenta:
    """Agrega un movimiento (sin commit) y actualiza el saldo cacheado del lector."""
    monto = _dinero(monto)
    movimiento = models.MovimientoCuenta(
        usuario_id=usuario.id, tipo=tipo, monto=monto, prestamo_id=prestamo_id,
        descripcion=descripcion, fecha=ahora(), personal_id=personal_id, cargo_id=cargo_id)
    db.add(movimiento)
    db.flush()
    usuario.saldo_multas = saldo(db, usuario.id)
    return movimiento


def aplicado_a(db: Session, cargo_id: int) -> Decimal:
    """Lo acreditado directamente a un cargo (condonaciones dirigidas), en negativo."""
    return _dinero(db.query(func.coalesce(func.sum(models.MovimientoCuenta.monto), 0)).filter(
        models.MovimientoCuenta.cargo_id == cargo_id).scalar())


def _credito(db: Session, usuario: models.Usuario, tipo: str, monto, descripcion: str,
             personal_id: Optional[int], cargo_id: Optional[int] = None) -> dict:
    monto = _dinero(monto)
    if monto <= 0:
        raise ReglaIncumplida("El monto debe ser mayor que cero")
    pendiente = saldo(db, usuario.id)
    if monto > pendiente:
        raise ReglaIncumplida(f"El monto supera la deuda pendiente (Bs. {pendiente:.2f})")
    prestamo_id = None
    if cargo_id is not None:
        cargo = db.get(models.MovimientoCuenta, cargo_id)
        if not cargo or cargo.usuario_id != usuario.id or cargo.monto <= 0:
            raise NoEncontrado("Cargo no encontrado en la cuenta del lector")
        restante = _dinero(cargo.monto) + aplicado_a(db, cargo.id)
        if monto > restante:
            raise ReglaIncumplida(f"A ese cargo le quedan Bs. {restante:.2f} por condonar")
        prestamo_id = cargo.prestamo_id
    registrar(db, usuario, tipo, -monto, descripcion=descripcion, personal_id=personal_id,
              prestamo_id=prestamo_id, cargo_id=cargo_id)
    db.commit()
    return estado_de_cuenta(db, usuario)


def pagar(db: Session, usuario: models.Usuario, monto, descripcion: Optional[str],
          personal_id: Optional[int]) -> dict:
    return _credito(db, usuario, "PAGO", monto, descripcion or "Pago en mostrador", personal_id)


def condonar(db: Session, usuario: models.Usuario, monto, motivo: str,
             personal_id: Optional[int], cargo_id: Optional[int] = None) -> dict:
    """Perdona deuda. Con `cargo_id`, se aplica a ese cargo (cuenta para los reintegros)."""
    if not motivo or not motivo.strip():
        raise ReglaIncumplida("Indica el motivo de la condonación")
    return _credito(db, usuario, "CONDONACION", monto, motivo.strip(), personal_id, cargo_id)


def estado_de_cuenta(db: Session, usuario: models.Usuario) -> dict:
    movimientos: List[models.MovimientoCuenta] = db.query(models.MovimientoCuenta).filter(
        models.MovimientoCuenta.usuario_id == usuario.id).order_by(
        models.MovimientoCuenta.fecha.desc(), models.MovimientoCuenta.id.desc()).all()
    actual, umbral = saldo(db, usuario.id), umbral_de_bloqueo(db)
    aplicados: dict = {}
    # Reintegros anteriores a cargo_id: se aplican a la reposición de su mismo préstamo.
    reposicion_de = {m.prestamo_id: m.id for m in movimientos
                     if m.tipo == "REPOSICION" and m.prestamo_id is not None}
    for m in movimientos:
        destino = m.cargo_id
        if destino is None and m.tipo == "REINTEGRO":
            destino = reposicion_de.get(m.prestamo_id)
        if destino is not None:
            aplicados[destino] = aplicados.get(destino, Decimal("0.00")) + _dinero(m.monto)
    return {
        "saldo": float(actual),
        "umbral_bloqueo": float(umbral),
        "bloqueado": esta_bloqueado(actual, umbral),
        "movimientos": [
            {
                "id": m.id,
                "tipo": m.tipo,
                "monto": float(m.monto),
                "descripcion": m.descripcion,
                "fecha": formatear_fecha_hora(m.fecha),
                "prestamo_id": m.prestamo_id,
                "cargo_id": m.cargo_id,
            }
            for m in movimientos
        ],
        # Débitos con algo por condonar: a qué se le puede aplicar una condonación.
        "cargos": [
            {"id": m.id, "tipo": m.tipo, "descripcion": m.descripcion,
             "fecha": formatear_fecha_hora(m.fecha), "monto": float(m.monto),
             "pendiente": float(min(restante, max(actual, Decimal("0.00"))))}
            for m in movimientos if m.monto > 0
            for restante in [_dinero(m.monto) + aplicados.get(m.id, Decimal("0.00"))]
            if restante > 0 and actual > 0
        ],
    }
