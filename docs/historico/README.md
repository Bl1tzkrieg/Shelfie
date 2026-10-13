# Material histórico

`data.sql` es el diseño de esquema original de Shelfie. **No se usa para crear la base**:
desde la Fase 1 la fuente de verdad son las migraciones de Alembic (`backend/migrations/`).

Se conserva como referencia porque describe tablas que todavía no existen y que el roadmap
retoma más adelante: `presupuestos` y `fondos` (adquisiciones, Fase 5), las columnas
`biblioteca_origen_id` / `biblioteca_actual_id` de usuarios e ítems (sucursales, Fase 3) y
`items.precio_reposicion` (cobro por pérdida en las cuentas del lector, Fase 3).
