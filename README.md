# Shelfie 📚

**Shelfie** es un sistema para la gestión integrada de bibliotecas. Con un enfoque modular y
escalable, cubre la catalogación bibliográfica, los flujos transaccionales de circulación, las
adquisiciones, las publicaciones seriadas y un portal público de consulta.

## 🚀 Módulos del sistema

| Módulo | Estado | Endpoints |
|---|---|---|
| **Catalogación** | ✅ | `/api/v1/catalog` — registro MARC21 con plantillas y editor, importación/exportación MARC y MARCXML, búsqueda de texto completo con facetas, ejemplares, reservas |
| **Circulación** | ✅ | `/api/v1/circulation` — préstamo, devolución, renovación y pérdida sobre reglas de circulación, calendario y cuentas del lector; gestión de reservas (cola, suspensión, sede de retiro, para sacar del estante) y traslados entre sedes |
| **Usuarios (Socios)** | ✅ | `/api/v1/users` — CRUD, suspensión, historial, importación/exportación CSV |
| **Adquisiciones** | ✅ | `/api/v1/acquisitions` — presupuestos y fondos (comprometido, gastado, disponible), proveedores, pedidos, recepción parcial contra factura que da de alta ejemplares, pedidos atrasados y sugerencias de compra |
| **Publicaciones Seriadas** | ✅ | `/api/v1/serials` — suscripciones ligadas al catálogo, patrón de predicción (frecuencia y numeración Vol./Núm.), recepción que da de alta ejemplares, atrasos y reclamos |
| **Informes** | ✅ | `/api/v1/reports` — estadísticas y 5 reportes descargables en CSV |
| **OPAC** | ✅ | `/api/v1/opac` — catálogo público (`/opac`): búsqueda con facetas, ficha con disponibilidad por sede; cuenta del lector con préstamos, renovaciones, reservas, multas, historial, listas y sugerencias de compra |
| **Autenticación y permisos** | ✅ | `/api/v1/auth`, `/api/v1/staff` — login del personal con sesión en cookie httpOnly y permisos por módulo al estilo Koha |

## 🧱 Stack

- **Backend:** FastAPI + SQLAlchemy + PostgreSQL
- **Frontend:** Next.js 16 (App Router) + TypeScript + Tailwind + shadcn/ui
- **Autenticación:** PBKDF2 (librería estándar) + JWT (PyJWT) en cookie httpOnly

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

En `.env`, `DATABASE_URL` apunta a la base **propia** de Shelfie con un usuario propio, p. ej.
`postgresql://shelfie:CLAVE@localhost:5432/shelfie`. No hace falta crearlos a mano: el
instalador los crea con una cuenta administradora (solo durante la instalación; no se guarda),
crea también `shelfie_test`, aplica las migraciones y opcionalmente carga datos de ejemplo:

```bash
./venv/Scripts/python.exe -m scripts.inicializar_bd --seed
# otra cuenta administradora:  --admin-user mi_admin
```

Es idempotente: correrlo de nuevo solo aplica las migraciones pendientes. Después de cada
`git pull` basta con `alembic upgrade head`.

> Base creada antes de la Fase 1 (con `create_all`): no correr el instalador ni `upgrade`;
> marcarla con `alembic stamp 0001_base` y verificar con `alembic check`.

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

### 4. Primer acceso a la intranet

Solo el **personal** entra a la intranet. Con `--seed` queda un superbibliotecario de ejemplo
(`douglas.worm` / `20260001`). En una instalación real, crea el tuyo:

```bash
./venv/Scripts/python.exe -m scripts.crear_admin
```

Si el carnet ya existe, lo convierte en superbibliotecario. Desde ahí, en **Usuarios → ⋯ →
Acceso y permisos** se da acceso al resto del personal con un perfil (Administrador,
Bibliotecario, Auxiliar de circulación) o permiso por permiso.

> ⚠️ Abre el frontend con el **mismo host** que usa `NEXT_PUBLIC_API_URL` (`localhost` en
> ambos, no `localhost` en uno y `127.0.0.1` en el otro): el navegador los trata como sitios
> distintos y no enviaría la cookie de sesión. En producción con HTTPS, `COOKIE_SECURE=true`.

### 5. URLs

| Servicio | URL |
|---|---|
| Frontend (intranet) | http://localhost:3000 |
| Catálogo público (OPAC) | http://localhost:3000/opac |
| API | http://127.0.0.1:8000 |
| Documentación (Swagger) | http://127.0.0.1:8000/docs |

## 🧪 Comandos útiles

```bash
# Frontend
npm run typecheck   # tsc --noEmit
npm run lint        # ESLint
npm run build       # build de producción

# Backend
./venv/Scripts/python.exe -m pip install -r requirements-dev.txt
./venv/Scripts/python.exe -m pytest

# Migraciones
./venv/Scripts/alembic.exe revision --autogenerate -m "describe el cambio"
./venv/Scripts/alembic.exe upgrade head
```

Los tests corren contra un PostgreSQL real, en una base **dedicada** que se borra y se
reconstruye con las migraciones en cada corrida. Por defecto usan la gemela `<base>_test`
de la `DATABASE_URL` del `.env` (mismo usuario y clave; `inicializar_bd` la crea); se cambia
con la variable `TEST_DATABASE_URL`. Su nombre debe contener `test`. Si no hay conexión, la
suite se detiene con un solo mensaje claro en vez de fallar en cada prueba.

## 🗄️ Sobre el esquema de base de datos

El esquema lo administra **Alembic** (`backend/migrations/`). `backend/app/models.py` describe
las tablas y cada cambio en él se acompaña de una migración generada con
`alembic revision --autogenerate`. Un test (`tests/test_migraciones.py`) falla si los modelos y
las migraciones se desalinean.

El diseño original (`data.sql`) quedó en `docs/historico/` solo como referencia.

## 🔄 Cómo decide la circulación

Todo se ajusta en **Configuración → Reglas y calendario** (`/configuracion/circulacion`).

- **Reglas** (`/api/v1/circulation-rules`): categoría de lector × tipo de ítem × sede, cada
  dimensión con comodín "todas". Se aplica la más específica (sede > tipo > categoría).
- **Calendario** (`/api/v1/calendar`): días cerrados semanales y feriados. Un vencimiento que cae
  cerrado pasa al siguiente día hábil; multas y plazos de retiro cuentan días hábiles.
- **Vencimiento**: a las 23:59 del día, hora de `ZONA_HORARIA` (por defecto America/Caracas).
- **Deuda**: la cuenta del lector suma multas y reposiciones y resta pagos y condonaciones. Por
  encima de `umbral_bloqueo` (Configuración → circulación) no puede prestar, renovar ni reservar.
- **Reservas**: al volver un ejemplar se aparta para el primero de la cola no suspendido. Si
  retira en otra sede, el ejemplar viaja allí (traslado) y el plazo de `dias_retiro_reserva`
  días hábiles corre desde que llega; si no lo retira, pasa al siguiente.
- **Sedes y traslados**: cada ejemplar tiene una sede propia y una actual. Quien opera elige
  su sede en la cabecera. Un ejemplar devuelto en otra sede vuelve a la suya, salvo que lo
  espere una reserva o que `retorno_a_sede_propia` esté apagado (colección flotante).
- **Pérdidas**: declarar perdido cobra la reposición; si el ejemplar aparece, devolverlo
  acredita ese cargo (o deja saldo a favor si ya se había pagado).

## 🛒 Cómo funcionan las adquisiciones

- **Presupuesto → fondos**: un período con un monto total, repartido en fondos (por área,
  sede o colección). Nada se guarda como saldo: **comprometido** es lo pedido sin recibir al
  costo estimado, **gastado** es lo recibido al costo real más los envíos cargados al fondo, y
  **disponible** es lo asignado menos ambos. Una línea no puede comprometer más de lo disponible.
- **Pedido**: se arma abierto, se cierra al enviarlo al proveedor y desde entonces se recibe.
  Cada título queda en el catálogo desde que se pide (se puede reservar).
- **Recepción**: siempre contra una factura del proveedor, en parciales. Cada unidad es un
  ejemplar nuevo; si el título tiene reservas, queda apartado o viaja a la sede de retiro.
- **Atrasos**: un pedido cerrado con algo pendiente está atrasado cuando pasan los días de
  entrega del proveedor.

## 🔎 Cómo busca el catálogo

PostgreSQL indexa título, autor, materia e ISBN de cada registro (`registros_bibliograficos.busqueda`,
índice GIN) con la configuración `shelfie_es`: español, **sin acentos** y **por raíz**. Así
"arbol" encuentra "Árboles" y "garcia marq" encuentra "García Márquez" (la última palabra es
prefijo). Un ISBN con o sin guiones o un código de barras también funcionan. Requiere la
extensión `unaccent`, que viene con PostgreSQL y la migración `0006` crea sin superusuario.

## 📚 Catalogación MARC

El registro MARC21 es la fuente, como en Koha: título, autor, materia, año e ISBN se derivan
de él cada vez que se guarda. Hay cuatro plantillas (`app/core/marc_plantillas.py`): Libros,
Publicaciones seriadas, Tesis y trabajos de grado, y Recursos electrónicos. El "Agregar
Material" del catálogo sigue siendo el alta rápida (arma un MARC completo con esos datos);
"Catalogar" abre el editor.

Importar y exportar acepta ISO 2709 (.mrc) y MARCXML. Los ejemplares van en el campo 952 con
los subcampos de Koha ($p código de barras, $y tipo, $o signatura, $a/$b sede, $v precio),
así que un archivo exportado de Koha entra con sus ejemplares, y viceversa.

## 🔐 Permisos del personal

| Permiso | Permite |
|---|---|
| `circulacion` | Préstamos, devoluciones, renovaciones, reservas, pérdidas y cobros |
| `catalogo` | Alta y edición de material |
| `lectores` | Alta, edición, suspensión, importación, exportación y condonación de deudas |
| `reportes` | Estadísticas y reportes |
| `configuracion` | Datos de la institución y políticas |
| `adquisiciones` | Proveedores y órdenes de compra |
| `seriadas` | Suscripciones y fascículos |
| `superbibliotecario` | Todo lo anterior y la gestión de permisos |

Cualquier miembro del personal puede **consultar** la intranet; para **modificar** necesita el
permiso del módulo. El OPAC (`/api/v1/opac`) es público. Préstamos y devoluciones guardan quién
del personal los registró.

## 🌐 El OPAC y la cuenta del lector

En `/opac` cualquiera busca en el catálogo y ve en qué sede hay ejemplares libres; nunca quién
tiene un ejemplar prestado. Los lectores entran con su carnet (la clave inicial es el carnet)
y desde **Mi cuenta** renuevan, reservan eligiendo dónde retirar, pausan o cancelan reservas,
ven sus multas e historial, arman listas (privadas o públicas, con enlace para compartir) y
sugieren compras, que llegan a Adquisiciones.

La sesión del lector es **aparte** de la del personal: va en otra cookie (`shelfie_opac`) y
su token no sirve en la intranet, ni el de la intranet en el OPAC. Alguien del personal puede
entrar al OPAC como lector con su propio carnet sin abrir la intranet. Las reglas son las
mismas que en el mostrador (renovaciones permitidas, reservas en cola, deuda máxima); el OPAC
solo dice al lector, en sus palabras, por qué algo no se puede.

## 🧩 Estructura del backend

```
app/
├── routers/    # HTTP: validan la entrada y llaman a un servicio
├── services/   # Reglas de negocio y consultas (sin dependencias de HTTP)
├── core/       # Utilidades compartidas: errores de negocio, fechas, CSV
├── models.py   # Tablas (SQLAlchemy)
└── schemas.py  # Contratos de entrada/salida (Pydantic)
```

Los servicios lanzan `ReglaIncumplida` (400), `NoEncontrado` (404), etc. y `main.py` los
traduce a `{"detail": "..."}`, la misma forma que ya consume el frontend.

## 📋 Estado del proyecto

El archivo [`TODO.md`](./TODO.md) lleva el detalle de lo completado y lo pendiente, incluidas
las limitaciones conocidas de autenticación y las tareas de infraestructura.
