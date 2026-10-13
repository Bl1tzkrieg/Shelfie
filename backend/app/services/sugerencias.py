"""Sugerencias de compra (purchase suggestions de Koha).

Pendiente ──▶ Aceptada ──(se agrega a un pedido)──▶ Pedida
    └──────▶ Rechazada (con motivo)

Las registra el personal, a nombre propio o de un lector. En la Fase 6 las podrán
enviar los lectores desde el OPAC.
"""

import re
from typing import List, Optional

from sqlalchemy import func

from sqlalchemy.orm import Session

from app import models
from app.core.errores import NoEncontrado, ReglaIncumplida
from app.core.tiempo import ahora, formatear_fecha
from app.services import adquisiciones, marc
from app.services.catalogo import buscar_por_isbn

S = models.Sugerencia
PENDIENTE, ACEPTADA, RECHAZADA, PEDIDA = "Pendiente", "Aceptada", "Rechazada", "Pedida"
ESTADOS = (PENDIENTE, ACEPTADA, RECHAZADA, PEDIDA)


def _vista(s: models.Sugerencia, lector, gestor, linea, en_catalogo) -> dict:
    return {
        "id": s.id,
        "titulo": s.titulo,
        "autor": s.autor,
        "isbn": s.isbn,
        "editorial": s.editorial,
        "ano": s.ano,
        "nota": s.nota,
        "estado": s.estado,
        "motivo": s.motivo,
        "fecha": formatear_fecha(s.fecha),
        "lector": f"{lector.nombre} {lector.apellido}" if lector else None,
        "carnet": lector.nro_carnet if lector else None,
        "gestionada_por": f"{gestor.nombre} {gestor.apellido}" if gestor else None,
        "fecha_gestion": formatear_fecha(s.fecha_gestion),
        "orden_id": linea.orden_id if linea else None,
        # Si ya hay un registro con ese ISBN, probablemente no haga falta comprarlo.
        "en_catalogo_id": en_catalogo.id if en_catalogo else None,
    }


def _vista_de(db: Session, s: models.Sugerencia) -> dict:
    return _vista(s, db.get(models.Usuario, s.usuario_id) if s.usuario_id else None,
                  db.get(models.Usuario, s.gestionada_por_id) if s.gestionada_por_id else None,
                  db.get(models.LineaOrden, s.linea_id) if s.linea_id else None,
                  buscar_por_isbn(db, marc.normalizar_isbn(s.isbn)))


def _digitos(isbn: Optional[str]) -> str:
    return re.sub(r"[^0-9X]", "", (isbn or "").upper())


def listar(db: Session, estado: Optional[str] = None) -> List[dict]:
    consulta = db.query(S)
    if estado:
        consulta = consulta.filter(S.estado.in_(estado.split(",")))
    filas = consulta.order_by(S.fecha.desc(), S.id.desc()).all()
    usuario_ids = {s.usuario_id for s in filas} | {s.gestionada_por_id for s in filas}
    usuarios = {u.id: u for u in db.query(models.Usuario).filter(
        models.Usuario.id.in_([i for i in usuario_ids if i]))}
    lineas = {l.id: l for l in db.query(models.LineaOrden).filter(
        models.LineaOrden.id.in_([s.linea_id for s in filas if s.linea_id]))}
    RB = models.RegistroBibliografico
    buscados = {_digitos(s.isbn) for s in filas if _digitos(s.isbn)}
    en_catalogo = {}
    if buscados:
        clave = func.upper(func.regexp_replace(RB.isbn, "[^0-9Xx]", "", "g"))
        for biblio, digitos in db.query(RB, clave).filter(clave.in_(buscados)).order_by(RB.id):
            en_catalogo.setdefault(digitos, biblio)
    return [_vista(s, usuarios.get(s.usuario_id), usuarios.get(s.gestionada_por_id),
                   lineas.get(s.linea_id), en_catalogo.get(_digitos(s.isbn))) for s in filas]


def crear(db: Session, datos: dict, personal: Optional[models.Usuario] = None) -> dict:
    titulo = (datos.get("titulo") or "").strip()
    if not titulo:
        raise ReglaIncumplida("La sugerencia necesita un título")
    usuario = personal
    if datos.get("nro_carnet"):
        usuario = db.query(models.Usuario).filter(
            models.Usuario.nro_carnet == datos["nro_carnet"].strip()).first()
        if not usuario:
            raise NoEncontrado("Lector no encontrado")
    limpio = lambda campo: (datos.get(campo) or "").strip() or None  # noqa: E731
    s = S(titulo=titulo, autor=limpio("autor"), isbn=limpio("isbn"), editorial=limpio("editorial"),
          ano=datos.get("ano"), nota=limpio("nota"), usuario_id=usuario.id if usuario else None,
          estado=PENDIENTE, fecha=ahora())
    db.add(s)
    db.commit()
    return _vista_de(db, s)


def _obtener(db: Session, sugerencia_id: int) -> models.Sugerencia:
    s = db.get(S, sugerencia_id)
    if not s:
        raise NoEncontrado("Sugerencia no encontrada")
    return s


def decidir(db: Session, sugerencia_id: int, aceptar: bool, motivo: Optional[str],
            personal_id: Optional[int]) -> dict:
    s = _obtener(db, sugerencia_id)
    if s.estado == PEDIDA:
        raise ReglaIncumplida("La sugerencia ya se pidió")
    if not aceptar and not (motivo or "").strip():
        raise ReglaIncumplida("Indica el motivo del rechazo: el lector lo verá")
    s.estado = ACEPTADA if aceptar else RECHAZADA
    s.motivo = (motivo or "").strip() or None
    s.gestionada_por_id = personal_id
    s.fecha_gestion = ahora()
    db.commit()
    return _vista_de(db, s)


def pedir(db: Session, sugerencia_id: int, datos: dict, personal_id: Optional[int]) -> dict:
    """Agrega la sugerencia como línea de un pedido abierto."""
    s = _obtener(db, sugerencia_id)
    if s.estado in (RECHAZADA, PEDIDA):
        raise ReglaIncumplida(f"La sugerencia está {s.estado.lower()}")
    respuesta = adquisiciones.agregar_linea(db, datos["orden_id"], {
        "titulo": s.titulo, "autor": s.autor, "isbn": s.isbn,
        "cantidad": datos.get("cantidad") or 1, "precio_unitario": datos.get("precio_unitario"),
        "descuento": datos.get("descuento"), "fondo_id": datos.get("fondo_id"),
        "notas": f"Sugerencia #{s.id}" + (f": {s.nota}" if s.nota else ""),
    })
    s.estado = PEDIDA
    s.linea_id = respuesta["linea_id"]
    s.gestionada_por_id = s.gestionada_por_id or personal_id
    s.fecha_gestion = s.fecha_gestion or ahora()
    db.commit()
    return _vista_de(db, s)
