"""Consultas públicas del OPAC. Nunca exponen datos personales de lectores."""

import re
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app import models
from app.core.errores import NoEncontrado
from app.core.tiempo import formatear_fecha
from app.services import busqueda, configuracion, marc, sedes

RB = models.RegistroBibliografico
ACTIVAS = ("Pendiente", "EnTransito", "EnEspera")


def vista_publica(biblio: models.RegistroBibliografico, items: list) -> dict:
    disponibles = [i for i in items if i.estado == "Disponible"]
    return {
        "id": str(biblio.id),
        "titulo": biblio.titulo,
        "autor": biblio.autor,
        "isbn": biblio.isbn,
        "ano_publicacion": biblio.ano_publicacion,
        "materia": biblio.materia,
        "ejemplares": len(items),
        "disponibles": len(disponibles),
        "estado": "Disponible" if disponibles else "Todos los ejemplares prestados",
        "ubicaciones": sorted({i.signatura_topografica for i in items
                               if i.signatura_topografica}),
    }


def _respuesta(db: Session, r: dict, **extra) -> dict:
    registros = r["registros"]
    items = busqueda.items_por_titulo(db, [b.id for b in registros])
    return {
        **extra,
        "total": r["total"],
        "pagina": r["pagina"],
        "paginas": r["paginas"],
        "resultados": [vista_publica(b, items[b.id]) for b in registros],
        "facetas": r["facetas"],
    }


def busqueda_basica(db: Session, q: str, limit: int, pagina: int = 1,
                    orden: str = "relevancia", *, materia: Optional[str] = None,
                    autor: Optional[str] = None, tipo: Optional[str] = None,
                    disponible: Optional[str] = None, decada: Optional[int] = None) -> dict:
    """Texto libre sobre título, autor, materia e ISBN, refinable con las facetas.

    `total` cuenta todo, no solo la página.
    """
    filtros = busqueda.Filtros(
        q=q, materia=materia or None, autor=autor or None, tipo=tipo or None,
        disponible={"si": True, "no": False}.get(disponible or ""),
        ano_desde=decada, ano_hasta=decada + 9 if decada is not None else None)
    r = busqueda.buscar(db, filtros, pagina=pagina, por_pagina=limit, orden=orden)
    return _respuesta(db, r, query=q)


def busqueda_avanzada(
    db: Session,
    titulo: Optional[str] = None,
    autor: Optional[str] = None,
    isbn: Optional[str] = None,
    materia: Optional[str] = None,
    ano_desde: Optional[int] = None,
    ano_hasta: Optional[int] = None,
    solo_disponibles: bool = False,
    limit: int = 50,
    pagina: int = 1,
) -> dict:
    filtros = busqueda.Filtros(
        campos={"titulo": titulo or "", "autor": autor or "", "isbn": isbn or "",
                "materia": materia or ""},
        ano_desde=ano_desde, ano_hasta=ano_hasta,
        disponible=True if solo_disponibles else None)
    r = busqueda.buscar(db, filtros, pagina=pagina, por_pagina=limit, orden="titulo")
    return _respuesta(db, r)


# --- Ficha -----------------------------------------------------------------------------

def _sin_puntuacion(texto: Optional[str]) -> Optional[str]:
    """Quita la puntuación ISBD del final ("Sudamericana," → "Sudamericana")."""
    if not texto:
        return None
    return re.sub(r"[\s/:;,=.]+$", "", texto.strip()) or None


def _todos(datos: dict, tag: str, codigo: str) -> List[str]:
    valores = []
    for campo in marc.campos(datos, tag):
        for v in marc.subcampos(campo, codigo):
            limpio = _sin_puntuacion(v)
            if limpio and limpio not in valores:
                valores.append(limpio)
    return valores


def _primero(datos: dict, *pares) -> Optional[str]:
    for tag, codigo in pares:
        valor = _sin_puntuacion(marc.primero(datos, tag, codigo))
        if valor:
            return valor
    return None


def descripcion(biblio: models.RegistroBibliografico) -> dict:
    """Lo que el OPAC muestra del registro MARC, en palabras."""
    d = biblio.marc_json or {}
    return {
        "subtitulo": _primero(d, ("245", "b")),
        "responsabilidad": _primero(d, ("245", "c")),
        "edicion": _primero(d, ("250", "a")),
        "lugar": _primero(d, ("264", "a"), ("260", "a")),
        "editorial": _primero(d, ("264", "b"), ("260", "b")),
        # La descripción física se muestra tal cual se cataloga: "471 p. ; 21 cm."
        "descripcion_fisica": " ".join(
            v.strip() for campo in marc.campos(d, "300")[:1]
            for s in (campo.get("subfields", []) if isinstance(campo, dict) else [])
            for v in s.values()) or None,
        "serie": _primero(d, ("490", "a"), ("830", "a")),
        "issn": _primero(d, ("022", "a")),
        "periodicidad": _primero(d, ("310", "a")),
        "notas": _todos(d, "500", "a"),
        "resumen": _primero(d, ("520", "a")),
        "materias": _todos(d, "650", "a") + _todos(d, "651", "a") or
                    ([biblio.materia] if biblio.materia else []),
        "otros_autores": _todos(d, "700", "a") + _todos(d, "710", "a"),
    }


def estado_publico(item: models.Item, tipo: Optional[models.TipoItem],
                   vence: Optional[str]) -> dict:
    """Lo que el público ve de un ejemplar. Nunca quién lo tiene."""
    prestable = tipo.es_prestable if tipo else True
    if item.estado == "Disponible":
        return {"estado": "Disponible" if prestable else "Solo consulta en sala",
                "disponible": True}
    if item.estado == "Prestado":
        return {"estado": f"Prestado, vence el {vence}" if vence else "Prestado",
                "disponible": False}
    if item.estado == "Reservado":
        return {"estado": "Apartado para un lector", "disponible": False}
    if item.estado == "EnTransito":
        return {"estado": "En tránsito entre sedes", "disponible": False}
    return {"estado": "No disponible", "disponible": False}


def _ejemplares(db: Session, items: list) -> List[dict]:
    if not items:
        return []
    ids = [i.id for i in items]
    vencimientos = {p.item_id: formatear_fecha(p.fecha_vencimiento) for p in db.query(
        models.Prestamo).filter(models.Prestamo.item_id.in_(ids),
                                models.Prestamo.fecha_devolucion == None)}  # noqa: E711
    tipos = {t.id: t for t in db.query(models.TipoItem)}
    nombres = sedes.nombres(db)
    filas = []
    for i in items:
        sede_id = i.biblioteca_actual_id or i.biblioteca_propia_id
        tipo = tipos.get(i.tipo_item_id)
        filas.append({
            "id": i.id,
            "sede_id": sede_id,
            "sede": nombres.get(sede_id) or "Sin sede",
            "signatura": i.signatura_topografica,
            "numeracion": i.enumeracion,
            "tipo": tipo.descripcion if tipo else None,
            "codigo_barras": i.codigo_barras,
            **estado_publico(i, tipo, vencimientos.get(i.id)),
        })
    return sorted(filas, key=lambda f: (f["sede"], f["numeracion"] or "", f["id"]))


def _por_sede(ejemplares: List[dict]) -> List[dict]:
    resumen: Dict[str, dict] = {}
    for e in ejemplares:
        r = resumen.setdefault(e["sede"], {"sede_id": e["sede_id"], "sede": e["sede"],
                                          "ejemplares": 0, "disponibles": 0})
        r["ejemplares"] += 1
        r["disponibles"] += 1 if e["disponible"] else 0
    return list(resumen.values())


def ficha(db: Session, biblio_id: int) -> dict:
    biblio = db.query(RB).filter(RB.id == biblio_id).first()
    if not biblio:
        raise NoEncontrado("Registro no encontrado")
    items = busqueda.items_por_titulo(db, [biblio.id])[biblio.id]
    ejemplares = _ejemplares(db, items)
    tipos = {t.id: t for t in db.query(models.TipoItem)}
    return {
        **vista_publica(biblio, items),
        **descripcion(biblio),
        "plantilla": biblio.plantilla,
        "ejemplares_detalle": ejemplares,
        "por_sede": _por_sede(ejemplares),
        "reservas": db.query(models.Reserva).filter(
            models.Reserva.biblio_id == biblio.id, models.Reserva.estado.in_(ACTIVAS)).count(),
        # Se puede reservar si hay al menos un ejemplar que se preste.
        "reservable": any((tipos.get(i.tipo_item_id).es_prestable
                           if tipos.get(i.tipo_item_id) else True)
                          and i.estado != "Perdido" for i in items),
    }


def puntos_de_retiro(db: Session) -> List[dict]:
    """Sedes donde un lector puede retirar sus reservas, con sus datos de contacto."""
    filas = db.query(models.Biblioteca).filter(
        models.Biblioteca.punto_retiro == True).order_by(models.Biblioteca.nombre)  # noqa: E712
    return [{k: v for k, v in sedes.vista(b).items() if k != "punto_retiro"} for b in filas]


def materias(db: Session) -> List[str]:
    filas = db.query(RB.materia).distinct().all()
    return sorted({f[0] for f in filas if f[0]})


def biblioteca(db: Session) -> dict:
    """Nombre y contacto de la institución, y sus sedes de retiro: la cabecera del OPAC."""
    inst = configuracion.leer(db, "institucion")
    return {
        "nombre": inst.get("nombre"),
        "direccion": inst.get("direccion"),
        "telefono": inst.get("telefono"),
        "email": inst.get("email"),
        "sedes": puntos_de_retiro(db),
    }
