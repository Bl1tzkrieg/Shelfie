"""Respaldo diario: la base (pg_dump) y el catálogo en MARC, MARCXML y CSV.

Cada respaldo es una carpeta `shelfie-AAAAMMDD-HHMM/` (hora local) dentro de la carpeta
configurada. Se arma en una carpeta temporal y se renombra al final: un respaldo fallido
nunca deja una carpeta a medias que la rotación cuente como buena.
"""

import glob
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import settings
from app.core import pg_dump as regla_pg_dump
from app.core.csv import texto_csv
from app.core.tiempo import a_local, a_utc, ahora as ahora_utc
from app.services import configuracion, intercambio_marc, registro

log = logging.getLogger("shelfie.respaldo")

CONSERVAR = 30
DIAS_PARA_ALERTA = 7
TIEMPO_MAXIMO_PG_DUMP = 600  # segundos
EDAD_DE_TEMPORAL_HUERFANO = 24 * 3600  # segundos
BASE_PG_WINDOWS = r"C:\Program Files\PostgreSQL"
# El sufijo -N aparece cuando dos respaldos caen en el mismo minuto.
_NOMBRE_RESPALDO = re.compile(r"^shelfie-\d{8}-\d{4}(-\d+)?$")

LEEME = """RESPALDO DE SHELFIE
Biblioteca: {biblioteca}
Fecha: {fecha}

Archivos de esta carpeta:
  base.dump     Copia completa de la base de datos (formato de pg_dump, -Fc).
  catalogo.mrc  El catálogo en MARC (ISO 2709), con un 952 por ejemplar, listo para Koha.
  catalogo.xml  El mismo catálogo en MARCXML.
  catalogo.csv  El catálogo en una hoja de cálculo (cota, título, autor, editorial, año,
                ISBN, materias y ejemplares). Ábrelo con Excel.
  LEEME.txt     Este archivo.

Para restaurar: restaurar.ps1 <esta carpeta>; si base.dump no sirve, importar catalogo.mrc
{avisos}"""

AVISO_OMITIDOS = """
ATENCIÓN: estos registros no caben en el formato ISO 2709 (un campo de más de 9999 bytes
o el registro de más de 99999) y NO están en catalogo.mrc. Están completos en catalogo.xml
y en base.dump:
{lista}
"""

AVISO_ARCHIVO = """
ATENCIÓN: no se pudo generar {archivo} ({motivo}). base.dump está completo.
"""


class ErrorDeRespaldo(Exception):
    """Un fallo previsto, con un mensaje que se le puede mostrar a la persona."""


def _sin_comillas(ruta: Optional[str]) -> str:
    """Windows («Copiar como ruta») pega las rutas entre comillas: "D:\\Respaldos"."""
    return (ruta or "").strip().strip('"').strip()


def problema_pg_dump(ruta: Optional[str]) -> Optional[str]:
    """Por qué esa ruta no se acepta como pg_dump (ver app/core/pg_dump.py), o None."""
    return regla_pg_dump.problema(ruta)


def encontrar_pg_dump(configurado: Optional[str] = None, *,
                      base_windows: str = BASE_PG_WINDOWS) -> Optional[str]:
    """La ruta de pg_dump: la configurada si existe y es un pg_dump aceptable, luego el PATH
    y por último `Program Files\\PostgreSQL\\<versión>\\bin`, con la versión más alta."""
    configurado = _sin_comillas(configurado)
    if configurado and os.path.isfile(configurado) and not problema_pg_dump(configurado):
        return configurado
    en_el_path = shutil.which("pg_dump")
    if en_el_path:
        return en_el_path
    candidatos = glob.glob(os.path.join(base_windows, "*", "bin", "pg_dump.exe"))

    def version(ruta: str) -> tuple:
        # Se comparan números («16» > «9.6»), no texto.
        carpeta = os.path.basename(os.path.dirname(os.path.dirname(ruta)))
        return tuple(int(n) for n in re.findall(r"\d+", carpeta))

    return max(candidatos, key=version) if candidatos else None


def _fecha(texto: Optional[str]) -> Optional[datetime]:
    try:
        return a_utc(datetime.fromisoformat(texto)) if texto else None
    except (TypeError, ValueError):
        return None


def estado(db: Session, ahora: Optional[datetime] = None) -> dict:
    """Cómo va el respaldo y si hay que avisar: el último falló, nunca hubo uno
    correcto o el último correcto tiene más de 7 días."""
    datos = configuracion.leer(db, "respaldo")
    ultimo, ultimo_ok = datos.get("ultimo"), datos.get("ultimo_ok")
    momento = a_utc(ahora or ahora_utc())
    motivo = None
    if ultimo and ultimo.get("ok") is False:
        motivo = f"El último respaldo falló: {ultimo.get('mensaje') or 'sin detalle'}"
    elif _fecha(ultimo_ok) is None:
        motivo = "Nunca se hizo un respaldo"
    elif momento - _fecha(ultimo_ok) > timedelta(days=DIAS_PARA_ALERTA):
        dias = (momento - _fecha(ultimo_ok)).days
        motivo = f"El último respaldo es de hace {dias} días"
    return {"ultimo": ultimo, "ultimo_ok": ultimo_ok, "alerta": motivo is not None,
            "motivo": motivo}


def _volcar_base(pg_dump: str, destino: str) -> None:
    url = make_url(settings.DATABASE_URL)
    args = [pg_dump, "-Fc", "-w"]
    if url.host:
        args += ["-h", url.host]
    if url.port:
        args += ["-p", str(url.port)]
    if url.username:
        args += ["-U", url.username]
    args += ["-f", destino, url.database]
    entorno = dict(os.environ)
    if url.password:
        entorno["PGPASSWORD"] = url.password  # nunca en la línea de comandos
    try:
        corrida = subprocess.run(args, env=entorno, capture_output=True,
                                 timeout=TIEMPO_MAXIMO_PG_DUMP)
    except subprocess.TimeoutExpired:
        raise ErrorDeRespaldo(
            f"pg_dump tardó más de {TIEMPO_MAXIMO_PG_DUMP // 60} minutos y se canceló")
    except OSError as error:
        raise ErrorDeRespaldo(f"No se pudo ejecutar pg_dump ({pg_dump}): {error}")
    if corrida.returncode != 0:
        detalle = corrida.stderr.decode("utf-8", "replace").strip()
        if url.password:
            detalle = detalle.replace(url.password, "***")
        raise ErrorDeRespaldo(f"pg_dump falló: {detalle[:500]}")
    if not os.path.isfile(destino) or os.path.getsize(destino) == 0:
        raise ErrorDeRespaldo("pg_dump no generó el archivo base.dump")


def _escribir(ruta: str, contenido, modo: str = "wb", **opciones) -> None:
    with open(ruta, modo, **opciones) as archivo:
        archivo.write(contenido)


def _xml(db: Session, ruta: str) -> None:
    contenido, _, _ = intercambio_marc.exportar(db, formato="marcxml")
    _escribir(ruta, contenido)


def _csv(db: Session, ruta: str) -> None:
    csv = texto_csv(intercambio_marc.exportar_csv(db), columnas=intercambio_marc.COLUMNAS_CSV)
    _escribir(ruta, csv, "w", encoding="utf-8", newline="")


def _armar(db: Session, temporal: str, pg_dump: str, momento: datetime) -> Optional[str]:
    """Arma la carpeta y devuelve un aviso (o None). Sin base.dump no hay respaldo: su fallo
    es un error. Un fallo en el catálogo (.mrc, .xml, .csv) no tira el base.dump bueno: el
    respaldo queda «ok con aviso» y LEEME.txt lo cuenta."""
    _volcar_base(pg_dump, os.path.join(temporal, "base.dump"))
    avisos, detalle = [], []
    for nombre, generar in (("catalogo.xml", _xml), ("catalogo.csv", _csv)):
        try:
            generar(db, os.path.join(temporal, nombre))
        except Exception as error:  # noqa: BLE001 — el base.dump ya está hecho
            log.exception("No se pudo generar %s", nombre)
            db.rollback()
            motivo = f"{type(error).__name__}: {error}"[:300]
            avisos.append(f"no se pudo generar {nombre} ({motivo})")
            detalle.append(AVISO_ARCHIVO.format(archivo=nombre, motivo=motivo))
    try:
        contenido, omitidos = intercambio_marc.exportar_iso2709_omitiendo(db)
        _escribir(os.path.join(temporal, "catalogo.mrc"), contenido)
    except Exception as error:  # noqa: BLE001
        log.exception("No se pudo generar catalogo.mrc")
        db.rollback()
        omitidos, motivo = [], f"{type(error).__name__}: {error}"[:300]
        avisos.append(f"no se pudo generar catalogo.mrc ({motivo})")
        detalle.append(AVISO_ARCHIVO.format(archivo="catalogo.mrc", motivo=motivo))
    if omitidos:
        nombres = ", ".join(f"«{o['titulo']}» (registro {o['id']})" for o in omitidos[:5])
        if len(omitidos) > 5:
            nombres += f" y {len(omitidos) - 5} más"
        avisos.append(f"{len(omitidos)} registro(s) no caben en ISO 2709 y quedaron solo en "
                      f"catalogo.xml: {nombres}")
        detalle.append(AVISO_OMITIDOS.format(lista="\n".join(
            f"  - «{o['titulo']}» (registro {o['id']}): {o['motivo']}" for o in omitidos)))
    biblioteca = configuracion.leer(db, "biblioteca").get("nombre") or "Biblioteca"
    _escribir(os.path.join(temporal, "LEEME.txt"),
              LEEME.format(biblioteca=biblioteca, fecha=f"{a_local(momento):%d/%m/%Y %H:%M}",
                           avisos="".join(detalle)),
              "w", encoding="utf-8", newline="\r\n")
    return ("Atención: " + "; ".join(avisos))[:1000] if avisos else None


def _ponerle_nombre(destino: str, temporal: str, momento: datetime) -> str:
    base = f"shelfie-{a_local(momento):%Y%m%d-%H%M}"
    nombre, n = base, 1
    while os.path.exists(os.path.join(destino, nombre)):
        n += 1
        nombre = f"{base}-{n}"
    final = os.path.join(destino, nombre)
    os.rename(temporal, final)
    return final


def _clave_de_orden(nombre: str) -> tuple:
    sello, _, sufijo = nombre[len("shelfie-"):].partition("-")  # AAAAMMDD, HHMM[-N]
    hora, _, n = sufijo.partition("-")
    return sello, hora, int(n or 1)


def _rotar(destino: str, final: str) -> None:
    """Borra los respaldos más viejos y deja como máximo CONSERVAR, contando el recién
    hecho (`final`), que nunca se borra aunque el reloj del equipo esté atrasado y su
    nombre quede como el más viejo. Solo toca carpetas con nombre de respaldo."""
    nuevo = os.path.basename(final)
    otros = sorted((n for n in os.listdir(destino)
                    if n != nuevo and _NOMBRE_RESPALDO.match(n)
                    and os.path.isdir(os.path.join(destino, n))),
                   key=_clave_de_orden)
    sobran = len(otros) - (CONSERVAR - 1)
    for nombre in otros[:max(sobran, 0)]:
        shutil.rmtree(os.path.join(destino, nombre), ignore_errors=True)


def _limpiar_temporales(destino: str) -> None:
    """Quita las carpetas `.respaldo-*` de más de un día: un proceso cancelado las deja."""
    limite = time.time() - EDAD_DE_TEMPORAL_HUERFANO
    try:
        for nombre in os.listdir(destino):
            ruta = os.path.join(destino, nombre)
            if (nombre.startswith(".respaldo-") and os.path.isdir(ruta)
                    and os.path.getmtime(ruta) < limite):
                shutil.rmtree(ruta, ignore_errors=True)
    except OSError:
        log.exception("No se pudieron limpiar los temporales de %s", destino)


def _tamano(carpeta: str) -> int:
    return sum(os.path.getsize(os.path.join(raiz, f))
               for raiz, _, archivos in os.walk(carpeta) for f in archivos)


def _crear(db: Session, carpeta: Optional[str], momento: datetime) -> dict:
    cfg = configuracion.leer(db, "respaldo")
    destino = _sin_comillas(carpeta) or _sin_comillas(cfg.get("carpeta"))
    if not destino:
        raise ErrorDeRespaldo("No hay carpeta de respaldo configurada")
    if not os.path.isdir(destino):
        raise ErrorDeRespaldo(
            f"La carpeta de respaldo no existe o no está disponible: {destino}")
    _limpiar_temporales(destino)
    motivo = problema_pg_dump(cfg.get("pg_dump"))
    if motivo:  # guardado antes de esta regla, o a mano en la base: no se ejecuta
        raise ErrorDeRespaldo(f"{motivo}. Corrígelo en Configuración → Respaldo.")
    pg_dump = encontrar_pg_dump(cfg.get("pg_dump"))
    if not pg_dump:
        raise ErrorDeRespaldo(
            "No se encontró pg_dump. Indica su ruta en Configuración → Respaldo "
            "(en Windows suele estar en C:\\Program Files\\PostgreSQL\\<versión>\\bin).")
    try:
        temporal = tempfile.mkdtemp(prefix=".respaldo-", dir=destino)
    except OSError as error:
        raise ErrorDeRespaldo(f"No se puede escribir en la carpeta de respaldo: {error}")
    try:
        aviso = _armar(db, temporal, pg_dump, momento)
        final = _ponerle_nombre(destino, temporal, momento)
    except BaseException:
        shutil.rmtree(temporal, ignore_errors=True)
        raise
    try:
        _rotar(destino, final)
    except OSError:  # la copia ya está hecha: una rotación fallida no la invalida
        log.exception("No se pudo rotar los respaldos de %s", destino)
    return {"carpeta_creada": final, "tamano": _tamano(final), "aviso": aviso}


def _tamano_legible(bytes_: int) -> str:
    return f"{bytes_ / 1024 / 1024:.1f} MB" if bytes_ >= 1024 * 1024 else f"{bytes_ / 1024:.0f} KB"


def ejecutar(db: Session, *, carpeta: Optional[str] = None,
             ahora: Optional[datetime] = None) -> dict:
    """Hace el respaldo y deja el resultado en la configuración y en el registro.

    Nunca lanza: cualquier fallo queda en `ok=False` con su mensaje. Un respaldo con el
    base.dump bueno pero algo incompleto en el catálogo es `ok=True` con `aviso`."""
    momento = a_utc(ahora or ahora_utc())
    try:
        hecho = _crear(db, carpeta, momento)
        resultado = {"ok": True, "carpeta_creada": hecho["carpeta_creada"],
                     "tamano": hecho["tamano"], "aviso": hecho["aviso"],
                     "mensaje": (f"Respaldo creado: {os.path.basename(hecho['carpeta_creada'])} "
                                 f"({_tamano_legible(hecho['tamano'])})")}
    except ErrorDeRespaldo as error:
        resultado = {"ok": False, "carpeta_creada": None, "tamano": None, "aviso": None,
                     "mensaje": str(error)}
    except Exception as error:  # noqa: BLE001 — este proceso es el último recurso
        log.exception("El respaldo falló")
        db.rollback()  # por si el fallo dejó la sesión en un estado inválido
        resultado = {"ok": False, "carpeta_creada": None, "tamano": None, "aviso": None,
                     "mensaje": f"Error inesperado: {type(error).__name__}: {error}"[:500]}
    _dejar_constancia(db, resultado, momento)
    return resultado


def _dejar_constancia(db: Session, resultado: dict, momento: datetime) -> None:
    fecha = momento.isoformat()
    cambios = {"ultimo": {"fecha": fecha, "ok": resultado["ok"],
                          "mensaje": resultado["mensaje"], "tamano": resultado["tamano"],
                          "aviso": resultado["aviso"]}}
    if resultado["ok"]:
        cambios["ultimo_ok"] = fecha  # si falló, el último correcto queda como estaba
    try:
        descripcion = (resultado["mensaje"] if resultado["ok"]
                       else f"Respaldo fallido: {resultado['mensaje']}")
        if resultado["aviso"]:
            descripcion += f". {resultado['aviso']}"
        registro.anotar(db, "respaldo", "respaldo", descripcion,
                        datos={"ok": resultado["ok"], "tamano": resultado["tamano"],
                               "carpeta": resultado["carpeta_creada"],
                               "aviso": resultado["aviso"]})
        configuracion.guardar(db, {"respaldo": cambios}, anotar=False)  # hace el commit
    except Exception:  # noqa: BLE001 — el respaldo ya se hizo (o falló): no se agrega otro error
        db.rollback()
        log.exception("No se pudo guardar el resultado del respaldo")
