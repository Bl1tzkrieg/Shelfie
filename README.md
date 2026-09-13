# Shelfie 📚

**Shelfie** es un sistema para la gestión integrada de bibliotecas. Con un enfoque modular y
escalable, cubre la catalogación bibliográfica, los flujos transaccionales de circulación, las
adquisiciones, las publicaciones seriadas y un portal público de consulta.

## 🚀 Módulos del sistema

| Módulo | Estado | Endpoints |
|---|---|---|
| **Catalogación** | ✅ | `/api/v1/catalog` — alta de material, ficha por título, ejemplares, reservas |
| **Circulación** | ✅ | `/api/v1/circulation` — préstamo, devolución con multa automática, renovación, exportación |
| **Usuarios (Socios)** | ✅ | `/api/v1/users` — CRUD, suspensión, historial, importación/exportación CSV |
| **Adquisiciones** | ✅ | `/api/v1/acquisitions` — proveedores, órdenes de compra, recepción que alta ejemplares |
| **Publicaciones Seriadas** | ✅ | `/api/v1/serials` — suscripciones, kardex de fascículos, pendientes de reclamo |
| **Informes** | ✅ | `/api/v1/reports` — estadísticas y 5 reportes descargables en CSV |
| **OPAC** | ✅ | `/api/v1/opac` — búsqueda pública básica y avanzada, sin datos personales |
| **Autenticación** | ⚠️ Parcial | `/api/v1/auth` — login con hash PBKDF2 y tokens JWT; las rutas de intranet aún no exigen el token |

## 🧱 Stack

- **Backend:** FastAPI + SQLAlchemy + PostgreSQL
- **Frontend:** Next.js 16 (App Router) + TypeScript + Tailwind + shadcn/ui
- **Autenticación:** PBKDF2 (librería estándar) + JWT (PyJWT)

## 🔧 Instalación y despliegue local

### Requisitos

- Python 3.11+
- Node.js 20+
- PostgreSQL 14+ corriendo en `localhost:5432`

### 1. Clonar el repositorio

```bash
git clone https://github.com/TU_USUARIO/Shelfie.git
cd Shelfie
```

### 2. Backend

```bash
cd backend
python -m venv venv

# Windows
./venv/Scripts/python.exe -m pip install -r requirements.txt
# Linux / macOS
# source venv/bin/activate && pip install -r requirements.txt

cp .env.example .env    # y editar DATABASE_URL y SECRET_KEY
```

Las tablas se crean solas al arrancar (`Base.metadata.create_all`). Para cargar datos de
ejemplo:

```bash
./venv/Scripts/python.exe seed.py
```

Levantar la API:

```bash
./venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

> ⚠️ **`NEXT_PUBLIC_API_URL` debe incluir el prefijo `/api/v1`.** Sin él, todas las llamadas
> del frontend devuelven 404.

### 4. Acceso

| Servicio | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API | http://127.0.0.1:8000 |
| Documentación (Swagger) | http://127.0.0.1:8000/docs |

## 🧪 Comandos útiles

```bash
# Frontend
npm run typecheck   # tsc --noEmit
npm run lint        # ESLint
npm run build       # build de producción

# Backend
./venv/Scripts/python.exe -m pytest   # (aún sin tests)
```

## 🗄️ Sobre el esquema de base de datos

La fuente de verdad del esquema es **`backend/app/models.py`**: las tablas se crean desde ahí
con `Base.metadata.create_all()` al arrancar la aplicación.

`data.sql` es un script histórico que **no coincide** con lo que realmente crea la aplicación
(declara columnas que los modelos no tienen). Se conserva como referencia, pero no debe usarse
para inicializar la base. Migrar a Alembic es una tarea pendiente registrada en `TODO.md`.

## 📋 Estado del proyecto

El archivo [`TODO.md`](./TODO.md) lleva el detalle de lo completado y lo pendiente, incluidas
las limitaciones conocidas de autenticación y las tareas de infraestructura.
