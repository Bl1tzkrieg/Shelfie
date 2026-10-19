"""Reservas (holds): cola por título, tránsito a la sede de retiro, espera, retiro y expiración.

Ciclo de vida, como en Koha:

    Pendiente ──(aparece un ejemplar)──▶ [EnTransito ──(llega a la sede)──▶] EnEspera ──▶ Cumplida
        │                                     │                                 │
        └────────────▶ Cancelada ◀────────────┴─────────────────────────────────┤
        └──(vence su fecha límite)──▶ Expirada ◀──(no lo retiran a tiempo)──────┘

Una reserva pendiente puede estar suspendida: conserva su turno pero ningún
ejemplar se le aparta hasta que se reanude (a mano o al llegar su fecha).

Mientras una reserva está EnEspera, su ejemplar queda "Reservado" y solo se le
presta a ese lector. Adónde va cada ejemplar liberado lo decide `traslados.ubicar`.
"""

from datetime import date
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.core.errores import NoEncontrado, ReglaIncumplida
from app.core.tiempo import ahora, fecha_local, fin_del_dia, formatear_fecha, hoy
from app.services import calendario, configuracion, cuentas, reglas, sedes

PENDIENTE, EN_TRANSITO, EN_ESPERA = "Pendiente", "EnTransito", "EnEspera"
CUMPLIDA, CANCELADA, EXPIRADA = "Cumplida", "Cancelada", "Expirada"
ACTIVAS = (PENDIENTE, EN_TRANSITO, EN_ESPERA)

Rs = models.Reserva


def _pendientes(db: Session, biblio_id: int) -> List[models.Reserva]:
    return db.query(Rs).filter(Rs.biblio_id == biblio_id, Rs.estado == PENDIENTE).order_by(
        Rs.prioridad, Rs.fecha_reserva, Rs.id).all()


def renumerar(db: Session, biblio_id: int) -> None:
    """Deja los turnos de las pendientes como 1, 2, 3… sin huecos ni repetidos."""
    db.flush()
    for turno, reserva in enumerate(_pendientes(db, biblio_id), start=1):
        reserva.prioridad = turno


def _cerrar(reserva: models.Reserva, estado: str) -> None:
    reserva.estado = estado
    reserva.fecha_cierre = ahora()


def _liberar(db: Session, item: models.Item) -> None:
    """El ejemplar de una reserva que se cerró queda libre en la sede donde está."""
    from app.services import traslados
    traslados.ubicar(db, item, item.biblioteca_actual_id, en_mano=False)


# --- Pasos del ciclo (los usa traslados.ubicar) ----------------------------------------

def _contexto_atencion(db: Session) -> tuple:
    return ({t.id: t for t in db.query(models.TipoItem)}, db.query(models.ReglaCirculacion).all())


def puede_atender(db: Session, usuario: Optional[models.Usuario], item: models.Item,
                  contexto: Optional[tuple] = None) -> bool:
    """¿Este ejemplar le sirve a este lector? Activo, y el material se le presta a domicilio."""
    if not usuario or not usuario.activo:
        return False
    tipos, todas = contexto or _contexto_atencion(db)
    tipo = tipos.get(item.tipo_item_id)
    if tipo is not None and not tipo.es_prestable:
        return False
    regla = reglas.elegir(todas, usuario.categoria_id, item.tipo_item_id,
                          item.biblioteca_actual_id or item.biblioteca_propia_id)
    return bool(regla is None or regla.prestable)


def siguiente_para(db: Session, item: models.Item,
                   bloquear: bool = False) -> Optional[models.Reserva]:
    """La primera reserva pendiente, no suspendida, a la que este ejemplar le sirve.

    Se saltan los lectores suspendidos y aquellos a quienes este material no se les presta
    (una copia de sala no atiende reservas). Con `bloquear`, la reserva elegida queda tomada
    (FOR UPDATE SKIP LOCKED): dos devoluciones simultáneas no se llevan la misma.
    """
    consulta = db.query(Rs).filter(
        Rs.biblio_id == item.biblio_id, Rs.estado == PENDIENTE,
        Rs.suspendida == False).order_by(  # noqa: E712
        Rs.prioridad, Rs.fecha_reserva, Rs.id)
    if bloquear:
        consulta = consulta.with_for_update(skip_locked=True)
    contexto = None
    for reserva in consulta:
        contexto = contexto or _contexto_atencion(db)
        if puede_atender(db, db.get(models.Usuario, reserva.usuario_id), item, contexto):
            return reserva
    return None


def motivo_no_reservable(db: Session, biblio_id: int) -> Optional[str]:
    """Por qué no se puede reservar un título (None si se puede).

    Hace falta al menos un ejemplar que se preste a domicilio y no esté perdido ni dado
    de baja, o una línea de pedido abierta (el título viene en camino).
    """
    I, T = models.Item, models.TipoItem
    prestables = db.query(I.id).outerjoin(T, T.id == I.tipo_item_id).filter(
        I.biblio_id == biblio_id, I.estado.notin_(("Perdido", "Retirado")),
        (T.es_prestable == True) | (I.tipo_item_id == None)).first()  # noqa: E711,E712
    if prestables:
        return None
    L, S = models.LineaOrden, models.Suscripcion
    en_pedido = db.query(L.id).filter(L.biblio_id == biblio_id,
                                      L.estado.in_(("Pendiente", "Parcial"))).first()
    suscrita = db.query(S.id).filter(S.biblio_id == biblio_id, S.estado == "Activa",
                                     S.crear_ejemplares == True).first()  # noqa: E712
    if en_pedido or suscrita:
        return None
    return "Este título no tiene ejemplares que se presten a domicilio"


def poner_en_espera(db: Session, reserva: models.Reserva, item: models.Item) -> None:
    dias = int(configuracion.leer(db, "circulacion")["dias_retiro_reserva"])
    vence = calendario.cargar(db).sumar_habiles(hoy(), dias)
    reserva.estado = EN_ESPERA
    reserva.item_id = item.id
    reserva.fecha_en_espera = ahora()
    reserva.fecha_expiracion = fin_del_dia(vence)
    item.estado = "Reservado"
    renumerar(db, item.biblio_id)
    _avisar(db, "RESERVA_LISTA", reserva, f"RESERVA_LISTA:{reserva.id}:{item.id}",
            retirar_hasta=formatear_fecha(reserva.fecha_expiracion))


def _avisar(db: Session, codigo: str, reserva: models.Reserva, clave: str, **extra) -> None:
    from app.services import avisos

    usuario = db.get(models.Usuario, reserva.usuario_id)
    biblio = db.get(models.RegistroBibliografico, reserva.biblio_id)
    sede = db.get(models.Biblioteca, reserva.biblioteca_retiro_id) \
        if reserva.biblioteca_retiro_id else None
    if usuario and biblio:
        avisos.para_lector(db, codigo, usuario, {
            "titulo": biblio.titulo, "autor": biblio.autor or "",
            "sede": sede.nombre if sede else "la biblioteca", **extra}, clave=clave)


def poner_en_transito(db: Session, reserva: models.Reserva, item: models.Item) -> None:
    reserva.estado = EN_TRANSITO
    reserva.item_id = item.id
    renumerar(db, item.biblio_id)


def volver_a_la_cola(db: Session, reserva: models.Reserva) -> None:
    """Una reserva en tránsito cuyo traslado se canceló recupera el primer turno."""
    reserva.estado = PENDIENTE
    reserva.item_id = None
    reserva.prioridad = 0
    renumerar(db, reserva.biblio_id)


def liberar_ejemplar(db: Session, item: models.Item) -> str:
    """El ejemplar apartado queda libre: pasa a la siguiente reserva, viaja o queda Disponible."""
    _liberar(db, item)
    return item.estado


def expirar_vencidas(db: Session) -> int:
    """Mantenimiento diario de la cola (sin commit). Devuelve cuántas reservas expiraron.

    - Reanuda las suspensiones cuya fecha llegó.
    - Expira las pendientes cuya fecha límite pasó.
    - Expira las en espera que no se retiraron a tiempo y libera su ejemplar.
    """
    hoy_ = hoy()
    for reserva in db.query(Rs).filter(Rs.estado == PENDIENTE, Rs.suspendida == True,  # noqa: E712
                                       Rs.suspendida_hasta != None,  # noqa: E711
                                       Rs.suspendida_hasta <= hoy_):
        reserva.suspendida, reserva.suspendida_hasta = False, None

    caducas = db.query(Rs).filter(Rs.estado == PENDIENTE, Rs.fecha_limite != None,  # noqa: E711
                                  Rs.fecha_limite < hoy_).all()
    for reserva in caducas:
        _cerrar(reserva, EXPIRADA)
    for biblio_id in {r.biblio_id for r in caducas}:
        renumerar(db, biblio_id)

    vencidas = db.query(Rs).filter(Rs.estado == EN_ESPERA, Rs.fecha_expiracion < ahora()).all()
    for reserva in vencidas:
        _cerrar(reserva, EXPIRADA)
        _avisar(db, "RESERVA_EXPIRADA", reserva, f"RESERVA_EXPIRADA:{reserva.id}")
        item = db.get(models.Item, reserva.item_id) if reserva.item_id else None
        if item and item.estado == "Reservado":
            _liberar(db, item)
    return len(caducas) + len(vencidas)


def resolver_al_prestar(db: Session, usuario: models.Usuario, item: models.Item) -> None:
    """Valida el préstamo de un ejemplar frente a las reservas y cumple la del lector."""
    if item.estado == "Reservado":
        reserva = db.query(Rs).filter(Rs.item_id == item.id, Rs.estado == EN_ESPERA).first()
        if reserva and reserva.usuario_id != usuario.id:
            titular = db.get(models.Usuario, reserva.usuario_id)
            raise ReglaIncumplida(
                f"Este ejemplar está apartado para {titular.nombre} {titular.apellido} "
                f"hasta el {formatear_fecha(reserva.fecha_expiracion)}")
        if reserva:
            _cerrar(reserva, CUMPLIDA)
            return

    # Si el lector tenía una reserva del título, este préstamo la cumple. Si ya tenía
    # otro ejemplar apartado, ese queda libre para el siguiente.
    propia = db.query(Rs).filter(Rs.biblio_id == item.biblio_id, Rs.usuario_id == usuario.id,
                                 Rs.estado.in_(ACTIVAS)).first()
    if not propia:
        return
    estado_previo, otro_item_id = propia.estado, propia.item_id
    _cerrar(propia, CUMPLIDA)
    renumerar(db, item.biblio_id)
    if not otro_item_id or otro_item_id == item.id:
        return
    otro = db.get(models.Item, otro_item_id)
    if not otro:
        return
    if estado_previo == EN_ESPERA and otro.estado == "Reservado":
        _liberar(db, otro)
    elif estado_previo == EN_TRANSITO:
        # El otro ejemplar iba hacia su sede para él: si no salió, no tiene que viajar.
        from app.services import traslados  # importa reservas: se resuelve al usarlo
        traslados.anular_si_no_salio(db, propia.id, otro)


def hay_cola(db: Session, biblio_id: int) -> bool:
    """Hay alguien esperando el título (las suspendidas no frenan una renovación)."""
    return db.query(Rs).filter(Rs.biblio_id == biblio_id, Rs.estado == PENDIENTE,
                               Rs.suspendida == False).count() > 0  # noqa: E712


# --- Operaciones del personal ---------------------------------------------------------

def _punto_de_retiro_por_defecto(db: Session, usuario: models.Usuario,
                                 sede_trabajo: Optional[int]) -> Optional[int]:
    for candidata in (usuario.biblioteca_id, sede_trabajo):
        if candidata:
            sede = db.get(models.Biblioteca, candidata)
            if sede and sede.punto_retiro:
                return sede.id
    primera = db.query(models.Biblioteca.id).filter(
        models.Biblioteca.punto_retiro == True).order_by(  # noqa: E712
        models.Biblioteca.id).first()
    return primera[0] if primera else None


def reservar(db: Session, biblio_id: int, nro_carnet: str, *,
             biblioteca_retiro_id: Optional[int] = None, fecha_limite: Optional[date] = None,
             notas: Optional[str] = None, sede_trabajo: Optional[int] = None,
             para_el_lector: bool = False) -> dict:
    """Crea la reserva. `para_el_lector`: los mensajes le hablan al lector (OPAC), no al personal."""
    def msg(personal: str, lector: str) -> str:
        return lector if para_el_lector else personal

    usuario = db.query(models.Usuario).filter(
        models.Usuario.nro_carnet == nro_carnet,
        models.Usuario.activo == True).first()  # noqa: E712
    if not usuario:
        raise NoEncontrado("Usuario no encontrado o inactivo")

    biblio = db.get(models.RegistroBibliografico, biblio_id)
    if not biblio:
        raise NoEncontrado("Título no encontrado en el catálogo")

    if db.query(Rs).filter(Rs.biblio_id == biblio.id, Rs.usuario_id == usuario.id,
                           Rs.estado.in_(ACTIVAS)).first():
        raise ReglaIncumplida(msg("El usuario ya tiene una reserva activa sobre este título",
                                  "Ya tienes una reserva de este título: la ves en Mi cuenta"))

    tiene_prestado = db.query(models.Prestamo).join(
        models.Item, models.Item.id == models.Prestamo.item_id).filter(
        models.Item.biblio_id == biblio.id, models.Prestamo.usuario_id == usuario.id,
        models.Prestamo.fecha_devolucion == None).first()  # noqa: E711
    if tiene_prestado:
        raise ReglaIncumplida(msg("El usuario ya tiene prestado un ejemplar de este título",
                                  "Ya tienes prestado un ejemplar de este título"))

    saldo, umbral = cuentas.saldo(db, usuario.id), cuentas.umbral_de_bloqueo(db)
    if cuentas.esta_bloqueado(saldo, umbral):
        raise ReglaIncumplida(msg(
            f"El usuario debe Bs. {saldo:.2f} (supera el máximo de Bs. {umbral:.2f})",
            f"Tienes una deuda de Bs. {saldo:.2f}: págala en la biblioteca para reservar"))

    regla = reglas.regla_para(db, usuario.categoria_id, None, usuario.biblioteca_id)
    activas = db.query(Rs).filter(Rs.usuario_id == usuario.id, Rs.estado.in_(ACTIVAS)).count()
    if activas >= regla.max_reservas:
        raise ReglaIncumplida(msg(
            f"El usuario alcanzó su límite de {regla.max_reservas} reservas activas",
            f"Llegaste al máximo de {regla.max_reservas} reservas activas: cancela alguna "
            "o espera a retirarlas"))

    motivo = motivo_no_reservable(db, biblio.id)
    if motivo:
        raise ReglaIncumplida(motivo)

    if fecha_limite is not None and fecha_limite < hoy():
        raise ReglaIncumplida("La fecha límite no puede estar en el pasado")

    retiro = (sedes.validar_punto_de_retiro(db, biblioteca_retiro_id)
              if biblioteca_retiro_id is not None
              else _punto_de_retiro_por_defecto(db, usuario, sede_trabajo))

    renumerar(db, biblio.id)
    reserva = Rs(
        biblio_id=biblio.id, usuario_id=usuario.id, estado=PENDIENTE, fecha_reserva=ahora(),
        prioridad=len(_pendientes(db, biblio.id)) + 1, biblioteca_retiro_id=retiro,
        fecha_limite=fecha_limite, notas=(notas or "").strip() or None)
    db.add(reserva)
    db.commit()
    db.refresh(reserva)

    disponibles = db.query(models.Item).filter(models.Item.biblio_id == biblio.id,
                                               models.Item.estado == "Disponible").count()
    mensaje = f"Reserva registrada. Turno número {reserva.prioridad} en la cola."
    if disponibles:
        mensaje += (f" Hay {disponibles} ejemplar(es) en el estante: aparecerá en "
                    "'Para sacar del estante'.")
    return {"mensaje": mensaje, "reserva_id": reserva.id, "prioridad": reserva.prioridad}


def _obtener(db: Session, reserva_id: int) -> models.Reserva:
    reserva = db.get(Rs, reserva_id)
    if not reserva:
        raise NoEncontrado("Reserva no encontrada")
    return reserva


def cancelar(db: Session, reserva_id: int) -> None:
    from app.services import traslados

    reserva = _obtener(db, reserva_id)
    if reserva.estado not in ACTIVAS:
        raise ReglaIncumplida(f"La reserva ya está cerrada ({reserva.estado})")

    estado_previo = reserva.estado
    _cerrar(reserva, CANCELADA)
    item = db.get(models.Item, reserva.item_id) if reserva.item_id else None
    if estado_previo == EN_ESPERA and item and item.estado == "Reservado":
        _liberar(db, item)
    elif estado_previo == EN_TRANSITO and item:
        # Si todavía no salió, el traslado se anula y el ejemplar se ubica donde está.
        # Si ya va en camino, sigue viaje: al llegar se decide qué hacer con él.
        traslados.anular_si_no_salio(db, reserva.id, item)
    renumerar(db, reserva.biblio_id)
    db.commit()


def modificar(db: Session, reserva_id: int, datos: dict) -> dict:
    """Turno, sede de retiro, suspensión, fecha límite y notas (lo enviado, nada más)."""
    reserva = _obtener(db, reserva_id)
    if reserva.estado not in ACTIVAS:
        raise ReglaIncumplida(f"La reserva ya está cerrada ({reserva.estado})")

    def solo_pendiente(que: str) -> None:
        if reserva.estado != PENDIENTE:
            raise ReglaIncumplida(
                f"Solo se puede cambiar {que} de una reserva pendiente; esta ya tiene "
                "un ejemplar asignado")

    if datos.get("biblioteca_retiro_id") is not None:
        solo_pendiente("la sede de retiro")
        reserva.biblioteca_retiro_id = sedes.validar_punto_de_retiro(
            db, datos["biblioteca_retiro_id"])

    # Mandar solo la fecha de reanudación es pedir la suspensión hasta ese día.
    if datos.get("suspendida_hasta") is not None and datos.get("suspendida") is None:
        datos = {**datos, "suspendida": True}
    if "suspendida" in datos and datos["suspendida"] is not None:
        solo_pendiente("la suspensión")
        hasta = datos.get("suspendida_hasta")
        if datos["suspendida"] and hasta is not None and hasta <= hoy():
            raise ReglaIncumplida("La fecha de reanudación debe ser posterior a hoy")
        reserva.suspendida = bool(datos["suspendida"])
        reserva.suspendida_hasta = hasta if reserva.suspendida else None

    if "fecha_limite" in datos:
        limite = datos["fecha_limite"]
        if limite is not None and limite < hoy():
            raise ReglaIncumplida("La fecha límite no puede estar en el pasado")
        reserva.fecha_limite = limite

    if "notas" in datos:
        reserva.notas = (datos["notas"] or "").strip() or None

    if datos.get("prioridad") is not None:
        solo_pendiente("el turno")
        cola = [r for r in _pendientes(db, reserva.biblio_id) if r.id != reserva.id]
        posicion = max(1, min(int(datos["prioridad"]), len(cola) + 1))
        cola.insert(posicion - 1, reserva)
        for turno, r in enumerate(cola, start=1):
            r.prioridad = turno

    db.commit()
    return _vista(db, reserva)


# --- Consultas ------------------------------------------------------------------------

def _consulta(db: Session):
    return db.query(Rs, models.RegistroBibliografico, models.Usuario, models.Item).join(
        models.RegistroBibliografico, models.RegistroBibliografico.id == Rs.biblio_id).join(
        models.Usuario, models.Usuario.id == Rs.usuario_id).outerjoin(
        models.Item, models.Item.id == Rs.item_id)


def _fila(r, biblio, usuario, item, nombres_sedes: dict, transito: dict) -> dict:
    dias_esperando = ((hoy() - fecha_local(r.fecha_en_espera)).days
                      if r.estado == EN_ESPERA and r.fecha_en_espera else None)
    vence_hoy = (r.estado == EN_ESPERA and r.fecha_expiracion is not None
                 and fecha_local(r.fecha_expiracion) == hoy())
    traslado = transito.get(r.id)
    return {
        "id": str(r.id),
        "biblioId": str(biblio.id),
        "title": biblio.titulo,
        "author": biblio.autor,
        "userName": f"{usuario.nombre} {usuario.apellido}",
        "userId": usuario.nro_carnet,
        "priority": r.prioridad,
        "status": r.estado,
        "reservedOn": formatear_fecha(r.fecha_reserva),
        "itemBarcode": item.codigo_barras if item else None,
        "callNumber": item.signatura_topografica if item else None,
        "pickupBranchId": r.biblioteca_retiro_id,
        "pickupBranch": nombres_sedes.get(r.biblioteca_retiro_id),
        "pickupBy": formatear_fecha(r.fecha_expiracion) if r.estado == EN_ESPERA else None,
        "waitingSince": formatear_fecha(r.fecha_en_espera) if r.estado == EN_ESPERA else None,
        "daysWaiting": dias_esperando,
        "expiresToday": vence_hoy,
        "suspended": bool(r.suspendida),
        "suspendedUntil": r.suspendida_hasta.isoformat() if r.suspendida_hasta else None,
        "notNeededAfter": r.fecha_limite.isoformat() if r.fecha_limite else None,
        "notes": r.notas,
        "transitFromId": traslado.desde_id if traslado else None,
        "transitFrom": nombres_sedes.get(traslado.desde_id) if traslado else None,
        "transitSent": bool(traslado and traslado.fecha_envio),
        "closedOn": formatear_fecha(r.fecha_cierre),
    }


def _traslados_abiertos(db: Session, reserva_ids) -> dict:
    T = models.Traslado
    if not reserva_ids:
        return {}
    filas = db.query(T).filter(T.reserva_id.in_(reserva_ids),
                               T.estado.in_(("Solicitado", "Enviado"))).all()
    return {t.reserva_id: t for t in filas}


def _vista(db: Session, reserva: models.Reserva) -> dict:
    fila = _consulta(db).filter(Rs.id == reserva.id).one()
    return _fila(*fila, sedes.nombres(db), _traslados_abiertos(db, [reserva.id]))


def listar(db: Session, solo_activas: bool = False, biblio_id: Optional[int] = None) -> List[dict]:
    if expirar_vencidas(db):
        db.commit()
    consulta = _consulta(db)
    if solo_activas:
        consulta = consulta.filter(Rs.estado.in_(ACTIVAS))
    if biblio_id is not None:
        consulta = consulta.filter(Rs.biblio_id == biblio_id)
    filas = consulta.order_by(Rs.biblio_id, Rs.prioridad, Rs.id).all()
    nombres_sedes = sedes.nombres(db)
    transito = _traslados_abiertos(db, [r.id for r, *_ in filas if r.estado == EN_TRANSITO])
    return [_fila(*f, nombres_sedes, transito) for f in filas]


def por_sacar(db: Session, sede_id: Optional[int] = None) -> List[dict]:
    """Títulos con reservas que esperan y ejemplares libres en el estante ("holds to pull").

    Con `sede_id`, solo los ejemplares que están en esa sede. Escanear uno en la
    devolución lo aparta para el primero de la cola (o lo manda a su sede de retiro).
    """
    if expirar_vencidas(db):
        db.commit()
    I = models.Item
    activas = db.query(Rs.biblio_id, func.count(Rs.id)).filter(
        Rs.estado == PENDIENTE, Rs.suspendida == False).group_by(  # noqa: E712
        Rs.biblio_id).all()
    if not activas:
        return []
    cola_por_titulo = dict(activas)

    consulta = db.query(I).filter(I.biblio_id.in_(cola_por_titulo), I.estado == "Disponible")
    if sede_id is not None:
        consulta = consulta.filter((I.biblioteca_actual_id == sede_id)
                                   | (I.biblioteca_actual_id == None))  # noqa: E711
    items = consulta.order_by(I.biblio_id, I.signatura_topografica, I.codigo_barras).all()
    if not items:
        return []

    titulos = list(dict.fromkeys(i.biblio_id for i in items))
    biblios = {b.id: b for b in db.query(models.RegistroBibliografico).filter(
        models.RegistroBibliografico.id.in_(titulos))}
    primeras = {}
    for reserva, lector in db.query(Rs, models.Usuario).join(
            models.Usuario, models.Usuario.id == Rs.usuario_id).filter(
            Rs.biblio_id.in_(titulos), Rs.estado == PENDIENTE,
            Rs.suspendida == False, models.Usuario.activo == True).order_by(  # noqa: E712
            Rs.biblio_id, Rs.prioridad, Rs.fecha_reserva, Rs.id):
        primeras.setdefault(reserva.biblio_id, (reserva, lector))

    nombres_sedes = sedes.nombres(db)
    contexto = _contexto_atencion(db)
    resultado = []
    for biblio_id in titulos:
        if biblio_id not in primeras:
            continue
        biblio = biblios[biblio_id]
        reserva, lector = primeras[biblio_id]
        # Solo las copias que le sirven; primero las que ya están en su sede de retiro.
        del_titulo = sorted(
            (i for i in items if i.biblio_id == biblio_id
             and puede_atender(db, lector, i, contexto)),
            key=lambda i: i.biblioteca_actual_id != reserva.biblioteca_retiro_id)
        if not del_titulo:
            continue
        resultado.append({
            "biblioId": str(biblio_id),
            "title": biblio.titulo,
            "author": biblio.autor,
            "holds": cola_por_titulo[biblio_id],
            "toPull": min(cola_por_titulo[biblio_id], len(del_titulo)),
            "firstPatron": f"{lector.nombre} {lector.apellido}",
            "firstPatronId": lector.nro_carnet,
            "pickupBranch": nombres_sedes.get(reserva.biblioteca_retiro_id),
            "reservedOn": formatear_fecha(reserva.fecha_reserva),
            "items": [{
                "barcode": i.codigo_barras,
                "callNumber": i.signatura_topografica,
                "branch": nombres_sedes.get(i.biblioteca_actual_id),
            } for i in del_titulo],
        })
    return resultado


def ejecutar_expiracion(db: Session) -> dict:
    expiradas = expirar_vencidas(db)
    db.commit()
    return {"expiradas": expiradas}
