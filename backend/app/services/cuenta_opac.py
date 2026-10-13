"""La cuenta del lector en el OPAC: lo que cada uno ve y hace con lo suyo.

Todo pasa por los mismos servicios que usa el personal (renovar, reservar, cuentas,
sugerencias), con dos diferencias: el lector solo toca lo propio (lo ajeno responde
404, como si no existiera) y los mensajes le hablan a él, no al bibliotecario.
"""

from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from app import models
from app.core.errores import NoEncontrado, ReglaIncumplida
from app.core.tiempo import ahora, fecha_local, formatear_fecha, hoy
from app.services import calendario, circulacion, cuentas, reservas, sedes, sugerencias

P = models.Prestamo
RB = models.RegistroBibliografico
# Sugerencias sin responder que un lector puede tener a la vez.
MAX_SUGERENCIAS_PENDIENTES = 5


def _bs(monto) -> str:
    """Bs. 19,50: el formato que ve el lector en el resto del OPAC."""
    cifra = f"{Decimal(str(monto)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"Bs. {cifra}"


def _deuda(db: Session, usuario: models.Usuario) -> dict:
    saldo, umbral = cuentas.saldo(db, usuario.id), cuentas.umbral_de_bloqueo(db)
    return {"saldo": float(saldo), "umbral_bloqueo": float(umbral),
            "bloqueado": cuentas.esta_bloqueado(saldo, umbral)}


def resumen(db: Session, usuario: models.Usuario) -> dict:
    categoria = db.get(models.CategoriaUsuario, usuario.categoria_id) if usuario.categoria_id else None
    sede = db.get(models.Biblioteca, usuario.biblioteca_id) if usuario.biblioteca_id else None
    activos = db.query(P).filter(P.usuario_id == usuario.id,
                                 P.fecha_devolucion == None).all()  # noqa: E711
    momento = ahora()
    if reservas.expirar_vencidas(db):
        db.commit()
    mis_reservas = db.query(models.Reserva).filter(
        models.Reserva.usuario_id == usuario.id,
        models.Reserva.estado.in_(reservas.ACTIVAS)).all()
    return {
        "carnet": usuario.nro_carnet,
        "nombre": usuario.nombre,
        "apellido": usuario.apellido,
        "email": usuario.email,
        "categoria": categoria.descripcion if categoria else None,
        "sede": sede.nombre if sede else None,
        "prestamos": len(activos),
        "vencidos": sum(1 for p in activos if p.fecha_vencimiento < momento),
        "reservas": len(mis_reservas),
        "para_retirar": sum(1 for r in mis_reservas if r.estado == reservas.EN_ESPERA),
        **_deuda(db, usuario),
    }


# --- Préstamos -------------------------------------------------------------------------

def _impedimento(db: Session, usuario: models.Usuario, prestamo: models.Prestamo,
                 item: models.Item, regla, bloqueado: bool) -> Optional[str]:
    """Por qué el lector no puede renovar este préstamo, en sus palabras (None: sí puede)."""
    if (prestamo.renovaciones_realizadas or 0) >= regla.max_renovaciones:
        if regla.max_renovaciones == 0:
            return "Este material no se renueva"
        return f"Ya usaste las {regla.max_renovaciones} renovaciones permitidas"
    if reservas.hay_cola(db, item.biblio_id):
        return "Otro lector lo reservó: hay que devolverlo"
    if bloqueado:
        return "Tienes una deuda pendiente: págala en la biblioteca para renovar"
    return None


def _cargo_al_renovar(cal, regla, prestamo: models.Prestamo) -> Decimal:
    """Lo que se cobrará por el atraso si el préstamo se renueva ahora (0 si no está vencido)."""
    momento = ahora()
    if momento <= prestamo.fecha_vencimiento:
        return Decimal("0.00")
    return circulacion.calcular_multa(cal, regla, prestamo.fecha_vencimiento, momento)


def prestamos(db: Session, usuario: models.Usuario) -> List[dict]:
    filas = db.query(P, models.Item, RB).join(models.Item, models.Item.id == P.item_id).join(
        RB, RB.id == models.Item.biblio_id).filter(
        P.usuario_id == usuario.id, P.fecha_devolucion == None).order_by(  # noqa: E711
        P.fecha_vencimiento, P.id).all()
    deuda = _deuda(db, usuario)
    bloqueado = deuda["bloqueado"]
    cal = calendario.cargar(db)
    momento = ahora()
    vista = []
    for p, item, biblio in filas:
        regla = circulacion.regla_del_prestamo(db, usuario, item)
        impedimento = _impedimento(db, usuario, p, item, regla, bloqueado)
        cargo = _cargo_al_renovar(cal, regla, p)
        atraso = (hoy() - fecha_local(p.fecha_vencimiento)).days
        vista.append({
            "id": p.id,
            "biblio_id": biblio.id,
            "titulo": biblio.titulo,
            "autor": biblio.autor,
            "codigo_barras": item.codigo_barras,
            "numeracion": item.enumeracion,
            "prestado": formatear_fecha(p.fecha_prestamo),
            "vence": formatear_fecha(p.fecha_vencimiento),
            "vence_iso": fecha_local(p.fecha_vencimiento).isoformat(),
            "vencido": p.fecha_vencimiento < momento,
            "dias_atraso": max(atraso, 0),
            "renovaciones": p.renovaciones_realizadas or 0,
            "renovaciones_permitidas": regla.max_renovaciones,
            "renovable": impedimento is None,
            "motivo": impedimento,
            # Renovar un préstamo vencido cobra el atraso: el lector lo ve antes de aceptar.
            "cargo_al_renovar": float(cargo),
            "bloquearia": bool(cargo) and cuentas.esta_bloqueado(
                Decimal(str(deuda["saldo"])) + cargo, Decimal(str(deuda["umbral_bloqueo"]))),
        })
    return vista


def _prestamo_propio(db: Session, usuario: models.Usuario, prestamo_id: int) -> models.Prestamo:
    prestamo = db.get(P, prestamo_id)
    if not prestamo or prestamo.usuario_id != usuario.id:
        raise NoEncontrado("Préstamo no encontrado")
    if prestamo.fecha_devolucion:
        raise ReglaIncumplida("Ese préstamo ya fue devuelto")
    return prestamo


def renovar(db: Session, usuario: models.Usuario, prestamo_id: int,
            aceptar_cargo: bool = False) -> dict:
    """Renueva un préstamo propio. Si está vencido, cobra el atraso solo con `aceptar_cargo`."""
    prestamo = _prestamo_propio(db, usuario, prestamo_id)
    item = db.get(models.Item, prestamo.item_id)
    regla = circulacion.regla_del_prestamo(db, usuario, item)
    impedimento = _impedimento(db, usuario, prestamo, item, regla,
                               _deuda(db, usuario)["bloqueado"])
    if impedimento:
        raise ReglaIncumplida(impedimento)
    cargo = _cargo_al_renovar(calendario.cargar(db), regla, prestamo)
    if cargo > 0 and not aceptar_cargo:
        raise ReglaIncumplida(
            f"Está vencido: renovarlo cobra {_bs(cargo)} por el atraso. Confírmalo para seguir")
    r = circulacion.renovar(db, prestamo.id)
    mensaje = f"Renovado hasta el {formatear_fecha(r['nueva_fecha_vencimiento'])}"
    if r["multa_aplicada"]:
        mensaje += f". Se cargó {_bs(r['multa_aplicada'])} por el atraso"
    return {"mensaje": mensaje, "vence": formatear_fecha(r["nueva_fecha_vencimiento"]),
            "multa": r["multa_aplicada"]}


def renovar_todos(db: Session, usuario: models.Usuario) -> dict:
    """Renueva lo que se pueda sin cobrar nada: los vencidos se renuevan uno por uno."""
    renovados, no = [], []
    for p in prestamos(db, usuario):
        if p["renovable"] and not p["cargo_al_renovar"]:
            renovar(db, usuario, p["id"])
            renovados.append(p["titulo"])
        elif p["renovable"]:
            no.append({"titulo": p["titulo"],
                       "motivo": "Está vencido: renuévalo por separado para ver el cargo"})
        else:
            no.append({"titulo": p["titulo"], "motivo": p["motivo"]})
    return {"renovados": renovados, "no_renovados": no}


def historial(db: Session, usuario: models.Usuario) -> List[dict]:
    filas = db.query(P, models.Item, RB).join(models.Item, models.Item.id == P.item_id).join(
        RB, RB.id == models.Item.biblio_id).filter(
        P.usuario_id == usuario.id, P.fecha_devolucion != None).order_by(  # noqa: E711
        P.fecha_devolucion.desc(), P.id.desc()).all()
    return [{
        "id": p.id,
        "biblio_id": biblio.id,
        "titulo": biblio.titulo,
        "autor": biblio.autor,
        "prestado": formatear_fecha(p.fecha_prestamo),
        "devuelto": formatear_fecha(p.fecha_devolucion),
        "perdido": bool(p.perdido),
    } for p, _item, biblio in filas]


# --- Reservas --------------------------------------------------------------------------

def mis_reservas(db: Session, usuario: models.Usuario) -> List[dict]:
    if reservas.expirar_vencidas(db):
        db.commit()
    Rs = models.Reserva
    filas = reservas._consulta(db).filter(Rs.usuario_id == usuario.id,
                                          Rs.estado.in_(reservas.ACTIVAS)).order_by(
        Rs.fecha_reserva, Rs.id).all()
    nombres = sedes.nombres(db)
    transito = reservas._traslados_abiertos(
        db, [r.id for r, *_ in filas if r.estado == reservas.EN_TRANSITO])
    vistas = []
    for fila in filas:
        v = reservas._fila(*fila, nombres, transito)
        # Lo que el lector necesita; ni el ejemplar ni datos internos del traslado.
        vistas.append({k: v[k] for k in (
            "id", "biblioId", "title", "author", "priority", "status", "reservedOn",
            "pickupBranchId", "pickupBranch", "pickupBy", "suspended", "suspendedUntil",
            "notNeededAfter")})
    return vistas


def _reserva_propia(db: Session, usuario: models.Usuario, reserva_id: int) -> models.Reserva:
    reserva = db.get(models.Reserva, reserva_id)
    if not reserva or reserva.usuario_id != usuario.id:
        raise NoEncontrado("Reserva no encontrada")
    return reserva


def reservar(db: Session, usuario: models.Usuario, datos: dict) -> dict:
    biblio = db.get(RB, datos["biblio_id"])
    if not biblio:
        raise NoEncontrado("Título no encontrado en el catálogo")
    prestables = db.query(models.Item).outerjoin(
        models.TipoItem, models.TipoItem.id == models.Item.tipo_item_id).filter(
        models.Item.biblio_id == biblio.id, models.Item.estado != "Perdido",
        (models.TipoItem.es_prestable == True) | (models.Item.tipo_item_id == None)  # noqa: E711,E712
    ).count()
    if not prestables:
        raise ReglaIncumplida("Este título no tiene ejemplares que se presten a domicilio")
    if _deuda(db, usuario)["bloqueado"]:
        raise ReglaIncumplida("Tienes una deuda pendiente: págala en la biblioteca para reservar")
    r = reservas.reservar(db, biblio.id, usuario.nro_carnet,
                          biblioteca_retiro_id=datos.get("biblioteca_retiro_id"),
                          fecha_limite=datos.get("fecha_limite"), notas=datos.get("notas"))
    reserva = db.get(models.Reserva, r["reserva_id"])
    sede = db.get(models.Biblioteca, reserva.biblioteca_retiro_id) if reserva.biblioteca_retiro_id else None
    mensaje = f"Reservado. Estás en el turno {reserva.prioridad}"
    if sede:
        mensaje += f"; lo retirarás en {sede.nombre}"
    return {"mensaje": mensaje + ".", "reserva_id": reserva.id, "turno": reserva.prioridad}


def cancelar_reserva(db: Session, usuario: models.Usuario, reserva_id: int) -> None:
    reservas.cancelar(db, _reserva_propia(db, usuario, reserva_id).id)


def modificar_reserva(db: Session, usuario: models.Usuario, reserva_id: int,
                      datos: dict) -> dict:
    """Sede de retiro y suspensión: lo que el lector decide sobre su reserva pendiente."""
    reserva = _reserva_propia(db, usuario, reserva_id)
    permitido = {k: datos[k] for k in ("biblioteca_retiro_id", "suspendida", "suspendida_hasta")
                 if k in datos}
    reservas.modificar(db, reserva.id, permitido)
    return next(r for r in mis_reservas(db, usuario) if r["id"] == str(reserva.id))


# --- Cuenta, sugerencias y contraseña -----------------------------------------------------

def multas(db: Session, usuario: models.Usuario) -> dict:
    estado = cuentas.estado_de_cuenta(db, usuario)
    return {
        "saldo": estado["saldo"],
        "umbral_bloqueo": estado["umbral_bloqueo"],
        "bloqueado": estado["bloqueado"],
        "movimientos": [{k: m[k] for k in ("id", "tipo", "monto", "descripcion", "fecha")}
                        for m in estado["movimientos"]],
    }


def mis_sugerencias(db: Session, usuario: models.Usuario) -> List[dict]:
    S = models.Sugerencia
    filas = db.query(S).filter(S.usuario_id == usuario.id).order_by(S.fecha.desc(), S.id.desc())
    return [{"id": s.id, "titulo": s.titulo, "autor": s.autor, "isbn": s.isbn,
             "editorial": s.editorial, "ano": s.ano, "nota": s.nota, "estado": s.estado,
             "motivo": s.motivo, "fecha": formatear_fecha(s.fecha)} for s in filas]


def sugerir(db: Session, usuario: models.Usuario, datos: dict) -> dict:
    S = models.Sugerencia
    abiertas = db.query(S).filter(S.usuario_id == usuario.id,
                                  S.estado == sugerencias.PENDIENTE).count()
    if abiertas >= MAX_SUGERENCIAS_PENDIENTES:
        raise ReglaIncumplida(
            f"Tienes {abiertas} sugerencias sin responder: espera a que la biblioteca las revise")
    datos = {k: v for k, v in datos.items() if k != "nro_carnet"}
    creada = sugerencias.crear(db, datos, personal=usuario)
    return next(s for s in mis_sugerencias(db, usuario) if s["id"] == creada["id"])
