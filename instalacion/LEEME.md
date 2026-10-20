# Shelfie-lite: instalación en Windows

Guía para quien instala y mantiene Shelfie-lite en la PC de la biblioteca. El personal
solo necesita la sección [Uso diario](#uso-diario).

## Requisitos

- Windows 10 u 11, con una cuenta de administrador.
- **PostgreSQL 16 o más reciente**, con el instalador oficial
  (<https://www.postgresql.org/download/windows/>). Anote la clave que elija para `postgres`:
  `instalar.ps1` la pide una vez y no la guarda.
- **Python 3.12 o más reciente** (<https://www.python.org/downloads/windows/>), **instalado para
  todos los usuarios**: en el instalador elija "Customize installation" y, en "Advanced Options",
  marque **"Install Python for all users"** (queda en `C:\Program Files\Python3xx`); marque
  también "Add python.exe to PATH". Se recomienda 3.12 o 3.13 (las dependencias están probadas
  con esas). El "Install Now" por defecto lo deja en `C:\Users\<usuario>\AppData\...`, donde
  ese usuario puede modificarlo, y Shelfie-lite lo ejecuta como SYSTEM: `instalar.ps1` lo rechaza
  (salvo con `-PermitirPythonDeUsuario`, que no se recomienda). El de la Microsoft Store tampoco
  sirve.
- Internet durante la instalación (se descargan los paquetes de Python).
- La PC servidor y las de circulación en la misma red, marcada como **privada** en Windows.

## Instalar

1. Descomprima `shelfie-lite-<versión>.zip` en una carpeta fija, por ejemplo `C:\Shelfie-lite`.
   No puede estar dentro de `C:\Users` (Descargas, escritorio, Documentos): las tareas apuntan a
   esa ruta y, ahí, el dueño del perfil podría reemplazar la carpeta protegida. El instalador se
   niega a seguir.
2. Abra **PowerShell como administrador** y ejecute:

   ```powershell
   cd C:\Shelfie-lite
   powershell -ExecutionPolicy Bypass -File .\instalacion\instalar.ps1
   ```

3. Responda lo que pregunta: la clave de `postgres`, el usuario y la contraseña del primer
   administrador, y la carpeta de respaldo.

`instalar.ps1` se puede volver a ejecutar cuando haga falta: respeta lo que ya está hecho.
Lo que hace, en orden:

1. Verifica Python (3.12+, instalado para todos los usuarios; no sirve el de la Microsoft Store) y
   PostgreSQL (16+; busca `psql.exe` en el PATH y en
   `C:\Program Files\PostgreSQL\<versión>\bin`, la versión más alta). La versión del servidor
   se comprueba antes de crear nada.
2. Fija los permisos (ver [Permisos](#permisos)).
3. Crea `backend\.env` **solo si no existe**, con `ENTORNO=produccion`, una `SECRET_KEY` y una
   clave de base al azar. Deja el archivo legible solo por Administradores y SYSTEM (si lo
   quiere editar, abra el Bloc de notas como administrador).
4. Crea `backend\.venv`, instala `requirements.txt`, crea el usuario y la base `shelfie_lite`
   (con `scripts.inicializar_bd`) y corre `alembic upgrade head`.
5. Si no hay administrador, crea el primero (`scripts.crear_admin`); si ya hay, ofrece crear
   otro o cambiar una contraseña.
6. Si no hay carpeta de respaldo configurada, la pide (por defecto `C:\Shelfie-respaldos`).
   Ver [Respaldos](#respaldos) para saber qué carpetas funcionan.
7. Abre el puerto **8080** en el firewall solo para redes privadas (regla
   "Shelfie-lite (TCP 8080)") y avisa si alguna red está como pública.
8. Registra dos tareas programadas que corren como SYSTEM (aunque nadie inicie sesión):
   - **Shelfie-lite**: al iniciar el equipo, `iniciar.ps1` levanta uvicorn en `0.0.0.0:8080`
     y lo vuelve a levantar si se cae.
   - **Shelfie-lite respaldo**: todos los días a las 13:00 y 5 minutos después de encender
     (`python -m scripts.respaldar`, que también hace la limpieza diaria).
9. Crea en el escritorio (de todos los usuarios) el acceso **Shelfie-lite** a
   `http://localhost:8080` y, en la carpeta de instalación, `Shelfie-lite (circulación).url`
   apuntando a `http://NOMBRE-PC:8080` para copiar a las PC de circulación.
10. Arranca el servidor, prueba un respaldo y muestra las direcciones para la red.

### Permisos

Las tareas corren como SYSTEM, así que quien pueda modificar los archivos de la instalación
podría ejecutar lo que quiera como SYSTEM. Una carpeta nueva en `C:\` hereda "Usuarios
autenticados: Modificar", por eso `instalar.ps1` (cada vez que se corre) deja:

| Qué | Permisos |
|---|---|
| La carpeta de instalación y todo su contenido (scripts, `backend`, `.venv`, `frontend\out`, `logs`) | Administradores y SYSTEM: control total. Usuarios: solo leer y ejecutar. Dueño: Administradores |
| `backend\.env` (clave de la base y `SECRET_KEY`) | Solo Administradores y SYSTEM |
| `respaldos-previos\` (copias que deja `restaurar.ps1`) | Solo Administradores y SYSTEM |
| La carpeta de respaldo, si es local y no está en un perfil de usuario | Solo Administradores y SYSTEM (los volcados traen las claves cifradas de los usuarios, y un `base.dump` puesto ahí se podría restaurar) |

Usa `icacls` con los SID conocidos (`*S-1-5-32-544` Administradores, `*S-1-5-18` SYSTEM,
`*S-1-5-32-545` Usuarios), que valen en Windows en cualquier idioma. Si agrega archivos a mano
a la carpeta, vuelva a correr `instalar.ps1`. La carpeta no puede ser la raíz de una unidad.

### En las PC de circulación

Copie `Shelfie-lite (circulación).url` al escritorio, o abra en el navegador
`http://NOMBRE-PC:8080` (el nombre lo muestra el instalador al final; también sirve la IP).
No hay que instalar nada. La búsqueda y la ficha del libro no piden usuario.

## Uso diario

- La PC servidor **debe estar encendida** en el horario de atención; Shelfie-lite arranca solo.
- Para catalogar: acceso **Shelfie-lite** del escritorio → Entrar con su usuario.
- Si en pantalla aparece el **aviso rojo de respaldo**, avise a quien administra el sistema:
  el último respaldo falló o tiene más de 7 días.

## Respaldos

Cada día queda en la carpeta configurada una carpeta `shelfie-AAAAMMDD-HHMM\` con
`base.dump`, `catalogo.mrc`, `catalogo.xml`, `catalogo.csv` y `LEEME.txt`. Se conservan los 30
últimos. La carpeta se cambia en **Configuración**.

La tarea de respaldo corre como **SYSTEM**, no como el usuario que tiene la sesión abierta.
Eso decide qué carpetas sirven:

| Destino | ¿Sirve? |
|---|---|
| Carpeta local o de un segundo disco (`D:\Shelfie-respaldos`) | Sí, lo mejor. `instalar.ps1` la deja solo para Administradores y SYSTEM |
| Pendrive que queda puesto | Sí, pero si es FAT/exFAT no admite permisos: cualquiera que use la PC puede leerlo |
| Google Drive para escritorio | Solo la carpeta en modo **"Duplicar archivos"** (queda dentro de `C:\Users\<usuario>\...`). La unidad `G:` es del usuario y SYSTEM no la ve |
| OneDrive (`C:\Users\<usuario>\OneDrive\...`) | Se escribe bien, pero solo se sube a la nube mientras ese usuario tiene la sesión abierta |
| `\\servidor\carpeta` | Solo si el recurso compartido deja escribir a la cuenta de este equipo (`NOMBRE-PC$`, en un dominio) o a Todos; en un grupo de trabajo, casi siempre no |
| Letra de unidad de red (`Z:`) | No: es del usuario, SYSTEM no la ve |

**Después de cambiar la carpeta**, pulse "Respaldar ahora" en Configuración y revise que el
resultado sea correcto (ese botón corre en el servidor, como SYSTEM, igual que la tarea).

"Respaldar ahora" también sirve para respaldar en el momento, por ejemplo antes de una
importación grande.

## Restaurar un respaldo

Como administrador:

```powershell
cd C:\Shelfie-lite
powershell -ExecutionPolicy Bypass -File .\instalacion\restaurar.ps1 "C:\Shelfie-respaldos\shelfie-20261020-1300"
```

`restaurar.ps1` comprueba que la carpeta tenga `base.dump`, pide escribir **RESTAURAR**,
detiene la tarea de respaldo (deja terminar uno en curso) y el servidor (si no puede liberar
el puerto 8080, se detiene sin tocar nada), guarda una copia de la base actual en
`respaldos-previos\antes-de-restaurar-...\` (se deshace pasándole esa carpeta al mismo
script), hace
`pg_restore --clean --if-exists --no-owner` en una sola transacción (si falla, la base queda
como estaba), corre `alembic upgrade head` y vuelve a iniciar.

Si `base.dump` está dañado: instale en limpio e importe `catalogo.mrc` del respaldo desde
Libros → Importar MARC.

## Actualizar a una versión nueva

1. Borre `backend\app`, `backend\migrations`, `backend\scripts` y `frontend\out` (así no quedan
   archivos viejos; **no** borre `backend\.env` ni `backend\.venv`).
2. Descomprima el zip nuevo encima de la misma carpeta, reemplazando los archivos.
3. Vuelva a ejecutar `instalar.ps1`: detiene el servidor, actualiza las dependencias, corre
   `alembic upgrade head`, deja las tareas al día y vuelve a iniciar. No pide la clave de
   `postgres` si la base ya existe.

## Problemas frecuentes

| Qué pasa | Qué hacer |
|---|---|
| No abre `http://localhost:8080` | Revise `logs\shelfie-AAAAMMDD.log` (se guardan 14 días). En el Programador de tareas, ejecute "Shelfie-lite" |
| Abre en el servidor pero no desde circulación | La red debe ser privada (el instalador indica el comando) y el firewall debe tener "Shelfie-lite (TCP 8080)" |
| El respaldo falla | El mensaje sale en Configuración; el detalle en `logs\respaldo-AAAAMMDD.log` |
| `instalar.ps1` se cortó a mitad | Corrija lo que indica el mensaje y vuelva a ejecutarlo |
| Se perdió `backend\.env` | Vuelva a ejecutar `instalar.ps1`: crea uno nuevo y le pone la clave nueva al usuario de la base (pide la clave de `postgres`). Las sesiones abiertas se cierran |

## Desinstalar

```powershell
Unregister-ScheduledTask -TaskName 'Shelfie-lite' -Confirm:$false
Unregister-ScheduledTask -TaskName 'Shelfie-lite respaldo' -Confirm:$false
Remove-NetFirewallRule -DisplayName 'Shelfie-lite (TCP 8080)'
```

Después borre la carpeta de instalación y el acceso del escritorio. La base `shelfie_lite`
queda en PostgreSQL hasta que la borre (`DROP DATABASE shelfie_lite;`); haga antes un respaldo.

## Intercambio con Koha

- Al **exportar a Koha**, cada ejemplar sale como un 952 rehecho solo con
  **$a $b $o $p $t $y $z** (biblioteca, biblioteca, cota, código de barras, copia, tipo de
  ítem y nota). Los demás subcampos de ejemplar de Koha (estado, ubicación, fechas, precio…)
  **no se conservan**.
- Al **importar**, la pantalla indica qué subcampos del 952 se ignoraron.

## Desarrollo (no para la biblioteca)

- Backend, desde `backend/`: `python -m uvicorn app.main:app --reload --port 8000`.
  Pruebas: `python -m pytest -q`.
- Frontend, desde `frontend/`: cree `frontend/.env.local` con
  `NEXT_PUBLIC_API_URL=http://localhost:8000` (el origen del backend, **sin** `/api/v1`) y
  corra `npm run dev`. En la instalación no se define: FastAPI sirve la API y el frontend en
  el mismo origen.
- El zip se arma en Linux con `scripts/empaquetar.sh` (queda en `dist/`).
- Los `.ps1` van en UTF-8 **con BOM** y finales de línea CRLF: Windows PowerShell 5.1 sin el
  BOM lee mal los acentos. `.gitattributes` evita que git los convierta.
