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
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import settings
from app.core.csv import texto_csv
from app.core.tiempo import a_local, a_utc, ahora as ahora_utc
from app.services import configuracion, intercambio_marc, registro

log = logging.getLogger("shelfie.respaldo")

CONSERVAR = 30
DIAS_PARA_ALERTA = 7
TIEMPO_MAXIMO_PG_DUMP = 600  # segundos
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
"""


class ErrorDeRespaldo(Exception):
    """Un fallo previsto, con un mensaje que se le puede mostrar a la persona."""


def encontrar_pg_dump(configurado: Optional[str] = None, *,
                      base_windows: str = BASE_PG_WINDOWS) -> Optional[str]:
    """La ruta de pg_dump: la configurada si existe, luego el PATH y por último
    `Program Files\\PostgreSQL\\<versión>\\bin`, con la versión más alta."""
    if configurado and os.path.isfile(configurado):
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


def _armar(db: Session, temporal: str, pg_dump: str, momento: datetime) -> None:
    _volcar_base(pg_dump, os.path.join(temporal, "base.dump"))
    for formato, nombre in (("marc", "catalogo.mrc"), ("marcxml", "catalogo.xml")):
        contenido, _, _ = intercambio_marc.exportar(db, formato=formato)
        _escribir(os.path.join(temporal, nombre), contenido)
    csv = texto_csv(intercambio_marc.exportar_csv(db), columnas=intercambio_marc.COLUMNAS_CSV)
    _escribir(os.path.join(temporal, "catalogo.csv"), csv, "w", encoding="utf-8", newline="")
    biblioteca = configuracion.leer(db, "biblioteca").get("nombre") or "Biblioteca"
    _escribir(os.path.join(temporal, "LEEME.txt"),
              LEEME.format(biblioteca=biblioteca, fecha=f"{a_local(momento):%d/%m/%Y %H:%M}"),
              "w", encoding="utf-8", newline="\r\n")


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


def _rotar(destino: str) -> None:
    """Borra los respaldos más viejos y deja los últimos CONSERVAR. Solo toca carpetas
    con el nombre de un respaldo; lo demás que haya en la carpeta no se toca."""
    propios = sorted((n for n in os.listdir(destino)
                      if _NOMBRE_RESPALDO.match(n) and os.path.isdir(os.path.join(destino, n))),
                     key=_clave_de_orden)
    for nombre in propios[:-CONSERVAR]:
        shutil.rmtree(os.path.join(destino, nombre), ignore_errors=True)


def _tamano(carpeta: str) -> int:
    return sum(os.path.getsize(os.path.join(raiz, f))
               for raiz, _, archivos in os.walk(carpeta) for f in archivos)


def _crear(db: Session, carpeta: Optional[str], momento: datetime) -> dict:
    cfg = configuracion.leer(db, "respaldo")
    destino = (carpeta or cfg.get("carpeta") or "").strip()
    if not destino:
        raise ErrorDeRespaldo("No hay carpeta de respaldo configurada")
    if not os.path.isdir(destino):
        raise ErrorDeRespaldo(
            f"La carpeta de respaldo no existe o no está disponible: {destino}")
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
        _armar(db, temporal, pg_dump, momento)
        final = _ponerle_nombre(destino, temporal, momento)
    except BaseException:
        shutil.rmtree(temporal, ignore_errors=True)
        raise
    try:
        _rotar(destino)
    except OSError:  # la copia ya está hecha: una rotación fallida no la invalida
        log.exception("No se pudo rotar los respaldos de %s", destino)
    return {"carpeta_creada": final, "tamano": _tamano(final)}


def _tamano_legible(bytes_: int) -> str:
    return f"{bytes_ / 1024 / 1024:.1f} MB" if bytes_ >= 1024 * 1024 else f"{bytes_ / 1024:.0f} KB"


def ejecutar(db: Session, *, carpeta: Optional[str] = None,
             ahora: Optional[datetime] = None) -> dict:
    """Hace el respaldo y deja el resultado en la configuración y en el registro.

    Nunca lanza: cualquier fallo queda en `ok=False` con su mensaje."""
    momento = a_utc(ahora or ahora_utc())
    try:
        hecho = _crear(db, carpeta, momento)
        resultado = {"ok": True, "carpeta_creada": hecho["carpeta_creada"],
                     "tamano": hecho["tamano"],
                     "mensaje": (f"Respaldo creado: {os.path.basename(hecho['carpeta_creada'])} "
                                 f"({_tamano_legible(hecho['tamano'])})")}
    except ErrorDeRespaldo as error:
        resultado = {"ok": False, "carpeta_creada": None, "tamano": None, "mensaje": str(error)}
    except Exception as error:  # noqa: BLE001 — este proceso es el último recurso
        log.exception("El respaldo falló")
        db.rollback()  # por si el fallo dejó la sesión en un estado inválido
        resultado = {"ok": False, "carpeta_creada": None, "tamano": None,
                     "mensaje": f"Error inesperado: {type(error).__name__}: {error}"[:500]}
    _dejar_constancia(db, resultado, momento)
    return resultado


def _dejar_constancia(db: Session, resultado: dict, momento: datetime) -> None:
    fecha = momento.isoformat()
    cambios = {"ultimo": {"fecha": fecha, "ok": resultado["ok"],
                          "mensaje": resultado["mensaje"], "tamano": resultado["tamano"]}}
    if resultado["ok"]:
        cambios["ultimo_ok"] = fecha  # si falló, el último correcto queda como estaba
    try:
        registro.anotar(db, "respaldo", "respaldo",
                        resultado["mensaje"] if resultado["ok"]
                        else f"Respaldo fallido: {resultado['mensaje']}",
                        datos={"ok": resultado["ok"], "tamano": resultado["tamano"],
                               "carpeta": resultado["carpeta_creada"]})
        configuracion.guardar(db, {"respaldo": cambios}, anotar=False)  # hace el commit
    except Exception:  # noqa: BLE001 — el respaldo ya se hizo (o falló): no se agrega otro error
        db.rollback()
        log.exception("No se pudo guardar el resultado del respaldo")
