"""Presupuestos y fondos: cuánto hay, cuánto está comprometido y cuánto se gastó.

Como en Koha, nada de esto se guarda: se calcula de los pedidos y las facturas.

- Comprometido: lo pedido y todavía no recibido, al costo estimado
  ((cantidad - recibida) × costo_estimado) en líneas vivas de pedidos vivos.
- Gastado: lo recibido, al costo real de cada recepción, más los envíos de las
  facturas cargados al fondo.
- Disponible: asignado - comprometido - gastado.
"""

from decimal import Decimal
from typing import Dict, Iterable, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.core.errores import NoEncontrado, ReglaIncumplida

P, F = models.Presupuesto, models.Fondo
L, O, R = models.LineaOrden, models.OrdenCompra, models.Recepcion

CERO = Decimal("0.00")
LINEAS_VIVAS = ("Pendiente", "Parcial")
PEDIDOS_VIVOS = ("Abierta", "Cerrada")


def _d(valor) -> Decimal:
    return Decimal(str(valor or 0)).quantize(Decimal("0.01"))


# --- Cálculo --------------------------------------------------------------------------

def movimientos(db: Session, fondo_ids: Optional[Iterable[int]] = None) -> Dict[int, dict]:
    """{fondo_id: {comprometido, gastado}} en tres consultas, para todos los fondos pedidos."""
    ids = list(fondo_ids) if fondo_ids is not None else None
    resultado: Dict[int, dict] = {}

    def acumular(filas, clave):
        for fondo_id, monto in filas:
            if fondo_id is not None:
                resultado.setdefault(fondo_id, {"comprometido": CERO, "gastado": CERO})
                resultado[fondo_id][clave] += _d(monto)

    filtro = [L.fondo_id.in_(ids)] if ids is not None else []
    acumular(db.query(L.fondo_id, func.sum((L.cantidad - L.cantidad_recibida) * L.costo_estimado))
             .join(O, O.id == L.orden_id)
             .filter(L.estado.in_(LINEAS_VIVAS), O.estado.in_(PEDIDOS_VIVOS), *filtro)
             .group_by(L.fondo_id), "comprometido")
    acumular(db.query(L.fondo_id, func.sum(R.cantidad * R.costo_unitario))
             .join(L, L.id == R.linea_id).filter(*filtro).group_by(L.fondo_id), "gastado")
    filtro_envio = ([models.Factura.fondo_envio_id.in_(ids)] if ids is not None else [])
    acumular(db.query(models.Factura.fondo_envio_id, func.sum(models.Factura.costo_envio))
             .filter(*filtro_envio).group_by(models.Factura.fondo_envio_id), "gastado")
    return resultado


def vista_fondo(f: models.Fondo, mov: dict, presupuesto: Optional[models.Presupuesto] = None,
                nombres_sedes: Optional[dict] = None) -> dict:
    asignado = _d(f.monto_asignado)
    comprometido = mov.get("comprometido", CERO)
    gastado = mov.get("gastado", CERO)
    datos = {
        "id": f.id,
        "presupuesto_id": f.presupuesto_id,
        "codigo": f.codigo,
        "nombre": f.nombre,
        "biblioteca_id": f.biblioteca_id,
        "biblioteca": (nombres_sedes or {}).get(f.biblioteca_id),
        "activo": bool(f.activo),
        "asignado": float(asignado),
        "comprometido": float(comprometido),
        "gastado": float(gastado),
        "disponible": float(asignado - comprometido - gastado),
    }
    if presupuesto is not None:
        datos["presupuesto"] = presupuesto.nombre
        datos["utilizable"] = bool(f.activo and presupuesto.activo)
    return datos


def disponible(db: Session, fondo: models.Fondo) -> Decimal:
    mov = movimientos(db, [fondo.id]).get(fondo.id, {})
    return _d(fondo.monto_asignado) - mov.get("comprometido", CERO) - mov.get("gastado", CERO)


def fondo_utilizable(db: Session, fondo_id: Optional[int]) -> Optional[models.Fondo]:
    """El fondo existe, está activo y su presupuesto también (o no se indicó fondo)."""
    if fondo_id is None:
        return None
    # Bloqueo de fila: dos pedidos a la vez sobre el mismo fondo no pasan juntos la
    # comprobación de saldo (se espera hasta que el otro termine).
    fondo = db.get(F, fondo_id, with_for_update=True)
    if not fondo:
        raise NoEncontrado("Fondo no encontrado")
    presupuesto = db.get(P, fondo.presupuesto_id)
    if not fondo.activo or not presupuesto.activo:
        raise ReglaIncumplida(f"El fondo {fondo.codigo} no está activo para pedidos nuevos")
    if presupuesto.bloqueado:
        raise ReglaIncumplida(
            f"El presupuesto {presupuesto.nombre} está bloqueado (ejercicio cerrado): "
            "no admite pedidos ni gastos nuevos")
    return fondo


def exigir_saldo(db: Session, fondo: Optional[models.Fondo], monto_nuevo: Decimal,
                 monto_previo: Decimal = CERO, que: str = "la línea compromete") -> None:
    """El fondo cubre `monto_nuevo` (descontando lo que esta misma línea ya comprometía)."""
    if fondo is None or monto_nuevo <= monto_previo:
        return
    libre = disponible(db, fondo) + monto_previo
    if monto_nuevo > libre:
        raise ReglaIncumplida(
            f"El fondo {fondo.codigo} tiene Bs. {libre:.2f} disponibles y {que} "
            f"Bs. {monto_nuevo:.2f}")


# --- Presupuestos ---------------------------------------------------------------------

def _obtener(db: Session, presupuesto_id: int) -> models.Presupuesto:
    presupuesto = db.get(P, presupuesto_id)
    if not presupuesto:
        raise NoEncontrado("Presupuesto no encontrado")
    return presupuesto


def _asignado(db: Session, presupuesto_id: int, sin_fondo: Optional[int] = None) -> Decimal:
    consulta = db.query(func.coalesce(func.sum(F.monto_asignado), 0)).filter(
        F.presupuesto_id == presupuesto_id)
    if sin_fondo is not None:
        consulta = consulta.filter(F.id != sin_fondo)
    return _d(consulta.scalar())


def vista_presupuesto(db: Session, p: models.Presupuesto, fondos: List[models.Fondo],
                      mov: Dict[int, dict], nombres_sedes: dict) -> dict:
    vistas = [vista_fondo(f, mov.get(f.id, {}), nombres_sedes=nombres_sedes) for f in fondos]
    asignado = sum((_d(f.monto_asignado) for f in fondos), CERO)
    return {
        "id": p.id,
        "nombre": p.nombre,
        "fecha_inicio": p.fecha_inicio.isoformat(),
        "fecha_fin": p.fecha_fin.isoformat(),
        "monto_total": float(_d(p.monto_total)),
        "activo": bool(p.activo),
        "bloqueado": bool(p.bloqueado),
        "asignado": float(asignado),
        "sin_asignar": float(_d(p.monto_total) - asignado),
        "comprometido": float(sum((Decimal(str(v["comprometido"])) for v in vistas), CERO)),
        "gastado": float(sum((Decimal(str(v["gastado"])) for v in vistas), CERO)),
        "fondos": vistas,
    }


def listar(db: Session) -> List[dict]:
    presupuestos = db.query(P).order_by(P.activo.desc(), P.fecha_inicio.desc(), P.id.desc()).all()
    fondos = db.query(F).order_by(F.codigo).all()
    mov = movimientos(db)
    nombres_sedes = {b.id: b.nombre for b in db.query(models.Biblioteca).all()}
    return [vista_presupuesto(db, p, [f for f in fondos if f.presupuesto_id == p.id], mov,
                              nombres_sedes) for p in presupuestos]


def obtener(db: Session, presupuesto_id: int) -> dict:
    p = _obtener(db, presupuesto_id)
    fondos = db.query(F).filter(F.presupuesto_id == p.id).order_by(F.codigo).all()
    nombres_sedes = {b.id: b.nombre for b in db.query(models.Biblioteca).all()}
    return vista_presupuesto(db, p, fondos, movimientos(db, [f.id for f in fondos]), nombres_sedes)


def _validar_presupuesto(db: Session, p: models.Presupuesto) -> None:
    if not (p.nombre or "").strip():
        raise ReglaIncumplida("El presupuesto necesita un nombre")
    if p.fecha_fin < p.fecha_inicio:
        raise ReglaIncumplida("El presupuesto termina antes de empezar")
    if _d(p.monto_total) < 0:
        raise ReglaIncumplida("El monto del presupuesto no puede ser negativo")
    if p.id and _d(p.monto_total) < _asignado(db, p.id):
        raise ReglaIncumplida(
            f"Los fondos ya tienen asignados Bs. {_asignado(db, p.id):.2f}: el total no puede "
            "ser menor")


def crear(db: Session, datos: dict) -> dict:
    p = P(nombre=(datos.get("nombre") or "").strip(), fecha_inicio=datos["fecha_inicio"],
          fecha_fin=datos["fecha_fin"], monto_total=_d(datos["monto_total"]),
          activo=datos.get("activo") is not False, bloqueado=False)
    _validar_presupuesto(db, p)
    db.add(p)
    db.commit()
    return obtener(db, p.id)


def actualizar(db: Session, presupuesto_id: int, datos: dict) -> dict:
    p = _obtener(db, presupuesto_id)
    solo_bloqueo = set(datos) <= {"bloqueado", "activo"}
    if p.bloqueado and not solo_bloqueo:
        raise ReglaIncumplida("El presupuesto está bloqueado: desbloquéalo para cambiarlo")
    for campo in ("nombre", "fecha_inicio", "fecha_fin", "activo", "bloqueado"):
        if datos.get(campo) is not None:
            setattr(p, campo, datos[campo].strip() if campo == "nombre" else datos[campo])
    if datos.get("monto_total") is not None:
        p.monto_total = _d(datos["monto_total"])
    _validar_presupuesto(db, p)
    db.commit()
    return obtener(db, p.id)


def eliminar(db: Session, presupuesto_id: int) -> None:
    p = _obtener(db, presupuesto_id)
    ids = [f.id for f in db.query(F).filter(F.presupuesto_id == p.id)]
    if ids and _fondos_usados(db, ids):
        raise ReglaIncumplida("El presupuesto tiene fondos con pedidos o facturas")
    db.delete(p)
    db.commit()


# --- Fondos ---------------------------------------------------------------------------

def _fondos_usados(db: Session, ids: List[int]) -> bool:
    return bool(db.query(L.id).filter(L.fondo_id.in_(ids)).first()
                or db.query(models.Factura.id).filter(models.Factura.fondo_envio_id.in_(ids)).first())


def _obtener_fondo(db: Session, fondo_id: int) -> models.Fondo:
    fondo = db.get(F, fondo_id)
    if not fondo:
        raise NoEncontrado("Fondo no encontrado")
    return fondo


def _aplicar_fondo(db: Session, fondo: models.Fondo, p: models.Presupuesto, datos: dict) -> None:
    if p.bloqueado:
        raise ReglaIncumplida("El presupuesto está bloqueado: sus fondos no se modifican")
    if "codigo" in datos and datos["codigo"] is not None:
        codigo = datos["codigo"].strip().upper()
        if not codigo:
            raise ReglaIncumplida("El fondo necesita un código")
        repetido = db.query(F).filter(F.presupuesto_id == p.id, F.codigo == codigo,
                                      F.id != (fondo.id or 0)).first()
        if repetido:
            raise ReglaIncumplida(f"Ya hay un fondo {codigo} en este presupuesto")
        fondo.codigo = codigo
    if "nombre" in datos and datos["nombre"] is not None:
        if not datos["nombre"].strip():
            raise ReglaIncumplida("El fondo necesita un nombre")
        fondo.nombre = datos["nombre"].strip()
    if "biblioteca_id" in datos:
        if datos["biblioteca_id"] is not None and not db.get(models.Biblioteca, datos["biblioteca_id"]):
            raise NoEncontrado("Sede no encontrada")
        fondo.biblioteca_id = datos["biblioteca_id"]
    if datos.get("activo") is not None:
        fondo.activo = bool(datos["activo"])
    if datos.get("monto_asignado") is not None:
        monto = _d(datos["monto_asignado"])
        if monto < 0:
            raise ReglaIncumplida("El monto asignado no puede ser negativo")
        libre = _d(p.monto_total) - _asignado(db, p.id, sin_fondo=fondo.id)
        if monto > libre:
            raise ReglaIncumplida(
                f"Al presupuesto {p.nombre} le quedan Bs. {libre:.2f} sin asignar")
        if fondo.id:
            mov = movimientos(db, [fondo.id]).get(fondo.id, {})
            usado = mov.get("comprometido", CERO) + mov.get("gastado", CERO)
            if monto < usado:
                raise ReglaIncumplida(
                    f"El fondo ya tiene Bs. {usado:.2f} comprometidos o gastados")
        fondo.monto_asignado = monto


def crear_fondo(db: Session, presupuesto_id: int, datos: dict) -> dict:
    p = _obtener(db, presupuesto_id)
    fondo = F(presupuesto_id=p.id, activo=True)
    for requerido in ("codigo", "nombre", "monto_asignado"):
        if datos.get(requerido) in (None, ""):
            raise ReglaIncumplida(f"Falta {requerido.replace('_', ' ')}")
    _aplicar_fondo(db, fondo, p, datos)
    db.add(fondo)
    db.commit()
    return vista_fondo(fondo, {}, p)


def actualizar_fondo(db: Session, fondo_id: int, datos: dict) -> dict:
    fondo = _obtener_fondo(db, fondo_id)
    p = db.get(P, fondo.presupuesto_id)
    _aplicar_fondo(db, fondo, p, datos)
    db.commit()
    return vista_fondo(fondo, movimientos(db, [fondo.id]).get(fondo.id, {}), p)


def eliminar_fondo(db: Session, fondo_id: int) -> None:
    fondo = _obtener_fondo(db, fondo_id)
    if db.get(P, fondo.presupuesto_id).bloqueado:
        raise ReglaIncumplida("El presupuesto está bloqueado: sus fondos no se modifican")
    if _fondos_usados(db, [fondo.id]):
        raise ReglaIncumplida(f"El fondo {fondo.codigo} tiene pedidos o facturas: desactívalo")
    db.delete(fondo)
    db.commit()


def fondos_para_pedir(db: Session) -> List[dict]:
    """Fondos activos de presupuestos activos, con su disponible (para los formularios)."""
    filas = db.query(F, P).join(P, P.id == F.presupuesto_id).filter(
        F.activo == True, P.activo == True).order_by(P.fecha_inicio.desc(), F.codigo).all()  # noqa: E712
    mov = movimientos(db, [f.id for f, _ in filas])
    return [vista_fondo(f, mov.get(f.id, {}), p) for f, p in filas]
