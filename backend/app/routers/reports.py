import csv
import io
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/api/v1", tags=["Reportes"])


def _ahora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _inicio_de_mes(fecha: datetime) -> datetime:
    return datetime(fecha.year, fecha.month, 1)


def _mes_anterior(fecha: datetime) -> datetime:
    return _inicio_de_mes(datetime(fecha.year - 1, 12, 1) if fecha.month == 1
                          else datetime(fecha.year, fecha.month - 1, 1))


@router.get("/reports/stats", response_model=schemas.SystemStatsResponse)
def get_system_stats(db: Session = Depends(get_db)):
    ahora = _ahora()
    inicio_mes = _inicio_de_mes(ahora)
    inicio_mes_pasado = _mes_anterior(ahora)

    total_items = db.query(models.Item).count()
    total_users = db.query(models.Usuario).count()

    loans_this_month = db.query(models.Prestamo).filter(
        models.Prestamo.fecha_prestamo >= inicio_mes).count()

    loans_last_month = db.query(models.Prestamo).filter(
        models.Prestamo.fecha_prestamo >= inicio_mes_pasado,
        models.Prestamo.fecha_prestamo < inicio_mes).count()

    # Crecimiento real contra el mes anterior, en vez del "+12%" fijo de antes.
    if loans_last_month:
        variacion = (loans_this_month - loans_last_month) / loans_last_month * 100
        growth = f"{variacion:+.0f}%"
    elif loans_this_month:
        growth = "+100%"
    else:
        growth = "0%"

    return {
        "total_items": total_items,
        "total_users": total_users,
        "loans_this_month": loans_this_month,
        "growth_percentage": growth,
    }


# --- Construcción de los distintos reportes ---------------------------------

def _rows_prestamos(db: Session, desde: datetime, hasta: datetime) -> List[dict]:
    prestamos = db.query(models.Prestamo).filter(
        models.Prestamo.fecha_prestamo >= desde,
        models.Prestamo.fecha_prestamo <= hasta).all()
    ahora = _ahora()
    filas = []
    for p in prestamos:
        item = db.query(models.Item).filter(models.Item.id == p.item_id).first()
        biblio = db.query(models.RegistroBibliografico).filter(
            models.RegistroBibliografico.id == item.biblio_id).first() if item else None
        usuario = db.query(models.Usuario).filter(
            models.Usuario.id == p.usuario_id).first()
        filas.append({
            "prestamo_id": p.id,
            "titulo": biblio.titulo if biblio else "Desconocido",
            "codigo_barras": item.codigo_barras if item else "N/A",
            "lector": f"{usuario.nombre} {usuario.apellido}" if usuario else "Desconocido",
            "carnet": usuario.nro_carnet if usuario else "N/A",
            "fecha_prestamo": p.fecha_prestamo.strftime("%Y-%m-%d"),
            "fecha_vencimiento": p.fecha_vencimiento.strftime("%Y-%m-%d"),
            "fecha_devolucion": p.fecha_devolucion.strftime("%Y-%m-%d") if p.fecha_devolucion else "",
            "renovaciones": p.renovaciones_realizadas or 0,
            "estado": "Devuelto" if p.fecha_devolucion else (
                "Vencido" if ahora > p.fecha_vencimiento else "Activo"),
        })
    return filas


def _rows_devoluciones(db: Session, desde: datetime, hasta: datetime) -> List[dict]:
    return [f for f in _rows_prestamos(db, desde, hasta) if f["estado"] == "Devuelto"]


def _rows_vencidos(db: Session, desde: datetime, hasta: datetime) -> List[dict]:
    return [f for f in _rows_prestamos(db, desde, hasta) if f["estado"] == "Vencido"]


def _rows_usuarios(db: Session, desde: datetime, hasta: datetime) -> List[dict]:
    usuarios = db.query(models.Usuario).all()
    filas = []
    for u in usuarios:
        activos = db.query(models.Prestamo).filter(
            models.Prestamo.usuario_id == u.id,
            models.Prestamo.fecha_devolucion == None).count()
        total = db.query(models.Prestamo).filter(
            models.Prestamo.usuario_id == u.id).count()
        categoria = db.query(models.CategoriaUsuario).filter(
            models.CategoriaUsuario.id == u.categoria_id).first()
        filas.append({
            "carnet": u.nro_carnet,
            "nombre": f"{u.nombre} {u.apellido}",
            "email": u.email,
            "departamento": u.departamento or "",
            "categoria": categoria.descripcion if categoria else "",
            "activo": "Sí" if u.activo else "No",
            "saldo_multas": f"{float(u.saldo_multas or 0):.2f}",
            "prestamos_activos": activos,
            "prestamos_totales": total,
        })
    return filas


def _rows_catalogo(db: Session, desde: datetime, hasta: datetime) -> List[dict]:
    registros = db.query(models.RegistroBibliografico).all()
    filas = []
    for b in registros:
        items = db.query(models.Item).filter(models.Item.biblio_id == b.id).all()
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


REPORTES = {
    "loans": ("Reporte de Préstamos", "Estadísticas de préstamos por período", _rows_prestamos),
    "returns": ("Reporte de Devoluciones", "Devoluciones registradas en el período", _rows_devoluciones),
    "overdue": ("Reporte de Vencidos", "Préstamos vencidos sin devolver", _rows_vencidos),
    "users": ("Reporte de Usuarios", "Actividad y estadísticas de usuarios", _rows_usuarios),
    "catalog": ("Reporte de Catálogo", "Inventario y estado de materiales", _rows_catalogo),
}

PERIODOS_EN_DIAS = {
    "week": 7,
    "month": 30,
    "quarter": 90,
    "year": 365,
}


def _rango(periodo: str) -> tuple:
    hasta = _ahora()
    if periodo == "all":
        return datetime(1970, 1, 1), hasta
    dias = PERIODOS_EN_DIAS.get(periodo)
    if dias is None:
        raise HTTPException(
            status_code=400,
            detail=f"Período inválido. Opciones: {', '.join(PERIODOS_EN_DIAS)} o 'all'")
    return hasta - timedelta(days=dias), hasta


@router.get("/reports/available", response_model=List[schemas.ReporteDisponible])
def listar_reportes(db: Session = Depends(get_db)):
    """Catálogo de reportes con el número real de filas que produce cada uno."""
    desde, hasta = datetime(1970, 1, 1), _ahora()
    salida = []
    for rid, (titulo, descripcion, fn) in REPORTES.items():
        salida.append({
            "id": rid,
            "title": titulo,
            "description": descripcion,
            "lastGenerated": None,
            "rows": len(fn(db, desde, hasta)),
        })
    return salida


@router.get("/reports/generate")
def generar_reporte(
    tipo: str = Query(..., description="loans, returns, overdue, users o catalog"),
    periodo: str = Query("month", description="week, month, quarter, year o all"),
    formato: str = Query("csv", description="csv o json"),
    db: Session = Depends(get_db),
):
    """Genera un reporte. CSV se descarga como archivo; JSON se devuelve inline."""
    if tipo not in REPORTES:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de reporte inválido. Opciones: {', '.join(REPORTES)}")

    desde, hasta = _rango(periodo)
    titulo, _descripcion, fn = REPORTES[tipo]
    filas = fn(db, desde, hasta)

    if formato == "json":
        return {"tipo": tipo, "titulo": titulo, "periodo": periodo, "filas": filas}

    if formato != "csv":
        raise HTTPException(status_code=400, detail="Formato inválido. Usa 'csv' o 'json'")

    buffer = io.StringIO()
    if filas:
        writer = csv.DictWriter(buffer, fieldnames=list(filas[0].keys()))
        writer.writeheader()
        writer.writerows(filas)
    else:
        buffer.write("sin datos para el período seleccionado\n")

    contenido = "﻿" + buffer.getvalue()
    nombre = f"{tipo}-{periodo}-{hasta.strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([contenido]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )
