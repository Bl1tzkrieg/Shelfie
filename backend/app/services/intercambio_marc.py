"""Importar y exportar registros MARC21 (ISO 2709 y MARCXML) con pymarc.

Los ejemplares viajan en el campo 952, con los mismos subcampos que usa Koha,
para poder migrar desde o hacia Koha sin transformar nada:

    952 $a y $b biblioteca   $o signatura   $p código de barras   $t número de copia
        $y tipo de ítem      $z nota

Al exportar, $a y $b llevan `biblioteca.codigo` y $y `biblioteca.tipo_item_koha`; al
importar se ignoran (también $1). Los ejemplares son la fuente de verdad: el 952 no se
guarda en el MARC del registro, se regenera al exportar.

La cota del registro importado es la del 092; si no hay, la del primer 952 $o, la del
082 ($a + $b) o la del 050 ($a + $b), en ese orden. No se escribe un 092: el MARC queda
como vino, para que la ida y vuelta con Koha no agregue campos. Sin ninguna, queda vacía.

Al importar, el duplicado se detecta por ISBN (solo dígitos, cualquiera de los 020). La política elige qué
hacer con él: omitirlo, reemplazar su MARC (conserva sus ejemplares y suma los
nuevos) o agregar un registro aparte.
"""

import io
import re
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Set

import pymarc
from sqlalchemy import func, literal
from sqlalchemy.orm import Session

from app import models
from app.core import marc_plantillas
from app.core.csv import Texto, celda_segura
from app.core.errores import ErroresDeValidacion, ReglaIncumplida
from app.core.signaturas import clave_signatura_sql, normalizar_cota
from app.core.tiempo import sello_archivo
from app.services import configuracion, ficha, marc
from app.services.catalogo import aplicar_marc, buscar_por_isbn, digitos_isbn
from app.services.libros import sin_acentos

FORMATOS = {"marc": ("application/marc", "mrc"), "marcxml": ("application/marcxml+xml", "xml")}
DUPLICADOS = ("omitir", "reemplazar", "agregar")
MAX_EN_RESPUESTA = 200
TAG_EJEMPLAR = "952"
# Campos que identifican al registro en el sistema de origen: no se importan.
TAGS_DE_OTRO_SISTEMA = {"999", TAG_EJEMPLAR}


# --- Exportación -------------------------------------------------------------------

def _campo_952(item: models.Item, biblioteca: str, tipo_item: str) -> dict:
    """Un 952 como lo espera Koha: $a $b $o $p $t $y $z; $a, $b e $y siempre van."""
    subs = []
    for codigo, valor in (("a", biblioteca), ("b", biblioteca),
                          ("o", item.signatura_topografica), ("p", item.codigo_barras),
                          ("t", item.numero_copia), ("y", tipo_item), ("z", item.nota)):
        if valor or codigo in "aby":
            subs.append({codigo: str(valor or "")})
    return {TAG_EJEMPLAR: {"ind1": " ", "ind2": " ", "subfields": subs}}


def _para_exportar(biblio: models.RegistroBibliografico, biblioteca: str, tipo_item: str,
                   ejemplares: List[models.Item]) -> pymarc.Record:
    origen = biblio.marc_json or marc.desde_columnas(biblio.titulo, biblio.autor, biblio.isbn,
                                                     biblio.ano_publicacion, biblio.materia)
    campos = [c for c in origen.get("fields", [])
              if next(iter(c)) not in {"001", "003"} | TAGS_DE_OTRO_SISTEMA]
    campos = [{"001": str(biblio.id)}, {"003": biblioteca}] + campos
    campos += [_campo_952(i, biblioteca, tipo_item) for i in ejemplares]
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


def _items_por_titulo(db: Session, biblio_ids: List[int]) -> Dict[int, list]:
    """Ejemplares de varios títulos en una sola consulta."""
    resultado: Dict[int, list] = {i: [] for i in biblio_ids}
    if biblio_ids:
        for item in db.query(models.Item).filter(
                models.Item.biblio_id.in_(biblio_ids)).order_by(models.Item.id):
            resultado[item.biblio_id].append(item)
    return resultado


def _para_exportar_todos(db: Session, ids: Optional[List[int]]) -> List[tuple]:
    """(registro, pymarc.Record) de todo el catálogo o de los `ids`, en orden de id."""
    consulta = db.query(models.RegistroBibliografico)
    if ids is not None:
        consulta = consulta.filter(models.RegistroBibliografico.id.in_(ids))
    registros = consulta.order_by(models.RegistroBibliografico.id).all()
    datos = configuracion.leer(db, "biblioteca")
    biblioteca = (datos.get("codigo") or "BIB").strip()  # hasta 10, como en Koha
    # El ajuste se guarda como lo escribieron; Koha espera el código en mayúsculas.
    tipo_item = (datos.get("tipo_item_koha") or "LIB").strip().upper()
    items = _items_por_titulo(db, [b.id for b in registros])
    return [(b, _para_exportar(b, biblioteca, tipo_item, items[b.id])) for b in registros]


def exportar(db: Session, *, formato: Literal["marc", "marcxml"],
             ids: Optional[List[int]] = None) -> tuple:
    """(contenido, tipo MIME, nombre de archivo) con todo el catálogo o con los `ids` pedidos.

    Cada ejemplar sale como un 952; un registro sin ejemplares sale sin 952. En ISO 2709,
    un registro que no cabe en el formato es un error (400) que dice usar MARCXML."""
    if formato not in FORMATOS:
        raise ReglaIncumplida("Formato no soportado: usa marc o marcxml")
    salida = io.BytesIO()
    if formato == "marcxml":
        escritor = pymarc.XMLWriter(salida)
        for _, registro in _para_exportar_todos(db, ids):
            escritor.write(registro)
        escritor.close(close_fh=False)
    else:
        for biblio, registro in _para_exportar_todos(db, ids):
            salida.write(_iso2709(registro, biblio))

    tipo_mime, extension = FORMATOS[formato]
    return salida.getvalue(), tipo_mime, f"catalogo-{sello_archivo()}.{extension}"


def exportar_iso2709_omitiendo(db: Session) -> tuple:
    """(contenido, omitidos) con todo el catálogo en ISO 2709 para el respaldo: un registro
    que no cabe en el formato se deja afuera (MARCXML sí lo lleva) en lugar de hacer fallar
    todo. `omitidos` es [{"id", "titulo", "motivo"}]."""
    salida, omitidos = io.BytesIO(), []
    for biblio, registro in _para_exportar_todos(db, None):
        try:
            salida.write(_iso2709(registro, biblio))
        except ReglaIncumplida as error:
            omitidos.append({"id": biblio.id, "titulo": biblio.titulo, "motivo": error.mensaje})
    return salida.getvalue(), omitidos


COLUMNAS_CSV = ("cota", "titulo", "autor", "editorial", "ano", "isbn", "materias", "ejemplares")


def exportar_csv(db: Session) -> List[dict]:
    """El catálogo en el orden del estante (sin cota al final), una fila por registro.

    Cada celda pasa por `celda_segura`: un título como «=HYPERLINK(...)» no se ejecuta como
    fórmula al abrirlo en una hoja de cálculo. La cota y el ISBN van como `Texto` para que
    Excel no los convierta en números."""
    RB = models.RegistroBibliografico
    ejemplares = (db.query(models.Item.biblio_id, func.count(models.Item.id).label("cantidad"))
                  .group_by(models.Item.biblio_id).subquery())
    filas = (db.query(RB, func.coalesce(ejemplares.c.cantidad, 0))
             .outerjoin(ejemplares, ejemplares.c.biblio_id == RB.id)
             .order_by(RB.cota.is_(None), clave_signatura_sql(RB.cota), RB.titulo, RB.id)
             .all())
    resultado = []
    for biblio, cantidad in filas:
        materias = ficha.desde_marc(biblio.marc_json or {}).materias
        fila = {"cota": biblio.cota or "", "titulo": biblio.titulo, "autor": biblio.autor or "",
                "editorial": biblio.editorial or "", "ano": biblio.ano_publicacion,
                "isbn": biblio.isbn or "", "materias": " | ".join(materias),
                "ejemplares": cantidad}
        resultado.append({k: Texto(v) if k in ("cota", "isbn") else celda_segura(v)
                          for k, v in fila.items()})
    return resultado


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


def _cota_del_952(registro: dict, campos_952: List[dict]) -> Optional[str]:
    """Sin 092, la cota del registro es la del primer 952 $o que sirve (antes que el 082 o
    el 050, que `aplicar_marc` lee del MARC). Una que no cabe en la columna se salta."""
    if marc.campos(registro, "092"):
        return None
    for campo in campos_952:
        valor = normalizar_cota((marc.subcampos(campo, "o") or [None])[0])
        if valor and len(valor) <= ficha.MAX_COTA:
            return valor
    return None


def _completar_008(registro: dict) -> dict:
    """Muchos registros de otros sistemas no traen 008; se genera uno básico."""
    if any("008" in c for c in registro["fields"]):
        return registro
    return {**registro,
            "fields": [{"008": marc.campo_008(marc.ano_de(registro))}] + registro["fields"]}


class _Contexto:
    """Datos que se acumulan a lo largo de una importación."""

    def __init__(self):
        self.barcodes_en_archivo: Set[str] = set()
        self.isbn_en_archivo: Dict[str, int] = {}
        self.subcampos_ignorados: Set[str] = set()

    def anotar_ignorados(self, campos_952: List[dict]) -> None:
        """Subcampos del 952 con datos que Shelfie no guarda ($1 y $7 solo si no son 0)."""
        for campo in campos_952:
            for sub in campo.get("subfields", []):
                codigo, valor = next(iter(sub.items()))
                valor = (valor or "").strip()
                if codigo in SUBCAMPOS_952_USADOS or not valor:
                    continue
                if codigo in ESTADOS_KOHA and valor == "0":
                    continue
                self.subcampos_ignorados.add(codigo)

    def resumen(self) -> List[str]:
        if not self.subcampos_ignorados:
            return []
        codigos = sorted(self.subcampos_ignorados, key=lambda c: (c.isdigit(), c))
        return ["Se ignoraron subcampos del 952 que Shelfie no guarda: " + ", ".join(codigos)]


# $o $p $t $z se guardan; $a, $b e $y se regeneran al exportar desde la configuración.
SUBCAMPOS_952_USADOS = set("abyoptz")
# Estados de Koha que Shelfie no maneja: $1 perdido y $7 no prestable (0 = normal).
ESTADOS_KOHA = {"1": "perdido", "7": "no prestable"}


def _sub_952(campo: dict, codigo: str) -> Optional[str]:
    valor = (marc.subcampos(campo, codigo) or [None])[0]
    return valor.strip() or None if isinstance(valor, str) else valor


def _misma_copia(signatura: Optional[str], copia: Optional[str]) -> tuple:
    return (normalizar_cota(signatura), normalizar_cota(copia))


def _ejemplares(db: Session, ctx: _Contexto, campos_952: List[dict], resultado: Resultado,
                biblio: Optional[models.RegistroBibliografico], aplicar: bool,
                existente: Optional[models.RegistroBibliografico] = None) -> None:
    """Crea los ejemplares de los 952. Con `existente` (se reemplaza un registro), un
    ejemplar sin código que ya tiene (misma signatura y copia) no se vuelve a agregar."""
    ya_tiene = set()
    if existente is not None:
        ya_tiene = {_misma_copia(i.signatura_topografica, i.numero_copia)
                    for i in db.query(models.Item).filter(models.Item.biblio_id == existente.id)}
    for campo in campos_952:
        def sub(codigo: str) -> Optional[str]:
            return _sub_952(campo, codigo)

        barcode = sub("p")  # opcional: Koha admite ejemplares sin código
        if barcode and (barcode in ctx.barcodes_en_archivo or db.query(models.Item.id).filter(
                models.Item.codigo_barras == barcode).first()):
            resultado.mensajes.append(f"El código de barras {barcode} ya existe: omitido")
            continue
        largo = next(((nombre, maximo) for nombre, valor, maximo in (
            ("código de barras ($p)", barcode, 50), ("signatura ($o)", sub("o"), 100),
            ("número de copia ($t)", sub("t"), 20)) if valor and len(valor) > maximo), None)
        if largo:
            quien = (barcode or "Ejemplar sin código")[:50]
            resultado.mensajes.append(
                f"{quien}: el {largo[0]} supera los {largo[1]} caracteres; ejemplar omitido")
            continue
        if not barcode and _misma_copia(sub("o"), sub("t")) in ya_tiene:
            resultado.mensajes.append(
                f"{_nombre_ejemplar(None, sub('o'), sub('t'))}: ejemplar sin código ya existe: omitido")
            continue
        if barcode:
            ctx.barcodes_en_archivo.add(barcode)
        for codigo, estado in ESTADOS_KOHA.items():
            if (sub(codigo) or "0") != "0":
                resultado.mensajes.append(
                    f"el ejemplar {_nombre_ejemplar(barcode, sub('o'), sub('t'))} figuraba "
                    f"{estado} en Koha; en Shelfie queda como uno más")
        resultado.ejemplares += 1
        if not aplicar:
            continue
        db.add(models.Item(biblio_id=biblio.id, codigo_barras=barcode,
                           signatura_topografica=sub("o"), numero_copia=sub("t"),
                           nota=sub("z")))


def _nombre_ejemplar(barcode: Optional[str], signatura: Optional[str],
                     copia: Optional[str]) -> str:
    if barcode:
        return barcode
    detalle = " ".join(p for p in (signatura, copia) if p)
    return f"sin código ({detalle})" if detalle else "sin código"


def _duplicado_sin_isbn(db: Session, campos_952: List[dict], derivado: dict) -> tuple:
    """(registro, cómo se detectó) para un registro entrante sin ISBN, o (None, None).

    Primero por códigos: todos los $p del archivo ya son ejemplares de un mismo registro.
    Si no, por título, autor y año (sin mayúsculas ni acentos, como en el alta de libros),
    cuando coincide exactamente un registro."""
    RB = models.RegistroBibliografico
    codigos = {c for c in (_sub_952(campo, "p") for campo in campos_952) if c}
    if codigos:
        filas = db.query(models.Item.biblio_id, models.Item.codigo_barras).filter(
            models.Item.codigo_barras.in_(codigos)).all()
        propietarios = {f.biblio_id for f in filas}
        if len({f.codigo_barras for f in filas}) == len(codigos) and len(propietarios) == 1:
            return db.get(RB, propietarios.pop()), "por códigos"
    iguales = db.query(RB).filter(
        sin_acentos(RB.titulo) == sin_acentos(literal(derivado["titulo"])),
        sin_acentos(func.coalesce(RB.autor, "")) == sin_acentos(literal(derivado["autor"] or "")),
        RB.ano_publicacion.is_not_distinct_from(derivado["ano_publicacion"]),
    ).order_by(RB.id).limit(2).all()
    if len(iguales) == 1:
        return iguales[0], "por título, autor y año"
    return None, None




def _importar_uno(db: Session, ctx: _Contexto, crudo, n: int, aplicar: bool, duplicados: str,
                  plantilla_pedida: str) -> Resultado:
    resultado = Resultado(n=n)
    if crudo is None:
        resultado.accion = "error"
        resultado.mensajes.append("Registro ilegible en el archivo")
        return resultado

    sin_ejemplares, campos_952 = _separar_ejemplares(marc.desde_pymarc(crudo))
    ctx.anotar_ignorados(campos_952)
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

    isbns = (derivado["isbns"] or "").split()
    digitos = [d for d in (digitos_isbn(i) for i in isbns) if d]
    existente = None
    if duplicados != "agregar":
        # Primero el archivo: al aplicar, el registro anterior ya está en la base y con
        # «reemplazar» este lo pisaría; en la vista previa se omitía. Igual en ambos modos.
        repetido = next((d for d in digitos if d in ctx.isbn_en_archivo), None)
        if repetido:
            resultado.accion = "omitir"
            resultado.mensajes.append(
                f"El ISBN se repite en el registro #{ctx.isbn_en_archivo[repetido]} del archivo")
            return resultado
        existente = buscar_por_isbn(db, isbns)
        if existente is None and not digitos:
            existente, como = _duplicado_sin_isbn(db, campos_952, derivado)
            if existente is not None:
                resultado.mensajes.append(f"sin ISBN: duplicado detectado {como}")
    if existente is not None and duplicados == "omitir":
        resultado.accion, resultado.registro_id = "omitir", existente.id
        resultado.mensajes.append(f"Ya existe como «{existente.titulo}» (registro {existente.id})")
        return resultado
    for d in digitos:
        ctx.isbn_en_archivo.setdefault(d, n)

    resultado.accion = "reemplazar" if existente is not None else "nuevo"
    biblio = existente
    if aplicar:
        punto = db.begin_nested()
        try:
            if biblio is None:
                biblio = models.RegistroBibliografico()
                db.add(biblio)
            aplicar_marc(biblio, canonico, plantilla)
            biblio.cota = _cota_del_952(canonico, campos_952) or biblio.cota
            db.flush()
            _ejemplares(db, ctx, campos_952, resultado, biblio, aplicar=True,
                        existente=existente)
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
        _ejemplares(db, ctx, campos_952, resultado, None, aplicar=False, existente=existente)
    return resultado


def importar(db: Session, contenido: bytes, *, aplicar: bool, duplicados: str = "omitir",
             plantilla: str = "auto", codificacion: str = "auto") -> dict:
    """Vista previa (aplicar=False, no escribe nada) o importación definitiva."""
    if duplicados not in DUPLICADOS:
        raise ReglaIncumplida(f"Política de duplicados no válida: {', '.join(DUPLICADOS)}")
    if codificacion not in CODIFICACIONES:
        raise ReglaIncumplida(f"Codificación no válida: {', '.join(CODIFICACIONES)}")
    formato, registros = _leer(contenido, codificacion)
    ctx = _Contexto()
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
        "mensajes": ctx.resumen(),
        "registros": [r.__dict__ for r in resultados[:MAX_EN_RESPUESTA]],
    }
