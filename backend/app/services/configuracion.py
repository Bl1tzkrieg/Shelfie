"""Configuración del sistema: pares clave/valor JSONB en `configuraciones`."""

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app import models
from app.core.tiempo import ahora, formatear_fecha_hora

# Valores usados cuando la tabla `configuraciones` todavía no tiene la clave.
DEFAULTS = {
    "biblioteca": {
        "nombre": "Biblioteca",
        # Va en el 952 $a/$b de la exportación a Koha y como organización del MARC exportado.
        "codigo": "BIB",
        # 952 $y: tipo de ítem que Koha asigna a cada ejemplar.
        "tipo_item_koha": "LIB",
    },
    # Solo se guarda y se devuelve aquí; `ultimo` y `ultimo_ok` los escribe el respaldo.
    "respaldo": {
        "carpeta": None,
        "pg_dump": None,
        "ultimo": None,       # {fecha, ok, mensaje, tamano}
        "ultimo_ok": None,    # fecha del último respaldo correcto
    },
    "seguridad": {
        # Quien entra con su usuario como contraseña, o con una que le puso el administrador,
        # tiene que elegir una propia antes de seguir.
        "forzar_cambio_clave": True,
        # Intentos fallidos seguidos (por usuario) antes de tener que esperar; 0 desactiva.
        "max_intentos": 5,
        "minutos_bloqueo": 15,
    },
}

SECCIONES = ("biblioteca", "respaldo")

def leer(db: Session, clave: str) -> dict:
    fila = db.query(models.Configuracion).filter(
        models.Configuracion.clave == clave).first()
    if fila and isinstance(fila.valor, dict):
        # Los defaults rellenan claves que falten en la fila guardada.
        return {**DEFAULTS.get(clave, {}), **fila.valor}
    return dict(DEFAULTS.get(clave, {}))


def leer_todo(db: Session) -> dict:
    return {clave: leer(db, clave) for clave in SECCIONES}


NOMBRE_SECCION = {
    "biblioteca": "datos de la biblioteca", "respaldo": "respaldo",
    "seguridad": "seguridad", "registro": "registro de acciones",
}


def guardar(db: Session, secciones: dict, anotar: bool = True) -> dict:
    """Guarda solo las secciones enviadas (las `None` quedan intactas).

    Lo que cambió queda en el registro de acciones (antes → después, por campo)."""
    from app.services import registro
    momento = ahora()
    if anotar:
        for clave, valor in secciones.items():
            if valor is None:
                continue
            antes = leer(db, clave)
            cambios = registro.diferencias(antes, {**antes, **valor}, campos=valor.keys())
            if cambios:
                registro.anotar(db, "configuracion", "ajustes",
                                f"Cambió {NOMBRE_SECCION.get(clave, clave)}: {', '.join(cambios)}",
                                objeto=("configuracion", None), datos={"seccion": clave,
                                                                        "cambios": cambios})
    for clave, valor in secciones.items():
        if valor is None:
            continue
        fila = db.query(models.Configuracion).filter(
            models.Configuracion.clave == clave).first()
        if fila:
            fila.valor = {**(fila.valor or {}), **valor}
            # JSONB mutado en sitio: SQLAlchemy necesita el aviso explícito.
            flag_modified(fila, "valor")
            fila.actualizado_en = momento
        else:
            db.add(models.Configuracion(clave=clave, valor=valor, actualizado_en=momento))
    # Un solo commit: o se guardan todas las secciones o ninguna.
    db.commit()

    return leer_todo(db)


def info_sistema(db: Session) -> dict:
    ultima = db.query(models.Configuracion).order_by(
        models.Configuracion.actualizado_en.desc()).first()
    return {
        "version": "Shelfie v1.0.0",
        "ultima_actualizacion": formatear_fecha_hora(ultima.actualizado_en) if ultima else None,
        "total_registros": db.query(models.RegistroBibliografico).count(),
        "total_ejemplares": db.query(models.Item).count(),
        "total_usuarios": db.query(models.Usuario).count(),
    }
