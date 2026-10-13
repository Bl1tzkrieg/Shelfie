"""Plantillas de catalogación MARC21 (los "frameworks" de Koha).

Cada plantilla dice qué campos ofrece el editor, cómo se llaman en español, cuáles
son obligatorios y cuáles se repiten. Un registro puede traer campos que su
plantilla no conoce (p. ej. al importar): se conservan y el editor los muestra
igual, solo que sin ayuda.

Se definen en código para empezar; si hace falta editarlas desde la intranet se
pasarán a tablas con estos mismos datos.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Subcampo:
    codigo: str
    nombre: str
    repetible: bool = False
    obligatorio: bool = False


@dataclass(frozen=True)
class Campo:
    tag: str
    nombre: str
    repetible: bool = False
    obligatorio: bool = False
    # Se muestra vacío en un registro nuevo, para que el catalogador no tenga que buscarlo.
    visible: bool = False
    subcampos: Tuple[Subcampo, ...] = ()
    # Opciones de indicadores: valor -> significado. Vacío = sin definir (" ").
    ind1: Tuple[Tuple[str, str], ...] = ()
    ind2: Tuple[Tuple[str, str], ...] = ()
    # Valores sugeridos al agregar el campo.
    ind1_defecto: str = " "
    ind2_defecto: str = " "

    @property
    def es_de_control(self) -> bool:
        return self.tag < "010"


@dataclass(frozen=True)
class Plantilla:
    codigo: str
    nombre: str
    descripcion: str
    lider: str
    campos: Tuple[Campo, ...] = field(default_factory=tuple)

    def campo(self, tag: str) -> Optional[Campo]:
        return next((c for c in self.campos if c.tag == tag), None)


S = Subcampo

# --- Campos comunes ---------------------------------------------------------------

C008 = Campo("008", "Datos de longitud fija", obligatorio=True, visible=True)
C020 = Campo("020", "ISBN", repetible=True, visible=True, subcampos=(
    S("a", "ISBN"), S("q", "Calificador (rústica, tapa dura…)", repetible=True),
    S("c", "Precio o disponibilidad"), S("z", "ISBN cancelado o no válido", repetible=True)))
C022 = Campo("022", "ISSN", repetible=True, visible=True, subcampos=(
    S("a", "ISSN"), S("l", "ISSN-L"), S("y", "ISSN incorrecto", repetible=True)))
C041 = Campo("041", "Código de idioma", repetible=True, subcampos=(
    S("a", "Idioma del texto", repetible=True), S("h", "Idioma original", repetible=True)),
    ind1=(("0", "No es traducción"), ("1", "Es traducción")))
C082 = Campo("082", "Clasificación Dewey", repetible=True, subcampos=(
    S("a", "Número de clasificación", repetible=True), S("b", "Número de ítem"),
    S("2", "Edición")), ind1=(("0", "Edición completa"), ("1", "Edición abreviada")),
    ind2=(("0", "Asignado por LC"), ("4", "Asignado por otra agencia")), ind2_defecto="4")
C100 = Campo("100", "Autor personal", visible=True, subcampos=(
    S("a", "Nombre (Apellido, Nombre)"), S("b", "Numeración"), S("c", "Títulos y otras palabras",
    repetible=True), S("d", "Fechas"), S("e", "Función", repetible=True)),
    ind1=(("0", "Nombre de pila"), ("1", "Apellido"), ("3", "Familia")), ind1_defecto="1")
C110 = Campo("110", "Autor corporativo", subcampos=(
    S("a", "Nombre de la entidad"), S("b", "Unidad subordinada", repetible=True),
    S("e", "Función", repetible=True)),
    ind1=(("0", "Nombre invertido"), ("1", "Jurisdicción"), ("2", "Orden directo")),
    ind1_defecto="2")
C245 = Campo("245", "Título", obligatorio=True, visible=True, subcampos=(
    S("a", "Título", obligatorio=True), S("b", "Resto del título"),
    S("c", "Mención de responsabilidad"), S("n", "Número de parte", repetible=True),
    S("p", "Nombre de parte", repetible=True), S("h", "Medio")),
    ind1=(("0", "Sin entrada secundaria de título"), ("1", "Con entrada secundaria")),
    ind2=tuple((str(n), f"{n} caracteres que no se alfabetizan") for n in range(10)),
    ind1_defecto="1", ind2_defecto="0")
C246 = Campo("246", "Variante del título", repetible=True, subcampos=(
    S("a", "Título"), S("b", "Resto del título")),
    ind1=(("1", "Nota y entrada"), ("3", "Sin nota, con entrada")),
    ind2=((" ", "Sin especificar"), ("1", "Título paralelo")), ind1_defecto="3")
C250 = Campo("250", "Edición", repetible=True, visible=True, subcampos=(
    S("a", "Mención de edición"), S("b", "Resto de la mención")))
C260 = Campo("260", "Publicación (forma anterior a RDA)", repetible=True, subcampos=(
    S("a", "Lugar", repetible=True), S("b", "Editorial", repetible=True),
    S("c", "Fecha", repetible=True)))
C264 = Campo("264", "Producción, publicación, distribución", repetible=True, visible=True,
             subcampos=(S("a", "Lugar", repetible=True), S("b", "Editorial", repetible=True),
                        S("c", "Fecha")),
             ind2=(("0", "Producción"), ("1", "Publicación"), ("2", "Distribución"),
                   ("3", "Fabricación"), ("4", "Copyright")), ind2_defecto="1")
C300 = Campo("300", "Descripción física", repetible=True, visible=True, subcampos=(
    S("a", "Extensión (páginas, volúmenes)", repetible=True),
    S("b", "Otros detalles (ilustraciones)"), S("c", "Dimensiones", repetible=True),
    S("e", "Material acompañante")))
C336 = Campo("336", "Tipo de contenido", repetible=True, subcampos=(
    S("a", "Término (texto, imagen fija…)", repetible=True), S("2", "Fuente")))
C337 = Campo("337", "Tipo de medio", repetible=True, subcampos=(
    S("a", "Término (sin mediación, computadora…)", repetible=True), S("2", "Fuente")))
C338 = Campo("338", "Tipo de soporte", repetible=True, subcampos=(
    S("a", "Término (volumen, recurso en línea…)", repetible=True), S("2", "Fuente")))
C490 = Campo("490", "Serie", repetible=True, subcampos=(
    S("a", "Título de la serie", repetible=True), S("v", "Volumen", repetible=True),
    S("x", "ISSN de la serie", repetible=True)),
    ind1=(("0", "No trazada"), ("1", "Trazada")))
C500 = Campo("500", "Nota general", repetible=True, subcampos=(S("a", "Nota"),))
C504 = Campo("504", "Nota de bibliografía", repetible=True, subcampos=(S("a", "Nota"),))
C505 = Campo("505", "Nota de contenido", repetible=True, subcampos=(
    S("a", "Contenido"), S("t", "Título", repetible=True)),
    ind1=(("0", "Contenido completo"), ("1", "Incompleto"), ("2", "Parcial")))
C520 = Campo("520", "Resumen", repetible=True, subcampos=(S("a", "Resumen"),))
C650 = Campo("650", "Materia (tema)", repetible=True, visible=True, subcampos=(
    S("a", "Tema"), S("x", "Subdivisión general", repetible=True),
    S("y", "Subdivisión cronológica", repetible=True),
    S("z", "Subdivisión geográfica", repetible=True), S("v", "Subdivisión de forma",
    repetible=True), S("2", "Fuente del encabezamiento")),
    ind2=(("0", "LCSH"), ("4", "Fuente no especificada"), ("7", "Fuente en $2")),
    ind2_defecto="4")
C651 = Campo("651", "Materia (lugar)", repetible=True, subcampos=(
    S("a", "Nombre geográfico"), S("x", "Subdivisión general", repetible=True)),
    ind2=(("0", "LCSH"), ("4", "Fuente no especificada"), ("7", "Fuente en $2")),
    ind2_defecto="4")
C653 = Campo("653", "Palabras clave", repetible=True, subcampos=(
    S("a", "Término", repetible=True),))
C700 = Campo("700", "Autor secundario", repetible=True, subcampos=(
    S("a", "Nombre (Apellido, Nombre)"), S("d", "Fechas"), S("e", "Función", repetible=True)),
    ind1=(("0", "Nombre de pila"), ("1", "Apellido"), ("3", "Familia")), ind1_defecto="1")
C710 = Campo("710", "Entidad secundaria", repetible=True, subcampos=(
    S("a", "Nombre de la entidad"), S("b", "Unidad subordinada", repetible=True),
    S("e", "Función", repetible=True)), ind1_defecto="2",
    ind1=(("0", "Nombre invertido"), ("1", "Jurisdicción"), ("2", "Orden directo")))
C856 = Campo("856", "Acceso electrónico", repetible=True, subcampos=(
    S("u", "URL", repetible=True), S("y", "Texto del enlace", repetible=True),
    S("z", "Nota pública", repetible=True)),
    ind1=(("4", "HTTP"), (" ", "Sin especificar")),
    ind2=(("0", "El recurso"), ("1", "Versión del recurso"), ("2", "Recurso relacionado")),
    ind1_defecto="4", ind2_defecto="0")

_LIBRO = (C008, C020, C041, C082, C100, C110, C245, C246, C250, C260, C264, C300, C336, C337,
          C338, C490, C500, C504, C505, C520, C650, C651, C653, C700, C710, C856)

BKS = Plantilla(
    "BKS", "Libros", "Monografías impresas: libros, folletos, manuales.",
    "00000nam a22000007i 4500", _LIBRO)

SER = Plantilla(
    "SER", "Publicaciones seriadas", "Revistas, periódicos, boletines y anuarios.",
    "00000nas a22000007i 4500", (
        C008, C022, C041, C082, C110, C245, C246, C260, C264, C300,
        Campo("310", "Periodicidad actual", visible=True, subcampos=(
            S("a", "Periodicidad (mensual, trimestral…)"), S("b", "Desde"))),
        Campo("321", "Periodicidad anterior", repetible=True, subcampos=(
            S("a", "Periodicidad"), S("b", "Fechas"))),
        C336, C337, C338,
        Campo("362", "Fechas y numeración", repetible=True, visible=True, subcampos=(
            S("a", "Numeración (Vol. 1, no. 1 (ene. 2020)-)"),),
            ind1=(("0", "Estilo formateado"), ("1", "Nota sin formato"))),
        C500, Campo("515", "Peculiaridades de la numeración", repetible=True,
                    subcampos=(S("a", "Nota"),)),
        C520, C650, C651, C653, C710,
        Campo("780", "Título anterior", repetible=True, subcampos=(
            S("t", "Título"), S("x", "ISSN")), ind1_defecto="0", ind2_defecto="0"),
        Campo("785", "Título posterior", repetible=True, subcampos=(
            S("t", "Título"), S("x", "ISSN")), ind1_defecto="0", ind2_defecto="0"),
        C856))

TES = Plantilla(
    "TES", "Tesis y trabajos de grado",
    "Trabajos de grado, tesis de maestría y doctorales. El tutor va en 700 con $e tutor.",
    "00000nam a22000007i 4500", (
        C008, C041, C082, C100, C245, C246, C264, C300, C336, C337, C338, C500,
        Campo("502", "Nota de tesis", obligatorio=True, visible=True, subcampos=(
            S("b", "Grado (Licenciatura, Maestría, Doctorado)"), S("c", "Institución"),
            S("d", "Año"), S("g", "Información adicional", repetible=True),
            S("a", "Nota completa (si no se separa en $b $c $d)"))),
        C504, C520, C650, C653,
        Campo("700", "Tutor, jurado u otro autor", repetible=True, visible=True, subcampos=(
            S("a", "Nombre (Apellido, Nombre)"), S("e", "Función (tutor, jurado…)",
            repetible=True)), ind1=(("0", "Nombre de pila"), ("1", "Apellido")),
            ind1_defecto="1"),
        C710, C856))

ERE = Plantilla(
    "ERE", "Recursos electrónicos",
    "Libros electrónicos, bases de datos, sitios web y archivos digitales.",
    "00000nmm a22000007i 4500", (
        C008, C020, C041, C082, C100, C110, C245, C246, C250, C264, C300, C336, C337, C338,
        Campo("347", "Características del archivo digital", repetible=True, visible=True,
              subcampos=(S("a", "Tipo de archivo (texto, imagen…)", repetible=True),
                         S("b", "Formato (PDF, EPUB…)", repetible=True),
                         S("c", "Tamaño", repetible=True))),
        C500, C520,
        Campo("538", "Requisitos del sistema", repetible=True, visible=True,
              subcampos=(S("a", "Nota"),)),
        C650, C653, C700, C710,
        Campo("856", "Acceso electrónico", repetible=True, obligatorio=True, visible=True,
              subcampos=(S("u", "URL", repetible=True, obligatorio=True),
                         S("y", "Texto del enlace", repetible=True),
                         S("z", "Nota pública", repetible=True)),
              ind1=(("4", "HTTP"), (" ", "Sin especificar")),
              ind2=(("0", "El recurso"), ("1", "Versión del recurso"),
                    ("2", "Recurso relacionado")), ind1_defecto="4", ind2_defecto="0")))

PLANTILLAS: Dict[str, Plantilla] = {p.codigo: p for p in (BKS, SER, TES, ERE)}
POR_DEFECTO = "BKS"

# Nombre de cada bloque de etiquetas, para agrupar el editor como lo hace Koha.
BLOQUES = {
    "0": "Control e identificadores", "1": "Autor principal", "2": "Título, edición y publicación",
    "3": "Descripción física", "4": "Serie", "5": "Notas", "6": "Materias",
    "7": "Entradas secundarias y enlaces", "8": "Acceso electrónico", "9": "Datos locales",
}


def obtener(codigo: Optional[str]) -> Plantilla:
    return PLANTILLAS.get(codigo or POR_DEFECTO, PLANTILLAS[POR_DEFECTO])


def como_dict(p: Plantilla) -> dict:
    """Definición para el editor del frontend."""
    return {
        "codigo": p.codigo,
        "nombre": p.nombre,
        "descripcion": p.descripcion,
        "lider": p.lider,
        "bloques": BLOQUES,
        "campos": [
            {
                "tag": c.tag, "nombre": c.nombre, "repetible": c.repetible,
                "obligatorio": c.obligatorio, "visible": c.visible, "control": c.es_de_control,
                "ind1": [{"valor": v, "nombre": n} for v, n in c.ind1],
                "ind2": [{"valor": v, "nombre": n} for v, n in c.ind2],
                "ind1_defecto": c.ind1_defecto, "ind2_defecto": c.ind2_defecto,
                "subcampos": [{"codigo": s.codigo, "nombre": s.nombre,
                               "repetible": s.repetible, "obligatorio": s.obligatorio}
                              for s in c.subcampos],
            }
            for c in p.campos
        ],
    }


def resumen(p: Plantilla) -> dict:
    return {"codigo": p.codigo, "nombre": p.nombre, "descripcion": p.descripcion}


def listar() -> List[dict]:
    return [resumen(p) for p in PLANTILLAS.values()]
