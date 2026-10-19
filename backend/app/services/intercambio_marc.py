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


MAX_CAMPO_ISO2709 = 9999       # el directorio guarda el largo de cada campo en 4 dígitos
MAX_REGISTRO_ISO2709 = 99999   # y el líder, el del registro en 5


def _iso2709(registro: pymarc.Record, biblio: models.RegistroBibliografico) -> bytes:
    """El registro en ISO 2709, o un error claro si no cabe en el formato.

    pymarc no lo comprueba: un 520 de más de 9999 bytes deja un directorio corrupto
    y el archivo no se puede leer en otro sistema. MARCXML no tiene ese límite.
    """
    for campo in registro.fields:
        largo = len(campo.as_marc("utf-8"))
        if largo > MAX_CAMPO_ISO2709:
            raise ReglaIncumplida(
                f"«{biblio.titulo}» (registro {biblio.id}) tiene el campo {campo.tag} de "
                f"{largo} bytes y el formato ISO 2709 admite hasta {MAX_CAMPO_ISO2709}: "
                "exporta en MARCXML")
    datos = registro.as_marc()
    if len(datos) > MAX_REGISTRO_ISO2709:
        raise ReglaIncumplida(
            f"«{biblio.titulo}» (registro {biblio.id}) ocupa {len(datos)} bytes y el formato "
            f"ISO 2709 admite hasta {MAX_REGISTRO_ISO2709}: exporta en MARCXML")
    return datos


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
            salida.write(_iso2709(_para_exportar(b, organizacion, items.get(b.id), tipos, sedes),
                                  b))

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


CODIFICACIONES = ("auto", "utf8", "marc8", "latin1")


def _opciones_de_codificacion(contenido: bytes, codificacion: str) -> dict:
    """Cómo decodificar un ISO 2709. Si el líder (posición 09) dice «a», siempre es UTF-8.

    Muchos sistemas exportan UTF-8 sin marcarlo en el líder; leído como MARC-8 sale
    «A©ło» en vez de «Año». En «auto», si los bytes son UTF-8 válido con algún carácter
    no ASCII, se lee como UTF-8; si no, como MARC-8 (lo que dice el estándar).
    """
    if codificacion == "utf8":
        return {"force_utf8": True}
    if codificacion == "latin1":
        return {"force_utf8": False, "file_encoding": "latin-1"}
    if codificacion == "marc8":
        return {"force_utf8": False}
    try:
        contenido.decode("utf-8")
    except UnicodeDecodeError:
        return {"force_utf8": False}
    return {"force_utf8": not contenido.isascii()}


def _leer(contenido: bytes, codificacion: str = "auto") -> tuple:
    """(formato, registros); un registro ilegible llega como None."""
    # Editores de Windows y algunas exportaciones anteponen la marca de orden de bytes.
    contenido = contenido.removeprefix(b"\xef\xbb\xbf")
    if not contenido.strip():
        raise ReglaIncumplida("El archivo está vacío")
    if contenido.lstrip()[:1] == b"<":
        try:
            return "marcxml", pymarc.parse_xml_to_array(io.BytesIO(contenido))
        except Exception as error:  # el XML puede fallar de muchas formas
            raise ReglaIncumplida(f"No es un MARCXML válido: {error}") from error
    lector = pymarc.MARCReader(io.BytesIO(contenido), to_unicode=True,
                               utf8_handling="replace", permissive=True,
                               **_opciones_de_codificacion(contenido, codificacion))
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
        def sub(codigo: str) -> Optional[str]:
            valor = (marc.subcampos(campo, codigo) or [None])[0]
            return valor.strip() or None if isinstance(valor, str) else valor

        barcode = sub("p")
        if not barcode:
            resultado.mensajes.append("952 sin código de barras ($p): ejemplar omitido")
            continue
        if barcode in ctx.barcodes_en_archivo or db.query(models.Item.id).filter(
                models.Item.codigo_barras == barcode).first():
            resultado.mensajes.append(f"El código de barras {barcode} ya existe: omitido")
            continue
        largo = next(((nombre, maximo) for nombre, valor, maximo in (
            ("código de barras ($p)", barcode, 50), ("signatura ($o)", sub("o"), 100),
            ("numeración ($h)", sub("h"), 100)) if valor and len(valor) > maximo), None)
        if largo:
            resultado.mensajes.append(
                f"{barcode[:50]}: el {largo[0]} supera los {largo[1]} caracteres; ejemplar omitido")
            continue
        precio = _precio(sub("v") or sub("g"))
        if precio is not None and precio >= Decimal("100000000"):
            resultado.mensajes.append(f"{barcode}: precio fuera de rango; se importó sin precio")
            precio = None
        codigo_tipo = sub("y")
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
        for codigo in ("a", "b"):
            if sub(codigo) and sub(codigo) not in ctx.sedes:
                resultado.mensajes.append(f"Sede «{sub(codigo)}» desconocida en {barcode} "
                                          f"(${codigo}): se usa la sede por defecto")
        estado = "Perdido" if _marcado(sub("1")) else "Retirado" if _marcado(sub("0")) else "Disponible"
        if _marcado(sub("7")):
            resultado.mensajes.append(
                f"{barcode} figura como no prestable ($7): revisa su tipo de ítem")
        if _marcado(sub("4")):
            resultado.mensajes.append(f"{barcode} figura como dañado ($4): Shelfie no lo registra")
        ctx.barcodes_en_archivo.add(barcode)
        resultado.ejemplares += 1
        if not aplicar:
            continue
        sede_propia = ctx.sedes.get(sub("a") or "", ctx.sede_defecto)
        db.add(models.Item(
            biblio_id=biblio.id, codigo_barras=barcode, tipo_item_id=tipo.id,
            signatura_topografica=sub("o"), enumeracion=sub("h"), estado=estado,
            biblioteca_propia_id=sede_propia,
            biblioteca_actual_id=ctx.sedes.get(sub("b") or "", sede_propia),
            precio_reposicion=precio,
        ))


def _marcado(valor: Optional[str]) -> bool:
    """Los subcampos de estado de Koha ($0, $1, $4, $7): vacío o 0 = no."""
    return (valor or "0") != "0"


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
    # Etiquetas propias de otros sistemas (FMT, LDR de Aleph/Alma): se descarta el campo,
    # no el registro, como hace Koha.
    ajenas = sorted({next(iter(c)) for c in sin_ejemplares.get("fields", [])
                     if isinstance(c, dict) and len(c) == 1
                     and not re.fullmatch(r"\d{3}", str(next(iter(c))))})
    if ajenas:
        sin_ejemplares = {**sin_ejemplares, "fields": [
            c for c in sin_ejemplares["fields"] if next(iter(c)) not in ajenas]}
        resultado.mensajes.append(f"Se descartaron campos que no son MARC: {', '.join(ajenas)}")
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
        # Primero el archivo: al aplicar, el registro anterior ya está en la base y con
        # «reemplazar» este lo pisaría; en la vista previa se omitía. Igual en ambos modos.
        if digitos and digitos in ctx.isbn_en_archivo:
            resultado.accion = "omitir"
            resultado.mensajes.append(
                f"El ISBN se repite en el registro #{ctx.isbn_en_archivo[digitos]} del archivo")
            return resultado
        existente = _duplicado(db, digitos)
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
             plantilla: str = "auto", codificacion: str = "auto") -> dict:
    """Vista previa (aplicar=False, no escribe nada) o importación definitiva."""
    if duplicados not in DUPLICADOS:
        raise ReglaIncumplida(f"Política de duplicados no válida: {', '.join(DUPLICADOS)}")
    if codificacion not in CODIFICACIONES:
        raise ReglaIncumplida(f"Codificación no válida: {', '.join(CODIFICACIONES)}")
    formato, registros = _leer(contenido, codificacion)
    ctx = _Contexto(db)
    resultados = [_importar_uno(db, ctx, r, n, aplicar, duplicados, plantilla)
                  for n, r in enumerate(registros, start=1)]
    def contar(accion):
        return sum(1 for r in resultados if r.accion == accion)

    if aplicar:
        from app.services import registro
        registro.anotar(
            db, "catalogo", "importacion",
            f"Importó {formato.upper()}: {contar('nuevo')} nuevos, {contar('reemplazar')} "
            f"reemplazados, {contar('omitir')} omitidos y {contar('error')} con errores",
            datos={"duplicados": duplicados, "plantilla": plantilla, "codificacion": codificacion,
                   "registros": [r.registro_id for r in resultados if r.registro_id][:500]})
        db.commit()
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
