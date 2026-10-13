"""Importar y exportar registros MARC21 (ISO 2709 y MARCXML) con pymarc.

Los ejemplares viajan en el campo 952, con los mismos subcampos que usa Koha,
para poder migrar desde o hacia Koha sin transformar nada:

    952 $a sede propietaria  $b sede actual   $h numeración (seriadas)
        $o signatura         $p código de barras              $y tipo de ítem
        $v precio de reposición                               $1 perdido (≠ 0)

Al importar, el duplicado se detecta por ISBN (solo dígitos). La política elige qué
hacer con él: omitirlo, reemplazar su MARC (conserva sus ejemplares y suma los
nuevos) o agregar un registro aparte.
"""

import io
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Set

import pymarc
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.core import marc_plantillas
from app.core.errores import ErroresDeValidacion, ReglaIncumplida
from app.core.tiempo import sello_archivo
from app.services import busqueda, configuracion, marc
from app.services.catalogo import aplicar_marc, sede_por_defecto

FORMATOS = {"marc": ("application/marc", "mrc"), "marcxml": ("application/marcxml+xml", "xml")}
DUPLICADOS = ("omitir", "reemplazar", "agregar")
MAX_EN_RESPUESTA = 200
TAG_EJEMPLAR = "952"
# Campos que identifican al registro en el sistema de origen: no se importan.
TAGS_DE_OTRO_SISTEMA = {"999", TAG_EJEMPLAR}


def _solo_digitos(isbn: Optional[str]) -> Optional[str]:
    if not isbn:
        return None
    limpio = re.sub(r"[^0-9Xx]", "", isbn).upper()
    return limpio or None


# --- Exportación -------------------------------------------------------------------

def _campo_952(item: models.Item, tipos: Dict[int, str], sedes: Dict[int, str]) -> dict:
    subs = []
    for codigo, valor in (("a", sedes.get(item.biblioteca_propia_id)),
                          ("b", sedes.get(item.biblioteca_actual_id)),
                          ("h", item.enumeracion),
                          ("o", item.signatura_topografica),
                          ("p", item.codigo_barras),
                          ("y", tipos.get(item.tipo_item_id)),
                          ("v", f"{item.precio_reposicion:.2f}"
                           if item.precio_reposicion is not None else None),
                          ("1", "1" if item.estado == "Perdido" else None)):
        if valor:
            subs.append({codigo: str(valor)})
    return {TAG_EJEMPLAR: {"ind1": " ", "ind2": " ", "subfields": subs}}


def _para_exportar(biblio: models.RegistroBibliografico, organizacion: str,
                   ejemplares: Optional[List[models.Item]], tipos, sedes) -> pymarc.Record:
    origen = biblio.marc_json or marc.desde_columnas(biblio.titulo, biblio.autor, biblio.isbn,
                                                     biblio.ano_publicacion, biblio.materia)
    campos = [c for c in origen.get("fields", [])
              if next(iter(c)) not in {"001", "003"} | TAGS_DE_OTRO_SISTEMA]
    campos = [{"001": str(biblio.id)}, {"003": organizacion}] + campos
    if ejemplares:
        campos += [_campo_952(i, tipos, sedes) for i in ejemplares]
    lider = (origen.get("leader") or marc_plantillas.obtener(biblio.plantilla).lider).ljust(24)
    lider = lider[:9] + "a" + lider[10:24]  # posición 9 = "a": texto en UTF-8
    return marc.a_pymarc({"leader": lider, "fields": campos})


def exportar(db: Session, filtros: busqueda.Filtros, formato: str,
             con_ejemplares: bool) -> tuple:
    """(contenido, tipo MIME, nombre de archivo) con los registros que cumplen la búsqueda."""
    if formato not in FORMATOS:
        raise ReglaIncumplida("Formato no soportado: usa marc o marcxml")
    registros = busqueda.todos_los_que_cumplen(db, filtros).all()
    organizacion = (configuracion.leer(db, "institucion").get("codigo") or "SHELFIE")[:16]
    items = busqueda.items_por_titulo(db, [b.id for b in registros]) if con_ejemplares else {}
    tipos = {t.id: t.codigo for t in db.query(models.TipoItem).all()}
    sedes = {b.id: b.codigo for b in db.query(models.Biblioteca).all()}

    salida = io.BytesIO()
    if formato == "marcxml":
        escritor = pymarc.XMLWriter(salida)
        for b in registros:
            escritor.write(_para_exportar(b, organizacion, items.get(b.id), tipos, sedes))
        escritor.close(close_fh=False)
    else:
        for b in registros:
            salida.write(_para_exportar(b, organizacion, items.get(b.id), tipos, sedes).as_marc())

    tipo_mime, extension = FORMATOS[formato]
    return salida.getvalue(), tipo_mime, f"catalogo-{sello_archivo()}.{extension}"


# --- Importación -------------------------------------------------------------------

@dataclass
class Resultado:
    n: int
    titulo: str = ""
    autor: Optional[str] = None
    isbn: Optional[str] = None
    plantilla: str = ""
    accion: str = "nuevo"          # nuevo | reemplazar | omitir | error
    registro_id: Optional[int] = None
    ejemplares: int = 0
    mensajes: List[str] = field(default_factory=list)


def _leer(contenido: bytes) -> tuple:
    """(formato, registros); un registro ilegible llega como None."""
    if not contenido.strip():
        raise ReglaIncumplida("El archivo está vacío")
    if contenido.lstrip()[:1] == b"<":
        try:
            return "marcxml", pymarc.parse_xml_to_array(io.BytesIO(contenido))
        except Exception as error:  # el XML puede fallar de muchas formas
            raise ReglaIncumplida(f"No es un MARCXML válido: {error}") from error
    lector = pymarc.MARCReader(io.BytesIO(contenido), to_unicode=True, force_utf8=False,
                               utf8_handling="replace", permissive=True)
    registros = list(lector)
    if registros and all(r is None for r in registros):
        raise ReglaIncumplida("No se reconoce el archivo como MARC (ISO 2709) ni MARCXML")
    return "marc", registros


def _plantilla_para(registro: dict, pedida: str) -> str:
    if pedida in marc_plantillas.PLANTILLAS:
        return pedida
    lider = registro.get("leader", "").ljust(24)
    if lider[7] == "s":
        return "SER"
    if lider[6] == "m":
        return "ERE"
    if marc.campos(registro, "502"):
        return "TES"
    return "BKS"


def _separar_ejemplares(registro: dict) -> tuple:
    ejemplares = [c[TAG_EJEMPLAR] for c in registro.get("fields", []) if TAG_EJEMPLAR in c]
    resto = [c for c in registro.get("fields", []) if next(iter(c)) not in TAGS_DE_OTRO_SISTEMA]
    return {"leader": registro.get("leader", ""), "fields": resto}, ejemplares


def _completar_008(registro: dict) -> dict:
    """Muchos registros de otros sistemas no traen 008; se genera uno básico."""
    if any("008" in c for c in registro["fields"]):
        return registro
    return {**registro,
            "fields": [{"008": marc.campo_008(marc.ano_de(registro))}] + registro["fields"]}


def _precio(texto: Optional[str]) -> Optional[Decimal]:
    if not texto:
        return None
    try:
        return Decimal(re.sub(r"[^0-9.]", "", texto.replace(",", "."))).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


class _Contexto:
    """Datos que se consultan una vez por importación."""

    def __init__(self, db: Session):
        self.tipos = {t.codigo: t for t in db.query(models.TipoItem).all()}
        self.tipo_defecto = self.tipos.get("LIB") or next(iter(self.tipos.values()), None)
        self.sedes = {b.codigo: b.id for b in db.query(models.Biblioteca).all()}
        self.sede_defecto = sede_por_defecto(db)
        self.barcodes_en_archivo: Set[str] = set()
        self.isbn_en_archivo: Dict[str, int] = {}


def _ejemplares(db: Session, ctx: _Contexto, campos_952: List[dict], resultado: Resultado,
                biblio: Optional[models.RegistroBibliografico], aplicar: bool) -> None:
    for campo in campos_952:
        barcode = (marc.subcampos(campo, "p") or [None])[0]
        if not barcode:
            resultado.mensajes.append("952 sin código de barras ($p): ejemplar omitido")
            continue
        if barcode in ctx.barcodes_en_archivo or db.query(models.Item.id).filter(
                models.Item.codigo_barras == barcode).first():
            resultado.mensajes.append(f"El código de barras {barcode} ya existe: omitido")
            continue
        codigo_tipo = (marc.subcampos(campo, "y") or [None])[0]
        tipo = ctx.tipos.get(codigo_tipo) if codigo_tipo else None
        if tipo is None:
            tipo = ctx.tipo_defecto
            if codigo_tipo:
                resultado.mensajes.append(
                    f"Tipo de ítem «{codigo_tipo}» desconocido en {barcode}: se usó "
                    f"{tipo.codigo if tipo else 'ninguno'}")
        if tipo is None:
            resultado.mensajes.append(f"No hay tipos de ítem definidos: {barcode} omitido")
            continue
        ctx.barcodes_en_archivo.add(barcode)
        resultado.ejemplares += 1
        if not aplicar:
            continue
        sede_propia = ctx.sedes.get((marc.subcampos(campo, "a") or [""])[0], ctx.sede_defecto)
        sede_actual = ctx.sedes.get((marc.subcampos(campo, "b") or [""])[0], sede_propia)
        perdido = (marc.subcampos(campo, "1") or ["0"])[0] not in ("", "0")
        db.add(models.Item(
            biblio_id=biblio.id, codigo_barras=barcode, tipo_item_id=tipo.id,
            signatura_topografica=(marc.subcampos(campo, "o") or [None])[0],
            enumeracion=(marc.subcampos(campo, "h") or [None])[0],
            estado="Perdido" if perdido else "Disponible",
            biblioteca_propia_id=sede_propia, biblioteca_actual_id=sede_actual,
            precio_reposicion=_precio((marc.subcampos(campo, "v") or
                                       marc.subcampos(campo, "g") or [None])[0]),
        ))


def _duplicado(db: Session, isbn_digitos: Optional[str]):
    if not isbn_digitos:
        return None
    return db.query(models.RegistroBibliografico).filter(
        func.upper(func.regexp_replace(models.RegistroBibliografico.isbn, "[^0-9Xx]", "", "g"))
        == isbn_digitos).order_by(models.RegistroBibliografico.id).first()


def _importar_uno(db: Session, ctx: _Contexto, crudo, n: int, aplicar: bool, duplicados: str,
                  plantilla_pedida: str) -> Resultado:
    resultado = Resultado(n=n)
    if crudo is None:
        resultado.accion = "error"
        resultado.mensajes.append("Registro ilegible en el archivo")
        return resultado

    sin_ejemplares, campos_952 = _separar_ejemplares(marc.desde_pymarc(crudo))
    codigo = _plantilla_para(sin_ejemplares, plantilla_pedida)
    plantilla = marc_plantillas.obtener(codigo)
    try:
        canonico = _completar_008(marc.normalizar(sin_ejemplares, plantilla))
    except ErroresDeValidacion as error:
        resultado.accion = "error"
        resultado.mensajes += [e["msg"] for e in error.errores]
        return resultado

    derivado = marc.derivar(canonico)
    resultado.titulo, resultado.autor, resultado.isbn, resultado.plantilla = (
        derivado["titulo"], derivado["autor"], derivado["isbn"], codigo)
    if not marc.primero(canonico, "245", "a"):
        resultado.accion = "error"
        resultado.mensajes.append("Sin título (245 $a)")
        return resultado
    # Lo demás que la plantilla pediría no impide importar (Koha tampoco lo exige).
    resultado.mensajes += [e["msg"] for e in marc.validar(canonico, plantilla)]

    digitos = _solo_digitos(derivado["isbn"])
    existente = None
    if duplicados != "agregar":
        existente = _duplicado(db, digitos)
        if existente is None and digitos in ctx.isbn_en_archivo:
            resultado.accion = "omitir"
            resultado.mensajes.append(
                f"El ISBN se repite en el registro #{ctx.isbn_en_archivo[digitos]} del archivo")
            return resultado
    if existente is not None and duplicados == "omitir":
        resultado.accion, resultado.registro_id = "omitir", existente.id
        resultado.mensajes.append(f"Ya existe como «{existente.titulo}» (registro {existente.id})")
        return resultado
    if digitos:
        ctx.isbn_en_archivo.setdefault(digitos, n)

    resultado.accion = "reemplazar" if existente is not None else "nuevo"
    biblio = existente
    if aplicar:
        punto = db.begin_nested()
        try:
            if biblio is None:
                biblio = models.RegistroBibliografico()
                db.add(biblio)
            aplicar_marc(biblio, canonico, plantilla)
            db.flush()
            _ejemplares(db, ctx, campos_952, resultado, biblio, aplicar=True)
            db.flush()
            punto.commit()
            resultado.registro_id = biblio.id
        except Exception as error:  # un registro malo no debe frenar al resto
            punto.rollback()
            resultado.accion = "error"
            resultado.ejemplares = 0
            resultado.mensajes.append(f"No se pudo guardar: {error.__class__.__name__}")
    else:
        resultado.registro_id = biblio.id if biblio else None
        _ejemplares(db, ctx, campos_952, resultado, None, aplicar=False)
    return resultado


def importar(db: Session, contenido: bytes, *, aplicar: bool, duplicados: str = "omitir",
             plantilla: str = "auto") -> dict:
    """Vista previa (aplicar=False, no escribe nada) o importación definitiva."""
    if duplicados not in DUPLICADOS:
        raise ReglaIncumplida(f"Política de duplicados no válida: {', '.join(DUPLICADOS)}")
    formato, registros = _leer(contenido)
    ctx = _Contexto(db)
    resultados = [_importar_uno(db, ctx, r, n, aplicar, duplicados, plantilla)
                  for n, r in enumerate(registros, start=1)]
    if aplicar:
        db.commit()

    def contar(accion):
        return sum(1 for r in resultados if r.accion == accion)

    return {
        "formato": formato,
        "aplicado": aplicar,
        "total": len(resultados),
        "nuevos": contar("nuevo"),
        "reemplazados": contar("reemplazar"),
        "omitidos": contar("omitir"),
        "con_errores": contar("error"),
        "ejemplares": sum(r.ejemplares for r in resultados if r.accion != "error"),
        "registros": [r.__dict__ for r in resultados[:MAX_EN_RESPUESTA]],
    }
