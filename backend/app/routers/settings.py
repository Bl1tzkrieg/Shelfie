from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/api/v1/settings", tags=["Configuración"])

# Valores usados cuando la tabla `configuraciones` todavía no tiene la clave.
DEFAULTS = {
    "institucion": {
        "nombre": "Biblioteca Central UNAGRO",
        "codigo": "BIB-UNAGRO-001",
        "direccion": "Campus Universitario, Edificio A, Piso 1",
        "telefono": "+58 212 555 0123",
        "email": "biblioteca@unagro.edu",
    },
    "politicas_prestamo": {
        "dias_estudiante": 7,
        "dias_docente": 30,
        "dias_personal": 14,
        "max_estudiante": 3,
        "max_docente": 10,
        "max_personal": 5,
        "renovaciones_permitidas": 2,
        "multa_por_dia": 1.5,
    },
    "notificaciones": {
        "recordatorio_dias_antes": 3,
        "canal": "email",
    },
}


def _leer(db: Session, clave: str) -> dict:
    fila = db.query(models.Configuracion).filter(
        models.Configuracion.clave == clave).first()
    if fila and isinstance(fila.valor, dict):
        # Los defaults rellenan claves que falten en la fila guardada.
        return {**DEFAULTS.get(clave, {}), **fila.valor}
    return dict(DEFAULTS.get(clave, {}))


@router.get("", response_model=schemas.ConfiguracionResponse)
def get_settings(db: Session = Depends(get_db)):
    return {
        "institucion": _leer(db, "institucion"),
        "politicas_prestamo": _leer(db, "politicas_prestamo"),
        "notificaciones": _leer(db, "notificaciones"),
    }


@router.put("", response_model=schemas.ConfiguracionResponse)
def update_settings(
    payload: schemas.ActualizarConfiguracionRequest,
    db: Session = Depends(get_db),
):
    """Guarda solo las secciones enviadas; las omitidas quedan intactas."""
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)
    secciones = {
        "institucion": payload.institucion,
        "politicas_prestamo": payload.politicas_prestamo,
        "notificaciones": payload.notificaciones,
    }

    for clave, valor in secciones.items():
        if valor is None:
            continue
        fila = db.query(models.Configuracion).filter(
            models.Configuracion.clave == clave).first()
        if fila:
            fila.valor = {**(fila.valor or {}), **valor}
            # JSONB mutado en sitio: SQLAlchemy necesita el aviso explícito.
            flag_modified(fila, "valor")
            fila.actualizado_en = ahora
        else:
            db.add(models.Configuracion(clave=clave, valor=valor, actualizado_en=ahora))

    db.commit()

    # Las políticas viven además en categorias_usuario, que es lo que realmente
    # consulta el checkout: se sincronizan para que no queden dos verdades.
    if payload.politicas_prestamo:
        _sincronizar_categorias(db, _leer(db, "politicas_prestamo"))

    return get_settings(db)


def _sincronizar_categorias(db: Session, politicas: dict) -> None:
    mapeo = {
        "EST": ("dias_estudiante", "max_estudiante"),
        "DOC": ("dias_docente", "max_docente"),
        "ADM": ("dias_personal", "max_personal"),
    }
    for codigo, (clave_dias, clave_max) in mapeo.items():
        categoria = db.query(models.CategoriaUsuario).filter(
            models.CategoriaUsuario.codigo == codigo).first()
        if not categoria:
            continue
        if clave_dias in politicas:
            categoria.dias_prestamo = int(politicas[clave_dias])
        if clave_max in politicas:
            categoria.max_prestamos = int(politicas[clave_max])
        if "multa_por_dia" in politicas:
            categoria.multa_por_dia = float(politicas["multa_por_dia"])
    db.commit()


@router.get("/system-info")
def system_info(db: Session = Depends(get_db)):
    """Datos técnicos reales para la tarjeta 'Sistema' de la pantalla de ajustes."""
    ultima = db.query(models.Configuracion).order_by(
        models.Configuracion.actualizado_en.desc()).first()
    return {
        "version": "Shelfie v1.0.0",
        "ultima_actualizacion": ultima.actualizado_en.strftime("%d %b %Y, %I:%M %p")
        if ultima and ultima.actualizado_en else None,
        "total_registros": db.query(models.RegistroBibliografico).count(),
        "total_ejemplares": db.query(models.Item).count(),
        "total_usuarios": db.query(models.Usuario).count(),
        "total_prestamos": db.query(models.Prestamo).count(),
    }
