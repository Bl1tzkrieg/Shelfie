"""Circulación: préstamo, devolución, renovación, pérdida y vistas de préstamos.

Las políticas salen de las reglas de circulación (app/services/reglas.py), las
fechas del calendario (app/services/calendario.py) y las deudas de la cuenta del
lector (app/services/cuentas.py).
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from app import models
from app.core.errores import NoEncontrado, ReglaIncumplida
from app.core.tiempo import ahora, fecha_local, fin_del_dia, formatear_fecha, hoy, mas_dias
from app.services import calendario, configuracion, cuentas, reglas, reservas, sedes, traslados

# El frontend clasifica a los lectores en tres grupos; los códigos de categoría
# de la base de datos se normalizan contra ese vocabulario.
USER_TYPE_POR_CATEGORIA = {
    "doc": "teacher",
    "docente": "teacher",
    "adm": "staff",
    "staff": "staff",
}


def tipo_de_lector(categoria: Optional[models.CategoriaUsuario]) -> str:
    if not categoria or not categoria.codigo:
        return "student"
    return USER_TYPE_POR_CATEGORIA.get(categoria.codigo.lower(), "student")


def estado_de_prestamo(prestamo: models.Prestamo, momento: Optional[datetime] = None) -> str:
    """active / overdue / returned, el vocabulario que usa el frontend."""
    if prestamo.fecha_devolucion:
        return "returned"
    return "overdue" if (momento or ahora()) > prestamo.fecha_vencimiento else "active"


def _sede_por_defecto(db: Session) -> Optional[int]:
    from app.services.catalogo import sede_por_defecto
    return sede_por_defecto(db)


def regla_del_prestamo(db: Session, usuario: models.Usuario, item: models.Item):
    return reglas.regla_para(db, usuario.categoria_id, item.tipo_item_id,
                             item.biblioteca_actual_id or _sede_por_defecto(db))


def _vencimiento(cal: calendario.Calendario, desde, dias: int) -> datetime:
    """`dias` corridos desde `desde`; si cae en día cerrado, el siguiente hábil. Vence a las 23:59."""
    return fin_del_dia(cal.siguiente_habil(mas_dias(desde, dias)))


def calcular_multa(cal: calendario.Calendario, regla: models.ReglaCirculacion,
                   vencimiento: datetime, momento: datetime) -> Decimal:
    """Multa por atraso: días hábiles de atraso × multa diaria, con gracia y tope.

    Si el atraso no supera los días de gracia, no hay multa; si los supera, se
    cobra desde el vencimiento (como el período de gracia de Koha).
    """
    dias = cal.habiles_entre(fecha_local(vencimiento), fecha_local(momento))
    if dias <= (regla.dias_gracia or 0):
        return Decimal("0.00")
    multa = Decimal(dias) * Decimal(str(regla.multa_por_dia))
    if regla.multa_maxima is not None:
        multa = min(multa, Decimal(str(regla.multa_maxima)))
    return multa.quantize(Decimal("0.01"))


def _bloquear_si_debe(db: Session, usuario: models.Usuario) -> None:
    saldo, umbral = cuentas.saldo(db, usuario.id), cuentas.umbral_de_bloqueo(db)
    if cuentas.esta_bloqueado(saldo, umbral):
        raise ReglaIncumplida(
            f"El usuario debe Bs. {saldo:.2f}, por encima del máximo permitido "
            f"de Bs. {umbral:.2f}. Debe pagar antes de seguir retirando material")


# --- Comandos ---------------------------------------------------------------------

def prestar(db: Session, codigo_barras: str, nro_carnet: str,
            personal_id: Optional[int] = None, sede_id: Optional[int] = None) -> models.Prestamo:
    reservas.expirar_vencidas(db)

    usuario = db.query(models.Usuario).filter(
        models.Usuario.nro_carnet == nro_carnet,
        models.Usuario.activo == True).first()  # noqa: E712
    if not usuario:
        raise NoEncontrado("Usuario no encontrado o inactivo")

    # Bloqueo de fila: dos mostradores con el mismo código no pasan juntos la comprobación.
    item = db.query(models.Item).filter(
        models.Item.codigo_barras == codigo_barras).with_for_update().first()
    if not item:
        raise NoEncontrado("Ejemplar de biblioteca no encontrado")
    if item.estado == "EnTransito":
        traslado = traslados.abierto_de(db, item.id)
        destino = sedes.nombres(db).get(traslado.hacia_id) if traslado else None
        raise ReglaIncumplida(
            f"El ejemplar está en tránsito{f' hacia {destino}' if destino else ''}: "
            "regístralo en la devolución para recibirlo antes de prestarlo")
    if item.estado not in ("Disponible", "Reservado"):
        raise ReglaIncumplida(f"El ítem no puede ser prestado. Estado actual: {item.estado}")

    if not usuario.categoria_id:
        raise ReglaIncumplida(
            "El usuario no tiene una categoría asignada, no se pueden aplicar políticas")

    tipo = db.get(models.TipoItem, item.tipo_item_id) if item.tipo_item_id else None
    regla = regla_del_prestamo(db, usuario, item)
    if not regla.prestable or (tipo is not None and not tipo.es_prestable):
        raise ReglaIncumplida("Este material no se presta a domicilio (solo consulta en sala)")

    activos = db.query(models.Prestamo).filter(
        models.Prestamo.usuario_id == usuario.id,
        models.Prestamo.fecha_devolucion == None).count()  # noqa: E711
    if activos >= regla.max_prestamos:
        raise ReglaIncumplida(
            f"El usuario alcanzó su límite de {regla.max_prestamos} préstamos simultáneos")

    _bloquear_si_debe(db, usuario)
    reservas.resolver_al_prestar(db, usuario, item)

    prestamo = models.Prestamo(
        item_id=item.id,
        usuario_id=usuario.id,
        fecha_prestamo=ahora(),
        fecha_vencimiento=_vencimiento(calendario.cargar(db), hoy(), regla.dias_prestamo),
        renovaciones_realizadas=0,
        personal_prestamo_id=personal_id,
        biblioteca_id=sede_id or item.biblioteca_actual_id or _sede_por_defecto(db),
    )
    item.estado = "Prestado"

    db.add(prestamo)
    db.commit()
    db.refresh(prestamo)
    return prestamo


def devolver(db: Session, codigo_barras: str, personal_id: Optional[int] = None,
             sede_id: Optional[int] = None) -> dict:
    """Todo ejemplar que pasa por el mostrador de devolución, como en Koha.

    Además de cerrar préstamos: recibe traslados, aparta ejemplares del estante para
    reservas ("Para sacar del estante") y recupera ejemplares perdidos.
    """
    reservas.expirar_vencidas(db)
    sede_id = sede_id or _sede_por_defecto(db)

    # Bloqueo de fila: dos mostradores con el mismo código no pasan juntos la comprobación.
    item = db.query(models.Item).filter(
        models.Item.codigo_barras == codigo_barras).with_for_update().first()
    if not item:
        raise NoEncontrado("Ejemplar de biblioteca no encontrado")
    if item.estado == "Perdido":
        return _recuperar_perdido(db, item, personal_id, sede_id)
    if item.estado == "EnTransito":
        ubicacion = traslados.llegada(db, item, sede_id, personal_id)
        return _resultado(db, item, ubicacion, "Traslado registrado")
    if item.estado == "Reservado":
        reserva = db.query(models.Reserva).filter(
            models.Reserva.item_id == item.id,
            models.Reserva.estado == reservas.EN_ESPERA).first()
        lector = db.get(models.Usuario, reserva.usuario_id) if reserva else None
        raise ReglaIncumplida(
            f"El ejemplar ya está apartado para {lector.nombre} {lector.apellido} hasta el "
            f"{formatear_fecha(reserva.fecha_expiracion)}: déjalo en el estante de reservas"
            if lector else "El ejemplar ya está apartado para una reserva")
    if item.estado == "Disponible":
        return _ubicar_del_estante(db, item, sede_id, personal_id)
    if item.estado != "Prestado":
        raise ReglaIncumplida("El ítem no está registrado como prestado en este momento")

    prestamo = db.query(models.Prestamo).filter(
        models.Prestamo.item_id == item.id,
        models.Prestamo.fecha_devolucion == None).first()  # noqa: E711
    if not prestamo:
        raise ReglaIncumplida(
            "El ejemplar figura prestado pero no tiene un préstamo activo asociado")

    usuario = db.get(models.Usuario, prestamo.usuario_id)
    momento = ahora()
    multa = Decimal("0.00")
    if usuario and momento > prestamo.fecha_vencimiento:
        regla = regla_del_prestamo(db, usuario, item)
        multa = calcular_multa(calendario.cargar(db), regla, prestamo.fecha_vencimiento, momento)
        if multa > 0:
            cuentas.registrar(
                db, usuario, "MULTA_ATRASO", multa, prestamo_id=prestamo.id,
                descripcion=f"Atraso en la devolución de {codigo_barras}", personal_id=personal_id)

    prestamo.fecha_devolucion = momento
    prestamo.personal_devolucion_id = personal_id
    return _reincorporar(db, item, "Devolución registrada correctamente en el inventario",
                         sede_id, personal_id, multa=multa)


def _ubicar_del_estante(db: Session, item: models.Item, sede_id: Optional[int],
                        personal_id: Optional[int]) -> dict:
    """Un ejemplar disponible escaneado: se aparta para una reserva o vuelve a su sede."""
    if not traslados.cambiaria(db, item, sede_id):
        raise ReglaIncumplida("El ítem no está registrado como prestado en este momento")
    ubicacion = traslados.ubicar(db, item, sede_id, personal_id=personal_id)
    mensaje = ("Ejemplar apartado para una reserva" if ubicacion.reserva
               else "Ejemplar registrado en esta sede")
    return _resultado(db, item, ubicacion, mensaje)


def _reincorporar(db: Session, item: models.Item, mensaje: str, sede_id: Optional[int],
                  personal_id: Optional[int], **extra) -> dict:
    """El ejemplar vuelve: a la cola de reservas, de viaje a otra sede o al estante."""
    ubicacion = traslados.ubicar(db, item, sede_id, personal_id=personal_id)
    return _resultado(db, item, ubicacion, mensaje, **extra)


def _resultado(db: Session, item: models.Item, ubicacion: "traslados.Ubicacion", mensaje: str,
               *, multa=Decimal("0.00"), recuperado=False, reintegro=Decimal("0.00"),
               lector_reintegro: Optional[models.Usuario] = None) -> dict:
    db.commit()
    return {
        "mensaje": mensaje,
        "multa_aplicada": float(multa),
        "nuevo_estado_item": item.estado,
        "recuperado": recuperado,
        "reintegro": float(reintegro),
        "lector_reintegro": (f"{lector_reintegro.nombre} {lector_reintegro.apellido}"
                             if lector_reintegro and reintegro > 0 else None),
        **traslados.describir(db, ubicacion),
    }


def _recuperar_perdido(db: Session, item: models.Item, personal_id: Optional[int],
                       sede_id: Optional[int] = None) -> dict:
    """Un ejemplar declarado perdido aparece: vuelve al inventario y se reintegra la reposición.

    Como en Koha (RefundLostOnReturn), se acredita al lector lo que se le cargó por
    reposición en el préstamo en que se perdió. Si ya lo había pagado, la cuenta
    queda con saldo a favor.
    """
    prestamo = db.query(models.Prestamo).filter(
        models.Prestamo.item_id == item.id, models.Prestamo.perdido.is_(True)).order_by(
        models.Prestamo.fecha_devolucion.desc(), models.Prestamo.id.desc()).first()

    reintegro, lector = Decimal("0.00"), None
    if prestamo:
        lector = db.get(models.Usuario, prestamo.usuario_id)
        # Lo cargado por reposición menos lo perdonado y lo ya reintegrado: se devuelve lo
        # pagado y se anula lo que seguía pendiente. Las condonaciones y pagos "en general"
        # cuentan, porque la imputación los asigna a los cargos más viejos.
        reposiciones = [c for c in cuentas.imputacion_de(db, prestamo.usuario_id).values()
                        if c["cargo"].tipo == "REPOSICION"
                        and c["cargo"].prestamo_id == prestamo.id]
        reintegro = sum((c["monto"] - c["condonado"] - c["reintegrado"] for c in reposiciones),
                        Decimal("0.00")).quantize(Decimal("0.01"))
        if lector and reintegro > 0:
            cuentas.registrar(
                db, lector, "REINTEGRO", -reintegro, prestamo_id=prestamo.id,
                descripcion=f"Reintegro: apareció el ejemplar {item.codigo_barras}",
                personal_id=personal_id, cargo_id=max(c["cargo"].id for c in reposiciones))
        else:
            reintegro = Decimal("0.00")

    return _reincorporar(db, item, "El ejemplar declarado perdido volvió al inventario",
                         sede_id or _sede_por_defecto(db), personal_id,
                         recuperado=True, reintegro=reintegro, lector_reintegro=lector)


def renovar(db: Session, prestamo_id: int, personal_id: Optional[int] = None) -> dict:
    prestamo = db.get(models.Prestamo, prestamo_id, with_for_update=True)
    if not prestamo:
        raise NoEncontrado("Préstamo no encontrado")
    if prestamo.fecha_devolucion:
        raise ReglaIncumplida("El préstamo ya fue devuelto, no puede renovarse")

    usuario = db.get(models.Usuario, prestamo.usuario_id)
    item = db.get(models.Item, prestamo.item_id)
    regla = regla_del_prestamo(db, usuario, item)

    realizadas = prestamo.renovaciones_realizadas or 0
    if realizadas >= regla.max_renovaciones:
        raise ReglaIncumplida(
            f"El préstamo agotó sus {regla.max_renovaciones} renovaciones permitidas")

    # No se renueva un ejemplar que otro lector está esperando.
    if reservas.hay_cola(db, item.biblio_id):
        raise ReglaIncumplida("No se puede renovar: hay reservas pendientes sobre este título")

    _bloquear_si_debe(db, usuario)

    # Si ya estaba atrasado, la mora hasta hoy se cobra ahora: renovar no la borra.
    cal = calendario.cargar(db)
    momento = ahora()
    multa = Decimal("0.00")
    if momento > prestamo.fecha_vencimiento:
        multa = calcular_multa(cal, regla, prestamo.fecha_vencimiento, momento)
        if multa > 0:
            cuentas.registrar(
                db, usuario, "MULTA_ATRASO", multa, prestamo_id=prestamo.id,
                descripcion=f"Atraso de {item.codigo_barras} cobrado al renovar",
                personal_id=personal_id)

    # Corre desde el vencimiento si aún no venció, y desde hoy si ya está atrasado.
    base = max(fecha_local(prestamo.fecha_vencimiento), hoy())
    prestamo.fecha_vencimiento = _vencimiento(cal, base, regla.dias_prestamo)
    prestamo.renovaciones_realizadas = realizadas + 1
    db.commit()
    db.refresh(prestamo)

    return {
        "mensaje": "Préstamo renovado correctamente",
        "nueva_fecha_vencimiento": prestamo.fecha_vencimiento,
        "renovaciones_realizadas": prestamo.renovaciones_realizadas,
        "renovaciones_restantes": regla.max_renovaciones - prestamo.renovaciones_realizadas,
        "multa_aplicada": float(multa),
    }


def declarar_perdido(db: Session, prestamo_id: int, personal_id: Optional[int] = None) -> dict:
    """Cierra el préstamo, marca el ejemplar como perdido y cobra la reposición."""
    prestamo = db.get(models.Prestamo, prestamo_id, with_for_update=True)
    if not prestamo:
        raise NoEncontrado("Préstamo no encontrado")
    if prestamo.fecha_devolucion:
        raise ReglaIncumplida("El préstamo ya está cerrado")

    usuario = db.get(models.Usuario, prestamo.usuario_id)
    item = db.get(models.Item, prestamo.item_id)
    ajustes = configuracion.leer(db, "circulacion")
    precio = item.precio_reposicion
    if precio is None:
        precio = ajustes["precio_reposicion"]

    # La mora acumulada hasta hoy no se borra por perder el libro (Koha: WhenLostForgiveFine).
    momento, multa = ahora(), Decimal("0.00")
    if not ajustes.get("perdonar_mora_al_perder") and momento > prestamo.fecha_vencimiento:
        multa = calcular_multa(calendario.cargar(db), regla_del_prestamo(db, usuario, item),
                               prestamo.fecha_vencimiento, momento)
        if multa > 0:
            cuentas.registrar(db, usuario, "MULTA_ATRASO", multa, prestamo_id=prestamo.id,
                              descripcion=f"Atraso de {item.codigo_barras} hasta declararlo perdido",
                              personal_id=personal_id)

    cuentas.registrar(db, usuario, "REPOSICION", precio, prestamo_id=prestamo.id,
                      descripcion=f"Reposición del ejemplar perdido {item.codigo_barras}",
                      personal_id=personal_id)
    prestamo.fecha_devolucion = ahora()
    prestamo.personal_devolucion_id = personal_id
    prestamo.perdido = True
    item.estado = "Perdido"
    db.commit()
    return {"mensaje": "Ejemplar declarado perdido", "cargo_reposicion": float(precio),
            "multa_atraso": float(multa)}


# --- Consultas --------------------------------------------------------------------

COLUMNAS_EXPORTACION = ["id", "bookTitle", "bookCode", "userName", "userId", "userType",
                        "loanDate", "dueDate", "returnDate", "renewals", "status"]


def _consulta_prestamos(db: Session):
    """Préstamo con ejemplar, título, lector y categoría en una sola consulta."""
    return db.query(models.Prestamo, models.Item, models.RegistroBibliografico,
                    models.Usuario, models.CategoriaUsuario).outerjoin(
        models.Item, models.Item.id == models.Prestamo.item_id).outerjoin(
        models.RegistroBibliografico, models.RegistroBibliografico.id == models.Item.biblio_id
    ).outerjoin(models.Usuario, models.Usuario.id == models.Prestamo.usuario_id).outerjoin(
        models.CategoriaUsuario, models.CategoriaUsuario.id == models.Usuario.categoria_id)


def _vista_prestamo(p, item, biblio, momento) -> dict:
    return {
        "id": str(p.id),
        "bookTitle": biblio.titulo if biblio else "Desconocido",
        "bookCode": item.codigo_barras if item else "N/A",
        "loanDate": formatear_fecha(p.fecha_prestamo),
        "dueDate": formatear_fecha(p.fecha_vencimiento),
        "returnDate": formatear_fecha(p.fecha_devolucion),
        "renewals": p.renovaciones_realizadas or 0,
        "status": estado_de_prestamo(p, momento),
        "lost": bool(p.perdido),
        # Perdido y todavía sin aparecer: se puede registrar que volvió.
        "recoverable": bool(p.perdido and item and item.estado == "Perdido"),
    }


def listar_prestamos(db: Session, estado: Optional[str] = None,
                     limite: Optional[int] = None) -> List[dict]:
    """Vista de préstamos que consume la tabla de circulación.

    `estado`: «vencidos» (sin devolver y ya vencidos) o «activos» (sin devolver); sin él,
    todos, históricos incluidos. `limite`: los N más recientes (el panel pide 5).
    """
    momento = ahora()
    P = models.Prestamo
    consulta = _consulta_prestamos(db)
    if estado in ("activos", "vencidos"):
        consulta = consulta.filter(P.fecha_devolucion == None)  # noqa: E711
    if estado == "vencidos":
        consulta = consulta.filter(P.fecha_vencimiento < momento)
    consulta = consulta.order_by(P.id.desc())
    if limite:
        consulta = consulta.limit(limite)
    filas = consulta.all()
    todas_las_reglas = db.query(models.ReglaCirculacion).all()
    sede = _sede_por_defecto(db)

    def renovaciones_permitidas(u, item) -> Optional[int]:
        if not u or not item:
            return None
        regla = reglas.elegir(todas_las_reglas, u.categoria_id, item.tipo_item_id,
                              item.biblioteca_actual_id or sede)
        return regla.max_renovaciones if regla else None

    return [
        {
            **_vista_prestamo(p, item, biblio, momento),
            "userName": f"{u.nombre} {u.apellido}" if u else "Desconocido",
            "userId": u.nro_carnet if u else "N/A",
            "userType": tipo_de_lector(categoria),
            "renewalsAllowed": renovaciones_permitidas(u, item),
        }
        for p, item, biblio, u, categoria in filas
    ]


def historial_de_lector(db: Session, nro_carnet: str) -> List[dict]:
    usuario = db.query(models.Usuario).filter(models.Usuario.nro_carnet == nro_carnet).first()
    if not usuario:
        raise NoEncontrado("Usuario no encontrado")

    momento = ahora()
    filas = _consulta_prestamos(db).filter(models.Prestamo.usuario_id == usuario.id).order_by(
        models.Prestamo.fecha_prestamo.desc()).all()
    return [_vista_prestamo(p, item, biblio, momento) for p, item, biblio, _u, _c in filas]
