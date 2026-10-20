# Shelfie-lite

Catálogo de biblioteca para las computadoras de una biblioteca universitaria: se ingresan los
libros con un formulario simple, se encuentran escribiendo lo que se recuerda de ellos y la
**cota** (el número que dice en qué lugar del estante está) aparece de inmediato.

## Por qué existe

La biblioteca llevaba su catálogo en un Koha alojado por un proveedor. Primero se perdieron
los datos con el robo de los servidores y después, cuando se dejó de pagar la suscripción,
volvieron a perderse. Lo que se improvisó en una lista de Word no sirve para buscar: devuelve
"mucha información que no necesito". Shelfie-lite resuelve tres cosas: ingreso sin saber MARC,
búsqueda que muestra el libro y su cota y nada más, y un respaldo diario que no depende de
nadie.

## Pantallas

| Ruta | Quién | Qué hace |
|---|---|---|
| `/` | Cualquiera | Buscar: caja grande, selector de campo y resultados con la cota destacada |
| `/libro?id=` | Cualquiera | Ficha con la cota y los ejemplares |
| `/login` | Personal | Inicio de sesión (la clave provisional se cambia al entrar) |
| `/ingreso` | Catalogador | Alta con «Guardar» y «Guardar y nuevo»; con `?id=`, edición y ejemplares |
| `/libros` | Catalogador | Lista en orden de estante; importar y exportar MARC, MARCXML y CSV |
| `/marc?id=` | Administrador | Editor MARC avanzado |
| `/usuarios` | Administrador | Crear personal, asignar rol, desactivar, restablecer clave |
| `/registro` | Administrador | Registro de acciones |
| `/configuracion` | Administrador | Datos de la biblioteca para Koha y respaldo |

Las rutas no usan segmentos `[id]`: el frontend es un sitio estático y el `id` va en `?id=`.

## Roles

| Rol | Permiso interno | Puede |
|---|---|---|
| Administrador | `superbibliotecario` | Todo |
| Catalogador | `catalogo` | Ingresar, editar, borrar, importar y exportar libros |
| Sin sesión | — | Buscar y ver fichas |

El primer administrador se crea con `python -m scripts.crear_admin` (lo hace el instalador).

## Búsqueda

Sin iniciar sesión, sobre título, autor, materia, editorial, cota e ISBN. Ignora acentos y
mayúsculas, exige todas las palabras y toma la última como prefijo, así que "bioquimica harp"
encuentra *Bioquímica de Harper*. La cota se escribe como sea ("616.39  h37") y se guarda y
busca normalizada ("616.39 H37"); "616.39" encuentra "616.39 H37". Con solo palabras vacías o
símbolos responde una lista vacía, nunca un error.

## Koha

Importa y exporta ISO 2709 y MARCXML. Por cada ejemplar se escribe un campo **952**:

| Subcampo | Contenido |
|---|---|
| `$a`, `$b` | Código de biblioteca (Configuración) |
| `$y` | Tipo de ítem (Configuración; por defecto `LIB`) |
| `$o` | Cota |
| `$p` | Código de barras, si existe |
| `$t` | Número de copia |
| `$z` | Nota |

Al importar se lee cada 952 como ejemplar. Si falta el 092, la cota sale del primer 952 `$o`
o, en su defecto, de 082 o 050; un registro sin ninguna sale como "Sin cota" al final de la
lista. Al editar con el formulario solo se tocan los campos del formulario: el resto del MARC
se conserva tal cual.

## Respaldo y restauración

Cada día se crea `shelfie-AAAAMMDD-HHMM/` en la carpeta elegida, con `base.dump`,
`catalogo.mrc`, `catalogo.xml`, `catalogo.csv` y `LEEME.txt`. Se conservan los 30 últimos. El
administrador ve un aviso rojo si el último respaldo correcto tiene más de 7 días o si el
último falló; también puede usar «Respaldar ahora» en Configuración. Cómo restaurar, con
`restaurar.ps1`, está en [`instalacion/LEEME.md`](instalacion/LEEME.md#restaurar-un-respaldo).

## Instalación

En Windows, con PostgreSQL 16+ y Python 3.12+: todo el procedimiento está en
[`instalacion/LEEME.md`](instalacion/LEEME.md). El servidor es un solo proceso en el puerto
8080 (la API en `/api/v1` y las páginas en el resto).

## Desarrollo

Requisitos: Python 3.12+, Node.js 20+ y PostgreSQL 16+. El entorno virtual va en la raíz del
repositorio (`.venv`, ignorado por git).

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows; en Linux/macOS: source .venv/bin/activate
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
cd backend
cp .env.example .env              # editar DATABASE_URL y SECRET_KEY
python -m scripts.inicializar_bd  # crea usuario y bases (<base> y <base>_test)
alembic upgrade head
python -m scripts.crear_admin
python -m uvicorn app.main:app --port 8000 --reload
```

Pruebas del backend (desde `backend/`), contra una base PostgreSQL dedicada que se borra y se
recrea:

```bash
TEST_DATABASE_URL=postgresql://usuario:clave@localhost:5432/shelfie_test python -m pytest -q
```

Frontend (desde `frontend/`):

```bash
npm install
cp .env.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000 (sin /api/v1)
npm run dev          # http://localhost:3000 (abrirlo con el mismo host que la API: localhost)
npm run typecheck
npm run lint
npm run build        # exporta el sitio estático a frontend/out
```

`frontend/next-env.d.ts` no se versiona: Next lo regenera en cada `dev` o `build`.

Recorrido de punta a punta (Playwright 1.56.0). Necesita `npm run build` hecho **sin** `NEXT_PUBLIC_API_URL`
(renombra `.env.local` mientras compilas: la prueba y la instalación usan el mismo origen) y una base
**exclusiva** cuyo nombre contenga `e2e`: **se borra entera en cada corrida**. Levanta uvicorn
en el puerto 8080 sirviendo `frontend/out`, crea el administrador y recorre ingreso, búsqueda
pública, edición sin cambios y respaldo.

```bash
createdb shelfie_e2e    # o créala desde pgAdmin
cd frontend
E2E_DATABASE_URL=postgresql://usuario:clave@localhost:5432/shelfie_e2e \
E2E_PYTHON=../.venv/bin/python npm run e2e
# PowerShell: $env:E2E_DATABASE_URL="..."; $env:E2E_PYTHON="..\.venv\Scripts\python.exe"; npm run e2e
```

`E2E_PYTHON` es el Python del `.venv` (por defecto `python` en Windows y `python3` en el
resto); `E2E_PG_DUMP` indica la ruta de `pg_dump` si no está en el PATH y `E2E_RESPALDO_DIR`
la carpeta donde la prueba hace su respaldo (por defecto, una temporal).

## Estructura

```
backend/
  app/
    core/         permisos, signaturas (cota), errores, plantillas MARC
    routers/      API: auth, libros, buscar, catalog (MARC), personal, settings, registro
    services/     reglas: ficha (formulario <-> MARC), libros, respaldo, importación/exportación
    estaticos.py  sirve frontend/out
  migrations/     0001_lite
  scripts/        crear_admin, inicializar_bd, respaldar, tareas
  tests/          pytest
frontend/
  app/            páginas (una carpeta por ruta)
  components/     lite/ (pantallas), layout/, auth/, ui/ (shadcn)
  e2e/            recorrido de Playwright
instalacion/      instalar.ps1, iniciar.ps1, restaurar.ps1, LEEME.md
scripts/          empaquetar.sh (arma el zip de instalación)
docs/             diseño y plan de Shelfie-lite
```
