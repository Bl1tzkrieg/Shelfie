# Shelfie-lite — estado

Estado al 2026-10-20: las 14 tareas del plan (`docs/superpowers/plans/2026-10-20-shelfie-lite.md`)
están hechas. Diseño en `docs/superpowers/specs/2026-10-20-shelfie-lite-design.md`.

## Verificación

| Qué | Resultado |
|---|---|
| `python -m pytest -q` (backend/, `TEST_DATABASE_URL`) | 240 pruebas pasan |
| Migración `0001_lite` | `alembic upgrade head` sobre base vacía (la ejerce el e2e y `test_migraciones`) |
| `npm run e2e` (Playwright 1.56.0) | 1 recorrido en verde: administrador → catalogador → ingreso → búsqueda pública → edición sin cambios → respaldo |
| `npm run typecheck` | sin errores |
| `npm run lint` | sin errores |
| `npm run build` | exporta `frontend/out` |
| Módulos eliminados en `backend/` y `frontend/` | `grep` sin módulos; solo queda el nombre heredado `lector` del registro de acciones (ver Pendientes menores) |

## Pendiente de Ronald

- [ ] Rotar la contraseña de PostgreSQL de `dev` (estuvo versionada en el historial del repo).
- [ ] Probar la instalación en una PC Windows real (`instalacion/instalar.ps1`, `restaurar.ps1`): los scripts no se pudieron ejecutar en el entorno de desarrollo.
- [ ] Probar el recorrido en un navegador con la bibliotecaria (ingreso de libros reales, búsqueda y cotas).
- [ ] Decidir dónde queda la copia de respaldo (otro disco o carpeta sincronizada).

## Pendientes menores

Detectados en las revisiones y no urgentes; se resuelven en una revisión final.

- **Concurrencia y datos:** dos administradores degradados a la vez pueden dejar el sistema sin administrador (falta un advisory lock); `username` es único sensible a mayúsculas mientras la aplicación no lo es, y los pre-chequeos pueden dar 500 en una carrera; dos respaldos simultáneos dan «Error inesperado»; dos copias sin código idénticas en el mismo registro importado se agregan ambas.
- **Catálogo y MARC:** año solo en 264 ©, no se puede borrar; `_ajustar_008` rehace un 008 de largo inválido; `_conciliar` compara solo el primer `$a`; borrar el autor de un 100 con `$e` deja un 100 con solo `$e`; un 130 sin 1XX más un autor nuevo pone el 100 junto al 130; `guardar_marc` (editor avanzado) cambia la cota del libro sin actualizar los ejemplares que la heredaban; 422 del editor MARC solo se ve como aviso.
- **Importación:** una cota de más de 100 caracteres se omite sin avisar; el 082 conserva las barras de Dewey; registros sin ISBN repetidos dentro del mismo archivo no se detectan; el duplicado por ISBN solo mira el primer 020.
- **Búsqueda:** `q` sin `max_length` y `pagina` sin tope (posible 500 con valores extremos); un ISBN «x» suelto coincide con todos los que terminan en X; el ranking tiene poca prueba; el conteo agrupa toda la tabla de ejemplares; falta prueba de «sesión inválida en `GET /settings` = anónimo»; `tipo_item_koha` sin pasar a mayúsculas.
- **Frontend:** el filtro de Libros no se resincroniza con `?q=` al volver atrás; el debounce puede reiniciar la página; `LLEGO_DE_BUSCAR` puede quedar viejo; la ficha sin `h1` en estados de error; página fuera de rango; Ctrl+Enter en el diálogo de duplicado; el detalle de tipo objeto pierde su mensaje; clases de tamaño de `Cota` sin `cn()`; `Badge` (div) dentro de `<p>` en la tarjeta de usuario (aviso de anidamiento); clave temporal sin `maxLength` en un formulario; «Respaldar» guarda los cambios de ruta sin avisar; `lib/fechas.ts` y `components/ui` con piezas sin uso; 307 de `/ruta` detrás de un proxy.
- **Instalación (Windows):** `ALTER ROLE` con la clave en texto plano puede quedar en el log de PostgreSQL si falla; restaurar un respaldo viejo tras una migración futura; `icacls` fallido solo avisa; junctions o symlinks hacia `C:\Users` no se detectan; la prueba del orden en `.env` es algo laxa; `stderr` en cp1252 al ejecutar `pg_dump`.
- **Pruebas:** `test_migraciones` salta con cualquier `OperationalError`, no solo con permiso denegado (pgcode 42501); falta un test automático de que las rutas públicas no piden sesión (lo cubre el e2e).
- **Texto y nombres:** el 409 `POSIBLE_DUPLICADO` no trae un mensaje legible (lo redacta el frontend); en el registro de acciones el «usuario afectado» sigue llamándose `lector` (columna `lector_id`, filtro `?lector=` y tipos del frontend), un nombre heredado de los módulos eliminados que conviene cambiar a `afectado` mientras no haya instalaciones con datos.
