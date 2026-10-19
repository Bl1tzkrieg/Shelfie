"""Configuración del sistema: pares clave/valor JSONB en `configuraciones`."""

from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app import models
from app.core.tiempo import ahora, formatear_fecha_hora

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
    "circulacion": {
        # Deuda a partir de la cual se bloquean préstamos, renovaciones y reservas.
        "umbral_bloqueo": 5.0,
        # Días hábiles que tiene un lector para retirar una reserva en espera.
        "dias_retiro_reserva": 3,
        # Cobro por pérdida cuando el ejemplar no tiene precio de reposición propio.
        "precio_reposicion": 20.0,
        # Un ejemplar devuelto en otra sede viaja de vuelta a la suya (si no lo espera
        # una reserva). Apagado, se queda donde lo devolvieron (Koha: "floating").
        "retorno_a_sede_propia": True,
        # Al declarar perdido un préstamo atrasado, se cobra la mora hasta ese día (como Koha
        # con WhenLostForgiveFine = no). En true, solo se cobra la reposición.
        "perdonar_mora_al_perder": False,
    },
    "calendario": {
        "dias_cerrados": [6],  # 0 = lunes … 6 = domingo
    },
    "seguridad": {
        # Quien entra con el carnet como contraseña, o con una que le puso el personal,
        # tiene que elegir una propia antes de seguir.
        "forzar_cambio_clave": True,
        # Intentos fallidos seguidos (por carnet) antes de tener que esperar; 0 desactiva.
        "max_intentos": 5,
        "minutos_bloqueo": 15,
    },
}

SECCIONES = ("institucion", "politicas_prestamo", "notificaciones", "circulacion", "calendario")

# La pantalla de Configuración edita las políticas por tipo de lector; desde la
# Fase 3 viven en las reglas de circulación de cada categoría (sin tipo de ítem ni
# sede). Este mapeo traduce entre ambas para que haya una sola fuente de verdad.
_CATEGORIA_POR_POLITICA = {
    "EST": ("dias_estudiante", "max_estudiante"),
    "DOC": ("dias_docente", "max_docente"),
    "ADM": ("dias_personal", "max_personal"),
}


def leer(db: Session, clave: str) -> dict:
    fila = db.query(models.Configuracion).filter(
        models.Configuracion.clave == clave).first()
    if fila and isinstance(fila.valor, dict):
        # Los defaults rellenan claves que falten en la fila guardada.
        return {**DEFAULTS.get(clave, {}), **fila.valor}
    return dict(DEFAULTS.get(clave, {}))


def leer_todo(db: Session) -> dict:
    datos = {clave: leer(db, clave) for clave in SECCIONES}
    datos["politicas_prestamo"] = {**datos["politicas_prestamo"], **_politicas_desde_reglas(db)}
    return datos


def _regla_de_categoria(db: Session, codigo: Optional[str]):
    R = models.ReglaCirculacion
    filtro_categoria = R.categoria_id.is_(None)
    if codigo is not None:
        categoria = db.query(models.CategoriaUsuario).filter_by(codigo=codigo).first()
        if not categoria:
            return None
        filtro_categoria = R.categoria_id == categoria.id
    return db.query(R).filter(filtro_categoria, R.tipo_item_id.is_(None),
                              R.biblioteca_id.is_(None)).first()


def _politicas_desde_reglas(db: Session) -> dict:
    """Lo que muestra la pantalla de políticas, leído de las reglas reales."""
    resultado = {}
    for codigo, (clave_dias, clave_max) in _CATEGORIA_POR_POLITICA.items():
        regla = _regla_de_categoria(db, codigo)
        if regla:
            resultado[clave_dias] = regla.dias_prestamo
            resultado[clave_max] = regla.max_prestamos
    general = _regla_de_categoria(db, None)
    if general:
        resultado["renovaciones_permitidas"] = general.max_renovaciones
        resultado["multa_por_dia"] = float(general.multa_por_dia)
    return resultado


NOMBRE_SECCION = {
    "institucion": "datos de la institución", "politicas_prestamo": "políticas de préstamo",
    "notificaciones": "avisos", "circulacion": "ajustes de circulación",
    "calendario": "días cerrados", "seguridad": "seguridad", "registro": "registro de acciones",
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
            if clave == "politicas_prestamo":
                antes = {**antes, **_politicas_desde_reglas(db)}
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
    if secciones.get("politicas_prestamo"):
        _aplicar_politicas_a_reglas(db, secciones["politicas_prestamo"])
    # Un solo commit: o se guarda todo (configuración y reglas) o nada.
    db.commit()

    return leer_todo(db)


def _aplicar_politicas_a_reglas(db: Session, politicas: dict) -> None:
    """Escribe las políticas editadas en Configuración en las reglas de circulación.

    Días y tope van a la regla de cada categoría; renovaciones y multa diaria van
    a la regla general y a las de categoría. Las reglas por tipo de ítem o por sede
    no se tocan: se editan una por una en "Reglas y calendario" y esas diferencias
    son justamente su razón de ser.
    """
    from app.services import reglas  # import diferido: reglas no depende de configuración

    base = reglas.regla_general(db)
    for codigo, (clave_dias, clave_max) in _CATEGORIA_POR_POLITICA.items():
        if clave_dias not in politicas and clave_max not in politicas:
            continue
        categoria = db.query(models.CategoriaUsuario).filter_by(codigo=codigo).first()
        if not categoria:
            continue
        regla = _regla_de_categoria(db, codigo)
        if regla is None:
            regla = models.ReglaCirculacion(
                categoria_id=categoria.id, prestable=True, dias_prestamo=base.dias_prestamo,
                max_prestamos=base.max_prestamos, max_renovaciones=base.max_renovaciones,
                multa_por_dia=base.multa_por_dia, multa_maxima=base.multa_maxima,
                dias_gracia=base.dias_gracia, max_reservas=base.max_reservas)
            db.add(regla)
        if clave_dias in politicas:
            regla.dias_prestamo = int(politicas[clave_dias])
        if clave_max in politicas:
            regla.max_prestamos = int(politicas[clave_max])

    if "renovaciones_permitidas" in politicas or "multa_por_dia" in politicas:
        amplias = db.query(models.ReglaCirculacion).filter(
            models.ReglaCirculacion.prestable.is_(True),
            models.ReglaCirculacion.tipo_item_id.is_(None),
            models.ReglaCirculacion.biblioteca_id.is_(None)).all()
        for regla in amplias:
            if "renovaciones_permitidas" in politicas:
                regla.max_renovaciones = int(politicas["renovaciones_permitidas"])
            if "multa_por_dia" in politicas:
                regla.multa_por_dia = float(politicas["multa_por_dia"])


def info_sistema(db: Session) -> dict:
    ultima = db.query(models.Configuracion).order_by(
        models.Configuracion.actualizado_en.desc()).first()
    return {
        "version": "Shelfie v1.0.0",
        "ultima_actualizacion": formatear_fecha_hora(ultima.actualizado_en) if ultima else None,
        "total_registros": db.query(models.RegistroBibliografico).count(),
        "total_ejemplares": db.query(models.Item).count(),
        "total_usuarios": db.query(models.Usuario).count(),
        "total_prestamos": db.query(models.Prestamo).count(),
    }
