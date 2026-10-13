"""Sedes de la biblioteca (bibliotecas en el esquema) y la sede de trabajo del personal.

La sede de trabajo es la de Koha "Set library": dónde está físicamente quien opera.
Decide adónde llega un ejemplar devuelto y qué traslados ve cada mostrador. El
frontend la envía en la cabecera `X-Shelfie-Sede`; si no llega o no existe, se usa
la sede de inscripción de la persona y, en último caso, la primera sede.
"""

import re
from typing import List, Optional

from sqlalchemy.orm import Session

from app import models
from app.core.errores import NoEncontrado, ReglaIncumplida

B = models.Biblioteca

CABECERA = "X-Shelfie-Sede"


def primera(db: Session) -> Optional[int]:
    fila = db.query(B.id).order_by(B.id).first()
    return fila[0] if fila else None


def de_trabajo(db: Session, actor: Optional[models.Usuario], cabecera: Optional[str]) -> Optional[int]:
    if cabecera and cabecera.strip().isdigit():
        sede = db.get(B, int(cabecera))
        if sede:
            return sede.id
    if actor and actor.biblioteca_id:
        return actor.biblioteca_id
    return primera(db)


def nombres(db: Session) -> dict:
    return {b.id: b.nombre for b in db.query(B).all()}


def vista(b: models.Biblioteca, uso: Optional[dict] = None) -> dict:
    datos = {
        "id": b.id,
        "codigo": b.codigo,
        "nombre": b.nombre,
        "direccion": b.direccion,
        "telefono": b.telefono,
        "email": b.email,
        "punto_retiro": bool(b.punto_retiro),
    }
    if uso is not None:
        datos.update(uso)
    return datos


def _uso(db: Session, sede_id: int) -> dict:
    I = models.Item
    return {
        "ejemplares": db.query(I).filter(I.biblioteca_propia_id == sede_id).count(),
        "lectores": db.query(models.Usuario).filter(
            models.Usuario.biblioteca_id == sede_id).count(),
    }


def listar(db: Session, con_uso: bool = False) -> List[dict]:
    return [vista(b, _uso(db, b.id) if con_uso else None)
            for b in db.query(B).order_by(B.nombre).all()]


def _normalizar_codigo(codigo: str) -> str:
    codigo = (codigo or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9_-]{1,10}", codigo):
        raise ReglaIncumplida(
            "El código de la sede lleva de 1 a 10 letras, números, guiones o guiones bajos")
    return codigo


def _aplicar(db: Session, sede: models.Biblioteca, datos: dict) -> None:
    if "codigo" in datos:
        codigo = _normalizar_codigo(datos["codigo"])
        otra = db.query(B).filter(B.codigo == codigo, B.id != (sede.id or 0)).first()
        if otra:
            raise ReglaIncumplida(f"Ya existe una sede con el código {codigo} ({otra.nombre})")
        sede.codigo = codigo
    if "nombre" in datos:
        nombre = (datos["nombre"] or "").strip()
        if not nombre:
            raise ReglaIncumplida("La sede necesita un nombre")
        sede.nombre = nombre
    for campo in ("direccion", "telefono", "email"):
        if campo in datos:
            setattr(sede, campo, (datos[campo] or "").strip() or None)
    if "punto_retiro" in datos and datos["punto_retiro"] is not None:
        if not datos["punto_retiro"] and sede.id and _unico_punto_de_retiro(db, sede.id):
            raise ReglaIncumplida("Debe quedar al menos una sede donde retirar reservas")
        sede.punto_retiro = bool(datos["punto_retiro"])


def _unico_punto_de_retiro(db: Session, sede_id: int) -> bool:
    return db.query(B).filter(B.punto_retiro == True, B.id != sede_id).count() == 0  # noqa: E712


def crear(db: Session, datos: dict) -> dict:
    sede = B(punto_retiro=True)
    _aplicar(db, sede, {"codigo": datos.get("codigo"), "nombre": datos.get("nombre"), **datos})
    db.add(sede)
    db.commit()
    db.refresh(sede)
    return vista(sede)


def obtener(db: Session, sede_id: int) -> models.Biblioteca:
    sede = db.get(B, sede_id)
    if not sede:
        raise NoEncontrado("Sede no encontrada")
    return sede


def actualizar(db: Session, sede_id: int, datos: dict) -> dict:
    sede = obtener(db, sede_id)
    _aplicar(db, sede, datos)
    db.commit()
    return vista(sede)


def eliminar(db: Session, sede_id: int) -> None:
    """Solo se borra una sede sin nada asociado: ejemplares, lectores, préstamos ni reservas."""
    sede = obtener(db, sede_id)
    I, R = models.Item, models.Reserva
    usos = [
        (db.query(I).filter((I.biblioteca_propia_id == sede_id)
                            | (I.biblioteca_actual_id == sede_id)).count(), "ejemplar(es)"),
        (db.query(models.Usuario).filter(models.Usuario.biblioteca_id == sede_id).count(),
         "lector(es) o personal"),
        (db.query(models.Prestamo).filter(models.Prestamo.biblioteca_id == sede_id).count(),
         "préstamo(s)"),
        (db.query(R).filter(R.biblioteca_retiro_id == sede_id).count(), "reserva(s)"),
        (db.query(models.Traslado).filter((models.Traslado.desde_id == sede_id)
                                          | (models.Traslado.hacia_id == sede_id)).count(),
         "traslado(s)"),
        (db.query(models.ReglaCirculacion).filter(
            models.ReglaCirculacion.biblioteca_id == sede_id).count(), "regla(s) de circulación"),
    ]
    en_uso = [f"{n} {que}" for n, que in usos if n]
    if en_uso:
        raise ReglaIncumplida(f"No se puede borrar {sede.nombre}: tiene {', '.join(en_uso)}")
    if sede.punto_retiro and _unico_punto_de_retiro(db, sede_id) and db.query(B).count() > 1:
        raise ReglaIncumplida("Debe quedar al menos una sede donde retirar reservas")
    db.delete(sede)
    db.commit()


def validar_punto_de_retiro(db: Session, sede_id: Optional[int]) -> Optional[int]:
    if sede_id is None:
        return None
    sede = obtener(db, sede_id)
    if not sede.punto_retiro:
        raise ReglaIncumplida(f"En {sede.nombre} no se retiran reservas")
    return sede.id
