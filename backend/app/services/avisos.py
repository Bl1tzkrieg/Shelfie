"""Avisos al lector (y a proveedores): plantillas, cola y envío.

Como en Koha, un aviso pasa por dos momentos:

1. **Se encola** cuando ocurre el hecho (una reserva queda lista) o cuando lo
   detecta una tarea programada (préstamos por vencer o vencidos). En ese momento
   se arma el texto con la plantilla, así la cola guarda exactamente lo que se
   mandó. `clave` evita encolar dos veces el mismo aviso.
2. **Se envía** desde la cola (tarea `enviar_cola`, cada pocos minutos). Si el
   transporte falla, se reintenta hasta MAX_INTENTOS y queda como Fallido.

Las plantillas se editan en Configuración → Avisos; los marcadores son `{nombre}`
y se validan al guardar (un marcador desconocido es un error, no un hueco).
"""

import re
from typing import Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app import models
from app.config import settings
from app.core.errores import NoEncontrado, ReglaIncumplida
from app.core.tiempo import ahora, formatear_fecha_hora
from app.services import configuracion, correo

A = models.Aviso
PENDIENTE, ENVIADO, FALLIDO = "Pendiente", "Enviado", "Fallido"
MAX_INTENTOS = 3
CLAVE_CONFIG = "avisos"

_LECTOR = ("nombre", "apellido", "carnet", "biblioteca", "contacto_biblioteca", "enlace_opac")

# Cada plantilla: para qué sirve, quién la recibe y qué marcadores admite.
TIPOS: Dict[str, dict] = {
    "PREAVISO": {
        "nombre": "Préstamo por vencer",
        "cuando": "Unos días antes del vencimiento (Configuración → Notificaciones).",
        "marcadores": _LECTOR + ("dias", "prestamos"),
        "asunto": "Tus préstamos vencen en {dias} días",
        "cuerpo": (
            "Hola, {nombre}:\n\n"
            "Te recordamos que estos préstamos vencen pronto:\n\n{prestamos}\n\n"
            "Puedes renovarlos desde tu cuenta: {enlace_opac}\n\n{biblioteca}\n{contacto_biblioteca}"),
    },
    "VENCIDO": {
        "nombre": "Préstamo vencido",
        "cuando": "Los días de atraso indicados en Configuración → Notificaciones.",
        "marcadores": _LECTOR + ("prestamos",),
        "asunto": "Tienes préstamos vencidos",
        "cuerpo": (
            "Hola, {nombre}:\n\n"
            "Estos préstamos ya vencieron y cada día de atraso suma multa:\n\n{prestamos}\n\n"
            "Devuélvelos o renuévalos lo antes posible: {enlace_opac}\n\n"
            "{biblioteca}\n{contacto_biblioteca}"),
    },
    "RESERVA_LISTA": {
        "nombre": "Reserva lista para retirar",
        "cuando": "Al apartar un ejemplar para el lector.",
        "marcadores": _LECTOR + ("titulo", "autor", "sede", "retirar_hasta"),
        "asunto": "Tu reserva está lista: {titulo}",
        "cuerpo": (
            "Hola, {nombre}:\n\n"
            "Apartamos para ti «{titulo}» ({autor}).\n"
            "Retíralo en {sede} hasta el {retirar_hasta}. Después pasa al siguiente lector.\n\n"
            "{biblioteca}\n{contacto_biblioteca}"),
    },
    "RESERVA_EXPIRADA": {
        "nombre": "Reserva expirada",
        "cuando": "Cuando una reserva lista no se retiró a tiempo.",
        "marcadores": _LECTOR + ("titulo", "sede"),
        "asunto": "Tu reserva expiró: {titulo}",
        "cuerpo": (
            "Hola, {nombre}:\n\n"
            "No retiraste «{titulo}» a tiempo en {sede} y la reserva expiró.\n"
            "Si todavía lo necesitas, puedes reservarlo de nuevo: {enlace_opac}\n\n{biblioteca}"),
    },
    "RECUPERAR_CLAVE": {
        "nombre": "Recuperar contraseña",
        "cuando": "Cuando el lector pide recuperar su contraseña en el OPAC.",
        "marcadores": _LECTOR + ("enlace", "minutos"),
        "asunto": "Recupera tu contraseña",
        "cuerpo": (
            "Hola, {nombre}:\n\n"
            "Para elegir una contraseña nueva entra a este enlace (vale {minutos} minutos y "
            "se usa una sola vez):\n\n{enlace}\n\n"
            "Si no lo pediste, ignora este correo: tu contraseña no cambia.\n\n{biblioteca}"),
    },
    "RECLAMO_SERIADA": {
        "nombre": "Reclamo de números atrasados",
        "cuando": "Al reclamar fascículos atrasados al proveedor.",
        "marcadores": ("proveedor", "numeros", "biblioteca", "contacto_biblioteca"),
        "asunto": "Reclamo de números no recibidos — {biblioteca}",
        "cuerpo": (
            "Estimados {proveedor}:\n\n"
            "No hemos recibido los siguientes números de nuestras suscripciones:\n\n{numeros}\n\n"
            "Les agradecemos el envío o una fecha estimada.\n\n{biblioteca}\n{contacto_biblioteca}"),
    },
}

_MARCADOR = re.compile(r"\{(\w+)\}")


# --- Plantillas --------------------------------------------------------------------------

def _guardadas(db: Session) -> dict:
    return configuracion.leer(db, CLAVE_CONFIG).get("plantillas", {})


def plantilla(db: Session, codigo: str) -> dict:
    if codigo not in TIPOS:
        raise NoEncontrado(f"No hay plantilla {codigo}")
    tipo = TIPOS[codigo]
    propia = _guardadas(db).get(codigo, {})
    return {
        "codigo": codigo,
        "nombre": tipo["nombre"],
        "cuando": tipo["cuando"],
        "marcadores": list(tipo["marcadores"]),
        "activo": propia.get("activo", True),
        "asunto": propia.get("asunto") or tipo["asunto"],
        "cuerpo": propia.get("cuerpo") or tipo["cuerpo"],
        "modificada": bool(propia.get("asunto") or propia.get("cuerpo")),
    }


def plantillas(db: Session) -> List[dict]:
    return [plantilla(db, c) for c in TIPOS]


def _validar(codigo: str, texto: str, campo: str) -> None:
    permitidos = set(TIPOS[codigo]["marcadores"])
    desconocidos = sorted({m for m in _MARCADOR.findall(texto)} - permitidos)
    if desconocidos:
        raise ReglaIncumplida(
            f"{campo}: marcadores desconocidos {', '.join('{' + d + '}' for d in desconocidos)}. "
            f"Se pueden usar: {', '.join('{' + p + '}' for p in sorted(permitidos))}")


def guardar_plantilla(db: Session, codigo: str, datos: dict) -> dict:
    plantilla(db, codigo)  # 404 si no existe
    actual = dict(_guardadas(db).get(codigo, {}))
    for campo in ("asunto", "cuerpo"):
        if datos.get(campo) is not None:
            texto = datos[campo].strip()
            if not texto:
                raise ReglaIncumplida(f"El {campo} no puede quedar vacío")
            _validar(codigo, texto, "Asunto" if campo == "asunto" else "Cuerpo")
            actual[campo] = texto
    if datos.get("activo") is not None:
        actual["activo"] = bool(datos["activo"])
    if datos.get("restablecer"):
        actual = {"activo": actual.get("activo", True)}
    from app.services import registro
    previa = _guardadas(db).get(codigo, {})
    cambios = registro.diferencias(previa, actual)
    if cambios:
        registro.anotar(db, "configuracion", "plantilla",
                        f"{'Restableció' if datos.get('restablecer') else 'Editó'} la plantilla "
                        f"«{codigo}» ({', '.join(cambios)})", objeto=("plantilla", None),
                        datos={"codigo": codigo, "cambios": cambios})
    todas = {**_guardadas(db), codigo: actual}
    _guardar_config(db, {"plantillas": todas})
    return plantilla(db, codigo)


def _guardar_config(db: Session, valores: dict) -> None:
    fila = db.query(models.Configuracion).filter_by(clave=CLAVE_CONFIG).first()
    if fila:
        fila.valor = {**(fila.valor or {}), **valores}
        flag_modified(fila, "valor")
        fila.actualizado_en = ahora()
    else:
        db.add(models.Configuracion(clave=CLAVE_CONFIG, valor=valores, actualizado_en=ahora()))
    db.commit()


def rellenar(texto: str, datos: dict) -> str:
    """Reemplaza `{marcador}` por su valor. Lo que no tenga valor queda vacío."""
    return _MARCADOR.sub(lambda m: str(datos.get(m.group(1), "") or ""), texto)


def ejemplo(db: Session, codigo: str, asunto: Optional[str] = None,
            cuerpo: Optional[str] = None) -> dict:
    """Vista previa con datos inventados, para revisar una plantilla antes de guardarla."""
    p = plantilla(db, codigo)
    asunto, cuerpo = asunto if asunto is not None else p["asunto"], cuerpo if cuerpo is not None else p["cuerpo"]
    _validar(codigo, asunto, "Asunto")
    _validar(codigo, cuerpo, "Cuerpo")
    datos = {
        **datos_de_la_biblioteca(db), "nombre": "Ana", "apellido": "Pérez", "carnet": "20260001",
        "dias": 3, "titulo": "Cien años de soledad", "autor": "Gabriel García Márquez",
        "sede": "Biblioteca Principal", "retirar_hasta": "21 oct 2026", "minutos": 60,
        "enlace": f"{settings.URL_PUBLICA}/opac/recuperar?token=…",
        "prestamos": "- Cien años de soledad (vence el 21 oct 2026)\n"
                     "- Ciencia del suelo (vence el 21 oct 2026)",
        "proveedor": "Suscripciones Andinas",
        "numeros": "- Agronomía Tropical, Vol. 74, Núm. 3 (esperado el 15 sep 2026)",
    }
    return {"asunto": rellenar(asunto, datos), "cuerpo": rellenar(cuerpo, datos)}


# --- Datos comunes -------------------------------------------------------------------------

def datos_de_la_biblioteca(db: Session) -> dict:
    inst = configuracion.leer(db, "institucion")
    contacto = " · ".join(filter(None, [inst.get("telefono"), inst.get("email")]))
    return {"biblioteca": inst.get("nombre") or "La biblioteca", "contacto_biblioteca": contacto,
            "enlace_opac": f"{settings.URL_PUBLICA}/opac/cuenta"}


def datos_del_lector(db: Session, usuario: models.Usuario) -> dict:
    return {**datos_de_la_biblioteca(db), "nombre": usuario.nombre, "apellido": usuario.apellido,
            "carnet": usuario.nro_carnet}


# --- Cola ----------------------------------------------------------------------------------

def encolar(db: Session, codigo: str, datos: dict, *, destinatario: Optional[str],
            usuario: Optional[models.Usuario] = None, proveedor_id: Optional[int] = None,
            clave: Optional[str] = None) -> Optional[models.Aviso]:
    """Arma el aviso con su plantilla y lo deja Pendiente (sin commit).

    No encola nada si la plantilla está desactivada, si no hay a quién mandarlo o si
    `clave` ya se usó. Devuelve el aviso, o None si no se encoló.
    """
    p = plantilla(db, codigo)
    if not p["activo"] or not (destinatario or "").strip():
        return None
    if clave and db.query(A.id).filter(A.clave == clave).first():
        return None
    aviso = A(codigo=codigo, usuario_id=usuario.id if usuario else None, proveedor_id=proveedor_id,
              destinatario=destinatario.strip(), asunto=rellenar(p["asunto"], datos)[:300],
              cuerpo=rellenar(p["cuerpo"], datos), estado=PENDIENTE, clave=clave,
              fecha_creacion=ahora())
    db.add(aviso)
    db.flush()
    return aviso


def para_lector(db: Session, codigo: str, usuario: models.Usuario, datos: dict,
                clave: Optional[str] = None) -> Optional[models.Aviso]:
    return encolar(db, codigo, {**datos_del_lector(db, usuario), **datos},
                   destinatario=usuario.email, usuario=usuario, clave=clave)


def _enviar_uno(aviso: models.Aviso) -> None:
    aviso.intentos = (aviso.intentos or 0) + 1
    try:
        correo.enviar(aviso.destinatario, aviso.asunto, aviso.cuerpo)
    except correo.CorreoNoEnviado as error:
        aviso.error = str(error)[:1000]
        if aviso.intentos >= MAX_INTENTOS:
            aviso.estado = FALLIDO
        return
    aviso.estado, aviso.error, aviso.fecha_envio = ENVIADO, None, ahora()


def enviar_cola(db: Session, limite: int = 200) -> dict:
    """Envía los pendientes, el más viejo primero. Con el correo desactivado no hace nada.

    `FOR UPDATE SKIP LOCKED`: si dos procesos corren la tarea a la vez, cada aviso
    lo toma uno solo.
    """
    if correo.modo() == "desactivado":
        return {"enviados": 0, "fallidos": 0, "pendientes": db.query(A).filter(
            A.estado == PENDIENTE).count(), "nota": "El envío está desactivado"}
    lote = db.query(A).filter(A.estado == PENDIENTE).order_by(A.id).limit(limite).with_for_update(
        skip_locked=True).all()
    for aviso in lote:
        _enviar_uno(aviso)
    db.commit()
    return {"enviados": sum(1 for a in lote if a.estado == ENVIADO),
            "con_error": sum(1 for a in lote if a.estado != ENVIADO),
            "pendientes": db.query(A).filter(A.estado == PENDIENTE).count()}


def enviar_ahora(db: Session, aviso: Optional[models.Aviso]) -> None:
    """Para lo urgente (recuperar la contraseña): no espera a la próxima vuelta de la cola."""
    if aviso is not None and correo.modo() != "desactivado":
        _enviar_uno(aviso)
        db.commit()


def reintentar(db: Session, aviso_id: int) -> dict:
    aviso = db.get(A, aviso_id)
    if not aviso:
        raise NoEncontrado("Aviso no encontrado")
    if aviso.estado == ENVIADO:
        raise ReglaIncumplida("Ese aviso ya se envió")
    aviso.estado, aviso.intentos = PENDIENTE, 0
    _enviar_uno(aviso)
    db.commit()
    return vista(db, aviso)


def prueba(db: Session, destinatario: str) -> dict:
    """Manda un correo de prueba directo, sin pasar por la cola."""
    bib = datos_de_la_biblioteca(db)["biblioteca"]
    try:
        correo.enviar(destinatario, f"Prueba de correo — {bib}",
                      f"Si lees esto, {bib} ya puede enviar avisos por correo.\n\n"
                      f"Modo: {correo.modo()} · {formatear_fecha_hora(ahora())}")
    except correo.CorreoNoEnviado as error:
        raise ReglaIncumplida(f"No se pudo enviar: {error}")
    return {"mensaje": f"Correo de prueba enviado a {destinatario}", **correo.estado()}


# --- Consultas ---------------------------------------------------------------------------

def vista(db: Session, a: models.Aviso, lector: Optional[models.Usuario] = None) -> dict:
    lector = lector or (db.get(models.Usuario, a.usuario_id) if a.usuario_id else None)
    return {
        "id": a.id,
        "codigo": a.codigo,
        "tipo": TIPOS.get(a.codigo, {}).get("nombre", a.codigo),
        "destinatario": a.destinatario,
        "lector": f"{lector.nombre} {lector.apellido}" if lector else None,
        "carnet": lector.nro_carnet if lector else None,
        "asunto": a.asunto,
        "cuerpo": a.cuerpo,
        "estado": a.estado,
        "intentos": a.intentos,
        "error": a.error,
        "creado": formatear_fecha_hora(a.fecha_creacion),
        "enviado": formatear_fecha_hora(a.fecha_envio),
    }


def listar(db: Session, estado: Optional[str] = None, carnet: Optional[str] = None,
           limite: int = 200) -> List[dict]:
    consulta = db.query(A, models.Usuario).outerjoin(models.Usuario,
                                                     models.Usuario.id == A.usuario_id)
    if estado:
        consulta = consulta.filter(A.estado.in_(estado.split(",")))
    if carnet:
        consulta = consulta.filter(models.Usuario.nro_carnet == carnet)
    filas = consulta.order_by(A.id.desc()).limit(limite).all()
    return [vista(db, a, u) for a, u in filas]


def resumen(db: Session) -> dict:
    from sqlalchemy import func
    conteos = dict(db.query(A.estado, func.count()).group_by(A.estado).all())
    return {"pendientes": conteos.get(PENDIENTE, 0), "enviados": conteos.get(ENVIADO, 0),
            "fallidos": conteos.get(FALLIDO, 0), "correo": correo.estado()}
