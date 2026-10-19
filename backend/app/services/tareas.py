"""Tareas programadas (los cron jobs de Koha).

Cada tarea es una función `(db) -> dict` que hace su trabajo y devuelve un resumen.
Se corren de tres formas, y todas dejan registro en `ejecuciones_tarea`:

- **Automática**: un hilo del propio backend (TAREAS_AUTOMATICAS) envía la cola
  cada pocos minutos y corre las diarias una vez al día desde HORA_TAREAS.
- **Desde la intranet**: Configuración → Avisos → Tareas, botón "Ejecutar ahora".
- **Desde la consola**: `python -m scripts.tareas [diarias|enviar_cola|…]`, para
  programarla con cron o el Programador de tareas de Windows.

Las diarias son idempotentes: correrlas dos veces el mismo día no duplica avisos
(cada aviso lleva una `clave` con la fecha).
"""

import logging
import threading
import time
from datetime import timedelta
from typing import Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.core.errores import NoEncontrado
from app.core.tiempo import a_local, ahora, fecha_local, formatear_fecha, formatear_fecha_hora, hoy
from app.services import avisos, configuracion, reservas

log = logging.getLogger("shelfie.tareas")
E = models.EjecucionTarea
P = models.Prestamo

DEFAULTS_AVISOS = {
    # Días de atraso en que se manda el aviso de vencido (como los "triggers" de Koha).
    "dias_vencido": [1, 7, 14],
    # Reclamar solos los números atrasados de seriadas, y cada cuántos días insistir.
    "reclamos_automaticos": False,
    "dias_entre_reclamos": 15,
}


def ajustes(db: Session) -> dict:
    guardado = configuracion.leer(db, avisos.CLAVE_CONFIG)
    notif = configuracion.leer(db, "notificaciones")
    return {**DEFAULTS_AVISOS, **{k: guardado[k] for k in DEFAULTS_AVISOS if k in guardado},
            "recordatorio_dias_antes": int(notif.get("recordatorio_dias_antes") or 0)}


# --- Las tareas ---------------------------------------------------------------------------

def _linea(p, biblio, extra: str) -> str:
    return f"- {biblio.titulo} ({extra})"


def _prestamos_activos(db: Session):
    return db.query(P, models.Usuario, models.RegistroBibliografico).join(
        models.Usuario, models.Usuario.id == P.usuario_id).join(
        models.Item, models.Item.id == P.item_id).join(
        models.RegistroBibliografico, models.RegistroBibliografico.id == models.Item.biblio_id
    ).filter(P.fecha_devolucion == None, models.Usuario.activo == True).order_by(  # noqa: E711,E712
        P.fecha_vencimiento)


def recordatorios(db: Session) -> dict:
    """PREAVISO: un correo por lector con lo que vence dentro de N días."""
    dias = ajustes(db)["recordatorio_dias_antes"]
    if dias <= 0:
        return {"encolados": 0, "nota": "Recordatorio desactivado (0 días)"}
    objetivo = hoy() + timedelta(days=dias)
    por_lector: Dict[int, list] = {}
    for p, u, b in _prestamos_activos(db):
        if fecha_local(p.fecha_vencimiento) == objetivo:
            por_lector.setdefault(u.id, [u]).append(
                _linea(p, b, f"vence el {formatear_fecha(p.fecha_vencimiento)}"))
    encolados = 0
    for usuario_id, (u, *lineas) in por_lector.items():
        if avisos.para_lector(db, "PREAVISO", u, {"dias": dias, "prestamos": "\n".join(lineas)},
                              clave=f"PREAVISO:{u.id}:{hoy().isoformat()}"):
            encolados += 1
    db.commit()
    return {"encolados": encolados, "vencen_el": objetivo.isoformat()}


def vencidos(db: Session) -> dict:
    """VENCIDO: un correo por lector el día 1, 7, 14… de atraso de alguno de sus préstamos."""
    marcas = {int(d) for d in ajustes(db)["dias_vencido"] if int(d) > 0}
    por_lector: Dict[int, list] = {}
    for p, u, b in _prestamos_activos(db):
        atraso = (hoy() - fecha_local(p.fecha_vencimiento)).days
        if atraso > 0:
            entrada = por_lector.setdefault(u.id, {"usuario": u, "lineas": [], "toca": False})
            entrada["lineas"].append(_linea(
                p, b, f"venció el {formatear_fecha(p.fecha_vencimiento)}, "
                      f"{atraso} día{'s' if atraso != 1 else ''} de atraso"))
            entrada["toca"] = entrada["toca"] or atraso in marcas
    encolados = 0
    for e in por_lector.values():
        # El correo lista todos sus vencidos, pero solo sale si alguno cumple una marca hoy.
        if e["toca"] and avisos.para_lector(
                db, "VENCIDO", e["usuario"], {"prestamos": "\n".join(e["lineas"])},
                clave=f"VENCIDO:{e['usuario'].id}:{hoy().isoformat()}"):
            encolados += 1
    db.commit()
    return {"encolados": encolados, "lectores_con_vencidos": len(por_lector)}


def reservas_diarias(db: Session) -> dict:
    """Reanuda suspensiones, expira reservas vencidas (con su aviso) y libera ejemplares."""
    expiradas = reservas.expirar_vencidas(db)
    db.commit()
    return {"expiradas": expiradas}


def reclamos_seriadas(db: Session) -> dict:
    from app.services import seriadas

    a = ajustes(db)
    if not a["reclamos_automaticos"]:
        return {"reclamados": 0, "nota": "Reclamos automáticos apagados"}
    resultado: List[dict] = []
    proveedores = {x["proveedor_id"] for x in seriadas.atrasados(db)
                   if x["proveedor_id"] and x["proveedor_email"]}
    for proveedor_id in sorted(proveedores):
        r = seriadas.reclamar_por_correo(db, proveedor_id,
                                         dias_entre_reclamos=int(a["dias_entre_reclamos"]))
        if r["reclamados"]:
            resultado.append(r)
    return {"reclamados": sum(r["reclamados"] for r in resultado), "proveedores": resultado}


def limpieza(db: Session) -> dict:
    T = models.TokenClave
    viejos = db.query(T).filter(T.expira < ahora() - timedelta(days=1)).delete(
        synchronize_session=False)
    corridas = db.query(E).filter(E.inicio < ahora() - timedelta(days=90)).delete(
        synchronize_session=False)
    intentos = db.query(models.IntentoAcceso).filter(
        models.IntentoAcceso.fecha < ahora() - timedelta(days=1)).delete(synchronize_session=False)
    cerradas = db.query(models.SesionCerrada).filter(
        models.SesionCerrada.expira < ahora()).delete(synchronize_session=False)
    from app.services import registro
    acciones = registro.depurar(db)
    db.commit()
    return {"enlaces_borrados": viejos, "registros_borrados": corridas,
            "intentos_borrados": intentos, "sesiones_borradas": cerradas,
            "acciones_borradas": acciones}


def enviar_cola(db: Session) -> dict:
    return avisos.enviar_cola(db)


def diarias(db: Session) -> dict:
    """Todas las diarias en orden, y al final se envía la cola."""
    resultado = {}
    for nombre in ("reservas", "recordatorios", "vencidos", "reclamos_seriadas", "limpieza",
                   "enviar_cola"):
        resultado[nombre] = TAREAS[nombre]["funcion"](db)
    return resultado


TAREAS: Dict[str, dict] = {
    "diarias": {"nombre": "Todas las diarias", "funcion": diarias,
                "descripcion": "Reservas, recordatorios, vencidos, reclamos y limpieza; al final "
                               "envía la cola. Corre sola una vez al día."},
    "enviar_cola": {"nombre": "Enviar la cola de correos", "funcion": enviar_cola,
                    "descripcion": "Manda los avisos pendientes. Corre sola cada pocos minutos."},
    "reservas": {"nombre": "Reservas", "funcion": reservas_diarias,
                 "descripcion": "Reanuda las pausadas, expira las vencidas y avisa al lector."},
    "recordatorios": {"nombre": "Recordatorios de vencimiento", "funcion": recordatorios,
                      "descripcion": "Avisa lo que vence dentro de los días configurados."},
    "vencidos": {"nombre": "Avisos de vencidos", "funcion": vencidos,
                 "descripcion": "Avisa a quien tiene préstamos vencidos en los días de atraso "
                                "configurados."},
    "reclamos_seriadas": {"nombre": "Reclamos de seriadas", "funcion": reclamos_seriadas,
                          "descripcion": "Reclama por correo los números atrasados a cada "
                                         "proveedor (si está activado)."},
    "limpieza": {"nombre": "Limpieza", "funcion": limpieza,
                 "descripcion": "Borra enlaces de recuperación vencidos, intentos de acceso viejos, "
                                "corridas de tareas de más de 90 días y el registro de acciones "
                                "más viejo que su retención."},
}


# --- Ejecución y registro -------------------------------------------------------------------

def ejecutar(db: Session, nombre: str, origen: str = "manual") -> dict:
    if nombre not in TAREAS:
        raise NoEncontrado(f"No hay una tarea llamada {nombre}")
    corrida = E(tarea=nombre, inicio=ahora(), origen=origen)
    db.add(corrida)
    db.commit()
    try:
        resultado = TAREAS[nombre]["funcion"](db)
        corrida.ok, corrida.resultado = True, resultado
    except Exception as error:  # se registra y se informa; la siguiente corrida reintenta
        db.rollback()
        corrida = db.get(E, corrida.id)
        corrida.ok, corrida.error = False, f"{type(error).__name__}: {error}"[:2000]
        log.exception("Falló la tarea %s", nombre)
    corrida.fin = ahora()
    db.commit()
    return _vista_corrida(corrida)


def _vista_corrida(c: models.EjecucionTarea) -> dict:
    return {"id": c.id, "tarea": c.tarea, "origen": c.origen, "ok": c.ok,
            "inicio": formatear_fecha_hora(c.inicio), "fin": formatear_fecha_hora(c.fin),
            "segundos": round((c.fin - c.inicio).total_seconds(), 2) if c.fin else None,
            "resultado": c.resultado, "error": c.error}


def listar(db: Session) -> List[dict]:
    ultimas = {}
    for c in db.query(E).order_by(E.inicio.desc()).limit(300):
        ultimas.setdefault(c.tarea, c)
    return [{"clave": k, "nombre": v["nombre"], "descripcion": v["descripcion"],
             "ultima": _vista_corrida(ultimas[k]) if k in ultimas else None}
            for k, v in TAREAS.items()]


def historial(db: Session, limite: int = 50) -> List[dict]:
    return [_vista_corrida(c) for c in db.query(E).order_by(E.inicio.desc()).limit(limite)]


def automaticas() -> dict:
    return {"activas": settings.TAREAS_AUTOMATICAS, "hora_diarias": settings.HORA_TAREAS,
            "cada_minutos_cola": INTERVALO_COLA // 60}


# --- Planificador dentro del backend ------------------------------------------------------------

INTERVALO_COLA = 120  # segundos
_hilo: Optional[threading.Thread] = None
_detener = threading.Event()


def _hora_diarias() -> tuple:
    try:
        h, m = (int(x) for x in settings.HORA_TAREAS.split(":"))
        return h, m
    except ValueError:
        return 6, 0


def _toca_diarias(db: Session) -> bool:
    ahora_local = a_local(ahora())
    h, m = _hora_diarias()
    if (ahora_local.hour, ahora_local.minute) < (h, m):
        return False
    ultima = db.query(E).filter(E.tarea == "diarias", E.ok == True).order_by(  # noqa: E712
        E.inicio.desc()).first()
    return ultima is None or fecha_local(ultima.inicio) < hoy()


def _vuelta(fabrica: Callable[[], Session]) -> None:
    db = fabrica()
    try:
        if _toca_diarias(db):
            ejecutar(db, "diarias", origen="automatica")
        elif db.query(models.Aviso.id).filter(models.Aviso.estado == avisos.PENDIENTE).first():
            avisos.enviar_cola(db)
    except Exception:
        log.exception("Error en el planificador de tareas")
    finally:
        db.close()


def iniciar(fabrica: Callable[[], Session]) -> None:
    """Arranca el hilo del planificador (una vez por proceso)."""
    global _hilo
    if _hilo and _hilo.is_alive():
        return
    _detener.clear()

    def bucle():
        time.sleep(5)  # que el backend termine de arrancar
        while not _detener.is_set():
            _vuelta(fabrica)
            _detener.wait(INTERVALO_COLA)

    _hilo = threading.Thread(target=bucle, name="shelfie-tareas", daemon=True)
    _hilo.start()
    log.info("Tareas automáticas activas: cola cada %ss, diarias desde las %s",
             INTERVALO_COLA, settings.HORA_TAREAS)


def detener() -> None:
    _detener.set()


def guardar_ajustes(db: Session, datos: dict) -> dict:
    from app.core.errores import ReglaIncumplida

    if datos.get("recordatorio_dias_antes") is not None:
        configuracion.guardar(db, {"notificaciones": {
            "recordatorio_dias_antes": int(datos["recordatorio_dias_antes"])}})
    propios = {}
    if datos.get("dias_vencido") is not None:
        dias = sorted({int(d) for d in datos["dias_vencido"]})
        if any(d < 1 or d > 365 for d in dias) or len(dias) > 6:
            raise ReglaIncumplida("Los días de atraso van de 1 a 365, hasta 6 valores")
        propios["dias_vencido"] = dias
    for clave in ("reclamos_automaticos", "dias_entre_reclamos"):
        if datos.get(clave) is not None:
            propios[clave] = datos[clave]
    if propios:
        from app.services import registro
        anteriores = configuracion.leer(db, avisos.CLAVE_CONFIG)
        cambios = registro.diferencias(anteriores, {**anteriores, **propios}, campos=propios.keys())
        if cambios:
            registro.anotar(db, "configuracion", "ajustes",
                            f"Cambió los ajustes de avisos: {', '.join(cambios)}",
                            datos={"seccion": "avisos", "cambios": cambios})
        avisos._guardar_config(db, propios)
    return ajustes(db)
