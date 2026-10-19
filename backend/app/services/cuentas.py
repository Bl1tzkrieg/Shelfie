"""Cuentas del lector: multas, reposiciones, pagos y condonaciones."""

from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional

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


# --- A qué cargo va cada crédito ----------------------------------------------------------
#
# Un crédito (pago, condonación, reintegro) puede apuntar a un cargo concreto (cargo_id) o
# ir "a la deuda en general". Los generales se imputan a los cargos más viejos con algo
# pendiente (FIFO), como hace Koha con los pagos sin línea elegida. Así cada cargo sabe
# cuánto se le pagó, cuánto se le perdonó y cuánto le queda, y el reintegro de un
# ejemplar perdido que aparece devuelve solo lo que corresponde.

_CLASE = {"PAGO": "pagado", "CONDONACION": "condonado", "REINTEGRO": "reintegrado",
          "AJUSTE": "condonado"}


def imputacion(movimientos: List[models.MovimientoCuenta]) -> Dict[int, dict]:
    """Por cada cargo (débito): monto, pagado, condonado, reintegrado y pendiente."""
    orden = sorted(movimientos, key=lambda m: (m.fecha, m.id))
    cargos: Dict[int, dict] = {}
    for m in orden:
        if m.monto > 0:
            cargos[m.id] = {"cargo": m, "monto": _dinero(m.monto), "pagado": Decimal("0.00"),
                            "condonado": Decimal("0.00"), "reintegrado": Decimal("0.00")}
    # Reintegros anteriores a cargo_id: van a la reposición de su mismo préstamo.
    reposicion_de = {m.prestamo_id: m.id for m in orden
                     if m.tipo == "REPOSICION" and m.prestamo_id is not None}

    def pendiente(c: dict) -> Decimal:
        return c["monto"] - c["pagado"] - c["condonado"] - c["reintegrado"]

    generales = []
    for m in orden:
        if m.monto >= 0:
            continue
        clase, restante = _CLASE.get(m.tipo, "condonado"), -_dinero(m.monto)
        destino = m.cargo_id
        if destino is None and m.tipo == "REINTEGRO":
            destino = reposicion_de.get(m.prestamo_id)
        if destino in cargos:
            # Un reintegro devuelve lo pagado: puede dejar el cargo "pagado" en negativo
            # neto, pero nunca imputa más de lo que el cargo tiene.
            aplicado = min(restante, pendiente(cargos[destino]) if clase != "reintegrado"
                           else cargos[destino]["monto"] - cargos[destino]["condonado"]
                           - cargos[destino]["reintegrado"])
            aplicado = max(aplicado, Decimal("0.00"))
            cargos[destino][clase] += aplicado
            restante -= aplicado
        if restante > 0:
            generales.append([clase, restante])
    for credito in generales:
        clase, restante = credito
        for c in cargos.values():
            if restante <= 0:
                break
            hueco = pendiente(c)
            if hueco > 0:
                aplicado = min(hueco, restante)
                c[clase] += aplicado
                restante -= aplicado
    for c in cargos.values():
        c["pendiente"] = max(pendiente(c), Decimal("0.00"))
    return cargos


def imputacion_de(db: Session, usuario_id: int) -> Dict[int, dict]:
    return imputacion(db.query(models.MovimientoCuenta).filter(
        models.MovimientoCuenta.usuario_id == usuario_id).all())


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
        restante = imputacion_de(db, usuario.id)[cargo.id]["pendiente"]
        if monto > restante:
            raise ReglaIncumplida(f"A ese cargo le quedan Bs. {restante:.2f} pendientes")
        prestamo_id = cargo.prestamo_id
    registrar(db, usuario, tipo, -monto, descripcion=descripcion, personal_id=personal_id,
              prestamo_id=prestamo_id, cargo_id=cargo_id)
    db.commit()
    return estado_de_cuenta(db, usuario)


def pagar(db: Session, usuario: models.Usuario, monto, descripcion: Optional[str],
          personal_id: Optional[int], cargo_id: Optional[int] = None) -> dict:
    """Con `cargo_id` el pago va a ese cargo; si no, a los más viejos primero."""
    return _credito(db, usuario, "PAGO", monto, descripcion or "Pago en mostrador", personal_id,
                    cargo_id)


def condonar(db: Session, usuario: models.Usuario, monto, motivo: str,
             personal_id: Optional[int], cargo_id: Optional[int] = None) -> dict:
    """Perdona deuda: a un cargo con `cargo_id`, o a los más viejos primero."""
    if not motivo or not motivo.strip():
        raise ReglaIncumplida("Indica el motivo de la condonación")
    return _credito(db, usuario, "CONDONACION", monto, motivo.strip(), personal_id, cargo_id)


def estado_de_cuenta(db: Session, usuario: models.Usuario) -> dict:
    movimientos: List[models.MovimientoCuenta] = db.query(models.MovimientoCuenta).filter(
        models.MovimientoCuenta.usuario_id == usuario.id).order_by(
        models.MovimientoCuenta.fecha.desc(), models.MovimientoCuenta.id.desc()).all()
    actual, umbral = saldo(db, usuario.id), umbral_de_bloqueo(db)
    cargos = imputacion(movimientos)
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
        # Cargos con algo pendiente: a qué se le puede aplicar un pago o una condonación.
        "cargos": [
            {"id": m.id, "tipo": m.tipo, "descripcion": m.descripcion,
             "fecha": formatear_fecha_hora(m.fecha), "monto": float(m.monto),
             "pagado": float(c["pagado"]), "condonado": float(c["condonado"]),
             "pendiente": float(c["pendiente"])}
            for m in movimientos if m.id in cargos
            for c in [cargos[m.id]] if c["pendiente"] > 0
        ],
    }
