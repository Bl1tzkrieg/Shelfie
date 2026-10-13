"""Traslados de ejemplares entre sedes y la decisión de adónde va cada ejemplar.

`ubicar` es el único lugar que decide qué pasa con un ejemplar que queda libre en
una sede (devuelto, recuperado, liberado de una reserva o recién llegado):

1. Si alguien lo espera (primera reserva pendiente no suspendida):
   - y la sede de retiro es esta → queda en espera (estante de reservas);
   - si no → viaja a la sede de retiro (traslado por `reserva`).
2. Si no, y pertenece a otra sede y está activado el retorno → vuelve a su sede.
3. Si no → queda Disponible aquí.

Un traslado nace Enviado cuando el ejemplar está en mano (se acaba de escanear) y
Solicitado cuando no (p. ej. venció una reserva y el ejemplar sigue en el estante):
alguien de esa sede tiene que sacarlo y marcarlo como enviado.
"""

from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session

from app import models
from app.core.errores import NoEncontrado, ReglaIncumplida
from app.core.tiempo import ahora, fecha_local, formatear_fecha, formatear_fecha_hora, hoy
from app.services import configuracion, reservas, sedes

SOLICITADO, ENVIADO, RECIBIDO, CANCELADO = "Solicitado", "Enviado", "Recibido", "Cancelado"
ABIERTOS = (SOLICITADO, ENVIADO)
RESERVA, RETORNO, MANUAL = "reserva", "retorno", "manual"

T = models.Traslado


@dataclass
class Ubicacion:
    """Qué se decidió con el ejemplar: espera | transito | retorno | disponible."""
    accion: str
    reserva: Optional[models.Reserva] = None
    traslado: Optional[models.Traslado] = None


def _distintas(a: Optional[int], b: Optional[int]) -> bool:
    """Solo hay viaje si ambas sedes se conocen y no son la misma."""
    return a is not None and b is not None and a != b


def _retorno_activo(db: Session) -> bool:
    return bool(configuracion.leer(db, "circulacion").get("retorno_a_sede_propia", True))


def abierto_de(db: Session, item_id: int) -> Optional[models.Traslado]:
    return db.query(T).filter(T.item_id == item_id, T.estado.in_(ABIERTOS)).order_by(
        T.id.desc()).first()


def _abrir(db: Session, item: models.Item, desde: int, hacia: int, motivo: str, *,
           reserva_id: Optional[int] = None, personal_id: Optional[int] = None,
           en_mano: bool = True, comentario: Optional[str] = None) -> models.Traslado:
    momento = ahora()
    traslado = T(item_id=item.id, desde_id=desde, hacia_id=hacia, motivo=motivo,
                 estado=ENVIADO if en_mano else SOLICITADO, reserva_id=reserva_id,
                 comentario=comentario, fecha_solicitud=momento,
                 fecha_envio=momento if en_mano else None,
                 personal_envio_id=personal_id if en_mano else None)
    item.estado = "EnTransito"
    item.biblioteca_actual_id = desde
    db.add(traslado)
    db.flush()
    return traslado


def cambiaria(db: Session, item: models.Item, sede_id: Optional[int]) -> bool:
    """¿Ubicar este ejemplar disponible en `sede_id` cambiaría algo?"""
    sede = sede_id if sede_id is not None else item.biblioteca_actual_id
    if sede != item.biblioteca_actual_id and item.biblioteca_actual_id is not None:
        return True
    if reservas.siguiente_para(db, item):
        return True
    return _retorno_activo(db) and _distintas(sede, item.biblioteca_propia_id)


def ubicar(db: Session, item: models.Item, sede_id: Optional[int], *,
           personal_id: Optional[int] = None, en_mano: bool = True,
           con_retorno: bool = True) -> Ubicacion:
    """Decide el destino de un ejemplar libre en `sede_id` (sin commit)."""
    if sede_id is not None:
        item.biblioteca_actual_id = sede_id
    sede = item.biblioteca_actual_id

    reserva = reservas.siguiente_para(db, item)
    if reserva:
        if _distintas(sede, reserva.biblioteca_retiro_id):
            reservas.poner_en_transito(db, reserva, item)
            traslado = _abrir(db, item, sede, reserva.biblioteca_retiro_id, RESERVA,
                              reserva_id=reserva.id, personal_id=personal_id, en_mano=en_mano)
            return Ubicacion("transito", reserva, traslado)
        reservas.poner_en_espera(db, reserva, item)
        return Ubicacion("espera", reserva)

    if con_retorno and _retorno_activo(db) and _distintas(sede, item.biblioteca_propia_id):
        traslado = _abrir(db, item, sede, item.biblioteca_propia_id, RETORNO,
                          personal_id=personal_id, en_mano=en_mano)
        return Ubicacion("retorno", traslado=traslado)

    item.estado = "Disponible"
    return Ubicacion("disponible")


def _recibir(db: Session, traslado: models.Traslado, personal_id: Optional[int]) -> Ubicacion:
    item = db.get(models.Item, traslado.item_id)
    traslado.estado = RECIBIDO
    traslado.fecha_recepcion = ahora()
    traslado.personal_recepcion_id = personal_id
    if traslado.fecha_envio is None:
        traslado.fecha_envio = traslado.fecha_recepcion
    item.biblioteca_actual_id = traslado.hacia_id

    reserva = db.get(models.Reserva, traslado.reserva_id) if traslado.reserva_id else None
    if reserva and reserva.estado == reservas.EN_TRANSITO and reserva.item_id == item.id:
        reservas.poner_en_espera(db, reserva, item)
        return Ubicacion("espera", reserva, traslado)
    # Llegó sin una reserva que lo espere (se canceló en el camino, era un retorno
    # o un traslado manual): se queda aquí, salvo que otra reserva lo pida. No se
    # devuelve de inmediato a su sede: eso pasa en su próxima devolución, como en Koha.
    ubicacion = ubicar(db, item, traslado.hacia_id, personal_id=personal_id, con_retorno=False)
    ubicacion.traslado = ubicacion.traslado or traslado
    return ubicacion


def _anular(traslado: models.Traslado, comentario: Optional[str] = None) -> None:
    traslado.estado = CANCELADO
    traslado.fecha_cancelacion = ahora()
    if comentario:
        traslado.comentario = (f"{traslado.comentario} · {comentario}"
                               if traslado.comentario else comentario)


def llegada(db: Session, item: models.Item, sede_id: Optional[int],
            personal_id: Optional[int]) -> Ubicacion:
    """Se escaneó en la devolución un ejemplar en tránsito (sin commit)."""
    traslado = abierto_de(db, item.id)
    if not traslado:
        return ubicar(db, item, sede_id, personal_id=personal_id)
    if sede_id is None or sede_id == traslado.hacia_id:
        return _recibir(db, traslado, personal_id)
    if traslado.estado == SOLICITADO and sede_id == traslado.desde_id:
        # Todavía en la sede de origen: escanearlo es sacarlo para enviarlo.
        _marcar_enviado(traslado, personal_id)
        reserva = db.get(models.Reserva, traslado.reserva_id) if traslado.reserva_id else None
        return Ubicacion("transito" if traslado.motivo == RESERVA else "retorno",
                         reserva, traslado)

    # Apareció en una tercera sede: este traslado termina aquí y se decide de nuevo.
    _anular(traslado, f"Llegó a {sedes.nombres(db).get(sede_id, 'otra sede')}")
    reserva = db.get(models.Reserva, traslado.reserva_id) if traslado.reserva_id else None
    if reserva and reserva.estado == reservas.EN_TRANSITO:
        reservas.volver_a_la_cola(db, reserva)
    return ubicar(db, item, sede_id, personal_id=personal_id)


def anular_si_no_salio(db: Session, reserva_id: int, item: models.Item) -> None:
    """La reserva en tránsito se canceló. Si el ejemplar no salió, se queda y se reubica."""
    traslado = db.query(T).filter(T.reserva_id == reserva_id, T.estado.in_(ABIERTOS)).first()
    if traslado and traslado.estado == SOLICITADO:
        _anular(traslado, "Se canceló la reserva")
        ubicar(db, item, traslado.desde_id, en_mano=False)


# --- Operaciones del personal ---------------------------------------------------------

def _obtener(db: Session, traslado_id: int) -> models.Traslado:
    traslado = db.get(T, traslado_id)
    if not traslado:
        raise NoEncontrado("Traslado no encontrado")
    return traslado


def _marcar_enviado(traslado: models.Traslado, personal_id: Optional[int]) -> None:
    traslado.estado = ENVIADO
    traslado.fecha_envio = ahora()
    traslado.personal_envio_id = personal_id


def crear(db: Session, codigo_barras: str, hacia_id: int, *, comentario: Optional[str] = None,
          sede_trabajo: Optional[int] = None, personal_id: Optional[int] = None) -> dict:
    item = db.query(models.Item).filter(models.Item.codigo_barras == codigo_barras.strip()).first()
    if not item:
        raise NoEncontrado("Ejemplar no encontrado")
    destino = sedes.obtener(db, hacia_id)
    if item.estado != "Disponible":
        raise ReglaIncumplida(
            f"Solo se trasladan ejemplares disponibles en el estante (estado: {item.estado})")
    desde = item.biblioteca_actual_id or sede_trabajo
    if desde is None:
        raise ReglaIncumplida("No se sabe en qué sede está el ejemplar")
    if desde == destino.id:
        raise ReglaIncumplida(f"El ejemplar ya está en {destino.nombre}")

    traslado = _abrir(db, item, desde, destino.id, MANUAL, personal_id=personal_id,
                      comentario=(comentario or "").strip() or None)
    db.commit()
    return _vista(db, traslado)


def enviar(db: Session, traslado_id: int, personal_id: Optional[int] = None) -> dict:
    traslado = _obtener(db, traslado_id)
    if traslado.estado != SOLICITADO:
        raise ReglaIncumplida(f"El traslado no está por enviar ({traslado.estado})")
    _marcar_enviado(traslado, personal_id)
    db.commit()
    return _vista(db, traslado)


def recibir(db: Session, traslado_id: int, personal_id: Optional[int] = None) -> dict:
    traslado = _obtener(db, traslado_id)
    if traslado.estado not in ABIERTOS:
        raise ReglaIncumplida(f"El traslado ya está cerrado ({traslado.estado})")
    ubicacion = _recibir(db, traslado, personal_id)
    db.commit()
    return {**_vista(db, traslado), "resultado": describir(db, ubicacion)}


def cancelar(db: Session, traslado_id: int) -> dict:
    """El ejemplar no viaja: queda disponible en la sede de origen.

    Si iba para una reserva, esta vuelve a la cola con el primer turno (como en Koha);
    el ejemplar aparecerá en "Para sacar del estante" de esa sede.
    """
    traslado = _obtener(db, traslado_id)
    if traslado.estado not in ABIERTOS:
        raise ReglaIncumplida(f"El traslado ya está cerrado ({traslado.estado})")
    _anular(traslado)
    item = db.get(models.Item, traslado.item_id)
    item.biblioteca_actual_id = traslado.desde_id
    item.estado = "Disponible"
    reserva = db.get(models.Reserva, traslado.reserva_id) if traslado.reserva_id else None
    if reserva and reserva.estado == reservas.EN_TRANSITO and reserva.item_id == item.id:
        reservas.volver_a_la_cola(db, reserva)
    db.commit()
    return _vista(db, traslado)


# --- Vistas ---------------------------------------------------------------------------

def describir(db: Session, ubicacion: Ubicacion) -> dict:
    """Lo que el mostrador tiene que hacer con el ejemplar, para la devolución y los traslados."""
    nombres = sedes.nombres(db)
    reserva, traslado = ubicacion.reserva, ubicacion.traslado
    lector = db.get(models.Usuario, reserva.usuario_id) if reserva else None
    abierto = traslado if traslado is not None and traslado.estado in ABIERTOS else None
    return {
        "accion": ubicacion.accion,
        "reserva": {
            "lector": f"{lector.nombre} {lector.apellido}",
            "carnet": lector.nro_carnet,
            "retirar_hasta": formatear_fecha(reserva.fecha_expiracion)
            if reserva.estado == reservas.EN_ESPERA else None,
            "sede_retiro": nombres.get(reserva.biblioteca_retiro_id),
        } if reserva else None,
        "traslado": {
            "id": abierto.id,
            "hacia": nombres.get(abierto.hacia_id),
            "motivo": abierto.motivo,
            "enviado": abierto.estado == ENVIADO,
        } if abierto else None,
    }


def _consulta(db: Session):
    return db.query(T, models.Item, models.RegistroBibliografico, models.Reserva,
                    models.Usuario).join(
        models.Item, models.Item.id == T.item_id).join(
        models.RegistroBibliografico, models.RegistroBibliografico.id == models.Item.biblio_id).outerjoin(
        models.Reserva, models.Reserva.id == T.reserva_id).outerjoin(
        models.Usuario, models.Usuario.id == models.Reserva.usuario_id)


def _fila(t, item, biblio, reserva, lector, nombres: dict) -> dict:
    dias = (hoy() - fecha_local(t.fecha_envio)).days if t.estado == ENVIADO and t.fecha_envio else None
    return {
        "id": t.id,
        "barcode": item.codigo_barras,
        "title": biblio.titulo,
        "callNumber": item.signatura_topografica,
        "fromId": t.desde_id,
        "from": nombres.get(t.desde_id),
        "toId": t.hacia_id,
        "to": nombres.get(t.hacia_id),
        "reason": t.motivo,
        "status": t.estado,
        "patron": f"{lector.nombre} {lector.apellido}" if lector else None,
        "patronId": lector.nro_carnet if lector else None,
        "holdActive": bool(reserva and reserva.estado == reservas.EN_TRANSITO),
        "comment": t.comentario,
        "requestedOn": formatear_fecha_hora(t.fecha_solicitud),
        "sentOn": formatear_fecha_hora(t.fecha_envio),
        "receivedOn": formatear_fecha_hora(t.fecha_recepcion),
        "cancelledOn": formatear_fecha_hora(t.fecha_cancelacion),
        "daysInTransit": dias,
    }


def _vista(db: Session, t: models.Traslado) -> dict:
    return _fila(*_consulta(db).filter(T.id == t.id).one(), sedes.nombres(db))


VISTAS = ("por_enviar", "por_recibir", "enviados", "historial")


def _filtro(vista: str, sede_id: Optional[int]):
    por_sede = sede_id is not None
    if vista == "por_enviar":
        return [T.estado == SOLICITADO] + ([T.desde_id == sede_id] if por_sede else [])
    if vista == "por_recibir":
        return [T.estado == ENVIADO] + ([T.hacia_id == sede_id] if por_sede else [])
    if vista == "enviados":
        return [T.estado == ENVIADO] + ([T.desde_id == sede_id] if por_sede else [])
    return [T.estado.in_((RECIBIDO, CANCELADO))] + (
        [(T.desde_id == sede_id) | (T.hacia_id == sede_id)] if por_sede else [])


def listar(db: Session, vista: str, sede_id: Optional[int]) -> List[dict]:
    if vista not in VISTAS:
        raise ReglaIncumplida(f"Vista desconocida: {vista}")
    consulta = _consulta(db).filter(*_filtro(vista, sede_id))
    consulta = (consulta.order_by(T.id.desc()).limit(200) if vista == "historial"
                else consulta.order_by(T.fecha_solicitud, T.id))
    nombres = sedes.nombres(db)
    return [_fila(*fila, nombres) for fila in consulta.all()]


def resumen(db: Session, sede_id: Optional[int]) -> dict:
    return {vista: db.query(T).filter(*_filtro(vista, sede_id)).count()
            for vista in VISTAS if vista != "historial"}
