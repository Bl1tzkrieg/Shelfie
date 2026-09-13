# TODO — Shelfie

Estado al 2026-09-13, rama `features/adding_buttons`.

**Diagnóstico corto:** el frontend está maquetado completo y las 5 pantallas ya leen datos reales del
backend, pero **ningún botón de acción tiene handler**. De 22 `<Button>` en pantallas de negocio, solo
7 responden a clics (y los 7 son de UI local: cambiar pestaña, mostrar/ocultar filtros, cambiar vista).
Todo lo que escribe en la base de datos — prestar, devolver, renovar, crear, editar, suspender, exportar —
está sin conectar. Del lado del backend solo existen 2 endpoints de escritura (`checkout` y `checkin`)
y ninguno de los dos es alcanzable desde la UI.

---

## Cómo levantar el proyecto

```bash
# Backend (requiere PostgreSQL corriendo en :5432)
cd backend
python -m venv venv
./venv/Scripts/python.exe -m pip install -r requirements.txt
./venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

| Servicio | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API | http://127.0.0.1:8000 |
| Swagger | http://127.0.0.1:8000/docs |

`frontend/.env.local` debe contener `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1`
(el prefijo `/api/v1` es obligatorio; sin él todos los `fetch` dan 404).

---

## P0 — Bugs que rompen lo que ya existe ✅ COMPLETADO

Los 5 arreglos están aplicados y verificados. `npx tsc --noEmit` pasa limpio; sobre el código
original reportaba los dos bugs principales (`TS2554` en la línea del `print()` y `TS2740` por el
contrato de `BookCard`), así que **agregar el type-check a CI habría evitado ambos**.

- [x] **`print()` en vez de `console.error()`** — `frontend/app/catalogo/page.tsx`.
      `print` no existe en JavaScript: si el fetch fallaba, el `catch` lanzaba `ReferenceError`,
      nunca corría el `finally` y la página quedaba colgada en "Cargando catálogo…" para siempre.

- [x] **`BookCard` recibía props que no coincidían con su interfaz** — era la causa de que
      **todas las tarjetas salieran con "No disp." y el botón "Prestar" deshabilitado**.
      Resuelto extendiendo el esquema (decisión tomada: ver "Decisiones" más abajo).

- [x] **`CatalogFilters` restituido** — se eliminó el `<input disabled>` con el botón "Filtros"
      inerte y volvió el componente real. El buscador ahora **filtra de verdad** (client-side, por
      título, autor, ISBN y materia) y el toggle grid/lista funciona.
      Pendiente: los 4 `<Select>` del panel desplegable (categoría, tipo, disponibilidad, año)
      siguen sin estado — ver P1.

- [x] **`/circulation/loans` ahora devuelve `userType`, `renewals` y `returnDate`** —
      `backend/app/routers/circulation.py`. Esto elimina el **"Renovar (NaN restantes)"** del menú
      de cada fila y completa la columna Usuario.

- [x] **`<Toaster />` montado** — `frontend/app/layout.tsx`, usando `sonner`. Ya hay canal de
      feedback para enchufar las acciones de los botones.

---

## Decisiones tomadas

- **Catálogo por título, no por ejemplar.** `/catalog/items` ahora agrupa por registro
  bibliográfico y devuelve `copies` / `available` contando sus items. Cada tarjeta representa un
  título con su disponibilidad real.
- **Esquema extendido** (en lugar de recortar la tarjeta): se agregaron
  `registros_bibliograficos.ano_publicacion`, `registros_bibliograficos.materia` e
  `items.signatura_topografica`, con backfill de los 5 registros existentes.
- **`availableBarcode`** — `/catalog/items` expone el código de barras del primer ejemplar libre,
  que es lo que `/circulation/checkout` necesita para poder prestar desde la tarjeta.
- **Formularios como modales in-place**, no páginas dedicadas (ver P2).

---

## ⚠️ `data.sql` no refleja la base real

Descubierto al aplicar P0, y afecta cómo se hace cualquier cambio de esquema de acá en adelante.

Las tablas **no fueron creadas por `data.sql`**, sino por `Base.metadata.create_all()` desde
`models.py` (`backend/app/main.py`). Por eso la BD real tenía menos columnas que el script:
`data.sql` declara `renovaciones_realizadas`, `signatura_topografica`, `fecha_creacion`,
`biblioteca_origen_id`, `issn`, `precio_reposicion` y varias más que **no existían en PostgreSQL**.

- [x] Sincronizadas por `ALTER TABLE` las 4 columnas que necesitaba este trabajo
      (`prestamos.renovaciones_realizadas`, `registros_bibliograficos.ano_publicacion`,
      `registros_bibliograficos.materia`, `items.signatura_topografica`) y agregadas a `models.py`.
- [ ] **Decidir cuál es la fuente de verdad del esquema.** Hoy hay tres versiones distintas
      (`data.sql`, `models.py`, y lo que realmente está en PostgreSQL). Lo sano es adoptar Alembic
      y dejar `data.sql` como semilla histórica o borrarlo.
- [ ] **`seed.py` no puebla los campos nuevos** — los registros que cree quedarán sin
      `ano_publicacion`, `materia` ni `signatura_topografica`.
- [ ] **Columnas de `usuarios` que el frontend espera y no existen** — `app/usuarios/page.tsx` lee
      `u.departamento` y `u.fecha_registro`; ninguna de las dos está en la tabla real, por eso el
      departamento siempre cae al fallback y la fecha muestra "2026".

---

## P1 — Los botones ✅ COMPLETADO

Los 22 `<Button>` de pantallas de negocio tienen handler. Cada acción muestra confirmación o
error con un toast, y refresca el listado afectado.

### Circulación
- [x] **"Nuevo Préstamo"** — modal con carnet + código de barras → `POST /circulation/checkout`.
      Valida disponibilidad, tope de préstamos de la categoría y multas pendientes.
- [x] **"Registrar Devolución"** — confirmación → `POST /circulation/checkin`. Informa la multa
      aplicada y el nuevo estado del ejemplar.
- [x] **"Renovar"** — nuevo `POST /circulation/renew`. Respeta el tope configurable, rechaza
      si hay reservas en cola y extiende desde el vencimiento (o desde hoy si ya venció).
- [x] **"Exportar"** — nuevo `GET /circulation/loans/export`, CSV con BOM para Excel.
- [x] Buscador y filtros de la pantalla (estado, tipo de usuario) conectados.

### Catálogo
- [x] **"Agregar Material"** — modal → `POST /catalog/items`. Si el ISBN ya existe, suma un
      ejemplar al título en lugar de duplicarlo.
- [x] **"Prestar"** — usa `availableBarcode` y reutiliza `checkout`.
- [x] **"Reservar"** — nuevo `POST /catalog/reservations`, con cola por prioridad.
- [x] **Los 4 `<Select>` del panel de filtros** — conectados, y sus opciones se derivan del
      catálogo real en vez de estar hardcodeadas.

### Usuarios
- [x] **"Nuevo Usuario"** — modal → `POST /users`. Contraseña inicial = carnet.
- [x] **"Editar"** — `PUT /users/{carnet}`.
- [x] **"Suspender" / "Reactivar"** — `PATCH /users/{carnet}/status`. Rechaza la suspensión
      si el lector tiene préstamos sin devolver.
- [x] **"Ver Perfil"** — página `/usuarios/[id]` con ficha, métricas e historial.
- [x] **"Importar" / "Exportar"** — CSV en ambos sentidos; la importación informa fila por fila
      qué se omitió y por qué.
- [x] **Paginación** — 10 por página, con reseteo al filtrar.

### Reportes
- [x] **"Generar Reporte"** — los 3 selectores tienen estado y `GET /reports/generate` produce
      5 reportes (préstamos, devoluciones, vencidos, usuarios, catálogo) en CSV o JSON.
- [x] **"Descargar"** — cada tarjeta descarga su reporte; la lista sale de `/reports/available`
      con el número real de filas, en vez del "Hace 2 días" hardcodeado.

### Configuración
- [x] **"Guardar Cambios"** — la pantalla ahora carga de `GET /settings` y guarda con
      `PUT /settings`. Las políticas se sincronizan con `categorias_usuario`, que es lo que
      realmente consulta el checkout, así que se acabaron las dos verdades.

### Layout
- [x] **Campana de notificaciones** — abre un panel con los préstamos vencidos reales; el punto
      rojo solo aparece si hay alguno.
- [x] **Buscador global** — navega a `/catalogo?q=…`.

---

## P2 — Rutas 404 ✅ RESUELTO

**Decisión aplicada: modales in-place.** Las Acciones Rápidas del dashboard abren los mismos
diálogos que el resto de la app, así que las tres rutas de alta ya no hacen falta.

- [x] `/circulacion/nuevo`, `/usuarios/nuevo`, `/catalogo/nuevo` → resueltas con modales.
- [x] `/usuarios/[id]` → página creada (ficha + historial de préstamos).
- [x] `/catalogo/[id]` → página creada (ficha bibliográfica + tabla de ejemplares con estado).

---

## P3 — Mocks ✅ RESUELTO

- [x] **`RecentLoans`** ahora recibe los 5 movimientos más recientes.
- [x] **"Préstamos Vencidos"** — `dashboard-stats` devuelve `overdueLoans` calculado.
- [x] **`growth_percentage`** — comparación real contra el mes anterior.
- [x] **`loans_this_month`** — cálculo corregido.
- [x] **Datos de institución** — salen de la tabla `configuraciones`.
- [x] **`department`** — columna real `usuarios.departamento`, sin fallback inventado.
- [x] **Portadas genéricas** — se eliminó la URL de Unsplash falsa; las tarjetas usan un ícono.
      Queda pendiente un sistema real de portadas si se quiere.

---

## P4 — Módulos del README ✅ IMPLEMENTADOS

- [x] **Adquisiciones** — tablas `proveedores`, `ordenes_compra`, `lineas_orden`.
      `/api/v1/acquisitions`: alta de proveedores y órdenes, cancelación, y **recepción que
      da de alta los ejemplares en el catálogo automáticamente**.
- [x] **Publicaciones Seriadas** — tablas `suscripciones`, `fasciculos`.
      `/api/v1/serials`: suscripciones, kardex de fascículos, acuse de recibo y listado de
      pendientes (la base del reclamo a proveedores).
- [x] **OPAC** — `/api/v1/opac`: búsqueda básica y avanzada, ficha pública y listado de materias.
      No expone ningún dato personal de lectores.
- [x] **Reservas** — `POST /catalog/reservations` con cola por prioridad; `checkin` ya la consulta.

> ⚠️ **Estos módulos tienen API pero todavía no tienen pantalla en el frontend.** Son
> consumibles desde Swagger. Construir su UI es el siguiente bloque natural de trabajo.

---

## P5 — Autenticación ⚠️ PARCIAL

- [x] **Hashing real** — `app/security.py` con PBKDF2-SHA256 (260k iteraciones, librería
      estándar, sin dependencias nativas) y comparación en tiempo constante.
- [x] **Login** — `POST /auth/login` acepta username o carnet y emite un JWT (PyJWT, 12 h).
      Mismo mensaje de error para usuario inexistente y contraseña incorrecta.
- [x] **`GET /auth/me`** protegido con `HTTPBearer`; la dependencia `get_current_user` está lista.
- [x] **Contraseñas del seed corregidas** — ya no guardan el literal `pbkdf2:sha256...`.
      Los 5 usuarios existentes tienen como clave inicial su número de carnet.
- [x] **`SECRET_KEY` y `CORS_ORIGINS` parametrizados** por entorno.
- [x] **`backend/.env` sacado del control de versiones** (`git rm --cached`).
- [ ] **⚠️ Las rutas de intranet todavía NO exigen el token.** La maquinaria está completa,
      pero falta agregar `Depends(get_current_user)` a los routers y construir la pantalla de
      login en el frontend. **Hasta entonces la API sigue siendo pública.**
- [ ] **Rotar la contraseña de PostgreSQL** — estuvo versionada en el repo, así que debe
      considerarse comprometida. Requiere acción manual.

---

## P6 — Higiene del repo ✅ MAYORMENTE RESUELTO

- [x] **`.env.example`** en backend y frontend, con el prefijo `/api/v1` documentado.
- [x] **`.gitignore` raíz** — cubre `venv/`, `__pycache__/`, `.idea/`, `.env`, `node_modules/`.
- [x] **`__pycache__` sacado del repo** (estaba versionado).
- [x] **ESLint funcionando** — `eslint-config-next` 16 en flat config. `npm run lint` pasa con
      **0 errores**. Se agregó `npm run typecheck`.
- [x] **Marca unificada** — el paquete pasó de `my-project` a `shelfie-frontend`.
- [x] **README reescrito** — estaba cortado a mitad de un bloque de código; ahora documenta
      requisitos, los dos servicios, el seed y la advertencia de `data.sql`.
- [x] **`datetime.utcnow()` deprecado** — reemplazado por `datetime.now(timezone.utc)`.
- [x] **`seed.py` actualizado** — puebla los campos nuevos y usa hashes reales.
- [ ] **Alembic** — sigue pendiente; hoy el esquema se crea con `create_all()`.
- [ ] **Tests** — no hay pytest en backend ni tests de frontend. La suite E2E usada para validar
      (43 casos contra la API real) quedó fuera del repo, en el scratchpad.
- [ ] **`data.sql`** — decidir si se borra o se marca como histórico (ya está advertido en el README).

---

## Verificación

| Comprobación | Resultado |
|---|---|
| Suite E2E del backend (43 casos) | ✅ 43 OK / 0 fallas |
| `npm run typecheck` | ✅ sin errores |
| `npm run lint` | ✅ 0 errores (6 avisos justificados) |
| `npm run build` | ✅ 9 rutas compiladas |
| Páginas HTTP 200 | ✅ 9/9, incluidas las que antes daban 404 |
| Endpoints HTTP 200 | ✅ 12/12 verificados |

**No verificado:** no se ejecutó una prueba manual en navegador. Los flujos se validaron contra
la API real y por contrato de tipos, pero nadie hizo clic en los botones todavía.

---

## Qué sigue

1. **Proteger la API** — agregar `Depends(get_current_user)` a los routers de intranet y crear
   la pantalla de login. Es el único punto que impide desplegar fuera de local.
2. **Pantallas para Adquisiciones, Seriadas y OPAC** — la API está lista y sin UI.
3. **Rotar la contraseña de PostgreSQL** que estuvo versionada.
4. **Alembic** para dejar de depender de `create_all()`.
5. **Tests automatizados**, empezando por portar la suite E2E al repo.
