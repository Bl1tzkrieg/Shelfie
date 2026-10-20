# Shelfie-lite: plan de implementación

> **Para agentes:** sub-skill OBLIGATORIA: usar superpowers:subagent-driven-development (recomendado) o superpowers:executing-plans para implementar este plan tarea por tarea. Los pasos usan casillas (`- [ ]`) para el seguimiento.

**Objetivo:** convertir la rama `shelfie-lite` en un catálogo MARC mínimo con cuatro piezas: ingreso con formulario simple, búsqueda pública que muestra la cota, compatibilidad con Koha y respaldo diario. Todo se instala en una PC con Windows y se usa desde la red local.

**Arquitectura:** se recorta Shelfie (FastAPI + SQLAlchemy + PostgreSQL + Next.js). El núcleo que se queda es MARC, búsqueda, autenticación, registro de acciones y configuración. Lo nuevo es una capa "ficha" (formulario ↔ MARC), un servicio de libros, la búsqueda pública y el respaldo. El frontend se exporta como estático y lo sirve el mismo FastAPI: un proceso y un puerto.

**Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, pymarc, PostgreSQL 16; Next.js 16 (`output: "export"`), React 19, shadcn/ui; Playwright para el e2e; PowerShell para la instalación.

**Spec:** `docs/superpowers/specs/2026-10-20-shelfie-lite-design.md`. El que implementa lee el spec y este plan.

## Restricciones globales

- Toda la interfaz, los mensajes, los nombres de dominio y los comentarios en **español**, como en el resto del código.
- **Los commits los hace Ronald.** Cada "Checkpoint" consiste en sincronizar al repo (`~/Documents/Nueva carpeta (3)/Shelfie`, rama `shelfie-lite`), verificar con md5 y entregarle los comandos de `git add`/`commit`. Antes de sobrescribir un archivo del dispositivo se verifica que no cambió.
- No tocar la base `dev` de AIRTEK ni las bases de odoo. Las pruebas usan `<base>_test`.
- Se conservan las capas `routers → services → models`, el mapeo de `core/errores` (400/401/403/404/409/422/429) y el patrón `registro.anotar(...)` antes del commit del servicio.
- Roles: **Administrador** = `superbibliotecario`; **Catalogador** = `catalogo`. La búsqueda y la ficha pública van **sin autenticación**.
- Exportación a Koha: un 952 por ejemplar con `$a` y `$b` = código de biblioteca, `$y` = tipo de ítem (por defecto `LIB`), `$o` cota, `$p` código, `$t` copia y `$z` nota.
- Respaldo: carpeta `shelfie-AAAAMMDD-HHMM/` con `base.dump`, `catalogo.mrc`, `catalogo.xml`, `catalogo.csv` y `LEEME.txt`. Se conservan los **30** últimos. El aviso salta si el último respaldo correcto tiene **más de 7 días** o si el último falló.
- Servidor: puerto **8080**, base `shelfie_lite`, PostgreSQL 16 o más reciente, Python 3.12 o más reciente. Las rutas del frontend no usan segmentos `[id]`; se usa `?id=`.
- Comandos desde `backend/`: `python -m pytest -q` y `alembic upgrade head`. En el contenedor: `TEST_DATABASE_URL=…/shelfie_test`.

## Puntos de revisión

1. **Cota mal escrita** ("616.39  h37", con doble espacio y en minúsculas): se debe guardar normalizada ("616.39 H37"), encontrarse igual y ordenarse en su lugar del estante. → Tarea 4 (`test_cota_se_normaliza`) y Tarea 6 (`test_busca_cota_con_espacios_y_minusculas`).
2. **Registro importado sin 092, sin 952 y sin 082/050:** se importa igual con la cota vacía y en `/libros` aparece al final como "Sin cota", sin error. → Tarea 7 (`test_importa_sin_cota`) y Tarea 5 (`test_lista_sin_cota_al_final`).
3. **Registro con 260 y sin 264** (catalogación vieja o de Koha): el formulario muestra lugar, editorial y año desde 260, y al guardar actualiza ese 260 en su sitio, sin crear un 264 duplicado. → Tarea 4 (`test_edita_260_en_su_lugar`).
4. **Búsqueda solo con palabras vacías o símbolos** ("de la", "¿?", "-"): responde 200 con la lista vacía y nunca un 500 de `to_tsquery`. → Tarea 6 (`test_busqueda_sin_terminos_utiles`).
5. **Destino del respaldo no disponible** (pendrive desconectado, carpeta sin permisos) o `pg_dump` no encontrado: el respaldo queda como fallido con el mensaje, el aviso se enciende y la API no da 500. → Tarea 8 (`test_respaldo_destino_inexistente`, `test_respaldo_sin_pg_dump`).

---

## Mapa de archivos

**Backend que se elimina** (Tarea 1):

- Routers: `acquisitions`, `circulation`, `inventario`, `notices`, `opac`, `opac_account`, `politicas`, `reports`, `serials`, `users`.
- Servicios: `adquisiciones`, `avisos`, `calendario`, `circulacion`, `correo`, `cuenta_opac`, `cuentas`, `inventario`, `listas`, `opac`, `presupuestos`, `reglas`, `reportes`, `reservas`, `sedes`, `seriadas`, `sugerencias`, `traslados`, `usuarios`.
- Pruebas de esos módulos.
- En `scripts/tareas.py` queda solo la limpieza del registro.

**Backend nuevo:**

- `app/core/signaturas.py`: `normalizar_cota` y `clave_signatura`, movidos desde `inventario.py`.
- `app/services/ficha.py`: formulario ↔ MARC.
- `app/services/libros.py`: alta, edición, baja, duplicados y ejemplares.
- `app/routers/libros.py`: `/api/v1/books`.
- `app/routers/buscar.py`: `/api/v1/buscar`, pública.
- `app/services/respaldo.py` y `scripts/respaldar.py`.
- `app/estaticos.py`: sirve `frontend/out`.
- `migrations/versions/0001_lite.py`: reemplaza 0001–0016.

**Frontend que se elimina:** `adquisiciones/`, `circulacion/`, `inventario/`, `opac/`, `reportes/`, `seriadas/`, `configuracion/{avisos,circulacion,sedes}`, `catalogo/`, `usuarios/[id]`, los componentes asociados y `components/dashboard`.

**Frontend nuevo:** `app/page.tsx` (Buscar), `app/libro/page.tsx`, `app/ingreso/page.tsx`, `app/libros/page.tsx`, `app/marc/page.tsx`, `app/usuarios/page.tsx` (rehecho), `app/configuracion/page.tsx` (rehecho) y `components/lite/*`.

**Instalación:** `instalacion/instalar.ps1`, `iniciar.ps1`, `restaurar.ps1`, `LEEME.md` y `scripts/empaquetar.sh`.

---

### Tarea 0: Línea base

- [ ] **Paso 1:** En el contenedor, partir de la copia de trabajo sincronizada con `main` en c35c164+ (incluye el commit del inventario). Correr `python -m pytest -q`. Esperado: 409 passed.
- [ ] **Paso 2:** Confirmar en el dispositivo que `git branch --show-current` da `shelfie-lite` y que `git status` está limpio.

### Tarea 1: Recortar el backend

**Archivos:**

- Borrar: los routers, servicios y pruebas de la lista "Backend que se elimina".
- Modificar:
  - `app/main.py`: solo incluye `auth`, `catalog`, `personal`, `registro`, `settings`.
  - `app/services/catalogo.py`: sin `reservas`, sin `estadisticas_dashboard` y sin la lógica de estados de préstamo en `editar_ejemplar` y `eliminar_ejemplar`.
  - `app/services/autenticacion.py`: sin la recuperación de clave por correo (`avisos`).
  - `app/services/configuracion.py`: sin `politicas` ni `reglas`.
  - `app/security.py`: sin `sede_de_trabajo` ni `sedes`.
  - `app/routers/catalog.py`: sin reservas, `dashboard-stats` ni `sede_de_trabajo`.
  - `app/routers/settings.py`: sin `branches`.
  - `app/core/permisos.py`.
  - `app/services/registro.py`: `MODULOS` = `catalogo`, `configuracion`, `sesion`, `respaldo`.
  - `scripts/tareas.py`.
- Crear: `app/core/signaturas.py`.
- Prueba: `tests/test_permisos.py` (ajustar), `tests/test_signaturas.py`.

**Interfaces:**

- Produce:
  - `Permiso` con solo `CATALOGO = "catalogo"` y `SUPERBIBLIOTECARIO = "superbibliotecario"`.
  - `PERFILES = {"administrador": [SUPERBIBLIOTECARIO], "catalogador": [CATALOGO]}`.
  - `normalizar_cota(texto: str | None) -> str | None`: quita espacios de más, pasa a mayúsculas y convierte "" en None.
  - `clave_signatura(cota: str) -> str`: la misma que en `inventario.py`.

- [ ] **Paso 1: prueba que falla.** En `tests/test_signaturas.py`:
  - `test_normalizar_cota`: `normalizar_cota(" 616.39  h37 ") == "616.39 H37"` y `normalizar_cota("  ") is None`.
  - `test_clave_signatura_ordena_como_el_estante`: copiar la del inventario.
- [ ] **Paso 2:** `python -m pytest tests/test_signaturas.py -q`. Esperado: FAIL (no existe el módulo).
- [ ] **Paso 3:** Crear `core/signaturas.py` y borrar los módulos de la lista.
- [ ] **Paso 4:** Recorrer `grep -rn "from app.services import\|from app.services\.\|models\.\(Prestamo\|Reserva\|Traslado\|MovimientoCuenta\|Proveedor\|Suscripcion\|Inventario\|Aviso\|Lista\)" app scripts tests` hasta que no quede ninguna referencia a lo eliminado. Los modelos se quedan como están; se recortan en la Tarea 2.
- [ ] **Paso 5:** En `tests/test_permisos.py`, ajustar a los dos perfiles. Agregar `test_rutas_de_admin_rechazan_catalogador` para `PUT /api/v1/settings` y `GET /api/v1/logs`, que deben dar 403 con `como(["catalogo"])`.
- [ ] **Paso 6:** `python -m pytest -q`. Esperado: todo verde con las pruebas que quedan: auth, claves, catalogo, busqueda, marc, intercambio_marc, registro, seguridad, config, configuracion, permisos, signaturas y ejemplares. `python -c "import app.main"` corre sin errores.
- [ ] **Paso 7: Checkpoint.** `Shelfie-lite: quitar los módulos que lite no usa`.

### Tarea 2: Modelo y migración única

**Archivos:**

- Modificar:
  - `app/models.py`: borrar los modelos eliminados en la Tarea 1, además de `Biblioteca`, `CategoriaUsuario` y `TipoItem`.
  - `app/schemas.py`.
  - `app/services/personal.py`: ahora gestiona altas, roles, estado y clave.
  - `app/routers/personal.py`.
  - `app/services/autenticacion.py`: busca por `username`.
  - `scripts/crear_admin.py`, `scripts/inicializar_bd.py`, `seed.py`.
  - `tests/conftest.py`: `datos.personal`, `datos.titulo` y `datos.ejemplar(biblio, codigo=None, cota=None, copia=None)`.
- Borrar: `migrations/versions/0001…0016`.
- Crear: `migrations/versions/0001_lite.py`.
- Prueba: `tests/test_migraciones.py`, `tests/test_personal.py`.

**Interfaces:**

- Produce, con estos nombres de columna (los usan todas las tareas siguientes):
  - `RegistroBibliografico`: se agregan `editorial: Text|None`, `cota: String(100)|None` (normalizada), `creado_en` y `actualizado_en`. `EXPRESION_BUSQUEDA` suma `editorial` con peso C y `cota` con `'simple'` y peso D.
  - `Item` (tabla `items`): `id`, `biblio_id`, `codigo_barras: String(50)|None` (índice único parcial `WHERE codigo_barras IS NOT NULL`), `signatura_topografica: String(100)|None` (952 $o), `numero_copia: String(20)|None` (952 $t), `nota: Text|None` (952 $z) y `creado_en`.
  - `Usuario`: `id`, `username` (único), `password_hash`, `nombre`, `apellido`, `email|None`, `activo`, `permisos` (JSONB), `debe_cambiar_clave` y `fecha_creacion`.
  - `personal.listar(db) -> list[dict]`.
  - `personal.crear(db, *, username, nombre, apellido, rol: Literal["administrador","catalogador"], clave_temporal) -> dict`.
  - `personal.cambiar_rol(db, usuario_id, rol) -> dict`.
  - `personal.cambiar_estado(db, usuario_id, activo: bool) -> dict`.
  - `personal.restablecer_clave(db, usuario_id, clave_temporal) -> dict`, que deja `debe_cambiar_clave=True`.
  - Vista: `{id, username, nombre, apellido, rol, activo, debe_cambiar_clave}`.
  - Rutas de `/api/v1/staff` (solo administrador): `GET ""`, `POST ""`, `PUT /{id}/role`, `PUT /{id}/active` y `POST /{id}/password`.

- [ ] **Paso 1: pruebas que fallan.**
  - `tests/test_migraciones.py::test_lite_sube_y_baja`: en una base vacía, `upgrade head` crea exactamente las tablas `registros_bibliograficos`, `items`, `usuarios`, `configuraciones`, `registro_acciones`, `sesiones_cerradas`, `intentos_acceso`, `ejecuciones_tarea` y `alembic_version`; `downgrade base` las quita todas.
  - `tests/test_personal.py`:
    - `test_admin_crea_catalogador_y_debe_cambiar_clave`
    - `test_no_quedar_sin_administradores` (desactivar o degradar al último administrador da 400)
    - `test_catalogador_no_gestiona_personal` (403)
    - `test_dos_codigos_vacios_no_chocan` (dos `Item` con `codigo_barras=None` en el mismo título)
    - `test_codigo_repetido_da_409`
- [ ] **Paso 2:** Correrlas. Esperado: FAIL.
- [ ] **Paso 3:** Escribir los modelos. Escribir `0001_lite.py` a mano: la configuración de texto `shelfie_es` copiada de `0006`, las tablas, el índice GIN y el índice único parcial. `downgrade` debe dejar la base vacía.
- [ ] **Paso 4:** Reescribir `personal.py`, `autenticacion.buscar` (por `username`, solo `activo`), los scripts y `conftest.py`.
- [ ] **Paso 5:** `python -m pytest -q` en verde. `alembic upgrade head` sobre una base nueva `shelfie_lite_dev` en el contenedor.
- [ ] **Paso 6: Checkpoint.** `Shelfie-lite: modelo reducido y migración inicial única`. Avisarle a Ronald que debe crear una base nueva (`shelfie_lite`) para la rama.

### Tarea 3: Configuración lite

**Archivos:** `app/services/configuracion.py` y `app/routers/settings.py`. Prueba: `tests/test_configuracion.py`.

**Interfaces:**

- Produce estas secciones en `configuraciones`:
  - `biblioteca: {nombre: str, codigo: str = "BIB", tipo_item_koha: str = "LIB"}`
  - `respaldo: {carpeta: str|None, pg_dump: str|None, ultimo: {fecha, ok: bool, mensaje, tamano}|None, ultimo_ok: fecha|None}`
- `GET /api/v1/settings` es **público** y devuelve solo `biblioteca.nombre` cuando no hay sesión. `PUT` exige administrador.

- [ ] **Paso 1: pruebas que fallan.**
  - `test_nombre_publico_sin_sesion`: `anonimo.get(...)` da 200 y no incluye la clave `respaldo`.
  - `test_codigo_biblioteca_obligatorio`: `codigo` vacío da 422.
  - `test_guardar_registra_diferencias`
- [ ] **Paso 2:** FAIL. **Paso 3:** implementar. **Paso 4:** PASS con la suite completa.
- [ ] **Paso 5: Checkpoint.**

### Tarea 4: Ficha ↔ MARC

**Archivos:** crear `app/services/ficha.py`; en `app/schemas.py`, `FichaLibro`. Prueba: `tests/test_ficha.py`.

**Interfaces:**

- Produce:
  - `FichaLibro` (pydantic) con:
    - `cota: str` y `titulo: str`, obligatorios
    - `subtitulo`, `mencion`, `autor`, `edicion`, `lugar`, `editorial`, `descripcion` y `notas`: `str|None`
    - `otros_autores: list[str] = []`, `isbn: list[str] = []`, `materias: list[str] = []`
    - `ano: int|None`
    - `paginas`, `ilustraciones` y `dimensiones`: `str|None`
  - `ficha.a_marc(ficha: FichaLibro, marc_actual: dict | None) -> dict`
  - `ficha.desde_marc(marc: dict) -> FichaLibro`
  - `ficha.CAMPOS_DEL_FORMULARIO = {"020","092","100","245","250","260","264","300","500","520","650","700"}`
- Mapeo: el de la §6 del spec.
  - Indicadores: 245 `1` y `0`, o `0` y `0` si no hay autor. El segundo indicador cuenta un artículo inicial (`El `, `La `, `Los `, `Las `, `Lo `, `Un `, `Una `, `The `, `A `, `An `).
  - Sin autor (100), el 245 usa primer indicador 0.
  - 264 con indicadores ` 1`. 650 con ` 4`.
  - 008/07-10 = año. 092 se parte por el primer espacio en `$a` y `$b`.
- Regla para 260/264: si `marc_actual` tiene 260 y no tiene 264, se reescribe el 260; en cualquier otro caso se escribe el 264.

**Algoritmo de `a_marc`** (corregido en la revisión de la Tarea 4, para cumplir la "Regla clave" del spec §6):

- Sin `marc_actual`, se genera todo desde la plantilla BKS.
- Con `marc_actual`, se trabaja **por grupo** del formulario y solo cambia lo que el usuario cambió:
  - Si un grupo quedó igual a `desde_marc(marc_actual)`, sus campos originales no se tocan.
  - Si cambió un grupo de valor único (092, 100, 245, 250, la publicación, 300, 500, 520), se editan solo los subcampos que controla el formulario en la primera aparición del campo. Se conservan los demás subcampos, los indicadores y las apariciones siguientes.
  - Los grupos repetibles (020, 650, 700) se concilian por `$a`: los que siguen quedan intactos (con sus subdivisiones), los que se quitaron se borran y los nuevos se agregan.
  - En la publicación solo se toca el campo que leyó `desde_marc`; nunca se borra un 264 con segundo indicador distinto de 1.
- El resto del registro (cabecera, 008 salvo 07-10, 040, 082, 090, 856, 952…) se conserva tal cual.

- [ ] **Paso 1: pruebas que fallan.** En `tests/test_ficha.py`:
  - `test_ida_y_vuelta`: una ficha completa da `desde_marc(a_marc(f, None)) == f`.
  - `test_conserva_campos_ajenos`: un MARC con 082, 856 y 952 conserva esos tres campos idénticos después de `a_marc`.
  - `test_articulo_inicial`: "El túnel" da el segundo indicador de 245 = "3".
  - `test_edita_260_en_su_lugar`: un MARC con 260 y sin 264 queda con un solo 260 actualizado y ningún 264.
  - `test_cota_se_normaliza`: la cota " 616.39  h37 " da 092 `$a` "616.39" y `$b` "H37".
  - `test_vacios_no_generan_campos`: sin edición no hay 250; con `materias=[]` no hay 650.
- [ ] **Paso 2:** FAIL. **Paso 3:** implementar con `marc.py` y `marc_plantillas`. **Paso 4:** PASS.
- [ ] **Paso 5: Checkpoint.**

### Tarea 5: Servicio y API de libros

**Archivos:**

- Crear: `app/services/libros.py` y `app/routers/libros.py`.
- Modificar:
  - `app/services/catalogo.py`: `aplicar_marc` también deriva `editorial` (264/260 `$b`) y `cota` (092 `$a`+`$b`, normalizada).
  - `app/main.py`.
- Borrar del router `catalog.py`: `POST /items`, que lo reemplaza `/books`. `/catalog` queda solo para MARC (`/items/{id}/marc`, `/records`, `/frameworks`, `/import`, `/export`).
- Prueba: `tests/test_libros.py`.

**Interfaces:**

- Consume `ficha.a_marc` y `ficha.desde_marc` de la Tarea 4, y `normalizar_cota` y `clave_signatura` de la Tarea 1.
- Produce:
  - `libros.crear(db, ficha: FichaLibro, *, ejemplares: int = 1, nota_ejemplares: str|None = None, forzar: bool = False) -> dict`. Si hay posibles duplicados y `forzar` es falso, lanza `ReglaIncumplida` con el `detail` `{"codigo": "POSIBLE_DUPLICADO", "coincidencias": [{id, titulo, autor, cota}]}` y status 409.
  - `libros.actualizar(db, biblio_id, ficha: FichaLibro) -> dict`. Cambia la cota de los ejemplares que tenían la cota anterior del registro y deja intactos los que tienen una cota propia.
  - `libros.obtener(db, biblio_id) -> dict`: `{id, ficha, ejemplares: [{id, cota, codigo_barras, numero_copia, nota}], creado_en, actualizado_en}`.
  - `libros.listar(db, *, q: str = "", pagina: int = 1, por_pagina: int = 50) -> dict`. Orden: `clave_signatura(cota)`, con los registros sin cota al final.
  - `libros.eliminar(db, biblio_id) -> None`.
  - `libros.agregar_ejemplar(db, biblio_id, *, cota=None, codigo_barras=None, numero_copia=None, nota=None) -> dict`, más `editar_ejemplar` y `eliminar_ejemplar`.
  - `libros.posibles_duplicados(db, ficha, propio_id=None) -> list[dict]`: mismo ISBN (solo dígitos), o mismo título y autor normalizados (`lower` + `unaccent`).
  - Rutas `/api/v1/books` (todas exigen catalogador):
    - `GET ""` (`q`, `pagina`)
    - `POST ""` con `{ficha, ejemplares, nota_ejemplares, forzar}`, que responde 201
    - `GET /{id}`, `PUT /{id}`, `DELETE /{id}` (204)
    - `POST /{id}/copies`, `PATCH /{id}/copies/{item_id}`, `DELETE /{id}/copies/{item_id}`
  - Registro de acciones en el módulo `catalogo`, con las acciones `alta`, `edicion`, `baja` y `ejemplar`.

- [ ] **Paso 1: pruebas que fallan.** En `tests/test_libros.py`:
  - `test_crear_con_tres_ejemplares`: 3 items con la misma cota y copias c.1, c.2 y c.3.
  - `test_aviso_de_duplicado_y_forzar`: el mismo ISBN da 409 `POSIBLE_DUPLICADO`; con `forzar=true` da 201.
  - `test_editar_cambia_cota_de_ejemplares_que_la_heredaban`: un ejemplar con cota propia la conserva.
  - `test_lista_sin_cota_al_final`
  - `test_lista_ordena_como_el_estante`: 92 B < 630 R6 < 863 G2.
  - `test_borrar_pide_catalogador`: anónimo 401, administrador y catalogador 204.
  - `test_registra_acciones`
- [ ] **Paso 2:** FAIL. **Paso 3:** implementar. **Paso 4:** PASS con la suite completa.
- [ ] **Paso 5: Checkpoint.**

### Tarea 6: Búsqueda pública

**Archivos:** modificar `app/services/busqueda.py`. Crear `app/routers/buscar.py`. Prueba: `tests/test_busqueda.py` (se rehace).

**Interfaces:**

- Produce:
  - `busqueda.CAMPOS = ("todo", "titulo", "autor", "materia", "cota", "isbn", "editorial")`.
  - `busqueda.buscar(db, q: str, *, campo: str = "todo", pagina: int = 1, por_pagina: int = 20) -> dict`, que devuelve `{total, pagina, resultados: [{id, cota, titulo, subtitulo, autor, edicion, editorial, ano, ejemplares: int}]}`.
  - Sale de `Filtros` todo lo que es faceta, tipo o disponibilidad.
  - `GET /api/v1/buscar?q=&campo=&pagina=` y `GET /api/v1/buscar/{id}`, que devuelve `{ficha, ejemplares: [{cota, numero_copia, nota}]}` **sin** códigos de barras ni MARC. Las dos rutas van sin autenticación; un `campo` inválido da 400.
- Reglas:
  - `todo`: tsquery AND con la última palabra como prefijo (la función actual), **o** cota por prefijo (`cota ILIKE norm(q)||'%'`, o el mismo prefijo en `items.signatura_topografica`), **o** ISBN (con o sin guiones).
  - `titulo`, `autor`, `materia` y `editorial`: tsquery sobre esa columna.
  - `cota`: solo por prefijo.
  - `isbn`: solo por dígitos.
  - Orden: `ts_rank` y luego `clave_signatura`.
  - Si `_PALABRA` no encuentra términos y la consulta no es ni cota ni ISBN, devuelve `total=0` sin consultar.

- [ ] **Paso 1: pruebas que fallan.**
  - `test_todas_las_palabras`: "bioquimica harper" encuentra "Bioquímica de Harper" y no "Bioquímica general".
  - `test_sin_acentos_y_prefijo`: "bioqui" lo encuentra.
  - `test_por_cada_campo`: el autor "Harper" con `campo=titulo` no encuentra un título sin esa palabra.
  - `test_busca_cota_con_espacios_y_minusculas`: "616.39  h" encuentra "616.39 H37".
  - `test_isbn_con_guiones`
  - `test_busqueda_sin_terminos_utiles`: para "de la", "¿?" y "-", da 200 y `total == 0`.
  - `test_es_publica`: `anonimo` da 200.
  - `test_ficha_publica_sin_codigos`: la respuesta no contiene `codigo_barras`.
  - `test_campo_invalido`: 400.
- [ ] **Paso 2:** FAIL. **Paso 3:** implementar. **Paso 4:** PASS con la suite completa.
- [ ] **Paso 5: Checkpoint.**

### Tarea 7: Importar y exportar compatible con Koha

**Archivos:** modificar `app/services/intercambio_marc.py`. Prueba: `tests/test_intercambio_marc.py` (se rehace).

**Interfaces:**

- Consume la sección `biblioteca` de la configuración (Tarea 3) y `aplicar_marc` (Tarea 5).
- Produce:
  - `exportar(db, *, formato: Literal["marc","marcxml"], ids: list[int]|None = None) -> tuple[bytes, str, str]`, que devuelve contenido, tipo MIME y nombre de archivo.
  - `exportar_csv(db) -> list[dict]` con las columnas `cota, titulo, autor, editorial, ano, isbn, materias, ejemplares`.
  - `importar(...)` mantiene la firma y las políticas actuales (`omitir`, `reemplazar`, `agregar`).
  - Exportar: un 952 por item con `$a` y `$b` = `biblioteca.codigo`, `$y` = `biblioteca.tipo_item_koha`, `$o`, `$p` (si hay), `$t` (si hay) y `$z` (si hay).
  - Importar: cada 952 se lee como item con `$o`, `$p`, `$t` y `$z`. `$a`, `$b`, `$y` y `$1` se ignoran. Un 952 sin `$p` **no** se omite.
  - Cota del registro: 092, si no el primer 952 `$o`, si no 082 `$a`, si no 050 `$a`. Si el 092 falta, se escribe en el MARC.
- Ruta nueva `GET /api/v1/catalog/export.csv` (catalogador).

- [ ] **Paso 1: pruebas que fallan.** Para el archivo de muestra: `tests/datos/koha_muestra.py` construye con pymarc 3 registros al estilo de Koha (con 952 `$a`, `$b`, `$o`, `$p`, `$y`, uno con 260 y otro sin 092 pero con 082) y devuelve los bytes ISO 2709. Pruebas:
  - `test_ida_y_vuelta_koha`: importar y exportar da los mismos 245, 100, 020, 650 y los mismos 952 `$o`, `$p` y `$t` por registro.
  - `test_952_sin_codigo_se_importa`
  - `test_cota_desde_082`
  - `test_importa_sin_cota`: un registro sin 092, 952, 082 ni 050 se importa con cota None.
  - `test_export_usa_codigo_de_biblioteca`
  - `test_csv_protegido`: un título que empieza con "=" sale con el prefijo de `celda_segura`.
- [ ] **Paso 2:** FAIL. **Paso 3:** implementar. **Paso 4:** PASS con la suite completa.
- [ ] **Paso 5: Checkpoint.**

### Tarea 8: Respaldo

**Archivos:**

- Crear: `app/services/respaldo.py` y `scripts/respaldar.py`.
- Modificar: `app/routers/settings.py`.
- Prueba: `tests/test_respaldo.py`.

**Interfaces:**

- Consume `intercambio_marc.exportar` y `exportar_csv` (Tarea 7), y la configuración `respaldo` (Tarea 3).
- Produce:
  - `respaldo.ejecutar(db, *, carpeta: str|None = None, ahora=None) -> dict`, que devuelve `{ok, carpeta_creada, mensaje, tamano}`. Nunca lanza una excepción: cualquier error queda en `ok=False`.
  - `respaldo.estado(db, ahora=None) -> {ultimo, ultimo_ok, alerta: bool, motivo: str|None}`.
  - `respaldo.encontrar_pg_dump() -> str|None`: busca la configuración, luego `PATH`, luego `C:\Program Files\PostgreSQL\*\bin\pg_dump.exe`, y toma la versión más alta.
  - Rutas (administrador): `POST /api/v1/settings/backup` (ejecutar ahora) y `GET /api/v1/settings/backup`. `GET /api/v1/auth/me` agrega `alerta_respaldo: bool` para el administrador.
  - `python -m scripts.respaldar` sale con código 0 si `ok` y con 1 si no.
- Detalles:
  - `pg_dump -Fc` se ejecuta con `PGPASSWORD` tomada de `DATABASE_URL` y nunca la pone en la línea de comandos.
  - La rotación borra solo las carpetas que coinciden con `^shelfie-\d{8}-\d{4}$`.
  - `LEEME.txt` tiene texto fijo: qué es cada archivo y "Para restaurar: restaurar.ps1 <esta carpeta>; si base.dump no sirve, importar catalogo.mrc".
  - Se anota en el módulo `respaldo` del registro.

- [ ] **Paso 1: pruebas que fallan.**
  - `test_respaldo_completo`: usa el `pg_dump` real del contenedor y `tmp_path`, y deja los 5 archivos con `base.dump` mayor que 0 bytes. Se salta con `pytest.skip` si `encontrar_pg_dump()` da None.
  - `test_rota_a_30`: con 32 carpetas falsas viejas y una con un nombre ajeno, quedan 30 más la ajena.
  - `test_respaldo_destino_inexistente`: `ok=False`, la alerta encendida y `POST` da 200 con `ok: false`.
  - `test_respaldo_sin_pg_dump`: con monkeypatch, `ok=False` y el mensaje contiene "pg_dump".
  - `test_alerta_por_antiguedad`: el último ok hace 8 días da `alerta=True`; hace 6 días da False.
  - `test_solo_admin`: catalogador 403.
- [ ] **Paso 2:** FAIL. **Paso 3:** implementar. **Paso 4:** PASS con la suite completa.
- [ ] **Paso 5: Checkpoint.**

### Tarea 9: Frontend recortado y exportable, servido por FastAPI

**Archivos:**

- Borrar las páginas y componentes de la lista "Frontend que se elimina", y los tipos que solo usaban ellos en `lib/types.ts`.
- Modificar:
  - `next.config.mjs`: `output: "export"`, `trailingSlash: true`, `images.unoptimized`; se conserva `turbopack.root`.
  - `components/layout/app-layout.tsx` y el sidebar: los ítems Buscar, Ingreso, Libros, Usuarios, Registro y Configuración, según el rol. Sin selector de sede.
  - `lib/api.ts`: `NEXT_PUBLIC_API_URL` vacía por defecto, que es el mismo origen.
- Crear: `backend/app/estaticos.py`.
- Modificar: `backend/app/main.py`, que lo monta al final.
- Prueba: `backend/tests/test_estaticos.py`.

**Interfaces:**

- Produce:
  - `estaticos.montar(app, carpeta: Path) -> None`: sirve archivos de `carpeta`. Para una ruta sin extensión, intenta `<ruta>/index.html` y si no existe responde `404.html`. Nunca intercepta `/api/`.
  - La carpeta sale de `settings.FRONTEND_DIR`, que por defecto es `../frontend/out`. Si no existe, no se monta nada.

- [ ] **Paso 1: pruebas que fallan.** En `test_estaticos.py`, con una carpeta temporal que contiene `index.html` e `ingreso/index.html`:
  - `test_sirve_index`
  - `test_sirve_ruta_con_barra_final`
  - `test_api_no_se_intercepta`: `/api/v1/buscar?q=x` sigue respondiendo JSON.
  - `test_404`
- [ ] **Paso 2:** FAIL. **Paso 3:** implementar y hacer el recorte en el frontend. Las páginas nuevas quedan como esqueletos con el título y el layout.
- [ ] **Paso 4:** pytest en verde. En `frontend/`: `npm run typecheck`, `npm run lint` (sin errores) y `npm run build`, que genera `out/index.html`, `out/ingreso/index.html`, etc.
- [ ] **Paso 5: Checkpoint.**

### Tarea 10: Pantallas Buscar y Libro

**Archivos:** `frontend/app/page.tsx`, `frontend/app/libro/page.tsx` y `frontend/components/lite/{buscador.tsx,resultado.tsx,ficha.tsx}`. En `lib/types.ts`: `ResultadoBusqueda`, `FichaLibro` y `EjemplarPublico`.

**Interfaces:** consume `GET /api/v1/buscar` y `/buscar/{id}` (Tarea 6), y `GET /api/v1/settings` (nombre de la biblioteca).

- [ ] **Paso 1:** El buscador lleva:
  - un input grande con foco automático
  - un `Select` de campo con "Todo", "Título", "Autor", "Materia", "Cota", "ISBN" y "Editorial"
  - una pausa de 300 ms antes de buscar
  - la consulta en `?q=&campo=`, para que funcione el botón "atrás"
  - la paginación

  Cada resultado muestra la **cota en `font-mono text-2xl`** a la izquierda, el título, subtítulo y autor, una línea con edición, editorial y año, y "N ejemplares". Sin resultados: "No se encontró nada con «…». Prueba con menos palabras o busca solo por autor o por cota."
- [ ] **Paso 2:** `/libro?id=` muestra la ficha con todos los campos no vacíos con su rótulo, la cota destacada y la lista de ejemplares.
- [ ] **Paso 3:** `npm run typecheck`, `lint` y `build` en verde. Probarlo a mano con el backend y 3 libros de muestra.
- [ ] **Paso 4: Checkpoint.**

### Tarea 11: Pantallas Ingreso, Libros y MARC

**Archivos:**

- `frontend/app/ingreso/page.tsx`, `frontend/app/libros/page.tsx` y `frontend/app/marc/page.tsx`.
- `components/lite/{formulario-libro.tsx,ejemplares.tsx,lista-libros.tsx}`.
- Se reutilizan `components/catalogo/editor-marc.tsx`, `campo-marc.tsx` e `intercambio-marc-dialog.tsx`, que se mueven a `components/marc/`.

**Interfaces:** consume `/api/v1/books*` (Tarea 5), `/api/v1/catalog/items/{id}/marc`, `/import`, `/export` y `/export.csv` (Tarea 7).

- [ ] **Paso 1: Formulario.** Los campos van en el orden de la §6 del spec. Cota y Título obligatorios. Otros autores, ISBN y materias son listas con botones "+" y "×". En alta, N.º de ejemplares (1 a 50) y nota.
  - **Guardar** va a `/libro?id=`.
  - **Guardar y nuevo** muestra un toast, limpia el formulario y pone el foco en Cota.
  - Ante un 409 `POSIBLE_DUPLICADO`, un diálogo muestra las coincidencias (con enlace) y los botones "Guardar igual" (`forzar`) y "Cancelar".
  - En edición (`?id=`) se agrega la sección Ejemplares: agregar, editar en línea o quitar con confirmación.
  - El administrador ve el enlace "Editar MARC".
- [ ] **Paso 2:** Libros: tabla Cota | Título | Autor | Año | Ej. con filtro, "Sin cota" en gris y paginación de 50. Acciones: editar, ver y borrar (diálogo de confirmación con el título). Botones "Importar MARC" (el diálogo actual) y "Exportar" (MARC, MARCXML, CSV).
- [ ] **Paso 3:** `/marc?id=` es solo para el administrador: el `EditorMarc` actual, que redirige a `/` si el usuario no es administrador.
- [ ] **Paso 4:** typecheck, lint y build en verde; prueba a mano: alta → duplicado → forzar → editar ejemplares.
- [ ] **Paso 5: Checkpoint.**

### Tarea 12: Usuarios, Configuración, Registro y aviso de respaldo

**Archivos:**

- `frontend/app/usuarios/page.tsx` (rehecho), `frontend/app/configuracion/page.tsx` (rehecho) y `frontend/app/registro/page.tsx` (ajuste).
- `components/lite/aviso-respaldo.tsx` y `components/layout/header.tsx`.

**Interfaces:** consume `/api/v1/staff*` (Tarea 2), `/api/v1/settings` y `/settings/backup` (Tareas 3 y 8), y `auth/me.alerta_respaldo` (Tarea 8).

- [ ] **Paso 1: Usuarios.** Tabla con usuario, nombre, rol y estado. Diálogo "Nuevo" con usuario, nombre, apellido, rol y clave temporal. Acciones: cambiar rol, activar o desactivar, restablecer clave. Se muestran los errores 400 del servicio, por ejemplo el del último administrador.
- [ ] **Paso 2: Configuración.** Tarjeta "Biblioteca" (nombre, código y tipo de ítem para Koha, con ayuda: "Koha exige estos dos datos al importar"). Tarjeta "Respaldo":
  - carpeta y ruta de `pg_dump` (con "Detectar")
  - el último resultado con fecha, tamaño y mensaje
  - el botón "Respaldar ahora" con su spinner
  - la recomendación de usar otro disco o una carpeta de Drive u OneDrive
- [ ] **Paso 3:** `AvisoRespaldo` en el header, si `alerta_respaldo`: un aviso rojo "El último respaldo es de hace N días / falló: …" con un enlace a Configuración.
- [ ] **Paso 4:** El registro de acciones conserva sus pestañas, y la lista de módulos sale del backend.
- [ ] **Paso 5:** typecheck, lint y build en verde. **Paso 6: Checkpoint.**

### Tarea 13: Instalación en Windows y empaquetado

**Archivos:**

- `instalacion/instalar.ps1`, `iniciar.ps1`, `restaurar.ps1` y `LEEME.md`.
- `scripts/empaquetar.sh`.
- Prueba: `backend/tests/test_instalacion.py`.

**Interfaces:** consume `scripts.crear_admin`, `scripts.respaldar`, `alembic` y `estaticos` (Tarea 9).

- [ ] **Paso 1: prueba que falla.** En `test_instalacion.py`:
  - `test_scripts_existen_y_nombran_lo_acordado`: `instalar.ps1` contiene `8080`, `shelfie_lite`, `Register-ScheduledTask`, `New-NetFirewallRule` con `-Profile Private`, y `respaldar`.
  - `test_ps_sintaxis`: si `pwsh` está disponible, `pwsh -NoProfile -Command "[System.Management.Automation.Language.Parser]::ParseFile(...)"` no da errores para los tres scripts; si no, se salta.
- [ ] **Paso 2:** FAIL. **Paso 3:** Escribir los scripts tal como los fija la §12 del spec:
  - `instalar.ps1` se puede volver a correr, se ejecuta como administrador, detecta `psql` igual que `encontrar_pg_dump`, genera la clave con `[System.Web.Security.Membership]::GeneratePassword` o `RandomNumberGenerator`, y no escribe la clave en ningún archivo salvo `backend/.env`.
  - Las tareas programadas: "Shelfie-lite" al inicio y "Shelfie-lite respaldo" diaria a las 13:00 y al inicio con 5 minutos de demora.
  - `restaurar.ps1` pide escribir `RESTAURAR`.
- [ ] **Paso 4:** `scripts/empaquetar.sh` hace `npm ci && npm run build` en `frontend/` y arma `dist/shelfie-lite-$(git describe --tags --always).zip` con `backend/` (sin `.env`, `__pycache__` ni `tests`), `frontend/out/` e `instalacion/`. Probarlo en el contenedor y listar el contenido del zip.
- [ ] **Paso 5:** PASS. **Paso 6: Checkpoint.** Ronald prueba `instalar.ps1` en su Windows contra una base nueva y reporta.

### Tarea 14: Recorrido e2e y documentación

**Archivos:**

- `frontend/e2e/recorrido-lite.spec.ts` y `frontend/playwright.config.ts`.
- `frontend/package.json`: devDependency `@playwright/test` con la versión exacta que ya está instalada en el contenedor, y el script `"e2e"`.
- `README.md`: se reescribe para lite.
- `TODO.md`.

- [ ] **Paso 1:** El recorrido corre contra uvicorn sirviendo `out/` en `:8080`, con una base de prueba nueva:
  1. El administrador inicia sesión, cambia la clave y crea un catalogador.
  2. El catalogador ingresa "Bioquímica de Harper" (cota "612.015 H37", 2 ejemplares) y otro libro con "Guardar y nuevo".
  3. En un contexto sin sesión, buscar "bioquimica harper" da 1 resultado con "612.015 H37" visible, y buscar por cota "612.015" lo encuentra.
  4. La ficha muestra los 2 ejemplares.
  5. El administrador hace "Respaldar ahora" y ve el resultado correcto.
- [ ] **Paso 2:** `npx playwright test` en verde.
- [ ] **Paso 3:** README: qué es lite, instalación (remite a `instalacion/LEEME.md`), respaldo y restauración, roles, Koha (los subcampos 952) y desarrollo (venv en la raíz, comandos desde `backend/`). TODO: tabla de verificación con pytest, migración, e2e y lint.
- [ ] **Paso 4: verificación final.** pytest completo, `npm run typecheck && npm run lint && npm run build`, e2e, y un `grep` de los módulos eliminados en `backend/` y `frontend/` sin resultados.
- [ ] **Paso 5: Checkpoint final.** `Shelfie-lite: recorrido e2e y documentación`.
