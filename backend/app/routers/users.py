from typing import Any, Dict, List

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.permisos import Permiso
from app.core.csv import respuesta_csv
from app.core.tiempo import sello_archivo
from app.database import get_db
from app.security import requiere, requiere_personal
from app.services import autenticacion, circulacion, cuentas, usuarios

router = APIRouter(prefix="/api/v1", tags=["Usuarios"],
                   dependencies=[Depends(requiere_personal)])

LECTORES = [Depends(requiere(Permiso.LECTORES))]


@router.get("/users", response_model=List[schemas.UserResponse])
def get_users(db: Session = Depends(get_db)):
    return usuarios.listar(db)


@router.post("/users", response_model=schemas.UserResponse, status_code=201,
             dependencies=LECTORES)
def crear_usuario(payload: schemas.NuevoUsuarioRequest, db: Session = Depends(get_db)):
    return usuarios.crear(db, payload)


@router.get("/users/{nro_carnet}", response_model=schemas.UserResponse)
def get_usuario(nro_carnet: str, db: Session = Depends(get_db)):
    return usuarios.vista_de_usuario(db, usuarios.obtener_por_carnet(db, nro_carnet))


@router.get("/users/{nro_carnet}/loans")
def get_prestamos_usuario(nro_carnet: str, db: Session = Depends(get_db)):
    """Historial de préstamos de un lector, para su ficha de perfil."""
    return circulacion.historial_de_lector(db, nro_carnet)


@router.get("/users/{nro_carnet}/account", response_model=schemas.EstadoCuentaResponse)
def estado_de_cuenta(nro_carnet: str, db: Session = Depends(get_db)):
    """Saldo y movimientos (multas, reposiciones, pagos, condonaciones) del lector."""
    return cuentas.estado_de_cuenta(db, usuarios.obtener_por_carnet(db, nro_carnet))


@router.post("/users/{nro_carnet}/account/payments", response_model=schemas.EstadoCuentaResponse)
def registrar_pago(nro_carnet: str, payload: schemas.PagoRequest, db: Session = Depends(get_db),
                   actor: models.Usuario = Depends(requiere(Permiso.CIRCULACION))):
    return cuentas.pagar(db, usuarios.obtener_por_carnet(db, nro_carnet), payload.monto,
                         payload.descripcion, actor.id, payload.cargo_id)


@router.post("/users/{nro_carnet}/account/waivers", response_model=schemas.EstadoCuentaResponse)
def condonar_deuda(nro_carnet: str, payload: schemas.CondonacionRequest,
                   db: Session = Depends(get_db),
                   actor: models.Usuario = Depends(requiere(Permiso.LECTORES))):
    """Perdona total o parcialmente la deuda. Exige motivo y el permiso de lectores."""
    return cuentas.condonar(db, usuarios.obtener_por_carnet(db, nro_carnet), payload.monto,
                            payload.motivo, actor.id, payload.cargo_id)


@router.put("/users/{nro_carnet}", response_model=schemas.UserResponse, dependencies=LECTORES)
def editar_usuario(
    nro_carnet: str, payload: schemas.EditarUsuarioRequest, db: Session = Depends(get_db)
):
    return usuarios.editar(db, nro_carnet, payload)


@router.patch("/users/{nro_carnet}/status", response_model=schemas.UserResponse,
              dependencies=LECTORES)
def cambiar_estado_usuario(
    nro_carnet: str, payload: schemas.EstadoUsuarioRequest, db: Session = Depends(get_db)
):
    return usuarios.cambiar_estado(db, nro_carnet, payload.activo)


@router.get("/users-export", dependencies=LECTORES)
def export_users(db: Session = Depends(get_db)):
    """Descarga el padrón de usuarios en CSV."""
    filas = usuarios.filas_padron(db)
    return respuesta_csv(
        filas,
        f"usuarios-{sello_archivo()}.csv",
        columnas=None if filas else ["nro_carnet"],
    )


@router.post("/users-import", dependencies=LECTORES)
def import_users(filas: List[Dict[str, Any]] = Body(..., max_length=20000),
                 db: Session = Depends(get_db)):
    """Cada fila se valida por separado: las inválidas se informan con su número."""
    return usuarios.importar(db, filas)


@router.get("/categories", response_model=List[schemas.CategoriaSchema])
def get_categorias(db: Session = Depends(get_db)):
    return usuarios.categorias(db)


@router.post("/users/{nro_carnet}/password", status_code=204)
def restablecer_clave(nro_carnet: str, payload: schemas.RestablecerClaveRequest,
                      db: Session = Depends(get_db),
                      actor: models.Usuario = Depends(requiere(Permiso.LECTORES))):
    """Fija una contraseña nueva (p. ej. si la olvidó). Cierra sus sesiones abiertas.

    La de un miembro del personal solo la restablece un superbibliotecario.
    """
    autenticacion.restablecer_clave(db, actor, usuarios.obtener_por_carnet(db, nro_carnet),
                                    payload.nueva)
