# Roadmap — Shelfie

Objetivo: cubrir lo que hace [Koha](https://koha-community.org/). El orden de las fases no es
arbitrario: **Alembic → tests → autenticación → circulación** es la secuencia crítica, porque
cada paso protege al siguiente. De la Fase 4 en adelante el orden puede ajustarse a lo que la
biblioteca necesite primero.

Estado al 2026-10-07.

---

## Fase 0 — Higiene ✅ (salvo dos acciones manuales)

- [x] Marca unificada: **Shelfie** es el producto; el nombre de la institución sale de
      Configuración (barra lateral y `<title>`). Se quitó `generator: 'v0.app'`.
- [x] `data.sql` movido a `docs/historico/` con una nota de qué partes retoma el roadmap.
- [x] `models.py`: sin `datetime.utcnow()` (usa `app.core.tiempo.ahora_utc`) y sin los
      comentarios `# <-- AGREGA ESTA LÍNEA…`.
- [x] `seed.py`: crea también las categorías `DOC` y `ADM` (antes solo `EST`, y no se podían dar
      de alta docentes ni personal) y usa fechas relativas a hoy.
- [x] `npm run lint` arreglado: Next 16 eliminó `next lint`; ahora ejecuta `eslint .`.
- [ ] **Rotar la contraseña de PostgreSQL** — estuvo versionada en el repo. Acción manual.
- [ ] **Prueba manual en navegador** de los flujos de P1 (nunca se hizo clic en los botones).

## Fase 1 — Base técnica ✅

- [x] **Alembic** (`backend/migrations/`). Migración `0001_base` = esquema que creaba
      `create_all()`. La API y `seed.py` ya no crean tablas.
      Base existente → `alembic stamp 0001_base` + `alembic check` (ver README).
- [x] **Suite pytest** (`backend/tests/`, 71 casos) contra PostgreSQL real, con rollback por
      test. Reconstruye la base de pruebas con las migraciones en cada corrida y verifica que
      `models.py` y las migraciones coincidan.
- [x] Los errores conocidos quedaron como `xfail` estrictos con la fase que los corrige: cuando
      se arreglen, el test pasa a fallar como "XPASS" y obliga a quitar la marca.
- [x] **Capa de servicios**: `routers/` (HTTP) → `services/` (reglas) → `models.py`. Utilidades
      comunes en `core/` (errores de negocio, fechas, CSV). Verificado que las respuestas de la
      API son idénticas antes y después (33 peticiones comparadas byte a byte).
- [x] **Instalador de base de datos** (`python -m scripts.inicializar_bd --seed`): crea el
      usuario, la base y `<base>_test` con una cuenta administradora que no se guarda, aplica
      las migraciones y carga datos de ejemplo. Idempotente.
- [x] Protecciones: Alembic ignora tablas ajenas a Shelfie en el mismo esquema, y la suite se
      niega a correr si la base de pruebas no lleva `test` en el nombre (la borra al empezar).
- [x] **Dependencias actualizadas para Python 3.13**: las versiones fijadas antes (pydantic 2.6,
      psycopg2-binary 2.9.9) no tenían wheels para 3.13 y `pip install` intentaba compilarlas.
      Ahora: FastAPI 0.115, pydantic 2.10, psycopg2-binary 2.9.10, SQLAlchemy 2.0.36. Suite y
      respuestas de la API verificadas también con 3.13.

## Fase 2 — Autenticación y permisos ✅

- [x] **Personal vs. lectores**: `usuarios.es_personal` + `usuarios.permisos` (JSONB), migración
      `0002_personal`. Ocho permisos por módulo al estilo Koha (`app/core/permisos.py`) y tres
      perfiles plantilla: Administrador, Bibliotecario, Auxiliar de circulación.
- [x] **Todas las rutas de intranet exigen sesión**; consultar basta con ser personal, modificar
      exige el permiso del módulo. El OPAC sigue público.
- [x] **Sesión en cookie httpOnly** (SameSite=Lax, `COOKIE_SECURE` para HTTPS) + rechazo de
      escrituras desde orígenes no autorizados (CSRF). El token nunca llega al JavaScript.
- [x] `/auth/set-password` eliminado. Nuevos `/auth/logout` y `/api/v1/staff` (listado,
      catálogo de permisos y asignación, solo superbibliotecario; nadie puede quitarse a sí
      mismo el superbibliotecario).
- [x] Suspender a alguien corta su sesión en la siguiente petición.
- [x] `python -m scripts.crear_admin` crea o promueve un superbibliotecario.
- [x] Frontend: pantalla `/login` (vuelve a la página pedida), las páginas privadas no se montan
      sin sesión, cierre de sesión, barra lateral con el usuario real y menú según permisos,
      aviso "sin acceso" por sección, diálogo **Acceso y permisos** en Usuarios.
- [x] Préstamos y devoluciones guardan quién del personal los registró
      (`personal_prestamo_id`, `personal_devolucion_id`). Los pagos llegan con las cuentas del
      lector en la Fase 3.
- [x] La UI oculta los botones de escritura que el permiso no habilita: prestar y reservar
      (circulación), alta, edición, importación y suspensión de lectores (lectores), acciones
      rápidas del dashboard según cada permiso. El backend sigue siendo quien decide (403).
- [x] **Cambio de la propia contraseña** (llave en la barra lateral) y **restablecimiento**
      desde la ficha del usuario (permiso lectores; la de otro miembro del personal, solo un
      superbibliotecario). Mínimo 8 caracteres y distinta del carnet. Cambiar la contraseña
      **cierra las demás sesiones**: el token lleva una huella del hash.

## Fase 3 — Núcleo de circulación ✅ (cerrada)

Decisiones: una sola sede por ahora, 3 días hábiles para retirar una reserva, bloqueo por deuda
a partir de un umbral (Bs. 5 por defecto) y calendario activo desde ya (domingos cerrados).

- [x] **Fechas con zona horaria** (migración `0003`): columnas `timestamptz`, lógica en UTC,
      "qué día es" según `ZONA_HORARIA` (America/Caracas), fechas en español ("05 oct 2026").
      Los préstamos vencen a las 23:59 del día, como en Koha. `tzdata` agregado para Windows.
- [x] **Sede** (migración `0004`): la primera sede existente o "Biblioteca Principal"; ejemplares
      (propia/actual), préstamos, reservas y lectores quedan asociados.
- [x] **Reglas de circulación** (`reglas_circulacion`): categoría × tipo de ítem × sede, con
      comodines. Días, tope, renovaciones, multa diaria, tope de multa, días de gracia, máximo de
      reservas y si se presta. Gana la más específica (sede > tipo > categoría). Se crearon desde
      las categorías existentes; Configuración ahora lee y escribe ahí (una sola verdad).
      API: `GET/PUT /circulation-rules`, `DELETE /circulation-rules/{id}`.
- [x] **Calendario**: días cerrados semanales + feriados (`/calendar`). Vencimientos que caen en
      día cerrado pasan al siguiente hábil; multas y plazo de retiro cuentan solo días hábiles.
- [x] **Ciclo de reservas**: Pendiente → EnEspera (ejemplar apartado, fecha límite) → Cumplida /
      Expirada / Cancelada, con turnos renumerados. Solo quien reservó retira el ejemplar
      apartado. Expiración automática al operar y `POST /circulation/holds/expire`.
      No se reserva lo que ya se tiene prestado, ni con deuda sobre el umbral, ni por encima del
      máximo de la regla.
- [x] **Cuentas del lector** (`movimientos_cuenta` reemplaza `multas`, con migración de saldos):
      multas, reposiciones, pagos (permiso circulación), condonaciones con motivo (permiso
      lectores). `GET /users/{carnet}/account`, `POST …/payments`, `POST …/waivers`.
- [x] **Declarar perdido**: cierra el préstamo y cobra la reposición (precio del ejemplar, el de
      la orden de compra o el valor por defecto de Configuración).
- [x] Renovar un préstamo vencido cobra la mora acumulada; ya no se pierde.
- [x] `es_prestable` y la regla `prestable` se respetan en el préstamo.
- [x] Reportes de vencidos y devoluciones filtran por la fecha correcta.
- [x] Sin consultas N+1 en préstamos, catálogo, padrón y reportes (hay un test que lo vigila).
- [x] Frontend: panel **Cuenta del lector** en la ficha (pagar / condonar), "Declarar perdido",
      aviso al devolver un ejemplar con reserva en cola, estados "Suspendido" vs. "Bloqueado
      por deuda", renovaciones restantes según la regla real, "N en cola" en el catálogo.
- [x] **Pantalla Reglas y calendario** (`/configuracion/circulacion`): alta, edición y baja de
      reglas (la general no se borra), "¿qué regla se aplica?" que resalta la regla ganadora,
      días cerrados, feriados, y deuda máxima / plazo de retiro / reposición por defecto
      (validados en el backend). `GET /circulation-rules/options` da las categorías, tipos y
      sedes. Configuración ya no edita políticas (solo enlaza): guardar los datos de la
      institución pisaba renovaciones y multas de todas las reglas.
- [x] Las políticas básicas de `PUT /settings` solo tocan la regla general y las de categoría;
      las reglas por tipo de ítem o sede se respetan.
- [x] **Ejemplar perdido que aparece**: devolverlo (desde el historial con "Apareció" o por
      código) lo reincorpora o lo aparta para la cola, y acredita la reposición cobrada
      (`REINTEGRO`, como RefundLostOnReturn de Koha). Si ya estaba pagada, queda saldo a favor.
      `prestamos.perdido` conserva que el préstamo terminó en pérdida aunque el ejemplar vuelva.
- [x] **Devolución por código de barras** en Circulación (el diálogo queda abierto para
      escanear la pila).
- [x] Migración `0005`: elimina las columnas obsoletas de `categorias_usuario` (al bajar se
      reconstruyen desde las reglas) y agrega `prestamos.perdido`.
- [x] Las condonaciones pueden aplicarse a un **cargo concreto** (migración `0011`,
      `movimientos_cuenta.cargo_id`). Si se condonó la reposición y el ejemplar aparece, solo
      se reintegra lo no condonado. Los reintegros también quedan ligados a su reposición.
- [ ] Pagos aplicados a un cargo concreto (hoy los pagos van a la deuda en general).

## Fase 4 — Catalogación y búsqueda ✅

- [x] **Búsqueda de texto completo** (migración `0006`): extensión `unaccent` (la crea el dueño
      de la base, sin superusuario), configuración `shelfie_es` (español sin acentos y por raíz)
      y columna `tsvector` generada con índice GIN. Título pesa más que autor, autor más que
      materia. La última palabra se busca como prefijo; un ISBN (con o sin guiones) o un código
      de barras exacto también encuentran el título.
- [x] `GET /catalog/search`: paginada, con orden (relevancia, título, año) y facetas
      (disponibilidad, tipo, materia, autor, década) calculadas sobre el resultado.
- [x] El OPAC usa la misma búsqueda. `total` ahora cuenta todo y no solo la página, y
      "solo disponibles" se filtra en la base (antes recortaba después de paginar).
- [x] Catálogo de la intranet: búsqueda en el servidor mientras se escribe, panel de facetas,
      etiquetas de filtros activos, orden y paginación. La búsqueda vive en la URL (se recarga,
      se comparte y el botón Atrás funciona); el buscador del encabezado lleva ahí.
- [x] **MARC como fuente** (migración `0007`): título, autor, materia, año e ISBN se derivan
      del registro MARC21 al guardar (245 $a $b $n $p, 100/110/111/700, 650/653,
      264/260/008, 020). Los registros existentes se completaron con sus columnas sin cambiar
      ninguna. El alta rápida, las órdenes de compra y el seed arman MARC completo.
- [x] **Plantillas** (`app/core/marc_plantillas.py`): Libros (BKS), Publicaciones seriadas
      (SER), Tesis y trabajos de grado (TES, 502 obligatorio) y Recursos electrónicos (ERE,
      856 $u obligatorio), con nombres en español, obligatorios, repetibles e indicadores.
- [x] **Editor MARC** (pestaña "Registro MARC" de la ficha y `/catalogo/nuevo`): campos
      agrupados por bloque, indicadores con su significado, agregar/repetir/quitar campos y
      subcampos, etiquetas fuera de la plantilla, vista de texto estilo MarcEdit, errores
      marcados junto a su campo (422 con ubicación) y aviso de ISBN repetido.
- [x] Agregar ejemplares a un registro existente y eliminar registros sin ejemplares.
- [x] **Importar** ISO 2709 y MARCXML con vista previa, política de duplicados por ISBN
      (omitir / reemplazar / agregar) y ejemplares en 952 como Koha ($p $y $o $a $b $v $1).
      **Exportar** la búsqueda actual o todo el catálogo, con 001/003 y 952 opcional.
- [x] La API expone `Content-Disposition`: las descargas ya llegan con su nombre de archivo.
- [ ] Plantillas editables desde la intranet (hoy están en código).
- [ ] Indexar también notas, editorial y materias secundarias en la búsqueda.
- [ ] Más adelante: copia de registros por Z39.50/SRU y autoridades.
- Nota: en los registros del seed anterior, el 100 ya decía "García Márquez, Gabriel"; al
  guardar ese registro por primera vez, el autor pasa a esa forma (la del MARC).

## Fase 5 — Pantallas de personal ✅

### Reservas y traslados ✅

- [x] **Sedes** (migración `0008`, Configuración › Sedes): alta, edición y baja (solo si no
      tienen nada asociado), datos de contacto y si son **punto de retiro**. Siempre queda al
      menos uno.
- [x] **Sede de trabajo** ("Set library" de Koha): selector en la cabecera cuando hay más de
      una sede. Viaja en `X-Shelfie-Sede`; sin ella se usa la sede del usuario.
- [x] **Traslados** (`/circulation/transfers`): por reserva, por retorno a la sede propia o
      manuales. Solicitado → Enviado → Recibido | Cancelado. Nacen enviados si el ejemplar se
      acaba de escanear, y "por enviar" si no (p. ej. venció una reserva y sigue en el estante).
- [x] **Una sola decisión de destino** (`traslados.ubicar`): al quedar libre, un ejemplar
      queda en espera si su lector retira en esta sede, viaja si retira en otra, vuelve a su
      sede si `retorno_a_sede_propia` está activo (Configuración › Reglas y calendario), o
      queda disponible. La usan la devolución, la recuperación de perdidos, la expiración y la
      cancelación.
- [x] **Devolución como mostrador único**, como el checkin de Koha: además de cerrar
      préstamos, recibe traslados (también si llegan a otra sede: se reencaminan) y aparta
      ejemplares del estante para reservas. Muestra qué hacer con el ejemplar (estante de
      reservas, enviar a X, al estante).
- [x] **Reservas**: sede de retiro, suspensión (con fecha de reanudación o sin ella), fecha
      límite ("no la necesita después del…"), notas y cambio de turno. Las suspendidas
      conservan su turno y no frenan renovaciones. Estado nuevo **EnTransito**: el plazo de
      retiro corre desde que llega. Prestar otra copia cumple la reserva y libera la apartada.
- [x] Pantalla **Reservas** (`/circulacion/reservas`): por retirar (con "vence hoy"), para sacar
      del estante (con botón Apartar), en tránsito y cola por título con subir/bajar, suspender,
      editar y cancelar. Pantalla **Traslados** (`/circulacion/traslados`): por recibir, por
      enviar, enviados e historial, escaneo de lo que llega y traslado manual.
- [x] La ficha del título muestra su cola de reservas y, con varias sedes, dónde está cada
      ejemplar y adónde viaja. "Reservar" está siempre disponible, no solo sin copias libres.
- [ ] Reserva de un ejemplar concreto (Koha "item-level hold") y reglas de qué sedes pueden
      atender reservas de otras.
- [ ] Aviso al lector cuando su reserva está lista (Fase 7).

### Adquisiciones ✅

- [x] **Presupuestos y fondos** (migración `0009`): período, monto total, activo y bloqueado
      (cierre del ejercicio). Los fondos reparten el total; no se asigna más de lo que hay.
      Comprometido, gastado y disponible se **calculan** de pedidos y facturas, como en Koha.
- [x] **Proveedores**: RIF, dirección, descuento habitual (se propone en cada línea), días de
      entrega (marcan los atrasos), notas, activo/inactivo.
- [x] **Pedidos** (las cestas de Koha): Abierto → Cerrado (enviado) → Recibido, o Cancelado.
      Cada línea apunta a un registro del catálogo: si es nuevo **se crea al pedir**, así se
      puede reservar lo que viene. Fondo, precio de lista, descuento y costo estimado; un fondo
      no se excede ni se usa si está inactivo.
- [x] **Recepción contra factura**, en parciales y al costo real. Los ejemplares nacen con
      código propio o generado (`OC0001-L001-01`), tipo, sede y signatura, y el costo como
      precio de reposición. Pasan por la misma decisión de destino que una devolución: si
      alguien los reservó, quedan apartados o viajan a su sede de retiro.
- [x] **Facturas**: número único por proveedor, envío cargado a un fondo, cerrar y reabrir.
      Deshacer una recepción si sus ejemplares no circularon.
- [x] Cancelar lo que falta de una línea (libera lo comprometido) o el pedido entero si no se
      recibió nada. **Pedidos atrasados** según los días de entrega, con reclamo por correo.
- [x] **Sugerencias de compra** del personal o a nombre de un lector: aceptar, rechazar con
      motivo o agregarla a un pedido. Avisa si ya hay un registro con ese ISBN.
- [x] Pantalla **Adquisiciones** (`/adquisiciones`): resumen, pedidos, facturas, proveedores,
      presupuestos y sugerencias; detalle de pedido y de factura.
- [x] El ISBN se compara sin guiones ni espacios (pedidos, sugerencias e importación MARC).
- [ ] Impuestos (IVA) y monedas extranjeras con tasa de cambio.
- [ ] Fondos jerárquicos (subfondos) y traspasos entre fondos.
- [x] Sugerencias desde el OPAC (Fase 6).
- [ ] Reclamos automáticos por correo (Fase 7).

### Seriadas ✅

- [x] **Suscripción ligada al catálogo** (migración `0010`): registro SER (se crea con 022 y
      310 si no existe), proveedor, sede que la recibe, tipo de ítem y si cada número da de
      alta un ejemplar. Vigencia, renovación y cancelación.
- [x] **Patrón de predicción**: frecuencia (cada N días, semanas, meses o años, o irregular) y
      numeración con `{X}` volumen, `{Y}` número, `{ANO}` y `{MES}`, con N números por volumen.
      Vista previa de los próximos números antes de guardar. Los existentes se convirtieron
      desde su `periodicidad`.
- [x] Siempre hay un **próximo número esperado**: recibirlo (o darlo por faltante) predice el
      siguiente, sin pasar de la fecha de fin. Números especiales fuera del patrón.
- [x] **Recepción**: el ejemplar nace con su numeración (`items.enumeracion`, 952 $h al
      exportar e importar) y pasa por las reservas del título.
- [x] **Atrasos y reclamos**: atrasado = fecha esperada + días de gracia; marcar reclamado
      (cuenta reclamos) y correo al proveedor con los números que faltan.
- [x] Pantalla **Seriadas** (`/seriadas`): suscripciones, por recibir y atrasados por proveedor;
      ficha con kardex por año.
- [ ] Listas de circulación (routing lists) e índices de contenidos.
- [ ] Varios patrones en uso a la vez (p. ej. números + suplementos) y numeración alfabética.

## Fase 6 — OPAC y cuenta del lector ✅

- [x] Sección pública **`/opac`** con su propia cabecera (nombre y contacto de la institución,
      sedes de retiro): portada con materias para explorar, búsqueda con las facetas del
      catálogo (disponibilidad, tipo, materia, autor, década) y paginación.
- [x] **Ficha pública**: datos del registro MARC en palabras (subtítulo, edición, publicación,
      descripción física, serie, resumen, notas, materias, otros autores), disponibilidad **por
      sede** y estado de cada ejemplar ("Prestado, vence el…", "En tránsito", "Solo consulta
      en sala") sin datos del lector que lo tiene. En el teléfono, un ejemplar por tarjeta.
- [x] **Sesión del lector** aparte de la del personal (cookie `shelfie_opac`, token con
      audiencia propia): cualquier usuario activo entra con su carnet; cambiar la contraseña
      cierra las demás sesiones.
- [x] **Mi cuenta**: préstamos con vencimiento y atraso; **renovar** uno o todos, con el motivo
      cuando no se puede (renovaciones agotadas, otro lector lo reservó, deuda); **reservas**
      (turno, sede de retiro, en camino, lista para retirar y hasta cuándo) con cambiar sede,
      pausar/reanudar y cancelar; **reservar** desde la ficha eligiendo dónde retirar y hasta
      cuándo lo necesita (no se reserva lo que no se presta ni con deuda); multas y movimientos;
      historial de préstamos devueltos.
- [x] **Renovar un préstamo vencido** desde el OPAC pide confirmación: muestra cuánto se cobra
      por el atraso y si con eso el lector queda bloqueado; sin aceptarlo la API no renueva
      (`aceptar_cargo`). "Renovar todo" deja los vencidos para renovarlos uno por uno.
- [x] **Sugerencias de compra** desde el OPAC (hasta 5 sin responder): llegan a
      Adquisiciones a nombre del lector, que ve la respuesta y el motivo de un rechazo.
- [x] **Listas** del lector (migración `0012`): privadas o públicas con enlace para compartir
      (muestran solo el nombre de pila de quien la armó); guardar desde la ficha, crear de paso.
- [x] Enlaces cruzados: "Catálogo público" en la barra de la intranet y "¿Eres lector?" en su login.
- [ ] Privacidad del historial (que el lector elija no guardarlo, o anonimizar a los N días).
- [ ] Que el lector actualice sus datos de contacto (con aprobación del personal, como en Koha).
- [ ] Portadas (Open Library por ISBN), "títulos nuevos" en la portada y RSS de búsquedas.
- [ ] Recuperar la contraseña por correo (necesita los avisos de la Fase 7).

## Fase 7 — Avisos y tareas programadas

- [ ] Plantillas de aviso (por vencer, vencido, reserva disponible, reserva expirada).
- [ ] Cola de correos y planificador (APScheduler o cron). Usa
      `notificaciones.recordatorio_dias_antes`, que hoy se guarda pero nadie lee.

## Fase 8 — Herramientas y extras

- [ ] Registro de auditoría, inventario, etiquetas y códigos de barras, modificación por lotes.
- [ ] Reportes armables por el usuario (con cuidado si se permite SQL).
- [ ] Portadas.
- [ ] Más adelante: préstamo interbibliotecario, reservas de curso, autopréstamo, i18n.

---

## Verificación

| Comprobación | Resultado |
|---|---|
| `pytest` | ✅ 308 pasan, 0 `xfail` |
| Migraciones `0001`→`0012` subir/bajar con datos, `alembic check` | ✅ |
| Navegador real (Chromium): login y permisos (Fase 2) | ✅ 15/15 comprobaciones |
| Navegador real: multa, bloqueo, pago, reserva, apartado, pérdida (Fase 3) | ✅ 14/14 comprobaciones |
| Navegador real: reglas, calendario, ajustes, ejemplar recuperado, devolución por código | ✅ 18/18 comprobaciones |
| Navegador real: búsqueda, facetas, orden, paginación, URL (Fase 4) | ✅ 21/21 comprobaciones |
| Migración `0006` con un dueño de base **sin** superusuario | ✅ |
| Navegador real: editor MARC, plantilla de tesis, errores, importación y exportación | ✅ 11/11 comprobaciones |
| Navegador real: OPAC sin sesión, ficha, entrar, reservar, listas, renovar, sugerir, sesiones separadas, teléfono (Fase 6) | ✅ 14/14 comprobaciones |
| `alembic upgrade` / `downgrade` / `check` en base vacía | ✅ |
| API antes vs. después de la capa de servicios | ✅ respuestas idénticas (33 peticiones) |
| `npm run typecheck` | ✅ sin errores |
| `npm run lint` | ✅ 0 errores, 29 avisos (todos `set-state-in-effect` en cargas iniciales) |
| `npm run build` | ⚠️ no verificado en el entorno de Claude (sin acceso a Google Fonts) |

## Historial (antes del roadmap)

P0–P6, cerrados el 2026-09-13: bugs que rompían el catálogo, los 22 botones conectados,
rutas 404 resueltas con modales y páginas de detalle, mocks reemplazados por datos reales,
API de adquisiciones / seriadas / OPAC / reservas, hashing PBKDF2 + JWT, y limpieza del repo
(`.env.example`, `.gitignore`, ESLint, README).
