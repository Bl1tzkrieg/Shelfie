from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware # 1. Importar CORS
from app.config import settings
from app.database import engine, Base
from app.routers import catalog, circulation, users, reports

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend transaccional modular para el sistema de automatización bibliotecaria Shelfie.",
    version="1.0.0"
)

# 2. Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # Origen de tu Frontend en Next.js
    allow_credentials=True,
    allow_methods=["*"], # Permitir GET, POST, PUT, DELETE
    allow_headers=["*"],
)

app.include_router(circulation.router)
app.include_router(catalog.router)
app.include_router(users.router, tags=["users"])
app.include_router(reports.router, tags=["reports"])

@app.get("/")
def read_root():
    return {"status": "online", "system": "Shelfie API Gateway"}