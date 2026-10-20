"""Inventario (Inventory de Koha): leer lo que hay en el estante y compararlo con lo esperado.

Un inventario abarca una sede, un tramo de signaturas y, si se quiere, un tipo de ítem.
**Esperados** son los ejemplares Disponibles de ese alcance. Los códigos se leen con el
escáner, pegados o desde un archivo, en una o varias sesiones; cada lectura queda con su
resultado y marca la fecha de último inventario del ejemplar. Lo esperado que no se leyó
son los **faltantes**. Al cerrar, el resumen se guarda tal como estaba.
"""

import re
from collections import Counter
from typing import Dict, Iterable, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.core.errores import NoEncontrado, ReglaIncumplida
from app.core.tiempo import ahora, fecha_local, formatear_fecha, formatear_fecha_hora, hoy
from app.services import registro, sedes

I, L = models.Inventario, models.LecturaInventario
ABIERTO, CERRADO = "Abierto", "Cerrado"
MAX_LECTURAS_POR_ENVIO = 2000

NOMBRE_RESULTADO = {
    "ok": "En su lugar",
    "fuera_de_lugar": "Fuera de lugar",
    "prestado": "Figura prestado",
    "devuelto": "Estaba prestado: se devolvió",
    "perdido": "Figura perdido",
    "retirado": "Figura dado de baja",
    "reservado": "Apartado para una reserva",
    "en_transito": "Figura en tránsito",
    "desconocido": "Código desconocido",
    "repetido": "Ya leído",
}


# --- Signaturas -----------------------------------------------------------------------

def clave_signatura(signatura: Optional[str]) -> str:
    """Para ordenar y comparar signaturas: mayúsculas, espacios simples y la parte numérica
    inicial con ceros a la izquierda (así «92 B» va antes de «630 R6», como en el estante)."""
    texto = re.sub(r"\s+", " ", (signatura or "").strip().upper())
    inicio = re.match(r"^(\d+)", texto)
    if inicio:
        texto = inicio.group(1).zfill(6) + texto[inicio.end():]
    return texto


def _en_tramo(signatura: Optional[str], desde: Optional[str], hasta: Optional[str]) -> bool:
    if not desde and not hasta:
        return True
    if not signatura:
        return False
    clave = clave_signatura(signatura)
    if desde and clave < clave_signatura(desde):
        return False
    if hasta:
        tope = clave_signatura(hasta)
        # «Hasta 699» incluye «699.5 X»: el tope vale como prefijo.
        if clave > tope and not clave.startswith(tope):
            return False
    return True


def _en_alcance(inv: models.Inventario, item: models.Item) -> bool:
    if inv.biblioteca_id and item.biblioteca_actual_id != inv.biblioteca_id:
        return False
    if inv.tipo_item_id and item.tipo_item_id != inv.tipo_item_id:
        return False
    return _en_tramo(item.signatura_topografica, inv.signatura_desde, inv.signatura_hasta)


def _candidatos(db: Session, inv: models.Inventario):
    consulta = db.query(models.Item)
    if inv.biblioteca_id:
        consulta = consulta.filter(models.Item.biblioteca_actual_id == inv.biblioteca_id)
    if inv.tipo_item_id:
        consulta = consulta.filter(models.Item.tipo_item_id == inv.tipo_item_id)
    return [i for i in consulta.all() if _en_alcance(inv, i)]


def esperados(db: Session, inv: models.Inventario) -> List[models.Item]:
    return sorted((i for i in _candidatos(db, inv) if i.estado == "Disponible"),
                  key=lambda i: (clave_signatura(i.signatura_topografica), i.codigo_barras))


# --- Crear y listar -------------------------------------------------------------------

def _obtener(db: Session, inventario_id: int, *, bloquear: bool = False) -> models.Inventario:
    inv = db.get(I, inventario_id, with_for_update=bloquear)
    if not inv:
        raise NoEncontrado("Inventario no encontrado")
    return inv


def crear(db: Session, datos: dict, actor_id: Optional[int]) -> dict:
    sede = sedes.obtener(db, datos["biblioteca_id"]) if datos.get("biblioteca_id") else None
    tipo = None
    if datos.get("tipo_item_codigo"):
        tipo = db.query(models.TipoItem).filter_by(codigo=datos["tipo_item_codigo"]).first()
        if not tipo:
            raise ReglaIncumplida(f"No existe el tipo de ítem '{datos['tipo_item_codigo']}'")
    desde = (datos.get("signatura_desde") or "").strip() or None
    hasta = (datos.get("signatura_hasta") or "").strip() or None
    if desde and hasta and clave_signatura(desde) > clave_signatura(hasta):
        raise ReglaIncumplida("La signatura «desde» va después de la «hasta»")
    nombre = (datos.get("nombre") or "").strip() or " · ".join(filter(None, [
        "Inventario", sede.nombre if sede else "todas las sedes",
        f"{desde or '…'}–{hasta or '…'}" if desde or hasta else None,
        formatear_fecha(ahora())]))
    inv = I(nombre=nombre[:120], biblioteca_id=sede.id if sede else None,
            tipo_item_id=tipo.id if tipo else None, signatura_desde=desde, signatura_hasta=hasta,
            devolver_prestados=bool(datos.get("devolver_prestados")), estado=ABIERTO,
            creado_por_id=actor_id, fecha_inicio=ahora())
    db.add(inv)
    db.flush()
    registro.anotar(db, "catalogo", "inventario", f"Abrió el inventario «{inv.nombre}»",
                    objeto=("inventario", inv.id))
    db.commit()
    return obtener(db, inv.id)


def _vista_corta(db: Session, inv: models.Inventario, nombres_sedes: dict, conteo_lecturas: int) -> dict:
    tipo = db.get(models.TipoItem, inv.tipo_item_id) if inv.tipo_item_id else None
    creador = db.get(models.Usuario, inv.creado_por_id) if inv.creado_por_id else None
    return {
        "id": inv.id,
        "nombre": inv.nombre,
        "estado": inv.estado,
        "biblioteca_id": inv.biblioteca_id,
        "sede": nombres_sedes.get(inv.biblioteca_id) if inv.biblioteca_id else None,
        "tipo_item": tipo.descripcion if tipo else None,
        "signatura_desde": inv.signatura_desde,
        "signatura_hasta": inv.signatura_hasta,
        "devolver_prestados": inv.devolver_prestados,
        "creado_por": f"{creador.nombre} {creador.apellido}" if creador else None,
        "fecha_inicio": formatear_fecha_hora(inv.fecha_inicio),
        "fecha_cierre": formatear_fecha_hora(inv.fecha_cierre),
        "lecturas": conteo_lecturas,
    }


def listar(db: Session) -> List[dict]:
    nombres = sedes.nombres(db)
    conteos = dict(db.query(L.inventario_id, func.count(L.id)).group_by(L.inventario_id).all())
    return [_vista_corta(db, inv, nombres, conteos.get(inv.id, 0))
            for inv in db.query(I).order_by(I.fecha_inicio.desc(), I.id.desc()).all()]


# --- Leer -----------------------------------------------------------------------------

def _detalle_prestado(prestamo, lector) -> str:
    """A quién figura prestado y hasta cuándo; si ya venció, cuántos días de atraso lleva."""
    if not (prestamo and lector):
        return "Figura prestado: pásalo por Devoluciones"
    fecha = formatear_fecha(prestamo.fecha_vencimiento)
    atraso = (hoy() - fecha_local(prestamo.fecha_vencimiento)).days
    plazo = (f"venció el {fecha} ({atraso} día{'' if atraso == 1 else 's'} de atraso)"
             if atraso > 0 else f"vence el {fecha}")
    return f"Prestado a {lector.nombre} {lector.apellido}, {plazo}: pásalo por Devoluciones"


def _clasificar(db: Session, inv: models.Inventario, item: models.Item, nombres: dict,
                actor_id: Optional[int], sede_trabajo: Optional[int]) -> tuple:
    if item.estado == "Prestado":
        prestamo = db.query(models.Prestamo).filter(
            models.Prestamo.item_id == item.id,
            models.Prestamo.fecha_devolucion.is_(None)).first()
        lector = db.get(models.Usuario, prestamo.usuario_id) if prestamo else None
        if inv.devolver_prestados:
            from app.core.errores import ErrorDeNegocio
            from app.services import circulacion
            # Punto de guardado: si la devolución falla, no se pierden las lecturas anteriores.
            punto = db.begin_nested()
            try:
                resultado = circulacion.devolver(db, item.codigo_barras, actor_id,
                                                 inv.biblioteca_id or sede_trabajo)
                return "devuelto", resultado.get("mensaje")
            except ErrorDeNegocio as error:
                punto.rollback()
                return "prestado", f"No se pudo devolver solo: {error.mensaje}"
        return "prestado", _detalle_prestado(prestamo, lector)
    if item.estado == "Perdido":
        return "perdido", "Figura perdido: pásalo por Devoluciones para recuperarlo"
    if item.estado == "Retirado":
        return "retirado", "Figura dado de baja (Retirado)"
    if item.estado == "Reservado":
        return "reservado", "Está apartado para una reserva: va en el estante de reservas"
    if item.estado == "EnTransito":
        return "en_transito", "Figura viajando entre sedes: regístralo en Devoluciones"
    if _en_alcance(inv, item):
        return "ok", None
    motivos = []
    if inv.biblioteca_id and item.biblioteca_actual_id != inv.biblioteca_id:
        motivos.append(f"figura en {nombres.get(item.biblioteca_actual_id, 'otra sede')}")
    if inv.tipo_item_id and item.tipo_item_id != inv.tipo_item_id:
        motivos.append("es de otro tipo de ítem")
    if not _en_tramo(item.signatura_topografica, inv.signatura_desde, inv.signatura_hasta):
        motivos.append(f"su signatura ({item.signatura_topografica or 'sin signatura'}) "
                       "está fuera del tramo")
    texto = "; ".join(motivos)
    return "fuera_de_lugar", (texto[:1].upper() + texto[1:]) if texto else "Fuera del alcance"


def leer(db: Session, inventario_id: int, codigos: Iterable[str], actor_id: Optional[int],
         sede_trabajo: Optional[int] = None) -> dict:
    """Registra los códigos leídos y devuelve qué es cada uno, en el orden en que llegaron."""
    inv = _obtener(db, inventario_id, bloquear=True)
    if inv.estado != ABIERTO:
        raise ReglaIncumplida("El inventario está cerrado")
    lista = [c.strip() for c in codigos if c and c.strip()]
    if not lista:
        raise ReglaIncumplida("No llegó ningún código")
    if len(lista) > MAX_LECTURAS_POR_ENVIO:
        raise ReglaIncumplida(f"Se leen hasta {MAX_LECTURAS_POR_ENVIO} códigos por vez")

    # Lectura vigente de cada código (la última que no fue repetida): al releerlo se recuerda
    # qué salió, salvo que el ejemplar haya cambiado desde entonces y toque clasificarlo de nuevo.
    vistos = {}
    for codigo_leido, res, det in db.query(L.codigo_barras, L.resultado, L.detalle).filter(
            L.inventario_id == inv.id, L.resultado != "repetido").order_by(L.id):
        vistos[codigo_leido.upper()] = (res, det)
    por_codigo = {i.codigo_barras.upper(): i for i in db.query(models.Item).filter(
        func.upper(models.Item.codigo_barras).in_({c.upper() for c in lista}))}
    nombres = sedes.nombres(db)
    momento = ahora()
    resultados = []
    for codigo in lista:
        item = por_codigo.get(codigo.upper())
        anterior = vistos.get(codigo.upper())
        if anterior and not _cambio_desde(anterior[0], item):
            resultado, detalle = "repetido", _detalle_repetido(*anterior)
        elif item is None:
            resultado, detalle = "desconocido", "No hay ningún ejemplar con este código"
        else:
            resultado, detalle = _clasificar(db, inv, item, nombres, actor_id, sede_trabajo)
            item.fecha_ultimo_inventario = momento
        if resultado != "repetido":
            vistos[codigo.upper()] = (resultado, detalle)
            if anterior:  # Se clasificó de nuevo: se cuenta qué había salido antes.
                antes = f"Antes: {NOMBRE_RESULTADO[anterior[0]].lower()}"
                detalle = f"{antes}. {detalle}" if detalle else antes
        db.add(L(inventario_id=inv.id, codigo_barras=(item.codigo_barras if item else codigo)[:50],
                 item_id=item.id if item else None, resultado=resultado, detalle=detalle,
                 usuario_id=actor_id, fecha=momento))
        resultados.append(_vista_lectura(db, codigo, item, resultado, detalle))
    db.commit()
    return {"lecturas": resultados, "conteos": dict(Counter(r["resultado"] for r in resultados))}


# Estado en que estaba el ejemplar cuando se leyó con cada resultado pendiente.
ESTADO_DEL_RESULTADO = {"prestado": "Prestado", "perdido": "Perdido", "retirado": "Retirado",
                        "reservado": "Reservado", "en_transito": "EnTransito"}


def _cambio_desde(resultado_anterior: str, item: Optional[models.Item]) -> bool:
    """¿Hay que volver a clasificarlo? Sí si lo pendiente se resolvió: se devolvió el prestado,
    se recuperó el perdido, llegó el que viajaba o se dio de alta el código desconocido."""
    if resultado_anterior == "desconocido":
        return item is not None
    estado = ESTADO_DEL_RESULTADO.get(resultado_anterior)
    return estado is not None and item is not None and item.estado != estado


def _detalle_repetido(resultado_anterior: str, detalle_anterior: Optional[str]) -> str:
    """Lo que salió antes, para no perder el aviso al releerlo."""
    texto = f"Antes: {NOMBRE_RESULTADO[resultado_anterior].lower()}"
    return f"{texto}. {detalle_anterior}" if detalle_anterior else texto


def _vista_lectura(db: Session, codigo: str, item: Optional[models.Item], resultado: str,
                   detalle: Optional[str]) -> dict:
    biblio = db.get(models.RegistroBibliografico, item.biblio_id) if item and item.biblio_id else None
    return {"codigo_barras": item.codigo_barras if item else codigo, "resultado": resultado,
            "resultado_nombre": NOMBRE_RESULTADO[resultado], "detalle": detalle,
            "titulo": biblio.titulo if biblio else None, "biblio_id": biblio.id if biblio else None,
            "signatura": item.signatura_topografica if item else None}


# --- Resultado --------------------------------------------------------------------------

def _vigentes(lecturas) -> set:
    """Ids de las lecturas que cuentan: las repetidas y, por código, la última que no lo fue
    (si un prestado se devolvió y se releyó, ya no figura como prestado)."""
    ultima = {}
    for l in lecturas:
        if l.resultado != "repetido":
            ultima[l.codigo_barras.upper()] = l.id
    return {l.id for l in lecturas if l.resultado == "repetido"} | set(ultima.values())


def _resumen_vivo(db: Session, inv: models.Inventario) -> dict:
    lecturas = db.query(L).filter(L.inventario_id == inv.id).order_by(L.id).all()
    vigentes = _vigentes(lecturas)
    leidos = {l.item_id for l in lecturas if l.item_id and l.resultado != "repetido"}
    lista_esperados = esperados(db, inv)
    titulos = {b.id: b.titulo for b in db.query(models.RegistroBibliografico).filter(
        models.RegistroBibliografico.id.in_({i.biblio_id for i in lista_esperados}))} \
        if lista_esperados else {}
    faltantes = [{"codigo_barras": i.codigo_barras, "titulo": titulos.get(i.biblio_id),
                  "biblio_id": i.biblio_id, "signatura": i.signatura_topografica,
                  "ultimo_inventario": formatear_fecha(i.fecha_ultimo_inventario)}
                 for i in lista_esperados if i.id not in leidos]
    conteos = Counter(l.resultado for l in lecturas if l.id in vigentes)
    esperados_leidos = sum(1 for i in lista_esperados if i.id in leidos)
    return {
        "esperados": len(lista_esperados),
        "esperados_leidos": esperados_leidos,
        "faltantes_total": len(faltantes),
        "avance": round(100 * esperados_leidos / len(lista_esperados)) if lista_esperados else 100,
        "conteos": {k: conteos.get(k, 0) for k in NOMBRE_RESULTADO},
        "faltantes": faltantes,
    }


def obtener(db: Session, inventario_id: int, resultado: Optional[str] = None,
            limite: int = 300) -> dict:
    """El inventario con su resumen, los faltantes y las últimas lecturas (o las de un resultado)."""
    inv = _obtener(db, inventario_id)
    resumen = inv.resumen if inv.estado == CERRADO and inv.resumen else _resumen_vivo(db, inv)
    vigentes = _vigentes(db.query(L.id, L.codigo_barras, L.resultado).filter(
        L.inventario_id == inv.id).order_by(L.id).all())
    consulta = db.query(L).filter(L.inventario_id == inv.id)
    if resultado:
        if resultado not in NOMBRE_RESULTADO:
            raise ReglaIncumplida(f"Resultado desconocido: {resultado}")
        consulta = consulta.filter(L.resultado == resultado, L.id.in_(vigentes or {0}))
    lecturas = consulta.order_by(L.id.desc()).limit(limite).all()
    items = {i.id: i for i in db.query(models.Item).filter(
        models.Item.id.in_({l.item_id for l in lecturas if l.item_id}))} if lecturas else {}
    conteo = db.query(func.count(L.id)).filter(L.inventario_id == inv.id).scalar()
    return {
        **_vista_corta(db, inv, sedes.nombres(db), conteo),
        **resumen,
        "nombres_resultado": NOMBRE_RESULTADO,
        "ultimas_lecturas": [
            {**_vista_lectura(db, l.codigo_barras, items.get(l.item_id), l.resultado, l.detalle),
             "fecha": formatear_fecha_hora(l.fecha), "vigente": l.id in vigentes}
            for l in lecturas],
    }


def cerrar(db: Session, inventario_id: int) -> dict:
    inv = _obtener(db, inventario_id, bloquear=True)
    if inv.estado == CERRADO:
        raise ReglaIncumplida("El inventario ya está cerrado")
    resumen = _resumen_vivo(db, inv)
    inv.resumen = {**resumen, "faltantes": resumen["faltantes"][:5000]}
    inv.estado = CERRADO
    inv.fecha_cierre = ahora()
    registro.anotar(
        db, "catalogo", "inventario",
        f"Cerró el inventario «{inv.nombre}»: {resumen['esperados_leidos']} de "
        f"{resumen['esperados']} esperados leídos, {resumen['faltantes_total']} faltantes",
        objeto=("inventario", inv.id), datos={"conteos": resumen["conteos"]})
    db.commit()
    return obtener(db, inv.id)


COLUMNAS_FALTANTES = ["codigo_barras", "signatura", "titulo", "ultimo_inventario"]


def faltantes(db: Session, inventario_id: int) -> List[Dict]:
    return obtener(db, inventario_id, limite=0)["faltantes"]
