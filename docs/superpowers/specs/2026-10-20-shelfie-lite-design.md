# Shelfie-lite — diseño

- **Fecha:** 2026-10-20
- **Rama:** `shelfie-lite`, que sale de `main` después del commit del inventario
- **Estado:** pendiente de revisión

## 1. Contexto

Una biblioteca de LUZ necesita un catálogo propio en sus computadoras. Antes usaban Koha
alojado por un proveedor. Primero perdieron los datos con el robo de los servidores durante
la pandemia y después volvieron a perderlos cuando dejaron de pagar la suscripción. Hoy
intentan llevar el catálogo en una lista de Word, pero la búsqueda les devuelve "mucha
información que no necesito".

Lo que pide la bibliotecaria:

- **Ingreso:** registrar cada texto con autor, título, descripción, datos físicos y la
  **cota** (número de clasificación que dice dónde está en la estantería), con "los mismos
  campos de acceso" que Koha.
- **Búsqueda:** que al pedir, por ejemplo, "el de bioquímica de Harper" el sistema muestre
  ese libro y su cota, y nada más.
- **Equipos:** debe funcionar en las computadoras de la biblioteca. El ingreso se hace en su
  PC y la búsqueda sobre todo en la de circulación.
- **Formato:** MARC, con posibilidad de migrar. Las bibliotecas de LUZ trabajan en MARC.
- **Administración:** un administrador decide quién puede hacer qué.
- **Fuera:** estadísticas y los demás módulos.

Ella no conoce de bases de datos. La instalación y el soporte quedan a cargo del
desarrollador.

## 2. Objetivos y no objetivos

**Objetivos**

1. Ingresar un libro con un formulario simple, sin saber MARC, y guardarlo en MARC 21.
2. Encontrarlo por título, autor, materia, ISBN, cota o editorial, y ver la cota de inmediato.
3. Importar y exportar MARC compatible con Koha (ISO 2709 y MARCXML, ejemplares en 952),
   de ida y de vuelta sin pérdidas.
4. Que no vuelva a perderse el catálogo: respaldo automático diario, legible fuera de
   Shelfie.
5. Instalarse en una PC con Windows de la red local, de modo que las demás entren por el
   navegador.

**No objetivos**

- Préstamos, reservas, multas, lectores, sedes, adquisiciones, seriadas, avisos, inventario,
  reportes o estadísticas, y OPAC público en internet.
- Servidor en Linux o en la nube. Sigue siendo posible, pero no es lo que se diseña aquí.

## 3. Decisiones

| Tema | Decisión | Alternativas descartadas |
|---|---|---|
| Base del código | Recortar Shelfie en la rama `shelfie-lite` | SQLite, porque obliga a reescribir la búsqueda; app nueva, porque pierde MARC, pruebas y seguridad |
| Base de datos | PostgreSQL, con la búsqueda actual (`shelfie_es`, sin acentos, AND, prefijo) | — |
| Ingreso | Formulario simple con MARC por debajo; editor MARC avanzado solo para el administrador | Tabla plana sin MARC |
| Copias | Se conservan los ejemplares (952 de Koha). Código de barras opcional, sin estados de préstamo | Solo "N.º de ejemplares" en el registro |
| Acceso | Búsqueda sin iniciar sesión. Iniciar sesión para ingresar | Todo con login |
| Roles | Administrador y Catalogador | Un único administrador |
| Despliegue | Frontend exportado como estático y servido por FastAPI: un proceso y un puerto, sin Node en la biblioteca | `next start` y `uvicorn` juntos |
| Restauración | Por script con confirmación, no desde la web | Botón en Configuración |

## 4. Alcance del recorte

**Se queda (backend)**

- `security.py` y `autenticacion.py`: login, bloqueo por intentos, cambio de clave
  obligatorio, revocación por `jti` y verificación de `SECRET_KEY`.
- `personal.py`: el personal. `Usuario` queda solo para el personal.
- `marc.py`, `core/marc_plantillas`, `catalogo.py`, `busqueda.py` e `intercambio_marc.py`.
- `registro.py` (registro de acciones), con los módulos `catalogo`, `configuracion` y `sesion`.
- `configuracion.py`, con las secciones de la biblioteca y de respaldo.
- `core/` completo: errores, tiempo y `celda_segura`.

**Se elimina, con modelos, routers, servicios, pruebas y pantallas**

- circulacion, reservas, traslados, reglas, calendario
- cuentas, usuarios (lectores y categorías), sedes
- adquisiciones, presupuestos, sugerencias
- seriadas, listas
- avisos, correo
- reportes, inventario, opac, cuenta_opac
- tareas, salvo la limpieza del registro

**Migraciones:** en la rama, 0001–0016 se reemplazan por una sola `0001_lite.py` con las
tablas que quedan y la configuración de búsqueda `shelfie_es`. Una base de Shelfie completo
no se actualiza a lite. Para pasar datos de una a otra se exporta MARC desde Shelfie y se
importa en lite.

## 5. Modelo de datos

```
registros_bibliograficos
  id, marc_json (JSONB, la fuente), plantilla
  titulo, autor, ano_publicacion, materia, isbn  ← derivados del MARC, como hoy
  editorial  (nuevo, de 264/260 $b)
  cota       (nuevo, de 092 $a + $b; ordenable con clave_signatura)
  busqueda   (tsvector calculado: título A, autor B, materia C, editorial C,
              ISBN y cota con 'simple' D)
  creado_en, actualizado_en

items  (se conservan el nombre de la tabla y el modelo Item; en la interfaz, "ejemplares")
  id, biblio_id (FK, CASCADE)
  cota          → 952 $o   (al crear, la del registro)
  codigo_barras → 952 $p   (opcional; único si existe: índice único parcial)
  nota          → 952 $z
  numero_copia  → 952 $t   ("c.1", "c.2"…)
  creado_en

usuarios (personal), configuraciones, registro_acciones, sesiones_cerradas,
intentos_acceso
(tokens_clave se va: sin correo, la clave la restablece el administrador)
```

Fuera: `tipos_item`, `bibliotecas` y las columnas de estado, sede, precio, recepción y
fascículo de `items`.

## 6. Formulario ↔ MARC 21

| Campo del formulario | MARC | Notas |
|---|---|---|
| Cota\* | 092 $a (clase) y $b (librística) | Se parte por el primer espacio. También va a los 952 $o nuevos |
| Título\* | 245 $a | Indicadores según artículo inicial (2.º indicador de 245) |
| Subtítulo | 245 $b | |
| Mención de responsabilidad | 245 $c | |
| Autor principal | 100 $a | Formato "Apellido, Nombre" |
| Otros autores | 700 $a (repetible) | |
| Edición | 250 $a | |
| Lugar | 264 _1 $a | Al importar se lee también 260 |
| Editorial | 264 _1 $b | |
| Año | 264 _1 $c y 008/07-10 | |
| Páginas | 300 $a | |
| Ilustraciones | 300 $b | |
| Dimensiones | 300 $c | |
| ISBN | 020 $a (repetible) | |
| Materias | 650 _4 $a (repetible) | |
| Descripción / resumen | 520 $a | |
| Notas | 500 $a | |
| N.º de ejemplares | — | Crea esa cantidad de ejemplares con la cota del registro y numero_copia c.1…c.N |
| Nota de ejemplares | 952 $z de los ejemplares nuevos | |

**Regla clave:** al editar, el formulario reemplaza **solo** los campos de la tabla. Todos
los demás campos MARC, por ejemplo los que vienen de una importación o los que agrega el
editor avanzado, se conservan sin cambios. Se cargan cabecera y 008 por defecto
(`marc_plantillas`, BKS).

## 7. Búsqueda

- `GET /api/v1/buscar?q=&campo=todo|titulo|autor|materia|cota|isbn|editorial&pagina=`,
  **sin autenticación**.
- Texto: todas las palabras (AND), sin acentos ni mayúsculas, con la última palabra como
  prefijo (es la regla actual de `busqueda.py`), y orden por relevancia.
- Cota: además del índice, `cota ILIKE 'texto%'` sobre el registro y los ejemplares, para
  que "616.39" encuentre "616.39 H37".
- ISBN con o sin guiones, igual que hoy.
- Resultado: id, cota, título, subtítulo, autor, edición, editorial, año y número de
  ejemplares. 20 por página.
- `GET /api/v1/buscar/{id}`: la ficha pública con todos los campos del formulario y la
  lista de ejemplares (cota, n.º de copia, nota). No incluye el MARC crudo.

## 8. Pantallas

Todas son exportables como estáticas, sin segmentos `[id]` (se usa `?id=`).

| Ruta | Quién | Qué |
|---|---|---|
| `/` | Cualquiera | Buscador grande, selector de campo y resultados con la **cota destacada**. Busca mientras se escribe (con una pausa corta). Si no hay resultados, sugiere quitar palabras |
| `/libro?id=` | Cualquiera | Ficha completa con cota y ejemplares |
| `/login` | — | Inicio de sesión, cambio de clave obligatorio |
| `/ingreso` | Catalogador | Formulario de la §6. "Guardar" y "Guardar y nuevo" (este último limpia el formulario y pone el foco en Cota). Aviso de posible duplicado (mismo ISBN, o mismo título y autor) con la opción de guardar igual |
| `/ingreso?id=` | Catalogador | Editar. Incluye la sección de ejemplares: agregar, editar o quitar copias |
| `/libros` | Catalogador | Lista en orden de estante con filtro. Editar, borrar (con confirmación), importar MARC (vista previa y política de duplicados, como hoy) y exportar MARC, MARCXML o CSV |
| `/marc?id=` | Administrador | Editor MARC avanzado (el actual) |
| `/usuarios` | Administrador | Personal: crear, asignar rol, desactivar y restablecer clave |
| `/registro` | Administrador | Registro de acciones (el actual) |
| `/configuracion` | Administrador | Nombre de la biblioteca, código de biblioteca y tipo de ítem para la exportación a Koha, y la sección de respaldo |

En el encabezado: nombre de la biblioteca, "Buscar" e "Ingreso / Libros" (si hay sesión).
Si el último respaldo es viejo o falló, el administrador ve un aviso en rojo.

## 9. Roles

| Rol en la interfaz | Permiso interno | Puede |
|---|---|---|
| Administrador | `superbibliotecario` | Todo |
| Catalogador | `catalogo` | Ingreso, edición, borrado, importar y exportar |
| (sin sesión) | — | Buscar y ver fichas |

El primer administrador se crea con `scripts.crear_admin`, que ya existe.

## 10. Compatibilidad con Koha

- Exportar: un 952 por ejemplar, con `$a` y `$b` = código de biblioteca (configurable,
  obligatorio en Koha), `$y` = tipo de ítem (configurable, por ejemplo `LIB`), `$o` cota,
  `$p` código (si existe), `$t` copia y `$z` nota. Un registro sin ejemplares sale sin 952.
- Importar: se lee cada 952 como ejemplar (`$o`, `$p`, `$t`, `$z`) y se ignoran `$a`, `$b`
  y `$y`. Si falta 092, la cota del registro se toma del primer 952 `$o`, y si tampoco hay,
  de 082 o 050. El duplicado se detecta por ISBN, con las políticas actuales (omitir,
  reemplazar o agregar).
- Criterio de aceptación: importar un `.mrc` exportado de Koha y volver a exportarlo da los
  mismos campos bibliográficos y los mismos 952 `$o`, `$p` y `$t`.

## 11. Respaldo

- `python -m scripts.respaldar` deja en la carpeta configurada `shelfie-AAAAMMDD-HHMM/`
  con:
  1. `base.dump` (`pg_dump -Fc`)
  2. `catalogo.mrc` y `catalogo.xml` (MARC completo, con 952)
  3. `catalogo.csv` (cota, título, autor, editorial, año, ISBN, materias, ejemplares;
     protegido con `celda_segura`)
  4. `LEEME.txt`: qué es cada archivo y cómo restaurarlo
- Se conservan los últimos 30 respaldos. El resultado (fecha, éxito o error, tamaño) queda
  en `configuraciones["respaldo"]` y en el registro de acciones.
- En Configuración: carpeta de destino, la ruta de `pg_dump` (se detecta sola), "Respaldar
  ahora" y el último resultado.
- Aviso en rojo si el último respaldo correcto tiene más de 7 días o si el último falló.
- Se recomienda en pantalla que la carpeta sea otro disco o una carpeta sincronizada (Drive
  u OneDrive).
- `restaurar.ps1 <carpeta>`: confirma, detiene el servicio, hace `pg_restore --clean` y lo
  vuelve a iniciar. Si `base.dump` no sirve, se puede restaurar importando `catalogo.mrc`
  en una base nueva.

## 12. Instalación en Windows

- **Entregable:** `shelfie-lite-X.Y.zip` con `backend/`, `frontend/out/` ya compilado,
  `instalar.ps1`, `restaurar.ps1`, `iniciar.ps1` y `LEEME.md`.
- **Requisitos:** PostgreSQL 16 o más reciente (instalador oficial) y Python 3.12 o más
  reciente.
- `instalar.ps1` (como administrador, se puede volver a correr):
  1. Verifica PostgreSQL y Python.
  2. Crea el rol y la base `shelfie_lite` con una clave al azar y escribe `backend/.env`
     (`ENTORNO=produccion`, `SECRET_KEY` al azar).
  3. Crea el venv, instala las dependencias y corre `alembic upgrade head`.
  4. Crea el primer administrador (pregunta usuario y clave).
  5. Abre el puerto 8080 en el firewall solo para la red privada.
  6. Registra las tareas de Windows: "Shelfie-lite" al iniciar el equipo (`iniciar.ps1` →
     `uvicorn`) y "Shelfie-lite respaldo" todos los días a las 13:00 y al iniciar.
  7. Crea en el escritorio un acceso directo a `http://localhost:8080`.
- FastAPI sirve `frontend/out` en `/` (con *fallback* a `index.html`) y la API en
  `/api/v1`. La configuración de Next queda con `output: "export"` e
  `images.unoptimized`.
- En circulación: un acceso directo a `http://NOMBRE-PC:8080`.
- **Actualizar:** reemplazar las carpetas, `alembic upgrade head` y reiniciar la tarea.

## 13. Pruebas y criterios de aceptación

**pytest** (se queda la suite de lo que se conserva, y se agrega):

- formulario → MARC → formulario sin pérdidas, y conservación de los campos que el
  formulario no maneja al editar;
- N.º de ejemplares crea N ejemplares con la cota; ejemplares sin código; código único
  cuando existe;
- búsqueda: AND, sin acentos, prefijo, por cada campo de acceso, cota por prefijo, ISBN con
  guiones, y que sea pública;
- permisos: catalogador y administrador, y un 401/403 para cada ruta protegida;
- ida y vuelta con Koha: un archivo de prueba con 952 (exportado de Koha) se importa, se
  exporta y se compara;
- respaldo: con `pg_dump` real genera los 4 archivos, rota a 30 y registra el resultado; el
  aviso se calcula bien.

**Playwright:** el administrador crea un catalogador → el catalogador ingresa con "Guardar
y nuevo" → desde un navegador sin sesión se busca por "bioquímica harper" y por la cota →
la ficha muestra la cota.

**Build:** `next build` exporta sin errores y FastAPI sirve las rutas estáticas.

**Aceptación con la bibliotecaria:** ingresa 10 libros reales y los encuentra desde
circulación por título, autor y cota. El respaldo del día aparece en la carpeta elegida.

## 14. Riesgos

| Riesgo | Mitigación |
|---|---|
| No hay red entre las PC, o no se sabe cómo están | El diseño también funciona en una sola PC. Se confirma en la visita antes de instalar |
| Se apaga la PC servidor y circulación no puede buscar | Va en el LEEME y en la capacitación: la PC servidor debe estar encendida en horario de atención |
| Fallan los respaldos sin que nadie lo note | Aviso en rojo, registro de acciones y copia a una carpeta sincronizada |
| Koha local de LUZ con subcampos 952 personalizados | Archivo de prueba real de una biblioteca de LUZ en cuanto se consiga. Hasta entonces se usa el mapeo estándar de Koha |
| Divergencia entre `main` y `shelfie-lite` | La rama solo recorta y agrega pantallas. Las correcciones al núcleo (MARC, búsqueda, seguridad) se hacen en `main` y se pasan con `cherry-pick` |
