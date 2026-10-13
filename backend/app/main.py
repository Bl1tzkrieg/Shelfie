from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.errores import ErrorDeNegocio
from app.routers import (
    acquisitions,
    auth,
    catalog,
    circulation,
    opac,
    opac_account,
    personal,
    politicas,
    reports,
    serials,
    settings as settings_router,
    users,
)

# El esquema lo administra Alembic (backend/migrations). Antes de arrancar:
#   alembic upgrade head

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



@app.exception_handler(ErrorDeNegocio)
def manejar_error_de_negocio(_request: Request, error: ErrorDeNegocio):
    """Traduce los errores de los servicios a la forma {"detail": ...} de FastAPI."""
    detalle = getattr(error, "errores", None) or error.mensaje
    return JSONResponse(status_code=error.status_code, content={"detail": detalle})


app.include_router(auth.router)
app.include_router(circulation.router)
app.include_router(catalog.router)
app.include_router(users.router)
app.include_router(reports.router)
app.include_router(settings_router.router)
app.include_router(acquisitions.router)
app.include_router(serials.router)
app.include_router(opac.router)
app.include_router(opac_account.router)
app.include_router(personal.router)
app.include_router(politicas.router)


@app.get("/")
def read_root():
    return {"status": "online", "system": "Shelfie API Gateway"}
