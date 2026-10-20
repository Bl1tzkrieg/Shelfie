from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.config import comprobar_clave_de_firma, settings
from app.core.errores import ErrorDeNegocio
from app.routers import (
    auth,
    catalog,
    libros,
    personal,
    registro as registro_router,
    settings as settings_router,
)

# El esquema lo administra Alembic (backend/migrations). Antes de arrancar:
#   alembic upgrade head

comprobar_clave_de_firma(settings)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend transaccional modular para el sistema de automatización bibliotecaria Shelfie.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Sin esto el navegador oculta el nombre de archivo de las descargas (CSV, MARC).
    expose_headers=["Content-Disposition"],
)



@app.exception_handler(IntegrityError)
def manejar_conflicto(_request: Request, error: IntegrityError):
    """Una restricción de la base que se coló (dos altas a la vez con el mismo código,
    un dato obligatorio vacío): 409 con un mensaje, no un 500 con la traza."""
    restriccion = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
    detalle = "Otro registro ya usa ese dato o falta un dato obligatorio: revisa y vuelve a intentar"
    if restriccion:
        detalle += f" ({restriccion})"
    return JSONResponse(status_code=409, content={"detail": detalle})


@app.exception_handler(ErrorDeNegocio)
def manejar_error_de_negocio(_request: Request, error: ErrorDeNegocio):
    """Traduce los errores de los servicios a la forma {"detail": ...} de FastAPI."""
    detalle = getattr(error, "errores", None) or error.detalle or error.mensaje
    return JSONResponse(status_code=error.status_code, content={"detail": detalle})


app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(libros.router)
app.include_router(personal.router)
app.include_router(registro_router.router)
app.include_router(settings_router.router)


@app.get("/")
def read_root():
    return {"status": "online", "system": "Shelfie API Gateway"}
