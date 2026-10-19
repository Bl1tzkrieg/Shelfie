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
| **Avisos y tareas** | ✅ | `/api/v1/notices` — correos al lector (por vencer, vencido, reserva lista o expirada, recuperar contraseña) y reclamos a proveedores, con plantillas editables, cola con reintentos y tareas programadas |
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

El entorno virtual va en la raíz del repositorio (`.venv`, ignorado por git); los comandos
del backend se corren desde `backend/`, donde están `alembic.ini` y `.env`.

```bash
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# Linux / macOS
# source .venv/bin/activate

pip install -r backend/requirements.txt -r backend/requirements-dev.txt
cd backend
cp .env.example .env    # y editar DATABASE_URL y SECRET_KEY
```

En `.env`, `DATABASE_URL` apunta a la base **propia** de Shelfie con un usuario propio, p. ej.
`postgresql://shelfie:CLAVE@localhost:5432/shelfie`. No hace falta crearlos a mano: el
instalador los crea con una cuenta administradora (solo durante la instalación; no se guarda),
crea también `shelfie_test`, aplica las migraciones y opcionalmente carga datos de ejemplo:

```bash
python -m scripts.inicializar_bd --seed
# otra cuenta administradora:  --admin-user mi_admin
```

Es idempotente: correrlo de nuevo solo aplica las migraciones pendientes. Después de cada
`git pull` basta con `alembic upgrade head`.

> Base creada antes de la Fase 1 (con `create_all`): no correr el instalador ni `upgrade`;
> marcarla con `alembic stamp 0001_base` y verificar con `alembic check`.

Levantar la API:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload   # con el .venv activo, en backend/
```

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

> ⚠️ **`NEXT_PUBLIC_API_URL` debe incluir el prefijo `/api/v1`.** Sin él, todas las llamadas
> del frontend devuelven 404. `NEXT_PUBLIC_ZONA_HORARIA` (por defecto America/Caracas) tiene
> que coincidir con `ZONA_HORARIA` del backend. Las fuentes vienen en el paquete `geist`: el
> build no necesita internet.

### 4. Primer acceso a la intranet

Solo el **personal** entra a la intranet. Con `--seed` queda un superbibliotecario de ejemplo
(`douglas.worm` / `20260001`); como esa contraseña es el carnet, al entrar se pide elegir una
propia (lo mismo para cualquier usuario recién creado o con la contraseña restablecida).
En una instalación real, crea el tuyo:

```bash
python -m scripts.crear_admin
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

# Backend (con el .venv activo, en backend/)
python -m pytest

# Migraciones
alembic revision --autogenerate -m "describe el cambio"
alembic upgrade head
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
  dimensión con comodín "todas". Se aplica la más específica (sede > tipo > categoría; Koha
  pone la categoría antes que el tipo, aquí gana el tipo para que "no se presta" valga para todos).
- **Calendario** (`/api/v1/calendar`): días cerrados semanales y feriados. Un vencimiento que cae
  cerrado pasa al siguiente día hábil; multas y plazos de retiro cuentan días hábiles.
- **Vencimiento**: a las 23:59 del día, hora de `ZONA_HORARIA` (por defecto America/Caracas).
- **Deuda**: la cuenta del lector suma multas y reposiciones y resta pagos y condonaciones. Por
  encima de `umbral_bloqueo` (Configuración → circulación) no puede prestar, renovar ni reservar.
- **Reservas**: al volver un ejemplar se aparta para el primero de la cola que puede
  llevárselo (no suspendido, activo y con una regla que le permite ese tipo de ítem). Solo se
  reserva un título con algún ejemplar prestable, o que está en pedido o con suscripción. Si
  retira en otra sede, el ejemplar viaja allí (traslado) y el plazo de `dias_retiro_reserva`
  días hábiles corre desde que llega; si no lo retira, pasa al siguiente.
- **Sedes y traslados**: cada ejemplar tiene una sede propia y una actual. Quien opera elige
  su sede en la cabecera. Un ejemplar devuelto en otra sede vuelve a la suya, salvo que lo
  espere una reserva o que `retorno_a_sede_propia` esté apagado (colección flotante).
- **Pérdidas**: declarar perdido cobra la reposición y, si estaba vencido, la mora hasta ese
  día (salvo `perdonar_mora_al_perder`); si el ejemplar aparece, devolverlo reintegra lo que
  se pagó de la reposición (lo condonado o pendiente simplemente se anula).
- **Pagos**: un pago o condonación "en general" se aplica a los cargos más viejos primero;
  también se puede aplicar a un cargo concreto.
- **Ejemplares**: se corrigen o se dan de baja (estado *Retirado*: no se presta ni se reserva
  y conserva su historial) desde la ficha del registro. Solo se borra uno sin préstamos.

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
los subcampos de Koha ($p código de barras, $y tipo, $o signatura, $a/$b sede, $v precio,
$1 perdido, $0 retirado), así que un archivo exportado de Koha entra con sus ejemplares, y
viceversa. Al importar ISO 2709 se elige la codificación (por defecto se detecta: muchos
sistemas exportan UTF-8 sin marcarlo en el líder). Un registro con un campo de más de 9999
bytes no cabe en ISO 2709: se exporta en MARCXML.

## 🔐 Permisos del personal

| Permiso | Permite |
|---|---|
| `circulacion` | Préstamos, devoluciones, renovaciones, reservas, pérdidas y cobros |
| `catalogo` | Alta y edición de material |
| `lectores` | Alta, edición, suspensión, importación, exportación y condonación de deudas |
| `reportes` | Estadísticas y reportes |
| `configuracion` | Datos de la institución, políticas, avisos y tareas programadas |
| `adquisiciones` | Proveedores y órdenes de compra |
| `seriadas` | Suscripciones y fascículos |
| `registro` | Consultar el registro de acciones |
| `superbibliotecario` | Todo lo anterior y la gestión de permisos |

En catálogo, circulación, usuarios y configuración cualquier miembro del personal puede
**consultar**; para **modificar** necesita el permiso del módulo. Adquisiciones, seriadas y
reportes piden el permiso incluso para consultar (tienen datos de proveedores, montos y
lectores). El OPAC (`/api/v1/opac`) es público. Préstamos y devoluciones guardan quién
del personal los registró.

Cualquiera del personal puede operar "desde" cualquier sede (la elige en la cabecera), como
Koha sin *IndependentBranches*: la sede de trabajo dice dónde está físicamente, no restringe.

## 🕵️ Registro de acciones

Como los `action_logs` de Koha: cada operación anota quién la hizo, cuándo, desde qué IP y
sede, y sobre qué lector, registro o ejemplar, con el detalle (antes → después en las
ediciones, el MARC anterior al editar un registro, montos en los cobros). Se consulta en
**Registro** (permiso `registro`) y en el "Historial de cambios" de cada ficha.

- La anotación entra en la misma transacción que la operación: si la operación falla, no queda.
- Nunca se guardan contraseñas, tokens ni claves, aunque vengan en los datos.
- En **Registro → Qué se registra** (permiso `configuracion`) se apaga o enciende cada módulo y
  se fija cuántos días se guarda (730 por defecto; 0 = siempre). La tarea de limpieza borra lo
  más viejo. Cambiar estos ajustes siempre queda registrado.
- Lo hecho por un lector desde el OPAC (renovar, reservar) se marca "desde el OPAC"; lo que
  hacen las tareas programadas figura como "Sistema".

## 🔒 Contraseñas y sesiones

- **Contraseña provisional**: la del alta (el carnet) o la que pone el personal al
  restablecerla. Al entrar con ella se pide elegir otra y la API no deja hacer nada más hasta
  cambiarla (`seguridad.forzar_cambio_clave` en la tabla `configuraciones` para apagarlo).
- **Intentos fallidos**: 5 por usuario o 30 por IP en 15 minutos y el login responde 429 hasta
  que pase el plazo (`seguridad.max_intentos`, `seguridad.minutos_bloqueo`).
- **Salir** anula el token en el servidor (`sesiones_cerradas`): una cookie copiada deja de
  servir. Cambiar la contraseña cierra las demás sesiones.
- **`SECRET_KEY`**: con `ENTORNO=produccion` (o `COOKIE_SECURE=true`) el backend no arranca si
  es el valor de ejemplo o tiene menos de 32 caracteres. Genera una con
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

## ✉️ Avisos por correo y tareas programadas

Los avisos se arman con su plantilla cuando ocurre algo (una reserva queda lista) o cuando una
tarea diaria lo detecta (préstamos por vencer o vencidos) y esperan en una **cola**. Desde ahí se
envían, con reintentos. Todo se ve y se edita en **Configuración → Avisos**: la cola, las
plantillas y cuándo se avisa.

**Cómo sale el correo** (`backend/.env`):

| `CORREO_MODO` | Qué pasa |
|---|---|
| `archivo` (por defecto) | Cada correo se guarda como `.eml` en `backend/correo_saliente/`. Se abre con Outlook o Thunderbird. Ideal para probar. |
| `smtp` | Se envía con `SMTP_HOST`, `SMTP_PUERTO`, `SMTP_USUARIO`, `SMTP_CLAVE` y `SMTP_SEGURIDAD` (`starttls`, `ssl` o `ninguno`). |
| `desactivado` | No sale nada: los avisos quedan en la cola. |

`URL_PUBLICA` es la dirección del frontend que va en los enlaces (recuperar la contraseña).

**Tareas.** Con `TAREAS_AUTOMATICAS=true` (por defecto) el backend las corre solo: envía la cola
cada 2 minutos y las diarias una vez al día a partir de `HORA_TAREAS`. Si se corre con varios
procesos o se prefiere un cron, se apaga y se programa la consola:

```bash
python -m scripts.tareas              # las diarias y envía la cola
python -m scripts.tareas enviar_cola  # solo la cola (cada 5–15 minutos)
python -m scripts.tareas --lista
```

En Windows, con el Programador de tareas: acción `C:\ruta\Shelfie\.venv\Scripts\python.exe`,
argumentos `-m scripts.tareas` y "Iniciar en" la carpeta `backend`.

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
