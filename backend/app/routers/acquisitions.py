"""Adquisiciones: proveedores, presupuestos y fondos, pedidos, facturas y sugerencias."""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.errores import ReglaIncumplida
from app.core.permisos import Permiso
from app.database import get_db
from app.security import requiere
from app.services import adquisiciones, presupuestos, registro, sugerencias

ADQUIERE = requiere(Permiso.ADQUISICIONES)

router = APIRouter(prefix="/api/v1/acquisitions", tags=["Adquisiciones"],
                   dependencies=[Depends(ADQUIERE)])


def _datos(payload) -> dict:
    return payload.model_dump(exclude_unset=True)


@router.get("/summary")
def resumen(db: Session = Depends(get_db)):
    return adquisiciones.resumen(db)


# --- Proveedores ----------------------------------------------------------------------

@router.get("/suppliers")
def listar_proveedores(db: Session = Depends(get_db)):
    return adquisiciones.listar_proveedores(db)


@router.post("/suppliers", status_code=201)
def crear_proveedor(payload: schemas.ProveedorRequest, db: Session = Depends(get_db)):
    r = adquisiciones.crear_proveedor(db, _datos(payload))
    registro.anotar_y_guardar(db, "adquisiciones", "alta", f"Alta del proveedor {r['nombre']}", objeto=("proveedor", r["id"]))
    return r


@router.put("/suppliers/{proveedor_id}")
def actualizar_proveedor(proveedor_id: int, payload: schemas.ProveedorRequest,
                         db: Session = Depends(get_db)):
    r = adquisiciones.actualizar_proveedor(db, proveedor_id, _datos(payload))
    registro.anotar_y_guardar(db, "adquisiciones", "edicion", f"Editó el proveedor {r['nombre']}", objeto=("proveedor", proveedor_id))
    return r


@router.get("/suppliers/{proveedor_id}/receivable")
def por_recibir(proveedor_id: int, db: Session = Depends(get_db)):
    """Lo pendiente de todos los pedidos cerrados del proveedor."""
    return adquisiciones.por_recibir(db, proveedor_id)


# --- Presupuestos y fondos ------------------------------------------------------------

@router.get("/budgets")
def listar_presupuestos(db: Session = Depends(get_db)):
    return presupuestos.listar(db)


@router.post("/budgets", status_code=201)
def crear_presupuesto(payload: schemas.PresupuestoRequest, db: Session = Depends(get_db)):
    datos = _datos(payload)
    for campo in ("nombre", "fecha_inicio", "fecha_fin", "monto_total"):
        if datos.get(campo) is None:
            raise ReglaIncumplida(f"Falta {campo.replace('_', ' ')}")
    r = presupuestos.crear(db, datos)
    registro.anotar_y_guardar(db, "adquisiciones", "alta", f"Creó el presupuesto {payload.nombre} (Bs. {payload.monto_total:.2f})", objeto=("presupuesto", r.get("id")))
    return r


@router.get("/budgets/{presupuesto_id}")
def obtener_presupuesto(presupuesto_id: int, db: Session = Depends(get_db)):
    return presupuestos.obtener(db, presupuesto_id)


@router.put("/budgets/{presupuesto_id}")
def actualizar_presupuesto(presupuesto_id: int, payload: schemas.PresupuestoRequest,
                           db: Session = Depends(get_db)):
    r = presupuestos.actualizar(db, presupuesto_id, _datos(payload))
    registro.anotar_y_guardar(db, "adquisiciones", "edicion", f"Editó el presupuesto {r.get('nombre', presupuesto_id)}" + (" (bloqueado)" if r.get("bloqueado") else ""), datos=_datos(payload), objeto=("presupuesto", presupuesto_id))
    return r


@router.delete("/budgets/{presupuesto_id}")
def eliminar_presupuesto(presupuesto_id: int, db: Session = Depends(get_db)):
    nombre = presupuestos.obtener(db, presupuesto_id)["nombre"]
    presupuestos.eliminar(db, presupuesto_id)
    registro.anotar_y_guardar(db, "adquisiciones", "eliminacion", f"Eliminó el presupuesto {nombre}",
                              objeto=("presupuesto", presupuesto_id))
    return {"mensaje": "Presupuesto eliminado"}


@router.post("/budgets/{presupuesto_id}/funds", status_code=201)
def crear_fondo(presupuesto_id: int, payload: schemas.FondoRequest, db: Session = Depends(get_db)):
    r = presupuestos.crear_fondo(db, presupuesto_id, _datos(payload))
    registro.anotar_y_guardar(db, "adquisiciones", "alta", f"Creó el fondo {payload.codigo} (Bs. {payload.monto_asignado or 0:.2f}) en el presupuesto {presupuesto_id}", objeto=("presupuesto", presupuesto_id))
    return r


@router.get("/funds")
def fondos_para_pedir(db: Session = Depends(get_db)):
    """Fondos activos de presupuestos activos, con lo disponible."""
    return presupuestos.fondos_para_pedir(db)


@router.put("/funds/{fondo_id}")
def actualizar_fondo(fondo_id: int, payload: schemas.FondoRequest, db: Session = Depends(get_db)):
    r = presupuestos.actualizar_fondo(db, fondo_id, _datos(payload))
    registro.anotar_y_guardar(db, "adquisiciones", "edicion", f"Editó el fondo {payload.codigo or fondo_id}", datos=_datos(payload), objeto=("fondo", fondo_id))
    return r


@router.delete("/funds/{fondo_id}")
def eliminar_fondo(fondo_id: int, db: Session = Depends(get_db)):
    presupuestos.eliminar_fondo(db, fondo_id)
    registro.anotar_y_guardar(db, "adquisiciones", "eliminacion", f"Eliminó el fondo {fondo_id}",
                              objeto=("fondo", fondo_id))
    return {"mensaje": "Fondo eliminado"}


# --- Pedidos --------------------------------------------------------------------------

@router.get("/orders")
def listar_ordenes(estado: Optional[str] = None, proveedor_id: Optional[int] = None,
                   db: Session = Depends(get_db)):
    """`estado` acepta varios separados por coma (Abierta,Cerrada)."""
    return adquisiciones.listar_ordenes(db, estado, proveedor_id)


@router.post("/orders", status_code=201)
def crear_orden(payload: schemas.OrdenCompraRequest, db: Session = Depends(get_db),
                actor: models.Usuario = Depends(ADQUIERE)):
    datos = payload.model_dump()
    datos["lineas"] = [l.model_dump(exclude_unset=True) for l in payload.lineas]
    r = adquisiciones.crear_orden(db, datos, actor.id)
    registro.anotar_y_guardar(db, "adquisiciones", "pedido", f"Creó el pedido «{r['nombre']}» a {r['proveedor_nombre']} ({r['titulos']} títulos)", objeto=("pedido", r["id"]))
    return r


@router.get("/orders/late")
def pedidos_atrasados(db: Session = Depends(get_db)):
    return adquisiciones.atrasados(db)


@router.get("/orders/{orden_id}")
def obtener_orden(orden_id: int, db: Session = Depends(get_db)):
    return adquisiciones.obtener_orden(db, orden_id)


@router.put("/orders/{orden_id}")
def actualizar_orden(orden_id: int, payload: schemas.EditarOrdenRequest,
                     db: Session = Depends(get_db)):
    r = adquisiciones.actualizar_orden(db, orden_id, _datos(payload))
    registro.anotar_y_guardar(db, "adquisiciones", "pedido", f"Editó el pedido «{r['nombre']}»", objeto=("pedido", orden_id))
    return r


@router.post("/orders/{orden_id}/lines", status_code=201)
def agregar_linea(orden_id: int, payload: schemas.LineaOrdenRequest, db: Session = Depends(get_db)):
    r = adquisiciones.agregar_linea(db, orden_id, _datos(payload))
    registro.anotar_y_guardar(db, "adquisiciones", "pedido", f"Agregó un título al pedido «{r['nombre']}»", objeto=("pedido", orden_id))
    return r


@router.put("/orders/{orden_id}/lines/{linea_id}")
def actualizar_linea(orden_id: int, linea_id: int, payload: schemas.LineaOrdenRequest,
                     db: Session = Depends(get_db)):
    r = adquisiciones.actualizar_linea(db, orden_id, linea_id, _datos(payload))
    registro.anotar_y_guardar(db, "adquisiciones", "pedido", f"Cambió una línea del pedido «{r['nombre']}»", objeto=("pedido", orden_id))
    return r


@router.delete("/orders/{orden_id}/lines/{linea_id}")
def eliminar_linea(orden_id: int, linea_id: int, db: Session = Depends(get_db)):
    r = adquisiciones.eliminar_linea(db, orden_id, linea_id)
    registro.anotar_y_guardar(db, "adquisiciones", "pedido", f"Quitó un título del pedido «{r['nombre']}»", objeto=("pedido", orden_id))
    return r


@router.post("/orders/{orden_id}/lines/{linea_id}/cancel")
def cancelar_pendiente(orden_id: int, linea_id: int, db: Session = Depends(get_db)):
    """Lo que falta recibir de la línea ya no llega."""
    r = adquisiciones.cancelar_pendiente(db, orden_id, linea_id)
    registro.anotar_y_guardar(db, "adquisiciones", "pedido", f"Canceló lo pendiente de una línea del pedido «{r['nombre']}»", objeto=("pedido", orden_id))
    return r


@router.post("/orders/{orden_id}/close")
def cerrar_orden(orden_id: int, db: Session = Depends(get_db)):
    """Se envía al proveedor: desde ahora se recibe."""
    r = adquisiciones.cerrar_orden(db, orden_id)
    registro.anotar_y_guardar(db, "adquisiciones", "pedido", f"Cerró (envió) el pedido «{r['nombre']}» a {r['proveedor_nombre']}", objeto=("pedido", orden_id))
    return r


@router.post("/orders/{orden_id}/reopen")
def reabrir_orden(orden_id: int, db: Session = Depends(get_db)):
    r = adquisiciones.reabrir_orden(db, orden_id)
    registro.anotar_y_guardar(db, "adquisiciones", "pedido", f"Reabrió el pedido «{r['nombre']}»", objeto=("pedido", orden_id))
    return r


@router.post("/orders/{orden_id}/cancel")
def cancelar_orden(orden_id: int, db: Session = Depends(get_db)):
    r = adquisiciones.cancelar_orden(db, orden_id)
    registro.anotar_y_guardar(db, "adquisiciones", "pedido", f"Canceló el pedido «{r['nombre']}»", objeto=("pedido", orden_id))
    return r


# --- Facturas y recepción -------------------------------------------------------------

@router.get("/invoices")
def listar_facturas(proveedor_id: Optional[int] = None, abiertas: Optional[bool] = None,
                    db: Session = Depends(get_db)):
    return adquisiciones.listar_facturas(db, proveedor_id, abiertas)


@router.post("/invoices", status_code=201)
def crear_factura(payload: schemas.FacturaRequest, db: Session = Depends(get_db)):
    if payload.proveedor_id is None:
        raise ReglaIncumplida("Indica el proveedor de la factura")
    r = adquisiciones.crear_factura(db, _datos(payload))
    registro.anotar_y_guardar(db, "adquisiciones", "factura", f"Registró la factura {r['numero']} de {r['proveedor_nombre']}", objeto=("factura", r["id"]))
    return r


@router.get("/invoices/{factura_id}")
def obtener_factura(factura_id: int, db: Session = Depends(get_db)):
    return adquisiciones.obtener_factura(db, factura_id)


@router.put("/invoices/{factura_id}")
def actualizar_factura(factura_id: int, payload: schemas.FacturaRequest,
                       db: Session = Depends(get_db)):
    datos = _datos(payload)
    datos.pop("proveedor_id", None)
    r = adquisiciones.actualizar_factura(db, factura_id, datos)
    registro.anotar_y_guardar(db, "adquisiciones", "factura", f"Editó la factura {r['numero']}", objeto=("factura", factura_id))
    return r


@router.delete("/invoices/{factura_id}")
def eliminar_factura(factura_id: int, db: Session = Depends(get_db)):
    numero = adquisiciones.obtener_factura(db, factura_id)["numero"]
    adquisiciones.eliminar_factura(db, factura_id)
    registro.anotar_y_guardar(db, "adquisiciones", "factura", f"Eliminó la factura {numero}",
                              objeto=("factura", factura_id))
    return {"mensaje": "Factura eliminada"}


@router.post("/invoices/{factura_id}/close")
def cerrar_factura(factura_id: int, db: Session = Depends(get_db)):
    r = adquisiciones.cerrar_factura(db, factura_id, True)
    registro.anotar_y_guardar(db, "adquisiciones", "factura", f"Cerró la factura {r['numero']}", objeto=("factura", factura_id))
    return r


@router.post("/invoices/{factura_id}/reopen")
def reabrir_factura(factura_id: int, db: Session = Depends(get_db)):
    r = adquisiciones.cerrar_factura(db, factura_id, False)
    registro.anotar_y_guardar(db, "adquisiciones", "factura", f"Reabrió la factura {r['numero']}", objeto=("factura", factura_id))
    return r


@router.post("/invoices/{factura_id}/receive")
def recibir(factura_id: int, payload: schemas.RecepcionRequest, db: Session = Depends(get_db),
            actor: models.Usuario = Depends(ADQUIERE)):
    """Recibe unidades de una línea contra la factura y da de alta los ejemplares."""
    r = adquisiciones.recibir(db, factura_id, _datos(payload), actor.id)
    registro.anotar_y_guardar(db, "adquisiciones", "recepcion", f"Recibió {payload.cantidad or 'lo pendiente de'} la línea {payload.linea_id} con la factura {factura_id}", objeto=("factura", factura_id))
    return r


@router.delete("/receipts/{recepcion_id}")
def deshacer_recepcion(recepcion_id: int, db: Session = Depends(get_db)):
    r = adquisiciones.deshacer_recepcion(db, recepcion_id)
    registro.anotar_y_guardar(db, "adquisiciones", "recepcion", f"Deshizo la recepción {recepcion_id}", objeto=("recepcion", recepcion_id))
    return r


# --- Sugerencias ----------------------------------------------------------------------

@router.get("/suggestions")
def listar_sugerencias(estado: Optional[str] = None, db: Session = Depends(get_db)):
    return sugerencias.listar(db, estado)


@router.post("/suggestions", status_code=201)
def crear_sugerencia(payload: schemas.SugerenciaRequest, db: Session = Depends(get_db),
                     actor: models.Usuario = Depends(ADQUIERE)):
    return sugerencias.crear(db, _datos(payload), actor)


@router.post("/suggestions/{sugerencia_id}/accept")
def aceptar_sugerencia(sugerencia_id: int, payload: schemas.DecisionSugerenciaRequest,
                       db: Session = Depends(get_db), actor: models.Usuario = Depends(ADQUIERE)):
    r = sugerencias.decidir(db, sugerencia_id, True, payload.motivo, actor.id)
    registro.anotar_y_guardar(db, "adquisiciones", "sugerencia", f"Aceptó la sugerencia «{r['titulo']}»", objeto=("sugerencia", sugerencia_id))
    return r


@router.post("/suggestions/{sugerencia_id}/reject")
def rechazar_sugerencia(sugerencia_id: int, payload: schemas.DecisionSugerenciaRequest,
                        db: Session = Depends(get_db), actor: models.Usuario = Depends(ADQUIERE)):
    r = sugerencias.decidir(db, sugerencia_id, False, payload.motivo, actor.id)
    registro.anotar_y_guardar(db, "adquisiciones", "sugerencia", f"Rechazó la sugerencia «{r['titulo']}»" + (f": {payload.motivo}" if payload.motivo else ""), objeto=("sugerencia", sugerencia_id))
    return r


@router.post("/suggestions/{sugerencia_id}/order")
def pedir_sugerencia(sugerencia_id: int, payload: schemas.PedirSugerenciaRequest,
                     db: Session = Depends(get_db), actor: models.Usuario = Depends(ADQUIERE)):
    r = sugerencias.pedir(db, sugerencia_id, _datos(payload), actor.id)
    registro.anotar_y_guardar(db, "adquisiciones", "sugerencia", f"Pidió la sugerencia {sugerencia_id} en el pedido {payload.orden_id}", objeto=("sugerencia", sugerencia_id))
    return r
