from fastapi import FastAPI
from app.config import settings
from app.database import engine, Base
from app.routers import circulation

# Comando automático para crear las tablas de base de datos si no existen al iniciar
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend transaccional modular para el sistema de automatización bibliotecaria Shelfie.",
    version="1.0.0"
)

# Inclusión de routers modulares
app.include_router(circulation.router)

@app.get("/")
def read_root():
    return {"status": "online", "system": "Shelfie API Gateway"}