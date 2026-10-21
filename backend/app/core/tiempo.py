"""Fechas y horas de Shelfie.

Regla única: en la base y en la lógica todo es UTC con zona (`timestamptz`);
la hora local de la biblioteca (ZONA_HORARIA, por defecto America/Caracas) se
usa solo para decidir "qué día es" (vencimientos, calendario) y para mostrar.
"""

from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from typing import Optional
from zoneinfo import ZoneInfo

from app.config import settings

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


@lru_cache
def zona() -> ZoneInfo:
    return ZoneInfo(settings.ZONA_HORARIA)


def ahora() -> datetime:
    """Instante actual en UTC, con zona."""
    return datetime.now(timezone.utc)


def a_utc(valor: datetime) -> datetime:
    """Normaliza a UTC; un datetime sin zona se interpreta como UTC."""
    if valor.tzinfo is None:
        return valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(timezone.utc)


def a_local(valor: datetime) -> datetime:
    return a_utc(valor).astimezone(zona())


def hoy() -> date:
    """Fecha de hoy en la zona de la biblioteca."""
    return a_local(ahora()).date()


def fecha_local(valor: datetime) -> date:
    return a_local(valor).date()


def inicio_del_dia(fecha: date) -> datetime:
    return datetime.combine(fecha, time.min, tzinfo=zona()).astimezone(timezone.utc)


def fin_del_dia(fecha: date) -> datetime:
    """23:59:59 hora local de `fecha`, en UTC: así vencen los préstamos."""
    return datetime.combine(fecha, time(23, 59, 59), tzinfo=zona()).astimezone(timezone.utc)


def formatear_fecha(valor: Optional[datetime]) -> Optional[str]:
    """'05 oct 2026' en hora local."""
    if valor is None:
        return None
    local = a_local(valor) if isinstance(valor, datetime) else valor
    return f"{local.day:02d} {MESES[local.month - 1]} {local.year}"


def formatear_fecha_hora(valor: Optional[datetime]) -> Optional[str]:
    if valor is None:
        return None
    local = a_local(valor)
    return f"{formatear_fecha(local)}, {local:%H:%M}"


def fecha_iso(valor: Optional[datetime]) -> str:
    """'2026-10-05' en hora local, para CSV."""
    return fecha_local(valor).isoformat() if valor else ""


def sello_archivo() -> str:
    """'20261005' para nombres de archivo."""
    return hoy().strftime("%Y%m%d")


def mas_dias(fecha: date, dias: int) -> date:
    return fecha + timedelta(days=dias)
