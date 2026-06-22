from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models

router = APIRouter(prefix="/api/v1/catalog", tags=["Catálogo"])

@router.get("/items")
def get_all_items(db: Session = Depends(get_db)):
    items = db.query(models.Item).all()
    resultado = []
    for item in items:
        biblio = db.query(models.RegistroBibliografico).filter(models.RegistroBibliografico.id == item.biblio_id).first()
        resultado.append({
            "id": str(item.id),
            "title": biblio.titulo if biblio else "Sin título",
            "author": biblio.autor if biblio else "Autor desconocido",
            "isbn": biblio.isbn if biblio else "N/A",
            "status": item.estado.lower() if item.estado else "disponible",
            # Imagen de relleno genérica por ahora
            "coverImage": "https://images.unsplash.com/photo-1544947950-fa07a98d237f?q=80&w=200&auto=format&fit=crop"
        })
    return resultado


# Modifica la línea del decorador para que use la ruta exacta que busca el Front:
@router.get("/dashboard-stats", tags=["Métricas"])
def get_dashboard_stats(db: Session = Depends(get_db)):
    total_libros = db.query(models.Item).count()
    total_usuarios = db.query(models.Usuario).filter(models.Usuario.activo == True).count()

    try:
        # Nota rápida: Verifica si tu modelo Prestamo usa la propiedad 'status' o 'fecha_devolucion'
        total_prestamos = db.query(models.Prestamo).filter(models.Prestamo.status.in_(["active", "overdue"])).count()
    except AttributeError:
        # Si da error porque no existe la columna 'status', contamos los que no tienen fecha de devolución
        total_prestamos = db.query(models.Prestamo).filter(models.Prestamo.fecha_devolucion == None).count()

    return {
        "totalItems": total_libros,
        "totalUsers": total_usuarios,
        "activeLoans": total_prestamos,
    }