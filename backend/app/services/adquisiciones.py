"""Adquisiciones: proveedores, pedidos (cestas), facturas y recepción, al estilo de Koha.

Ciclo de un pedido:

    Abierta ──(cerrar: se envía al proveedor)──▶ Cerrada ──(todo recibido o cancelado)──▶ Recibida
       ▲                                            │
       └──────(reabrir, si no se recibió nada)──────┘          Abierta/Cerrada ──▶ Cancelada

Cada línea guarda su registro del catálogo (se crea al pedir, así se puede reservar
lo que viene), su fondo y su costo estimado. Se recibe contra una factura, en
parciales y al costo real; cada unidad recibida es un ejemplar nuevo que pasa por
la misma decisión de destino que una devolución (reservas, traslados).
"""

from datetime import timedelta
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.core.errores import NoEncontrado, ReglaIncumplida
from app.core.tiempo import ahora, fecha_local, formatear_fecha, hoy
from app.services import marc, presupuestos, traslados
from app.services.catalogo import aplicar_marc, buscar_por_isbn, sede_por_defecto

O, L, R = models.OrdenCompra, models.LineaOrden, models.Recepcion
Fa, Pr = models.Factura, models.Proveedor

ABIERTA, CERRADA, RECIBIDA, CANCELADA = "Abierta", "Cerrada", "Recibida", "Cancelada"
PENDIENTE, PARCIAL = "Pendiente", "Parcial"
TIPO_ITEM_RECEPCION = "LIB"
CERO = Decimal("0.00")


def _d(valor) -> Decimal:
    return Decimal(str(valor or 0)).quantize(Decimal("0.01"))


def costo_con_descuento(precio, descuento) -> Decimal:
    return (_d(precio) * (Decimal(100) - Decimal(str(descuento or 0))) / Decimal(100)).quantize(
        Decimal("0.01"))


# --- Proveedores ----------------------------------------------------------------------

CAMPOS_PROVEEDOR = ("nombre", "contacto", "email", "telefono", "rif", "direccion", "descuento",
                    "dias_entrega", "notas", "activo")


def _obtener_proveedor(db: Session, proveedor_id: int) -> models.Proveedor:
    proveedor = db.get(Pr, proveedor_id)
    if not proveedor:
        raise NoEncontrado("Proveedor no encontrado")
    return proveedor


def vista_proveedor(p: models.Proveedor, uso: Optional[dict] = None) -> dict:
    datos = {
        "id": p.id, "nombre": p.nombre, "contacto": p.contacto, "email": p.email,
        "telefono": p.telefono, "rif": p.rif, "direccion": p.direccion,
        "descuento": float(_d(p.descuento)), "dias_entrega": p.dias_entrega, "notas": p.notas,
        "activo": bool(p.activo),
    }
    if uso is not None:
        datos.update(uso)
    return datos


def listar_proveedores(db: Session) -> List[dict]:
    proveedores = db.query(Pr).order_by(Pr.activo.desc(), Pr.nombre).all()
    vivos = dict(db.query(O.proveedor_id, func.count(O.id)).filter(
        O.estado.in_((ABIERTA, CERRADA))).group_by(O.proveedor_id).all())
    facturas = dict(db.query(Fa.proveedor_id, func.count(Fa.id)).filter(
        Fa.cerrada == False).group_by(Fa.proveedor_id).all())  # noqa: E712
    return [vista_proveedor(p, {"pedidos_vivos": vivos.get(p.id, 0),
                                "facturas_abiertas": facturas.get(p.id, 0)})
            for p in proveedores]


def _aplicar_proveedor(p: models.Proveedor, datos: dict) -> None:
    for campo in CAMPOS_PROVEEDOR:
        if campo not in datos:
            continue
        valor = datos[campo]
        if isinstance(valor, str):
            valor = valor.strip() or None
        if campo == "nombre" and not valor:
            raise ReglaIncumplida("El proveedor necesita un nombre")
        if campo == "descuento":
            valor = _d(valor)
            if not (CERO <= valor <= Decimal(100)):
                raise ReglaIncumplida("El descuento va de 0 a 100 %")
        if campo == "activo" and valor is None:
            continue
        setattr(p, campo, valor)


def crear_proveedor(db: Session, datos: dict) -> dict:
    proveedor = Pr(activo=True, descuento=0)
    _aplicar_proveedor(proveedor, {"nombre": datos.get("nombre"), **datos})
    db.add(proveedor)
    db.commit()
    return vista_proveedor(proveedor)


def actualizar_proveedor(db: Session, proveedor_id: int, datos: dict) -> dict:
    proveedor = _obtener_proveedor(db, proveedor_id)
    _aplicar_proveedor(proveedor, datos)
    db.commit()
    return vista_proveedor(proveedor)


# --- Vistas de pedidos ----------------------------------------------------------------

def _vista_linea(l: models.LineaOrden, fondos: dict, recepciones: dict) -> dict:
    pendiente = l.cantidad - l.cantidad_recibida if l.estado in (PENDIENTE, PARCIAL) else 0
    recibido = recepciones.get(l.id, CERO)
    fondo = fondos.get(l.fondo_id)
    return {
        "id": l.id,
        "orden_id": l.orden_id,
        "biblio_id": l.biblio_id,
        "titulo": l.titulo,
        "autor": l.autor,
        "isbn": l.isbn,
        "cantidad": l.cantidad,
        "cantidad_recibida": l.cantidad_recibida,
        "pendiente": pendiente,
        "precio_unitario": float(_d(l.precio_unitario)),
        "descuento": float(_d(l.descuento)),
        "costo_estimado": float(_d(l.costo_estimado)),
        "total_estimado": float(_d(l.costo_estimado) * l.cantidad),
        "total_recibido": float(recibido),
        "fondo_id": l.fondo_id,
        "fondo": fondo.codigo if fondo else None,
        "estado": l.estado,
        "notas": l.notas,
    }


def _datos_de_lineas(db: Session, lineas: List[models.LineaOrden]):
    fondo_ids = {l.fondo_id for l in lineas if l.fondo_id}
    fondos = {f.id: f for f in db.query(models.Fondo).filter(models.Fondo.id.in_(fondo_ids))} \
        if fondo_ids else {}
    ids = [l.id for l in lineas]
    recepciones = dict(db.query(R.linea_id, func.sum(R.cantidad * R.costo_unitario)).filter(
        R.linea_id.in_(ids)).group_by(R.linea_id).all()) if ids else {}
    return fondos, {k: _d(v) for k, v in recepciones.items()}


def _atraso(orden: models.OrdenCompra, proveedor: Optional[models.Proveedor]) -> Optional[int]:
    """Días de atraso de un pedido cerrado con algo pendiente (None si no está atrasado)."""
    if orden.estado != CERRADA or not orden.fecha_cierre or not proveedor or \
            proveedor.dias_entrega is None:
        return None
    esperado = fecha_local(orden.fecha_cierre) + timedelta(days=proveedor.dias_entrega)
    dias = (hoy() - esperado).days
    return dias if dias > 0 else None


def _vista_orden(orden: models.OrdenCompra, proveedor, lineas, fondos, recepciones,
                 nombres_sedes: dict, con_lineas: bool = True) -> dict:
    vivas = [l for l in lineas if l.estado != CANCELADA]
    datos = {
        "id": orden.id,
        "nombre": orden.nombre or f"Pedido {orden.id}",
        "proveedor_id": orden.proveedor_id,
        "proveedor_nombre": proveedor.nombre if proveedor else None,
        "estado": orden.estado,
        "observaciones": orden.observaciones,
        "biblioteca_entrega_id": orden.biblioteca_entrega_id,
        "biblioteca_entrega": nombres_sedes.get(orden.biblioteca_entrega_id),
        "fecha_emision": orden.fecha_emision,
        "fecha_cierre": orden.fecha_cierre,
        "fecha_recepcion": orden.fecha_recepcion,
        "titulos": len(vivas),
        "ejemplares": sum(l.cantidad for l in vivas),
        "recibidos": sum(l.cantidad_recibida for l in vivas),
        "total": float(sum((_d(l.costo_estimado) * l.cantidad for l in vivas), CERO)),
        "total_recibido": float(sum((recepciones.get(l.id, CERO) for l in lineas), CERO)),
        "dias_atraso": _atraso(orden, proveedor),
    }
    if con_lineas:
        datos["lineas"] = [_vista_linea(l, fondos, recepciones) for l in lineas]
    return datos


def _nombres_sedes(db: Session) -> dict:
    return {b.id: b.nombre for b in db.query(models.Biblioteca).all()}


def _obtener_orden(db: Session, orden_id: int) -> models.OrdenCompra:
    orden = db.get(O, orden_id)
    if not orden:
        raise NoEncontrado("Pedido no encontrado")
    return orden


def obtener_orden(db: Session, orden_id: int) -> dict:
    orden = _obtener_orden(db, orden_id)
    lineas = db.query(L).filter(L.orden_id == orden.id).order_by(L.id).all()
    fondos, recepciones = _datos_de_lineas(db, lineas)
    return _vista_orden(orden, db.get(Pr, orden.proveedor_id), lineas, fondos, recepciones,
                        _nombres_sedes(db))


def listar_ordenes(db: Session, estado: Optional[str] = None,
                   proveedor_id: Optional[int] = None) -> List[dict]:
    consulta = db.query(O)
    if estado:
        consulta = consulta.filter(O.estado.in_(estado.split(",")))
    if proveedor_id is not None:
        consulta = consulta.filter(O.proveedor_id == proveedor_id)
    ordenes = consulta.order_by(O.id.desc()).all()
    ids = [o.id for o in ordenes]
    lineas = db.query(L).filter(L.orden_id.in_(ids)).all() if ids else []
    fondos, recepciones = _datos_de_lineas(db, lineas)
    proveedores = {p.id: p for p in db.query(Pr).all()}
    nombres_sedes = _nombres_sedes(db)
    return [_vista_orden(o, proveedores.get(o.proveedor_id),
                         [l for l in lineas if l.orden_id == o.id], fondos, recepciones,
                         nombres_sedes, con_lineas=False) for o in ordenes]


# --- Pedidos --------------------------------------------------------------------------

def _exigir_estado(orden: models.OrdenCompra, *estados: str, accion: str) -> None:
    if orden.estado not in estados:
        raise ReglaIncumplida(f"No se puede {accion}: el pedido está {orden.estado.lower()}")


def crear_orden(db: Session, datos: dict, personal_id: Optional[int] = None) -> dict:
    proveedor = _obtener_proveedor(db, datos["proveedor_id"])
    if not proveedor.activo:
        raise ReglaIncumplida(f"{proveedor.nombre} está inactivo")
    entrega = datos.get("biblioteca_entrega_id")
    if entrega is not None and not db.get(models.Biblioteca, entrega):
        raise NoEncontrado("Sede no encontrada")
    orden = O(proveedor_id=proveedor.id, nombre=(datos.get("nombre") or "").strip() or None,
              observaciones=datos.get("observaciones"), estado=ABIERTA, fecha_emision=ahora(),
              biblioteca_entrega_id=entrega or sede_por_defecto(db), creado_por_id=personal_id)
    db.add(orden)
    db.flush()
    for linea in datos.get("lineas") or []:
        _nueva_linea(db, orden, proveedor, linea)
    db.commit()
    return obtener_orden(db, orden.id)


def actualizar_orden(db: Session, orden_id: int, datos: dict) -> dict:
    orden = _obtener_orden(db, orden_id)
    _exigir_estado(orden, ABIERTA, CERRADA, accion="modificar el pedido")
    if "nombre" in datos:
        orden.nombre = (datos["nombre"] or "").strip() or None
    if "observaciones" in datos:
        orden.observaciones = datos["observaciones"]
    if datos.get("biblioteca_entrega_id") is not None:
        if not db.get(models.Biblioteca, datos["biblioteca_entrega_id"]):
            raise NoEncontrado("Sede no encontrada")
        orden.biblioteca_entrega_id = datos["biblioteca_entrega_id"]
    db.commit()
    return obtener_orden(db, orden.id)


def _registro_para(db: Session, datos: dict) -> models.RegistroBibliografico:
    """El registro existente (por id o ISBN) o uno mínimo nuevo, como al pedir en Koha."""
    if datos.get("biblio_id"):
        biblio = db.get(models.RegistroBibliografico, datos["biblio_id"])
        if not biblio:
            raise NoEncontrado("Registro bibliográfico no encontrado")
        return biblio
    titulo = (datos.get("titulo") or "").strip()
    if not titulo:
        raise ReglaIncumplida("La línea necesita un título o un registro del catálogo")
    existente = buscar_por_isbn(db, marc.normalizar_isbn(datos.get("isbn")))
    if existente:
        return existente
    canonico, plantilla = marc.preparar(
        marc.desde_columnas(titulo, datos.get("autor"), datos.get("isbn")), "BKS")
    biblio = models.RegistroBibliografico()
    aplicar_marc(biblio, canonico, plantilla)
    db.add(biblio)
    db.flush()
    return biblio


def _cantidad_y_precio(datos: dict, proveedor: models.Proveedor, linea=None):
    cantidad = int(datos.get("cantidad") or (linea.cantidad if linea else 1))
    if cantidad < 1:
        raise ReglaIncumplida("La cantidad debe ser al menos 1")
    precio = _d(datos["precio_unitario"] if datos.get("precio_unitario") is not None
                else (linea.precio_unitario if linea else 0))
    if precio < 0:
        raise ReglaIncumplida("El precio no puede ser negativo")
    descuento = (datos["descuento"] if datos.get("descuento") is not None
                 else (linea.descuento if linea else proveedor.descuento))
    descuento = _d(descuento)
    if not (CERO <= descuento <= Decimal(100)):
        raise ReglaIncumplida("El descuento va de 0 a 100 %")
    return cantidad, precio, descuento


def _nueva_linea(db: Session, orden: models.OrdenCompra, proveedor: models.Proveedor,
                 datos: dict) -> models.LineaOrden:
    cantidad, precio, descuento = _cantidad_y_precio(datos, proveedor)
    costo = costo_con_descuento(precio, descuento)
    fondo = presupuestos.fondo_utilizable(db, datos.get("fondo_id"))
    presupuestos.exigir_saldo(db, fondo, costo * cantidad)
    biblio = _registro_para(db, datos)
    linea = L(orden_id=orden.id, biblio_id=biblio.id, fondo_id=fondo.id if fondo else None,
              titulo=biblio.titulo, autor=biblio.autor, isbn=biblio.isbn or datos.get("isbn"),
              cantidad=cantidad, precio_unitario=precio, descuento=descuento,
              costo_estimado=costo, cantidad_recibida=0, estado=PENDIENTE,
              notas=(datos.get("notas") or "").strip() or None)
    db.add(linea)
    db.flush()
    return linea


def agregar_linea(db: Session, orden_id: int, datos: dict) -> dict:
    orden = _obtener_orden(db, orden_id)
    _exigir_estado(orden, ABIERTA, accion="agregar títulos")
    linea = _nueva_linea(db, orden, db.get(Pr, orden.proveedor_id), datos)
    db.commit()
    return {"linea_id": linea.id, **obtener_orden(db, orden.id)}


def _obtener_linea(db: Session, orden: models.OrdenCompra, linea_id: int) -> models.LineaOrden:
    linea = db.get(L, linea_id)
    if not linea or linea.orden_id != orden.id:
        raise NoEncontrado("Línea no encontrada en este pedido")
    return linea


def actualizar_linea(db: Session, orden_id: int, linea_id: int, datos: dict) -> dict:
    orden = _obtener_orden(db, orden_id)
    _exigir_estado(orden, ABIERTA, accion="modificar títulos")
    linea = _obtener_linea(db, orden, linea_id)
    cantidad, precio, descuento = _cantidad_y_precio(datos, db.get(Pr, orden.proveedor_id), linea)
    costo = costo_con_descuento(precio, descuento)
    fondo_id = datos["fondo_id"] if "fondo_id" in datos else linea.fondo_id
    fondo = (presupuestos.fondo_utilizable(db, fondo_id) if fondo_id != linea.fondo_id
             else (db.get(models.Fondo, fondo_id) if fondo_id else None))
    previo = _d(linea.costo_estimado) * linea.cantidad if fondo_id == linea.fondo_id else CERO
    presupuestos.exigir_saldo(db, fondo, costo * cantidad, previo)
    linea.cantidad, linea.precio_unitario, linea.descuento = cantidad, precio, descuento
    linea.costo_estimado, linea.fondo_id = costo, fondo_id
    if "notas" in datos:
        linea.notas = (datos["notas"] or "").strip() or None
    db.commit()
    return obtener_orden(db, orden.id)


def eliminar_linea(db: Session, orden_id: int, linea_id: int) -> dict:
    orden = _obtener_orden(db, orden_id)
    _exigir_estado(orden, ABIERTA, accion="quitar títulos")
    linea = _obtener_linea(db, orden, linea_id)
    db.query(models.Sugerencia).filter(models.Sugerencia.linea_id == linea.id).update(
        {models.Sugerencia.linea_id: None, models.Sugerencia.estado: "Aceptada"},
        synchronize_session=False)
    db.delete(linea)
    db.commit()
    return obtener_orden(db, orden.id)


def cerrar_orden(db: Session, orden_id: int) -> dict:
    """Se envía al proveedor: desde ahora se recibe y ya no se le agregan títulos."""
    orden = _obtener_orden(db, orden_id)
    _exigir_estado(orden, ABIERTA, accion="cerrar el pedido")
    if not db.query(L).filter(L.orden_id == orden.id).count():
        raise ReglaIncumplida("El pedido no tiene títulos")
    orden.estado = CERRADA
    orden.fecha_cierre = ahora()
    db.commit()
    return obtener_orden(db, orden.id)


def _tiene_recepciones(db: Session, orden_id: int) -> bool:
    return db.query(R.id).join(L, L.id == R.linea_id).filter(L.orden_id == orden_id).first() \
        is not None


def reabrir_orden(db: Session, orden_id: int) -> dict:
    orden = _obtener_orden(db, orden_id)
    _exigir_estado(orden, CERRADA, accion="reabrir el pedido")
    if _tiene_recepciones(db, orden.id):
        raise ReglaIncumplida("Ya se recibió parte del pedido: no se puede reabrir")
    orden.estado = ABIERTA
    orden.fecha_cierre = None
    db.commit()
    return obtener_orden(db, orden.id)


def cancelar_orden(db: Session, orden_id: int) -> dict:
    orden = _obtener_orden(db, orden_id)
    _exigir_estado(orden, ABIERTA, CERRADA, accion="cancelar el pedido")
    if _tiene_recepciones(db, orden.id):
        raise ReglaIncumplida(
            "Ya se recibió parte del pedido: cancela solo lo que falta, línea por línea")
    db.query(L).filter(L.orden_id == orden.id).update({L.estado: CANCELADA},
                                                      synchronize_session=False)
    orden.estado = CANCELADA
    db.commit()
    return obtener_orden(db, orden.id)


def _cerrar_si_completa(db: Session, orden: models.OrdenCompra) -> None:
    db.flush()
    estados = {e for (e,) in db.query(L.estado).filter(L.orden_id == orden.id)}
    if estados and estados <= {RECIBIDA, CANCELADA}:
        if RECIBIDA in estados:
            orden.estado = RECIBIDA
            orden.fecha_recepcion = ahora()
        else:
            orden.estado = CANCELADA
    elif orden.estado == RECIBIDA:
        orden.estado = CERRADA
        orden.fecha_recepcion = None


def cancelar_pendiente(db: Session, orden_id: int, linea_id: int) -> dict:
    """Lo que falta de una línea ya no llega: se libera lo comprometido."""
    orden = _obtener_orden(db, orden_id)
    _exigir_estado(orden, CERRADA, accion="cancelar lo pendiente")
    linea = _obtener_linea(db, orden, linea_id)
    if linea.estado not in (PENDIENTE, PARCIAL):
        raise ReglaIncumplida(f"La línea ya está {linea.estado.lower()}")
    if linea.cantidad_recibida:
        faltan = linea.cantidad - linea.cantidad_recibida
        linea.notas = "; ".join(filter(None, [linea.notas, f"Se cancelaron {faltan} sin recibir"]))
        linea.cantidad = linea.cantidad_recibida
        linea.estado = RECIBIDA
    else:
        linea.estado = CANCELADA
    _cerrar_si_completa(db, orden)
    db.commit()
    return obtener_orden(db, orden.id)


def atrasados(db: Session) -> List[dict]:
    """Pedidos cerrados con algo pendiente cuyo plazo de entrega del proveedor pasó."""
    ordenes = db.query(O).filter(O.estado == CERRADA).all()
    proveedores = {p.id: p for p in db.query(Pr).all()}
    resultado = []
    for orden in ordenes:
        dias = _atraso(orden, proveedores.get(orden.proveedor_id))
        if dias is None:
            continue
        pendientes = db.query(L).filter(L.orden_id == orden.id,
                                        L.estado.in_((PENDIENTE, PARCIAL))).all()
        if not pendientes:
            continue
        p = proveedores[orden.proveedor_id]
        resultado.append({
            "orden_id": orden.id,
            "nombre": orden.nombre or f"Pedido {orden.id}",
            "proveedor_id": p.id,
            "proveedor_nombre": p.nombre,
            "proveedor_email": p.email,
            "fecha_cierre": formatear_fecha(orden.fecha_cierre),
            "dias_atraso": dias,
            "lineas": [{"id": l.id, "titulo": l.titulo, "isbn": l.isbn,
                        "pendiente": l.cantidad - l.cantidad_recibida} for l in pendientes],
        })
    return sorted(resultado, key=lambda r: -r["dias_atraso"])


# --- Facturas -------------------------------------------------------------------------

def _obtener_factura(db: Session, factura_id: int) -> models.Factura:
    factura = db.get(Fa, factura_id)
    if not factura:
        raise NoEncontrado("Factura no encontrada")
    return factura


def _vista_factura(db: Session, f: models.Factura, proveedor, fondo, total_recibido: Decimal,
                   unidades: int, recepciones: Optional[List[dict]] = None) -> dict:
    datos = {
        "id": f.id,
        "proveedor_id": f.proveedor_id,
        "proveedor_nombre": proveedor.nombre if proveedor else None,
        "numero": f.numero,
        "fecha": f.fecha.isoformat(),
        "costo_envio": float(_d(f.costo_envio)),
        "fondo_envio_id": f.fondo_envio_id,
        "fondo_envio": fondo.codigo if fondo else None,
        "cerrada": bool(f.cerrada),
        "fecha_cierre": f.fecha_cierre,
        "notas": f.notas,
        "unidades": unidades,
        "subtotal": float(total_recibido),
        "total": float(total_recibido + _d(f.costo_envio)),
    }
    if recepciones is not None:
        datos["recepciones"] = recepciones
    return datos


def listar_facturas(db: Session, proveedor_id: Optional[int] = None,
                    abiertas: Optional[bool] = None) -> List[dict]:
    consulta = db.query(Fa)
    if proveedor_id is not None:
        consulta = consulta.filter(Fa.proveedor_id == proveedor_id)
    if abiertas is not None:
        consulta = consulta.filter(Fa.cerrada == (not abiertas))
    facturas = consulta.order_by(Fa.cerrada, Fa.fecha.desc(), Fa.id.desc()).all()
    totales = {fid: (_d(t), int(n)) for fid, t, n in db.query(
        R.factura_id, func.sum(R.cantidad * R.costo_unitario), func.sum(R.cantidad)).filter(
        R.factura_id.in_([f.id for f in facturas])).group_by(R.factura_id)} if facturas else {}
    proveedores = {p.id: p for p in db.query(Pr).all()}
    fondos = {f.id: f for f in db.query(models.Fondo).all()}
    return [_vista_factura(db, f, proveedores.get(f.proveedor_id), fondos.get(f.fondo_envio_id),
                           *totales.get(f.id, (CERO, 0))) for f in facturas]


def obtener_factura(db: Session, factura_id: int) -> dict:
    f = _obtener_factura(db, factura_id)
    filas = db.query(R, L, O).join(L, L.id == R.linea_id).join(O, O.id == L.orden_id).filter(
        R.factura_id == f.id).order_by(R.id).all()
    items = {}
    for item in db.query(models.Item).filter(models.Item.recepcion_id.in_([r.id for r, *_ in filas])):
        items.setdefault(item.recepcion_id, []).append(item.codigo_barras)
    fondos = {x.id: x for x in db.query(models.Fondo).all()}
    recepciones = [{
        "id": r.id,
        "linea_id": l.id,
        "orden_id": o.id,
        "orden": o.nombre or f"Pedido {o.id}",
        "titulo": l.titulo,
        "biblio_id": l.biblio_id,
        "fondo": fondos[l.fondo_id].codigo if l.fondo_id in fondos else None,
        "cantidad": r.cantidad,
        "costo_unitario": float(_d(r.costo_unitario)),
        "costo_estimado": float(_d(l.costo_estimado)),
        "total": float(_d(r.costo_unitario) * r.cantidad),
        "fecha": formatear_fecha(r.fecha),
        "ejemplares": sorted(items.get(r.id, [])),
    } for r, l, o in filas]
    total = sum((Decimal(str(x["total"])) for x in recepciones), CERO)
    return _vista_factura(db, f, db.get(Pr, f.proveedor_id), fondos.get(f.fondo_envio_id),
                          total, sum(x["cantidad"] for x in recepciones), recepciones)


def _aplicar_factura(db: Session, f: models.Factura, datos: dict) -> None:
    if datos.get("numero") is not None:
        numero = datos["numero"].strip()
        if not numero:
            raise ReglaIncumplida("La factura necesita un número")
        repetida = db.query(Fa).filter(Fa.proveedor_id == f.proveedor_id, Fa.numero == numero,
                                       Fa.id != (f.id or 0)).first()
        if repetida:
            raise ReglaIncumplida(f"Ya se registró la factura {numero} de este proveedor")
        f.numero = numero
    if datos.get("fecha") is not None:
        f.fecha = datos["fecha"]
    if datos.get("costo_envio") is not None:
        if _d(datos["costo_envio"]) < 0:
            raise ReglaIncumplida("El costo de envío no puede ser negativo")
        f.costo_envio = _d(datos["costo_envio"])
    if "fondo_envio_id" in datos:
        if datos["fondo_envio_id"] is not None and datos["fondo_envio_id"] != f.fondo_envio_id:
            presupuestos.fondo_utilizable(db, datos["fondo_envio_id"])
        f.fondo_envio_id = datos["fondo_envio_id"]
    if "notas" in datos:
        f.notas = (datos["notas"] or "").strip() or None
    if _d(f.costo_envio) > 0 and f.fondo_envio_id is None:
        raise ReglaIncumplida("Indica a qué fondo se carga el envío")


def crear_factura(db: Session, datos: dict) -> dict:
    proveedor = _obtener_proveedor(db, datos["proveedor_id"])
    f = Fa(proveedor_id=proveedor.id, fecha=datos.get("fecha") or hoy(), costo_envio=0,
           cerrada=False)
    _aplicar_factura(db, f, {"numero": datos.get("numero") or "", **datos})
    db.add(f)
    db.commit()
    return obtener_factura(db, f.id)


def actualizar_factura(db: Session, factura_id: int, datos: dict) -> dict:
    f = _obtener_factura(db, factura_id)
    if f.cerrada:
        raise ReglaIncumplida("La factura está cerrada: reábrela para cambiarla")
    _aplicar_factura(db, f, datos)
    db.commit()
    return obtener_factura(db, f.id)


def cerrar_factura(db: Session, factura_id: int, cerrada: bool) -> dict:
    f = _obtener_factura(db, factura_id)
    f.cerrada = cerrada
    f.fecha_cierre = ahora() if cerrada else None
    db.commit()
    return obtener_factura(db, f.id)


def eliminar_factura(db: Session, factura_id: int) -> None:
    f = _obtener_factura(db, factura_id)
    if db.query(R.id).filter(R.factura_id == f.id).first():
        raise ReglaIncumplida("La factura tiene recepciones: deshazlas primero")
    db.delete(f)
    db.commit()


# --- Recepción ------------------------------------------------------------------------

def por_recibir(db: Session, proveedor_id: int) -> List[dict]:
    """Líneas pendientes de todos los pedidos cerrados del proveedor (para una factura)."""
    filas = db.query(L, O).join(O, O.id == L.orden_id).filter(
        O.proveedor_id == proveedor_id, O.estado == CERRADA,
        L.estado.in_((PENDIENTE, PARCIAL))).order_by(O.id, L.id).all()
    lineas = [l for l, _ in filas]
    fondos, recepciones = _datos_de_lineas(db, lineas)
    return [{**_vista_linea(l, fondos, recepciones), "orden": o.nombre or f"Pedido {o.id}",
             "biblioteca_entrega_id": o.biblioteca_entrega_id} for l, o in filas]


def _codigos(db: Session, linea: models.LineaOrden, cantidad: int, dados: Optional[List[str]]):
    if dados:
        codigos = [c.strip() for c in dados if c and c.strip()]
        if len(codigos) != cantidad:
            raise ReglaIncumplida(
                f"Se reciben {cantidad} ejemplar(es) y se dieron {len(codigos)} código(s)")
        if len(set(codigos)) != len(codigos):
            raise ReglaIncumplida("Hay códigos de barras repetidos")
        usados = [c for (c,) in db.query(models.Item.codigo_barras).filter(
            models.Item.codigo_barras.in_(codigos))]
        if usados:
            raise ReglaIncumplida(f"Ya existen los códigos: {', '.join(sorted(usados))}")
        return codigos
    # Generados: OC0001-L001-01, -02… siguiendo lo ya recibido de la línea.
    codigos, n = [], linea.cantidad_recibida
    while len(codigos) < cantidad:
        n += 1
        codigo = f"OC{linea.orden_id:04d}-L{linea.id:03d}-{n:02d}"
        if not db.query(models.Item.id).filter(models.Item.codigo_barras == codigo).first():
            codigos.append(codigo)
    return codigos


def recibir(db: Session, factura_id: int, datos: dict, personal_id: Optional[int] = None) -> dict:
    factura = _obtener_factura(db, factura_id)
    if factura.cerrada:
        raise ReglaIncumplida("La factura está cerrada: reábrela para recibir contra ella")
    linea = db.get(L, datos["linea_id"])
    if not linea:
        raise NoEncontrado("Línea de pedido no encontrada")
    orden = db.get(O, linea.orden_id)
    if orden.proveedor_id != factura.proveedor_id:
        raise ReglaIncumplida("La línea es de un pedido a otro proveedor")
    _exigir_estado(orden, CERRADA, accion="recibir (ciérralo primero para enviarlo)")
    if linea.estado not in (PENDIENTE, PARCIAL):
        raise ReglaIncumplida(f"La línea ya está {linea.estado.lower()}")
    pendiente = linea.cantidad - linea.cantidad_recibida
    cantidad = int(datos.get("cantidad") or pendiente)
    if not (1 <= cantidad <= pendiente):
        raise ReglaIncumplida(f"Quedan {pendiente} ejemplar(es) por recibir de esta línea")
    costo = _d(datos["costo_unitario"] if datos.get("costo_unitario") is not None
               else linea.costo_estimado)
    if costo < 0:
        raise ReglaIncumplida("El costo no puede ser negativo")

    tipo_codigo = datos.get("tipo_item_codigo") or TIPO_ITEM_RECEPCION
    tipo = db.query(models.TipoItem).filter(models.TipoItem.codigo == tipo_codigo).first()
    if datos.get("tipo_item_codigo") and not tipo:
        raise NoEncontrado(f"Tipo de ítem {tipo_codigo} no encontrado")
    sede = datos.get("biblioteca_id") or orden.biblioteca_entrega_id or sede_por_defecto(db)
    if datos.get("biblioteca_id") and not db.get(models.Biblioteca, sede):
        raise NoEncontrado("Sede no encontrada")
    codigos = _codigos(db, linea, cantidad, datos.get("codigos_barras"))

    if linea.biblio_id is None or not db.get(models.RegistroBibliografico, linea.biblio_id):
        linea.biblio_id = _registro_para(db, {"titulo": linea.titulo, "autor": linea.autor,
                                              "isbn": linea.isbn}).id

    recepcion = R(linea_id=linea.id, factura_id=factura.id, cantidad=cantidad,
                  costo_unitario=costo, fecha=ahora(), personal_id=personal_id)
    db.add(recepcion)
    db.flush()

    destinos = []
    for codigo in codigos:
        item = models.Item(
            biblio_id=linea.biblio_id, codigo_barras=codigo,
            tipo_item_id=tipo.id if tipo else None, estado="Disponible",
            signatura_topografica=(datos.get("signatura") or "").strip() or None,
            biblioteca_propia_id=sede, biblioteca_actual_id=sede,
            # Lo que costó es la referencia natural para cobrar una pérdida.
            precio_reposicion=costo or None, recepcion_id=recepcion.id)
        db.add(item)
        db.flush()
        # Lo que llega puede tener reservas esperándolo (se reservó estando pedido).
        ubicacion = traslados.ubicar(db, item, sede, personal_id=personal_id)
        destinos.append({"codigo_barras": codigo, **traslados.describir(db, ubicacion)})

    linea.cantidad_recibida += cantidad
    linea.estado = RECIBIDA if linea.cantidad_recibida >= linea.cantidad else PARCIAL
    _cerrar_si_completa(db, orden)
    db.commit()
    return {"recepcion_id": recepcion.id, "linea_id": linea.id, "biblio_id": linea.biblio_id,
            "cantidad": cantidad, "estado_linea": linea.estado, "estado_pedido": orden.estado,
            "ejemplares": destinos}


def deshacer_recepcion(db: Session, recepcion_id: int) -> dict:
    """Se borra lo recibido si ningún ejemplar circuló todavía."""
    recepcion = db.get(R, recepcion_id)
    if not recepcion:
        raise NoEncontrado("Recepción no encontrada")
    factura = db.get(Fa, recepcion.factura_id) if recepcion.factura_id else None
    if factura and factura.cerrada:
        raise ReglaIncumplida("La factura está cerrada: reábrela para deshacer la recepción")
    items = db.query(models.Item).filter(models.Item.recepcion_id == recepcion.id).all()
    ocupados = [i.codigo_barras for i in items if i.estado != "Disponible"] + [
        i.codigo_barras for i in items
        if db.query(models.Prestamo.id).filter(models.Prestamo.item_id == i.id).first()]
    if ocupados:
        raise ReglaIncumplida(
            f"Estos ejemplares ya circularon o están apartados: {', '.join(sorted(set(ocupados)))}")
    linea = db.get(L, recepcion.linea_id)
    orden = db.get(O, linea.orden_id)
    for item in items:
        db.query(models.Traslado).filter(models.Traslado.item_id == item.id).delete()
        db.delete(item)
    linea.cantidad_recibida -= recepcion.cantidad
    linea.estado = PARCIAL if linea.cantidad_recibida else PENDIENTE
    db.delete(recepcion)
    _cerrar_si_completa(db, orden)
    if orden.estado == RECIBIDA:
        orden.estado = CERRADA
    db.commit()
    return obtener_orden(db, orden.id)


# --- Resumen --------------------------------------------------------------------------

def resumen(db: Session) -> dict:
    por_estado = dict(db.query(O.estado, func.count(O.id)).group_by(O.estado).all())
    return {
        "pedidos_abiertos": por_estado.get(ABIERTA, 0),
        "pedidos_por_recibir": por_estado.get(CERRADA, 0),
        "pedidos_atrasados": len(atrasados(db)),
        "facturas_abiertas": db.query(Fa).filter(Fa.cerrada == False).count(),  # noqa: E712
        "sugerencias_pendientes": db.query(models.Sugerencia).filter(
            models.Sugerencia.estado == "Pendiente").count(),
        "fondos": presupuestos.fondos_para_pedir(db),
    }
