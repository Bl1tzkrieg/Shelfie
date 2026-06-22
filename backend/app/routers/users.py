from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from app.database import SessionLocal
from app import models

router = APIRouter(prefix="/api/v1", tags=["Usuarios"])


# Dependencia para la base de datos
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Esquemas Pydantic para formatear la salida limpia hacia el Frontend
class CategoriaSchema(BaseModel):
    codigo: str
    descripcion: str

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    nro_carnet: str
    nombre: str
    apellido: str
    email: str
    activo: bool
    saldo_multas: float
    categoria: Optional[CategoriaSchema] = None
    prestamos_activos_count: int
    total_prestamos_count: int

    class Config:
        from_attributes = True


@router.get("/users", response_model=List[UserResponse])
def get_users(db: Session = Depends(get_db)):
    usuarios = db.query(models.Usuario).all()

    result = []
    for u in usuarios:
        # Contar préstamos activos (sin fecha de devolución registrada)
        activos = db.query(models.Prestamo).filter(
            models.Prestamo.usuario_id == u.id,
            models.Prestamo.fecha_devolucion == None
        ).count()

        # Contar el histórico total de préstamos
        total = db.query(models.Prestamo).filter(
            models.Prestamo.usuario_id == u.id
        ).count()

        # SOLUCIÓN: Buscamos manualmente la categoría usando el id si la relación no existe
        categoria_obj = None
        if hasattr(u, "categoria_id") and u.categoria_id:
            categoria_obj = db.query(models.CategoriaUsuario).filter(
                models.CategoriaUsuario.id == u.categoria_id
            ).first()

        result.append({
            "nro_carnet": u.nro_carnet,
            "nombre": u.nombre,
            "apellido": u.apellido,
            "email": u.email,
            "activo": u.activo,
            "saldo_multas": u.saldo_multas,
            "categoria": categoria_obj,  # Enviamos el objeto encontrado o None
            "prestamos_activos_count": activos,
            "total_prestamos_count": total
        })

    return result