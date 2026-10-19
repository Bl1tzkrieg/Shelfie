"""Calendario de la biblioteca: qué días está cerrada.

Se usa para dos cosas, como en Koha:
- un vencimiento que cae en día cerrado se corre al siguiente día hábil;
- los días cerrados no cuentan para las multas ni para el plazo de retiro de reservas.
"""

from datetime import date, timedelta
from typing import List, Set

from sqlalchemy.orm import Session

from app import models
from app.core.errores import NoEncontrado, ReglaIncumplida
from app.services import configuracion

NOMBRE_DIA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


class Calendario:
    """Instantánea del calendario para hacer muchos cálculos con una sola consulta."""

    def __init__(self, dias_cerrados: Set[int], feriados: Set[date]):
        self.dias_cerrados = dias_cerrados  # 0 = lunes … 6 = domingo
        self.feriados = feriados

    def es_habil(self, fecha: date) -> bool:
        return fecha.weekday() not in self.dias_cerrados and fecha not in self.feriados

    def siguiente_habil(self, fecha: date) -> date:
        """`fecha` si es hábil; si no, el primer día hábil posterior."""
        for _ in range(366):
            if self.es_habil(fecha):
                return fecha
            fecha += timedelta(days=1)
        raise ReglaIncumplida("El calendario no tiene días hábiles en el próximo año")

    def sumar_habiles(self, desde: date, dias: int) -> date:
        """El día hábil número `dias` contando después de `desde`."""
        fecha, contados = desde, 0
        while contados < dias:
            fecha += timedelta(days=1)
            if self.es_habil(fecha):
                contados += 1
        return fecha

    def habiles_entre(self, despues_de: date, hasta: date) -> int:
        """Días hábiles en el intervalo (despues_de, hasta]."""
        total, fecha = 0, despues_de
        while fecha < hasta:
            fecha += timedelta(days=1)
            if self.es_habil(fecha):
                total += 1
        return total


def cargar(db: Session) -> Calendario:
    ajustes = configuracion.leer(db, "calendario")
    feriados = {f for (f,) in db.query(models.Feriado.fecha).all()}
    return Calendario(set(ajustes.get("dias_cerrados", [])), feriados)


# --- Administración -----------------------------------------------------------------

def vista(db: Session) -> dict:
    ajustes = configuracion.leer(db, "calendario")
    feriados = db.query(models.Feriado).order_by(models.Feriado.fecha).all()
    return {
        "dias_cerrados": sorted(ajustes.get("dias_cerrados", [])),
        "dias_cerrados_nombres": [NOMBRE_DIA[d] for d in sorted(ajustes.get("dias_cerrados", []))],
        "feriados": [{"id": f.id, "fecha": f.fecha, "descripcion": f.descripcion}
                     for f in feriados],
    }


def fijar_dias_cerrados(db: Session, dias: List[int]) -> dict:
    if any(d not in range(7) for d in dias):
        raise ReglaIncumplida("Los días cerrados van de 0 (lunes) a 6 (domingo)")
    if len(set(dias)) == 7:
        raise ReglaIncumplida("La biblioteca no puede estar cerrada todos los días")
    configuracion.guardar(db, {"calendario": {"dias_cerrados": sorted(set(dias))}})
    return vista(db)


def agregar_feriado(db: Session, fecha: date, descripcion: str) -> dict:
    if db.query(models.Feriado).filter(models.Feriado.fecha == fecha).first():
        raise ReglaIncumplida(f"Ya hay un feriado registrado el {fecha.isoformat()}")
    db.add(models.Feriado(fecha=fecha, descripcion=descripcion))
    from app.services import registro
    registro.anotar(db, "configuracion", "calendario",
                    f"Agregó el feriado {fecha.isoformat()} ({descripcion})")
    db.commit()
    return vista(db)


def eliminar_feriado(db: Session, feriado_id: int) -> dict:
    feriado = db.get(models.Feriado, feriado_id)
    if not feriado:
        raise NoEncontrado("Feriado no encontrado")
    from app.services import registro
    registro.anotar(db, "configuracion", "calendario",
                    f"Quitó el feriado {feriado.fecha.isoformat()} ({feriado.descripcion})")
    db.delete(feriado)
    db.commit()
    return vista(db)
