"""Publicaciones seriadas: suscripciones, predicción, recepción y reclamos."""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.permisos import Permiso
from app.database import get_db
from app.security import requiere
from app.services import registro, seriadas

SERIADAS = requiere(Permiso.SERIADAS)

router = APIRouter(prefix="/api/v1/serials", tags=["Publicaciones Seriadas"],
                   dependencies=[Depends(SERIADAS)])


@router.get("/suppliers")
def proveedores(db: Session = Depends(get_db)):
    """Proveedores activos para elegir en una suscripción (sin exigir el permiso de adquisiciones)."""
    return [{"id": p.id, "nombre": p.nombre, "email": p.email}
            for p in db.query(models.Proveedor).filter(models.Proveedor.activo == True)  # noqa: E712
            .order_by(models.Proveedor.nombre)]


@router.get("/subscriptions")
def listar_suscripciones(estado: Optional[str] = None, db: Session = Depends(get_db)):
    return seriadas.listar(db, estado)


@router.post("/subscriptions", status_code=201)
def crear_suscripcion(payload: schemas.SuscripcionRequest, db: Session = Depends(get_db)):
    r = seriadas.crear(db, payload.model_dump(exclude_unset=True))
    _anotar(db, "suscripcion", f"Creó la suscripción de «{r['titulo']}»", r["id"], r.get("biblio_id"))
    return r


@router.post("/prediction")
def vista_previa(payload: schemas.PrediccionRequest):
    """Los próximos números que produciría el patrón (antes de guardar la suscripción)."""
    return seriadas.predecir(payload.frecuencia_unidad, payload.frecuencia_cada,
                             payload.numeracion, payload.numeros_por_volumen,
                             payload.volumen_inicial, payload.numero_inicial,
                             payload.primer_fasciculo, payload.cantidad)


@router.get("/subscriptions/{suscripcion_id}")
def get_suscripcion(suscripcion_id: int, db: Session = Depends(get_db)):
    """La suscripción con su kardex de fascículos."""
    return seriadas.obtener(db, suscripcion_id)


@router.put("/subscriptions/{suscripcion_id}")
def actualizar_suscripcion(suscripcion_id: int, payload: schemas.SuscripcionRequest,
                           db: Session = Depends(get_db)):
    r = seriadas.actualizar(db, suscripcion_id, payload.model_dump(exclude_unset=True))
    _anotar(db, "suscripcion", f"Editó la suscripción de «{r['titulo']}»", suscripcion_id,
            r.get("biblio_id"), datos=payload.model_dump(exclude_unset=True, mode="json"))
    return r


@router.post("/subscriptions/{suscripcion_id}/cancel")
def cancelar_suscripcion(suscripcion_id: int, db: Session = Depends(get_db)):
    r = seriadas.cancelar(db, suscripcion_id)
    _anotar(db, "suscripcion", f"Canceló la suscripción de «{r['titulo']}»", suscripcion_id,
            r.get("biblio_id"))
    return r


@router.post("/subscriptions/{suscripcion_id}/renew")
def renovar_suscripcion(suscripcion_id: int, payload: schemas.RenovarSuscripcionRequest,
                        db: Session = Depends(get_db)):
    r = seriadas.reactivar(db, suscripcion_id, payload.fecha_fin)
    _anotar(db, "suscripcion", f"Renovó la suscripción de «{r['titulo']}»"
            + (f" hasta el {payload.fecha_fin.isoformat()}" if payload.fecha_fin else ""),
            suscripcion_id, r.get("biblio_id"))
    return r


@router.post("/subscriptions/{suscripcion_id}/issues", status_code=201)
def registrar_fasciculo(suscripcion_id: int, payload: schemas.FasciculoRequest,
                        db: Session = Depends(get_db)):
    """Un número fuera del patrón (especial, suplemento) o de una suscripción irregular."""
    r = seriadas.registrar_fasciculo(db, suscripcion_id, payload.model_dump())
    _anotar(db, "fasciculo", f"Registró el número {payload.numero} fuera del patrón en "
            f"{_suscripcion(db, suscripcion_id)}", suscripcion_id)
    return r


@router.post("/issues/{fasciculo_id}/receive")
def recibir_fasciculo(fasciculo_id: int, payload: Optional[schemas.RecibirFasciculoRequest] = None,
                      db: Session = Depends(get_db), actor: models.Usuario = Depends(SERIADAS)):
    """Acusa recibo, da de alta el ejemplar y predice el siguiente número."""
    datos = payload.model_dump(exclude_unset=True) if payload else {}
    que = _fasciculo(db, fasciculo_id)
    r = seriadas.recibir_fasciculo(db, fasciculo_id, datos, actor.id)
    _anotar(db, "fasciculo", f"Recibió {que}", _sus_de(db, fasciculo_id))
    return r


@router.post("/issues/{fasciculo_id}/missing")
def marcar_faltante(fasciculo_id: int, payload: Optional[schemas.NotaRequest] = None,
                    db: Session = Depends(get_db)):
    que = _fasciculo(db, fasciculo_id)
    r = seriadas.marcar_faltante(db, fasciculo_id, payload.notas if payload else None)
    _anotar(db, "fasciculo", f"Marcó como faltante {que}", _sus_de(db, fasciculo_id))
    return r


@router.post("/issues/{fasciculo_id}/claim")
def reclamar(fasciculo_id: int, db: Session = Depends(get_db)):
    que = _fasciculo(db, fasciculo_id)
    r = seriadas.reclamar(db, fasciculo_id)
    _anotar(db, "fasciculo", f"Reclamó {que}", _sus_de(db, fasciculo_id))
    return r


@router.post("/suppliers/{proveedor_id}/claim")
def reclamar_al_proveedor(proveedor_id: int, suscripcion_id: Optional[int] = None,
                          db: Session = Depends(get_db)):
    """Un correo al proveedor con sus números atrasados (de una suscripción, o de todas)."""
    r = seriadas.reclamar_por_correo(db, proveedor_id, suscripcion_id=suscripcion_id)
    proveedor = db.get(models.Proveedor, proveedor_id)
    _anotar(db, "fasciculo", f"Reclamó por correo a {proveedor.nombre if proveedor else proveedor_id} "
            "los números atrasados", suscripcion_id)
    return r


@router.get("/issues/expected")
def por_recibir(db: Session = Depends(get_db)):
    """Lo que se espera de todas las suscripciones activas."""
    return seriadas.por_recibir(db)


@router.get("/issues/late")
def atrasados(db: Session = Depends(get_db)):
    """Fascículos atrasados (pasaron los días de gracia): lo que hay que reclamar."""
    return seriadas.atrasados(db)


@router.get("/issues/pending")
def fasciculos_pendientes(db: Session = Depends(get_db)):
    """Compatibilidad: lo mismo que /issues/expected."""
    return seriadas.por_recibir(db)


# --- Registro de acciones -------------------------------------------------------------

def _anotar(db: Session, accion: str, que: str, suscripcion_id: Optional[int] = None,
            biblio_id: Optional[int] = None, datos: Optional[dict] = None) -> None:
    if biblio_id is None and suscripcion_id:
        s = db.get(models.Suscripcion, suscripcion_id)
        biblio_id = s.biblio_id if s else None
    registro.anotar_y_guardar(db, "seriadas", accion, que, biblio=biblio_id, datos=datos,
                              objeto=("suscripcion", suscripcion_id) if suscripcion_id else None)


def _suscripcion(db: Session, suscripcion_id: int) -> str:
    s = db.get(models.Suscripcion, suscripcion_id)
    return f"«{s.titulo}»" if s else f"la suscripción {suscripcion_id}"


def _sus_de(db: Session, fasciculo_id: int) -> Optional[int]:
    f = db.get(models.Fasciculo, fasciculo_id)
    return f.suscripcion_id if f else None


def _fasciculo(db: Session, fasciculo_id: int) -> str:
    f = db.get(models.Fasciculo, fasciculo_id)
    if not f:
        return f"el fascículo {fasciculo_id}"
    return f"el número {f.numero} de {_suscripcion(db, f.suscripcion_id)}"
