"""Estadísticas y reportes descargables."""

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Dict, List, Tuple

from sqlalchemy.orm import Session

from app import models
from app.core.errores import ReglaIncumplida
from app.core.tiempo import ahora, fecha_iso, hoy, inicio_del_dia

INICIO_DE_LOS_TIEMPOS = datetime(1970, 1, 1, tzinfo=timezone.utc)

PERIODOS_EN_DIAS = {"week": 7, "month": 30, "quarter": 90, "year": 365}
FORMATOS = ("csv", "json")


def _inicio_de_mes(fecha: date) -> datetime:
    """Primer instante del mes en hora local, expresado en UTC."""
    return inicio_del_dia(date(fecha.year, fecha.month, 1))


def _inicio_mes_anterior(fecha: date) -> datetime:
    if fecha.month == 1:
        return inicio_del_dia(date(fecha.year - 1, 12, 1))
    return inicio_del_dia(date(fecha.year, fecha.month - 1, 1))


def estadisticas(db: Session) -> dict:
    inicio_mes = _inicio_de_mes(hoy())
    inicio_mes_pasado = _inicio_mes_anterior(hoy())

    este_mes = db.query(models.Prestamo).filter(
        models.Prestamo.fecha_prestamo >= inicio_mes).count()
    mes_pasado = db.query(models.Prestamo).filter(
        models.Prestamo.fecha_prestamo >= inicio_mes_pasado,
        models.Prestamo.fecha_prestamo < inicio_mes).count()

    if mes_pasado:
        crecimiento = f"{(este_mes - mes_pasado) / mes_pasado * 100:+.0f}%"
    elif este_mes:
        crecimiento = "+100%"
    else:
        crecimiento = "0%"

    return {
        "total_items": db.query(models.Item).count(),
        "total_users": db.query(models.Usuario).count(),
        "loans_this_month": este_mes,
        "growth_percentage": crecimiento,
    }


# --- Filas de cada reporte ---------------------------------------------------------

def _filas_de(db: Session, *filtros) -> List[dict]:
    """Filas de préstamos con ejemplar, título y lector en una sola consulta."""
    P = models.Prestamo
    filas = db.query(P, models.Item, models.RegistroBibliografico, models.Usuario).outerjoin(
        models.Item, models.Item.id == P.item_id).outerjoin(
        models.RegistroBibliografico, models.RegistroBibliografico.id == models.Item.biblio_id
    ).outerjoin(models.Usuario, models.Usuario.id == P.usuario_id).filter(*filtros).order_by(
        P.id).all()
    momento = ahora()
    return [
        {
            "prestamo_id": p.id,
            "titulo": biblio.titulo if biblio else "Desconocido",
            "codigo_barras": item.codigo_barras if item else "N/A",
            "lector": f"{u.nombre} {u.apellido}" if u else "Desconocido",
            "carnet": u.nro_carnet if u else "N/A",
            "fecha_prestamo": fecha_iso(p.fecha_prestamo),
            "fecha_vencimiento": fecha_iso(p.fecha_vencimiento),
            "fecha_devolucion": fecha_iso(p.fecha_devolucion),
            "renovaciones": p.renovaciones_realizadas or 0,
            "estado": "Devuelto" if p.fecha_devolucion else (
                "Vencido" if momento > p.fecha_vencimiento else "Activo"),
        }
        for p, item, biblio, u in filas
    ]


def _filas_prestamos(db: Session, desde: datetime, hasta: datetime) -> List[dict]:
    """Préstamos realizados en el período."""
    P = models.Prestamo
    return _filas_de(db, P.fecha_prestamo >= desde, P.fecha_prestamo <= hasta)


def _filas_devoluciones(db: Session, desde: datetime, hasta: datetime) -> List[dict]:
    """Devoluciones registradas en el período (por fecha de devolución)."""
    P = models.Prestamo
    return _filas_de(db, P.fecha_devolucion >= desde, P.fecha_devolucion <= hasta)


def _filas_vencidos(db: Session, desde: datetime, hasta: datetime) -> List[dict]:
    """Préstamos sin devolver cuyo vencimiento cayó en el período y ya pasó."""
    P = models.Prestamo
    limite = min(hasta, ahora())
    return _filas_de(db, P.fecha_devolucion == None,  # noqa: E711
                     P.fecha_vencimiento >= desde, P.fecha_vencimiento < limite)


def _filas_usuarios(db: Session, desde: datetime, hasta: datetime) -> List[dict]:
    from app.services.usuarios import listar
    return [
        {
            "carnet": d["nro_carnet"],
            "nombre": f"{d['nombre']} {d['apellido']}",
            "email": d["email"],
            "departamento": d["departamento"] or "",
            "categoria": d["categoria"].descripcion if d["categoria"] else "",
            "activo": "Sí" if d["activo"] else "No",
            "saldo_multas": f"{d['saldo_multas']:.2f}",
            "prestamos_activos": d["prestamos_activos_count"],
            "prestamos_totales": d["total_prestamos_count"],
        }
        for d in listar(db)
    ]


def _filas_catalogo(db: Session, desde: datetime, hasta: datetime) -> List[dict]:
    items_por_titulo = defaultdict(list)
    for item in db.query(models.Item).order_by(models.Item.id).all():
        items_por_titulo[item.biblio_id].append(item)
    filas = []
    for b in db.query(models.RegistroBibliografico).order_by(models.RegistroBibliografico.id).all():
        items = items_por_titulo[b.id]
        disponibles = len([i for i in items if i.estado == "Disponible"])
        filas.append({
            "id": b.id,
            "titulo": b.titulo,
            "autor": b.autor or "",
            "isbn": b.isbn or "",
            "ano_publicacion": b.ano_publicacion or "",
            "materia": b.materia or "",
            "ejemplares": len(items),
            "disponibles": disponibles,
            "prestados": len(items) - disponibles,
            "signaturas": ", ".join(i.signatura_topografica or "" for i in items).strip(", "),
        })
    return filas


GeneradorDeFilas = Callable[[Session, datetime, datetime], List[dict]]

REPORTES: Dict[str, Tuple[str, str, GeneradorDeFilas]] = {
    "loans": ("Reporte de Préstamos", "Estadísticas de préstamos por período", _filas_prestamos),
    "returns": ("Reporte de Devoluciones", "Devoluciones registradas en el período",
                _filas_devoluciones),
    "overdue": ("Reporte de Vencidos", "Préstamos vencidos sin devolver", _filas_vencidos),
    "users": ("Reporte de Usuarios", "Actividad y estadísticas de usuarios", _filas_usuarios),
    "catalog": ("Reporte de Catálogo", "Inventario y estado de materiales", _filas_catalogo),
}


def rango(periodo: str) -> Tuple[datetime, datetime]:
    hasta = ahora()
    if periodo == "all":
        return INICIO_DE_LOS_TIEMPOS, hasta
    dias = PERIODOS_EN_DIAS.get(periodo)
    if dias is None:
        raise ReglaIncumplida(
            f"Período inválido. Opciones: {', '.join(PERIODOS_EN_DIAS)} o 'all'")
    return hasta - timedelta(days=dias), hasta


def disponibles(db: Session) -> List[dict]:
    """Catálogo de reportes con el número real de filas que produce cada uno."""
    desde, hasta = INICIO_DE_LOS_TIEMPOS, ahora()
    return [
        {"id": rid, "title": titulo, "description": descripcion,
         "lastGenerated": None, "rows": len(generar_filas(db, desde, hasta))}
        for rid, (titulo, descripcion, generar_filas) in REPORTES.items()
    ]


def generar(db: Session, tipo: str, periodo: str, formato: str) -> dict:
    """Valida los parámetros y devuelve título, rango y filas del reporte."""
    if tipo not in REPORTES:
        raise ReglaIncumplida(f"Tipo de reporte inválido. Opciones: {', '.join(REPORTES)}")
    desde, hasta = rango(periodo)
    if formato not in FORMATOS:
        raise ReglaIncumplida("Formato inválido. Usa 'csv' o 'json'")

    titulo, _descripcion, generar_filas = REPORTES[tipo]
    return {"titulo": titulo, "hasta": hasta, "filas": generar_filas(db, desde, hasta)}
