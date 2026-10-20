"""Registro de acciones (action_logs de Koha): quién hizo qué, cuándo y sobre qué.

Los servicios llaman a `anotar` justo antes de su commit, así la anotación entra en la
misma transacción que la operación: si la operación falla, no queda registrada, y si
se guarda, su anotación también.

Quién actuó y desde qué IP lo deja la sesión en `db.info` (ver `app/security.py`); sin
sesión (una tarea programada, la consola) el actor es el sistema.
Qué módulos se registran se elige en Configuración → Registro de acciones.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, aliased

from app import models
from app.core.errores import ReglaIncumplida
from app.core.tiempo import ahora, fin_del_dia, formatear_fecha_hora, inicio_del_dia

R = models.RegistroAccion

MODULOS: Dict[str, str] = {
    "catalogo": "Libros, ejemplares y registros MARC: altas, cambios, bajas e importaciones",
    "configuracion": "Ajustes, personal y permisos",
    "sesion": "Entradas y salidas del personal, y cambios de contraseña",
    "respaldo": "Respaldos de la base y del catálogo",
}

NOMBRE_ACCION: Dict[str, str] = {
    "alta": "Alta", "edicion": "Edición", "baja": "Baja", "eliminacion": "Eliminación",
    "clave_restablecida": "Contraseña restablecida", "clave_cambiada": "Contraseña cambiada",
    "permisos": "Permisos", "importacion": "Importación", "ajustes": "Ajustes",
    "entrada": "Entrada", "entrada_fallida": "Entrada fallida", "salida": "Salida",
}

POR_DEFECTO = {"modulos": {m: True for m in MODULOS}, "dias_retencion": 730}

# Nada que parezca un secreto llega al registro, aunque venga en los datos.
_SECRETOS = ("clave", "password", "token", "secret", "contrasena", "contraseña")


def ajustes(db: Session) -> dict:
    from app.services import configuracion
    guardado = configuracion.leer(db, "registro")
    return {
        "modulos": {**POR_DEFECTO["modulos"], **(guardado.get("modulos") or {})},
        "dias_retencion": guardado.get("dias_retencion", POR_DEFECTO["dias_retencion"]),
    }


def guardar_ajustes(db: Session, datos: dict) -> dict:
    """Qué módulos se registran y cuántos días se guarda. El cambio en sí siempre queda
    registrado: apagar el registro no puede pasar sin dejar rastro."""
    from app.services import configuracion
    antes = ajustes(db)
    nuevos = {"modulos": dict(antes["modulos"]), "dias_retencion": antes["dias_retencion"]}
    for modulo, activo in (datos.get("modulos") or {}).items():
        if modulo not in MODULOS:
            raise ReglaIncumplida(f"Módulo desconocido: {modulo}")
        nuevos["modulos"][modulo] = bool(activo)
    if datos.get("dias_retencion") is not None:
        dias = int(datos["dias_retencion"])
        if dias < 0:
            raise ReglaIncumplida("Los días de retención no pueden ser negativos")
        nuevos["dias_retencion"] = dias
    cambios = diferencias(_aplanar(antes), _aplanar(nuevos))
    if cambios:
        anotar(db, "configuracion", "ajustes", "Cambió qué se guarda en el registro de acciones",
               datos={"cambios": cambios}, forzar=True)
    configuracion.guardar(db, {"registro": nuevos}, anotar=False)  # hace el commit
    return ajustes(db)


def _aplanar(a: dict) -> dict:
    plano = {f"modulos.{k}": v for k, v in a["modulos"].items()}
    plano["dias_retencion"] = a["dias_retencion"]
    return plano


# --- Anotar ---------------------------------------------------------------------------

def _sin_secretos(valor: Any) -> Any:
    if isinstance(valor, dict):
        return {k: ("***" if any(s in str(k).lower() for s in _SECRETOS) else _sin_secretos(v))
                for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_sin_secretos(v) for v in valor]
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    if hasattr(valor, "is_finite"):  # Decimal
        return float(valor)
    return valor


def _id(objeto) -> Optional[int]:
    return getattr(objeto, "id", objeto)


def anotar(db: Session, modulo: str, accion: str, descripcion: str, *,
           lector=None, biblio=None, item=None,
           objeto: Optional[Tuple[str, Optional[int]]] = None,
           datos: Optional[dict] = None, actor=None, forzar: bool = False) -> None:
    """Agrega una anotación a la sesión (sin commit: entra con el de la operación).

    `lector`, `biblio` e `item` aceptan el objeto o su id. `actor` solo hace falta cuando
    no hay sesión abierta todavía (p. ej. al entrar).
    """
    if modulo not in MODULOS:
        raise ValueError(f"Módulo de registro desconocido: {modulo}")
    if not forzar and not ajustes(db)["modulos"].get(modulo, True):
        return
    actor_id = _id(actor) if actor is not None else db.info.get("actor_id")
    db.add(R(
        fecha=ahora(), usuario_id=actor_id,
        desde_opac=bool(db.info.get("desde_opac")) if actor is None else False,
        modulo=modulo, accion=accion, descripcion=descripcion[:2000],
        lector_id=_id(lector), biblio_id=_id(biblio), item_id=_id(item),
        objeto_tipo=objeto[0] if objeto else None, objeto_id=objeto[1] if objeto else None,
        datos=_sin_secretos(datos) if datos else None,
        ip=db.info.get("ip"),
    ))


def anotar_y_guardar(db: Session, modulo: str, accion: str, descripcion: str, **extra) -> None:
    """Para anotar desde un router, después de que el servicio hizo su commit. Si la
    anotación falla, la operación ya está hecha: se avisa en el log y se sigue."""
    try:
        anotar(db, modulo, accion, descripcion, **extra)
        db.commit()
    except Exception:  # el registro nunca debe tumbar una operación que ya se guardó
        db.rollback()
        logging.getLogger("shelfie.registro").exception("No se pudo anotar: %s", descripcion)


def diferencias(antes: dict, despues: dict, campos: Optional[Iterable[str]] = None) -> dict:
    """{campo: [antes, después]} solo con lo que cambió."""
    claves = list(campos) if campos is not None else sorted(set(antes) | set(despues))
    return {k: [_sin_secretos(antes.get(k)), _sin_secretos(despues.get(k))]
            for k in claves if antes.get(k) != despues.get(k)}


def nombre(u: Optional[models.Usuario]) -> str:
    return f"{u.nombre} {u.apellido} ({u.nro_carnet})" if u else "—"


# --- Consultar ------------------------------------------------------------------------

def _filtrar(db: Session, filtros: dict):
    Actor, Lector = aliased(models.Usuario), aliased(models.Usuario)
    consulta = db.query(R, Actor, Lector, models.RegistroBibliografico, models.Item).outerjoin(
        Actor, Actor.id == R.usuario_id).outerjoin(
        Lector, Lector.id == R.lector_id).outerjoin(
        models.RegistroBibliografico, models.RegistroBibliografico.id == R.biblio_id).outerjoin(
        models.Item, models.Item.id == R.item_id)
    if filtros.get("modulo"):
        consulta = consulta.filter(R.modulo == filtros["modulo"])
    if filtros.get("accion"):
        consulta = consulta.filter(R.accion == filtros["accion"])
    if filtros.get("actor"):
        quien = filtros["actor"].strip()
        if quien.lower() == "sistema":
            consulta = consulta.filter(R.usuario_id.is_(None))
        else:
            consulta = consulta.filter(or_(func.lower(Actor.nro_carnet) == quien.lower(),
                                           func.lower(Actor.username) == quien.lower()))
    if filtros.get("lector"):
        consulta = consulta.filter(func.lower(Lector.nro_carnet) == filtros["lector"].strip().lower())
    if filtros.get("biblio_id"):
        consulta = consulta.filter(R.biblio_id == filtros["biblio_id"])
    if filtros.get("codigo"):
        consulta = consulta.filter(func.upper(models.Item.codigo_barras)
                                   == filtros["codigo"].strip().upper())
    if filtros.get("desde"):
        consulta = consulta.filter(R.fecha >= inicio_del_dia(filtros["desde"]))
    if filtros.get("hasta"):
        consulta = consulta.filter(R.fecha <= fin_del_dia(filtros["hasta"]))
    if filtros.get("q") and filtros["q"].strip():
        consulta = consulta.filter(R.descripcion.ilike(f"%{filtros['q'].strip()}%"))
    return consulta


def _fila(r: models.RegistroAccion, actor, lector, biblio, item) -> dict:
    return {
        "id": r.id,
        "fecha": formatear_fecha_hora(r.fecha),
        "fecha_iso": r.fecha.isoformat(),
        "modulo": r.modulo,
        "accion": r.accion,
        "accion_nombre": NOMBRE_ACCION.get(r.accion, r.accion),
        "descripcion": r.descripcion,
        "actor": (f"{actor.nombre} {actor.apellido}" if actor else "Sistema"),
        "actor_carnet": actor.nro_carnet if actor else None,
        "desde_opac": r.desde_opac,
        "lector": f"{lector.nombre} {lector.apellido}" if lector else None,
        "lector_carnet": lector.nro_carnet if lector else None,
        "biblio_id": r.biblio_id,
        "titulo": biblio.titulo if biblio else None,
        "codigo_barras": item.codigo_barras if item else None,
        "datos": r.datos,
        "ip": r.ip,
    }


def consultar(db: Session, filtros: dict, pagina: int = 1, por_pagina: int = 50) -> dict:
    consulta = _filtrar(db, filtros)
    total = consulta.count()
    filas = consulta.order_by(R.fecha.desc(), R.id.desc()).offset(
        (pagina - 1) * por_pagina).limit(por_pagina).all()
    return {"total": total, "pagina": pagina,
            "paginas": max(1, -(-total // por_pagina)),
            "filas": [_fila(*f) for f in filas]}


COLUMNAS_EXPORTACION = ["fecha", "modulo", "accion_nombre", "descripcion", "actor", "actor_carnet",
                        "lector", "lector_carnet", "titulo", "codigo_barras", "ip"]


def exportar(db: Session, filtros: dict, limite: int = 50000) -> List[dict]:
    filas = _filtrar(db, filtros).order_by(R.fecha.desc(), R.id.desc()).limit(limite).all()
    return [_fila(*f) for f in filas]


def depurar(db: Session) -> int:
    """Borra lo más viejo que los días de retención (0 = guardar todo). Sin commit."""
    dias = ajustes(db)["dias_retencion"]
    if not dias:
        return 0
    return db.query(R).filter(R.fecha < ahora() - timedelta(days=dias)).delete(
        synchronize_session=False)
