from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.routers import (
    acquisitions,
    auth,
    catalog,
    circulation,
    opac,
    reports,
    serials,
    settings as settings_router,
    users,
)

Base.metadata.create_all(bind=engine)

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
)

app.include_router(auth.router)
app.include_router(circulation.router)
app.include_router(catalog.router)
app.include_router(users.router)
app.include_router(reports.router)
app.include_router(settings_router.router)
app.include_router(acquisitions.router)
app.include_router(serials.router)
app.include_router(opac.router)


@app.get("/")
def read_root():
    return {"status": "online", "system": "Shelfie API Gateway"}
