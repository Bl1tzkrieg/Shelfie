#Requires -Version 5.1
#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Instala (o actualiza) Shelfie-lite en esta PC: base de datos, entorno de Python,
    primer administrador, firewall, tareas programadas y acceso directo.

.DESCRIPTION
    Se ejecuta como administrador desde la carpeta descomprimida:

        powershell -ExecutionPolicy Bypass -File .\instalacion\instalar.ps1

    Se puede volver a correr sin riesgo: lo que ya está hecho se respeta. En particular,
    backend\.env se crea solo la primera vez (se conservan la clave de la base y la
    SECRET_KEY) y la clave del superusuario de PostgreSQL se pide solo si hace falta,
    nunca se guarda en ningún archivo.

.PARAMETER SuperusuarioPg
    Cuenta administradora de PostgreSQL (la del instalador oficial es postgres).

.PARAMETER PuertoPg
    Puerto de PostgreSQL (5432 por defecto).

.PARAMETER PermitirPythonDeUsuario
    Acepta un Python instalado solo para un usuario (en C:\Users\...). No se recomienda:
    ese usuario podría cambiar código que SYSTEM ejecuta al iniciar el equipo.
#>
[CmdletBinding()]
param(
    [string]$SuperusuarioPg = 'postgres',
    [int]$PuertoPg = 5432,
    [switch]$PermitirPythonDeUsuario
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'comun.ps1')

$BaseShelfie = 'shelfie_lite'
$UsuarioShelfie = 'shelfie_lite'
$VersionMinimaPg = 160000          # server_version_num de PostgreSQL 16
$IniciarPs1 = Join-Path $PSScriptRoot 'iniciar.ps1'

function Clave-AlAzar([int]$Bytes) {
    <# Hexadecimal de bytes criptográficamente aleatorios (sin símbolos: no hay que
       escaparla ni en la URL ni en SQL). #>
    $buffer = New-Object byte[] $Bytes
    $generador = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generador.GetBytes($buffer) } finally { $generador.Dispose() }
    return ([System.BitConverter]::ToString($buffer) -replace '-', '').ToLowerInvariant()
}

function Texto-DeClaveSegura([System.Security.SecureString]$Segura) {
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Segura)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}

function Es-PythonDeUsuario([string]$BasePrefix) {
    <# Instalado solo para un usuario (lo normal con "Install Now" de python.org va a
       %LOCALAPPDATA%\Programs\Python): ese usuario puede modificar el intérprete y la
       biblioteca estándar que usa el venv, es decir, código que SYSTEM corre al iniciar. #>
    return Esta-Dentro $BasePrefix $CarpetaPerfiles
}

function Buscar-Python {
    <# El primer Python 3.12 o más reciente: el lanzador py (3.12, 3.13, el más nuevo) o python.
       Se descarta el de la Microsoft Store (WindowsApps): es por usuario y SYSTEM no lo ve.
       Uno instalado solo para un usuario se descarta salvo con -PermitirPythonDeUsuario. #>
    $script:PythonDeUsuarioDescartado = $null
    foreach ($candidato in @('py -3.12', 'py -3.13', 'py -3', 'python')) {
        $partes = $candidato -split ' '
        $comando = Get-Command $partes[0] -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $comando -or $comando.Source -like '*\WindowsApps\*') { continue }
        $extra = @($partes | Select-Object -Skip 1)
        $r = Ejecutar-Capturando $partes[0] ($extra + @('-c', "import sys; print(sys.version_info[0], sys.version_info[1], sys.executable, sys.base_prefix, sep='|')"))
        if ($r.Codigo -ne 0) { continue }
        $m = [regex]::Match($r.Salida, '(?m)^(\d+)\|(\d+)\|([^|]+)\|([^|\r\n]+)\s*$')
        if (-not $m.Success) { continue }
        $mayor = [int]$m.Groups[1].Value
        $menor = [int]$m.Groups[2].Value
        $ejecutable = $m.Groups[3].Value.Trim()
        $basePrefix = $m.Groups[4].Value.Trim()
        if ($ejecutable -like '*\WindowsApps\*') { continue }
        if (-not ($mayor -eq 3 -and $menor -ge 12)) { continue }
        $encontrado = [pscustomobject]@{ Ejecutable = $ejecutable; Version = "$mayor.$menor"; BasePrefix = $basePrefix }
        if ((Es-PythonDeUsuario $basePrefix) -and -not $PermitirPythonDeUsuario) {
            if (-not $script:PythonDeUsuarioDescartado) { $script:PythonDeUsuarioDescartado = $encontrado }
            continue
        }
        return $encontrado
    }
    return $null
}

function Consultar-Pg([string]$Usuario, [string]$Clave, [string]$Base, [string]$Sql) {
    <# Corre SQL con psql; la clave viaja en PGPASSWORD y el SQL por la entrada estándar
       (nada de eso aparece en la lista de procesos). #>
    $env:PGPASSWORD = $Clave
    try {
        return Ejecutar-Capturando $Psql @('-X', '-w', '-q', '-t', '-A', '-v', 'ON_ERROR_STOP=1',
            '-h', $Conexion.Servidor, '-p', "$($Conexion.Puerto)", '-U', $Usuario, '-d', $Base) $Sql
    } finally {
        Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    }
}

function Version-Pg([string]$Salida) {
    $numero = 0
    [void][int]::TryParse(($Salida -split "`n")[-1].Trim(), [ref]$numero)
    return $numero
}

function Exigir-Pg16([int]$Numero) {
    if ($Numero -lt $VersionMinimaPg) {
        Detener-ConError "El servidor PostgreSQL es la versión $Numero; se necesita PostgreSQL 16 o más reciente."
    }
}

function Proteger-CarpetaDeRespaldo([string]$Ruta) {
    <# Los respaldos traen toda la base (con las claves cifradas de los usuarios) y un
       base.dump puesto ahí se podría restaurar: si la carpeta es local, solo
       Administradores y SYSTEM. #>
    if ($Ruta.StartsWith('\\')) {
        Escribir-Info 'Carpeta de red: los permisos los da el recurso compartido (debe dejar escribir a la cuenta de este equipo o a Todos).'
        return
    }
    if (Es-RaizDeUnidad $Ruta) {
        Escribir-Aviso "Es la raíz de una unidad: no se cambian sus permisos. Mejor una subcarpeta, por ejemplo $($Ruta.TrimEnd('\'))\Shelfie-respaldos."
        return
    }
    $unidad = New-Object System.IO.DriveInfo ([System.IO.Path]::GetPathRoot($Ruta))
    if ($unidad.DriveType -eq 'Network') {
        Escribir-Aviso "$($unidad.Name) es una unidad de red de este usuario: SYSTEM no la ve y el respaldo fallará. Use una carpeta local o una ruta \\servidor\carpeta."
        return
    }
    if (Esta-Dentro $Ruta $CarpetaPerfiles) {
        Escribir-Info 'Está en el perfil de un usuario (p. ej. su OneDrive): la leen ese usuario, los administradores y SYSTEM. No se cambia, para que siga sincronizando.'
        return
    }
    $problema = Proteger-Carpeta $Ruta
    if ($problema) {
        Escribir-Aviso "No se pudieron restringir los permisos de $Ruta (¿pendrive FAT/exFAT, que no los admite?): $problema"
    } else {
        Escribir-Ok "$($Ruta): solo Administradores y SYSTEM"
    }
}

function Correr-Python([string[]]$Argumentos, [string]$QueHace) {
    & $ShelfiePython @Argumentos
    if ($LASTEXITCODE -ne 0) { Detener-ConError "$QueHace falló (código $LASTEXITCODE). Revise los mensajes de arriba." }
}

Write-Host ''
Write-Host 'Instalación de Shelfie-lite' -ForegroundColor Cyan
Write-Host "Carpeta: $ShelfieRaiz"
if (-not (Test-Path (Join-Path $ShelfieBackend 'app\main.py'))) {
    Detener-ConError "No se encontró backend\app\main.py en $ShelfieRaiz. Ejecute el script desde la carpeta descomprimida."
}
if (-not (Test-Path (Join-Path $ShelfieRaiz 'frontend\out\index.html'))) {
    Escribir-Aviso 'No está frontend\out\index.html: el sistema solo respondería la API. Use el zip de empaquetar.sh.'
}
# Los archivos de un zip bajado de internet quedan "bloqueados"; se desbloquean los scripts.
Get-ChildItem -Path $PSScriptRoot -Filter '*.ps1' | Unblock-File -ErrorAction SilentlyContinue
# Dentro de C:\Users el dueño del perfil puede borrar o renombrar la carpeta protegida (tiene
# "eliminar subcarpetas" sobre la carpeta de arriba) y poner otra en su lugar.
if (Esta-Dentro $ShelfieRaiz $CarpetaPerfiles) {
    Detener-ConError "Shelfie-lite está dentro de una carpeta de usuario ($ShelfieRaiz). Muévalo a una carpeta fija fuera de $CarpetaPerfiles, por ejemplo C:\Shelfie-lite, y vuelva a ejecutar."
}

# --- 1. Requisitos -----------------------------------------------------------------
Escribir-Paso '1. Requisitos: Python 3.12 o más reciente y PostgreSQL 16 o más reciente'
$PythonBase = Buscar-Python
if (-not $PythonBase -and $script:PythonDeUsuarioDescartado) {
    Detener-ConError ("Solo hay un Python instalado para un usuario: $($script:PythonDeUsuarioDescartado.BasePrefix). " +
        'Ese usuario podría modificarlo, y Shelfie-lite lo ejecuta como SYSTEM al iniciar el equipo. ' +
        'Reinstale Python desde https://www.python.org/downloads/windows/ con "Customize installation" y, en ' +
        '"Advanced Options", marque "Install Python for all users" (queda en C:\Program Files\Python3xx). ' +
        'Si acepta el riesgo, vuelva a ejecutar con -PermitirPythonDeUsuario.')
}
if (-not $PythonBase) {
    Detener-ConError 'No se encontró Python 3.12 o más reciente. Instálelo desde https://www.python.org/downloads/windows/ con "Customize installation" → "Install Python for all users" (y "Add python.exe to PATH") y vuelva a ejecutar.'
}
Escribir-Ok "Python $($PythonBase.Version): $($PythonBase.Ejecutable)"
if (Es-PythonDeUsuario $PythonBase.BasePrefix) {
    Escribir-Aviso "Python instalado solo para un usuario ($($PythonBase.BasePrefix)), aceptado por -PermitirPythonDeUsuario."
    Escribir-Aviso 'Ese usuario puede modificar código que SYSTEM ejecuta al iniciar el equipo. Lo seguro es reinstalar Python "for all users" y volver a ejecutar instalar.ps1 sin esa opción.'
}
if ([version]$PythonBase.Version -gt [version]'3.13') {
    Escribir-Aviso 'Las dependencias están probadas con Python 3.12 y 3.13; con una versión más nueva podría faltar algún paquete.'
}
$Psql = Buscar-ProgramaPg 'psql'
if (-not $Psql) {
    Detener-ConError 'No se encontró PostgreSQL (psql.exe). Instale PostgreSQL 16 o más reciente con el instalador oficial (https://www.postgresql.org/download/windows/) y vuelva a ejecutar.'
}
Escribir-Ok "psql: $Psql"
foreach ($herramienta in @('pg_dump', 'pg_restore')) {
    if (-not (Test-Path (Join-Path (Split-Path $Psql) "$herramienta.exe"))) {
        Escribir-Aviso "No está $herramienta.exe junto a psql.exe: el respaldo o la restauración no funcionarán."
    }
}

# Antes de tocar el entorno de Python, se detiene el servidor si ya estaba instalado
# (Windows no deja reemplazar archivos que un proceso tiene abiertos).
if (-not (Detener-Shelfie)) {
    Detener-ConError "El puerto 8080 sigue ocupado por otro programa. Ciérrelo (netstat -ano | findstr :8080) y vuelva a ejecutar."
}

# --- Permisos de la carpeta --------------------------------------------------------
# Lo que está aquí lo corre SYSTEM al iniciar el equipo. Una carpeta nueva en C:\ hereda
# "Usuarios autenticados: Modificar": cualquier cuenta del personal podría cambiar un .ps1,
# un .py o un paquete del venv y ejecutarlo como SYSTEM. Se deja: Administradores y SYSTEM
# control total; Usuarios (S-1-5-32-545) solo leer y ejecutar.
Escribir-Paso 'Permisos: la carpeta de instalación solo la modifican los administradores'
if (Es-RaizDeUnidad $ShelfieRaiz) {
    Detener-ConError "Shelfie-lite está en la raíz de una unidad ($ShelfieRaiz). Muévalo a una carpeta, por ejemplo C:\Shelfie-lite."
}
$problema = Proteger-Carpeta $ShelfieRaiz -UsuariosLeen
if ($problema) { Detener-ConError "No se pudieron fijar los permisos de $($ShelfieRaiz): $problema" }
Escribir-Ok "$($ShelfieRaiz): Administradores y SYSTEM total, Usuarios solo lectura"
# El /reset de la raíz le quitó al .env sus permisos propios: se restringen ya mismo, antes
# de cualquier otro paso que pudiera fallar y dejarlo legible para los usuarios.
if (Test-Path $ShelfieEnv) {
    $problema = Proteger-Env
    if ($problema) { Detener-ConError "No se pudieron restringir los permisos de backend\.env: $problema" }
    Escribir-Ok 'backend\.env: solo Administradores y SYSTEM'
}
# Las copias que deja restaurar.ps1 tienen los datos y las claves cifradas de los usuarios.
$respaldosPrevios = Join-Path $ShelfieRaiz 'respaldos-previos'
New-Item -ItemType Directory -Force -Path $respaldosPrevios | Out-Null
$problema = Proteger-Carpeta $respaldosPrevios
if ($problema) { Detener-ConError "No se pudieron fijar los permisos de $($respaldosPrevios): $problema" }
Escribir-Ok 'respaldos-previos: solo Administradores y SYSTEM'

# --- 2. backend\.env -----------------------------------------------------------------
Escribir-Paso '2. Configuración (backend\.env)'
$EnvNuevo = -not (Test-Path $ShelfieEnv)
if ($EnvNuevo) {
    $claveBase = Clave-AlAzar 24
    $contenido = @(
        '# Generado por instalar.ps1. Contiene la clave de la base: no lo comparta.',
        "DATABASE_URL=postgresql://${UsuarioShelfie}:$claveBase@localhost:$PuertoPg/$BaseShelfie",
        "SECRET_KEY=$(Clave-AlAzar 48)",
        'ENTORNO=produccion',
        'CORS_ORIGINS=http://localhost:8080',
        'ZONA_HORARIA=America/Caracas',
        ''
    ) -join "`r`n"
    [System.IO.File]::WriteAllText($ShelfieEnv, $contenido, $Utf8SinBom)
    Escribir-Ok 'backend\.env creado (clave de la base y SECRET_KEY al azar)'
} else {
    Escribir-Ok 'backend\.env ya existe: se conserva tal cual'
}
# Un .env recién creado hereda "Usuarios: leer" de la raíz: se restringe enseguida.
$problema = Proteger-Env
if ($problema) { Detener-ConError "No se pudieron restringir los permisos de backend\.env: $problema" }
Escribir-Ok 'backend\.env: solo lo leen los administradores y el sistema'

$Variables = Leer-Env
if (-not $Variables['DATABASE_URL']) { Detener-ConError 'backend\.env no tiene DATABASE_URL.' }
$Conexion = Leer-Conexion $Variables['DATABASE_URL']
if (-not $Conexion) { Detener-ConError 'DATABASE_URL de backend\.env no tiene la forma postgresql://usuario:clave@servidor:puerto/base' }

# --- 3. Entorno de Python ------------------------------------------------------------
Escribir-Paso '3. Entorno de Python y dependencias'
Set-Location $ShelfieBackend
if (Test-Path $ShelfiePython) {
    $r = Ejecutar-Capturando $ShelfiePython @('-c', 'import sys; print(sys.base_prefix)')
    $baseDelVenv = ($r.Salida -split "`n")[-1].Trim()
    if ($r.Codigo -ne 0) {
        Escribir-Aviso 'El entorno backend\.venv no funciona (¿se desinstaló Python?): se vuelve a crear.'
        Remove-Item -Recurse -Force (Join-Path $ShelfieBackend '.venv')
    } elseif ((Es-PythonDeUsuario $baseDelVenv) -and -not $PermitirPythonDeUsuario) {
        Escribir-Aviso "backend\.venv usa un Python de usuario ($baseDelVenv): se vuelve a crear con $($PythonBase.Ejecutable)."
        Remove-Item -Recurse -Force (Join-Path $ShelfieBackend '.venv')
    }
}
if (-not (Test-Path $ShelfiePython)) {
    & $PythonBase.Ejecutable -m venv (Join-Path $ShelfieBackend '.venv')
    if ($LASTEXITCODE -ne 0) { Detener-ConError 'No se pudo crear el entorno de Python (backend\.venv).' }
    Escribir-Ok 'backend\.venv creado'
}
Correr-Python @('-m', 'pip', 'install', '--disable-pip-version-check', '--quiet', '--upgrade', 'pip') 'Actualizar pip'
Correr-Python @('-m', 'pip', 'install', '--disable-pip-version-check', '--quiet', '-r', 'requirements.txt') 'Instalar las dependencias (requiere internet)'
Escribir-Ok 'dependencias instaladas'

# --- 4. Base de datos ----------------------------------------------------------------
Escribir-Paso "4. Base de datos '$($Conexion.Base)'"
$r = Consultar-Pg $Conexion.Usuario $Conexion.Clave $Conexion.Base 'SHOW server_version_num;'
if ($r.Codigo -eq 0 -and -not $EnvNuevo) {
    Escribir-Ok "la base ya existe y Shelfie se conecta con su propio usuario ($($Conexion.Usuario))"
} else {
    Escribir-Info "Para crear el usuario y la base se necesita la clave de '$SuperusuarioPg' de PostgreSQL"
    Escribir-Info '(la que se eligió al instalar PostgreSQL). Se usa solo ahora y no se guarda.'
    $segura = Read-Host "Clave de '$SuperusuarioPg'" -AsSecureString
    $claveSuper = Texto-DeClaveSegura $segura
    try {
        $r = Consultar-Pg $SuperusuarioPg $claveSuper 'postgres' 'SHOW server_version_num;'
        if ($r.Codigo -ne 0) {
            Detener-ConError "No se pudo entrar a PostgreSQL como '$SuperusuarioPg' (¿clave incorrecta? ¿servicio detenido?): $($r.Salida)"
        }
        # Antes de crear nada: con un PostgreSQL viejo no se toca el servidor.
        Exigir-Pg16 (Version-Pg $r.Salida)
        # Si el usuario de Shelfie ya existía (p. ej. se borró el .env), se le pone la clave
        # del .env; si no existe, inicializar_bd lo crea con esa misma clave.
        $sql = @'
DO $$ BEGIN
  IF EXISTS (SELECT FROM pg_roles WHERE rolname = '__USUARIO__') THEN
    ALTER ROLE "__USUARIO__" LOGIN PASSWORD '__CLAVE__';
  END IF;
END $$;
'@
        $sql = $sql.Replace('__USUARIO__', $Conexion.Usuario.Replace("'", "''").Replace('"', '""')).Replace('__CLAVE__', $Conexion.Clave.Replace("'", "''"))
        if ($Conexion.Usuario -ne $SuperusuarioPg) { $r = Consultar-Pg $SuperusuarioPg $claveSuper 'postgres' $sql }
        if ($r.Codigo -ne 0) { Detener-ConError "No se pudo actualizar la clave del usuario '$($Conexion.Usuario)': $($r.Salida)" }
        # scripts.inicializar_bd crea el usuario y la base (si faltan) y migra; lee PGPASSWORD.
        $env:PGPASSWORD = $claveSuper
        Correr-Python @('-m', 'scripts.inicializar_bd', '--admin-user', $SuperusuarioPg, '--sin-test') 'Crear el usuario y la base'
    } finally {
        Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
        $claveSuper = $null
    }
    $r = Consultar-Pg $Conexion.Usuario $Conexion.Clave $Conexion.Base 'SHOW server_version_num;'
    if ($r.Codigo -ne 0) { Detener-ConError "Shelfie no puede conectarse a la base con su usuario: $($r.Salida)" }
}
$versionPg = Version-Pg $r.Salida
Exigir-Pg16 $versionPg
Escribir-Ok "PostgreSQL $([math]::Floor($versionPg / 10000))"
Correr-Python @('-m', 'alembic', 'upgrade', 'head') 'Actualizar el esquema (alembic upgrade head)'
Escribir-Ok 'esquema al día (alembic upgrade head)'

# --- 5. Administrador ----------------------------------------------------------------
Escribir-Paso '5. Administrador'
$contarAdmins = @'
from app.database import SessionLocal
from app import models
db = SessionLocal()
print(sum(1 for u in db.query(models.Usuario).all() if u.activo and 'superbibliotecario' in (u.permisos or [])))
db.close()
'@
$r = Ejecutar-Capturando $ShelfiePython @('-') $contarAdmins
$admins = 0
[void][int]::TryParse(($r.Salida -split "`n")[-1].Trim(), [ref]$admins)
if ($admins -eq 0) {
    Escribir-Info 'Todavía no hay administrador. Cree el primero (usuario y contraseña para entrar):'
    Correr-Python @('-m', 'scripts.crear_admin') 'Crear el administrador'
} else {
    Escribir-Ok "ya hay $admins administrador(es)"
    $respuesta = Read-Host '   ¿Crear otro administrador o cambiar una contraseña? [s/N]'
    if ($respuesta.Trim().ToLower() -eq 's') { Correr-Python @('-m', 'scripts.crear_admin') 'Crear el administrador' }
}

# --- 6. Carpeta de respaldo ----------------------------------------------------------
Escribir-Paso '6. Carpeta de respaldo'
$leerCarpeta = @'
from app.database import SessionLocal
from app.services import configuracion
db = SessionLocal()
print(configuracion.leer(db, 'respaldo').get('carpeta') or '')
db.close()
'@
$r = Ejecutar-Capturando $ShelfiePython @('-') $leerCarpeta
$carpeta = ''
if ($r.Codigo -eq 0 -and $r.Salida) { $carpeta = ($r.Salida -split "`n")[-1].Trim() }
if ($carpeta) {
    Escribir-Ok "configurada: $carpeta (se cambia en Configuración)"
    if (Test-Path -LiteralPath $carpeta -PathType Container) { Proteger-CarpetaDeRespaldo $carpeta }
    else { Escribir-Aviso "La carpeta configurada no existe o no está disponible: $carpeta" }
} else {
    $sugerida = Join-Path $env:SystemDrive 'Shelfie-respaldos'
    Escribir-Info 'El respaldo corre como SYSTEM, no como un usuario. Funciona:'
    Escribir-Info '  - una carpeta local o de un segundo disco (lo mejor), por ejemplo D:\Shelfie-respaldos;'
    Escribir-Info '  - la carpeta de Google Drive en modo "Duplicar archivos" (dentro de C:\Users\...), no la unidad G:;'
    Escribir-Info '  - la carpeta de OneDrive, que solo sincroniza mientras su usuario tiene la sesión abierta;'
    Escribir-Info '  - \\servidor\carpeta solo si el recurso deja escribir a la cuenta de este equipo o a Todos.'
    Escribir-Info 'Letras de unidad de red (Z:) o G: de Drive no: SYSTEM no las ve.'
    Escribir-Info 'Si la cambia luego en Configuración, pulse "Respaldar ahora" y revise que el resultado sea correcto.'
    $carpeta = (Read-Host "   Carpeta de respaldo [Enter = $sugerida]").Trim().Trim('"')
    if (-not $carpeta) { $carpeta = $sugerida }
    try {
        New-Item -ItemType Directory -Force -Path $carpeta | Out-Null
        $env:SHELFIE_CARPETA_RESPALDO = (Resolve-Path $carpeta).Path
        $guardarCarpeta = @'
import os
from app.database import SessionLocal
from app.services import configuracion
db = SessionLocal()
configuracion.guardar(db, {'respaldo': {'carpeta': os.environ['SHELFIE_CARPETA_RESPALDO']}}, anotar=False)
db.close()
'@
        $r = Ejecutar-Capturando $ShelfiePython @('-') $guardarCarpeta
        if ($r.Codigo -eq 0) {
            Escribir-Ok "carpeta de respaldo: $($env:SHELFIE_CARPETA_RESPALDO)"
            Proteger-CarpetaDeRespaldo $env:SHELFIE_CARPETA_RESPALDO
        } else { Escribir-Aviso "No se pudo guardar la carpeta; configúrela en Configuración. $($r.Salida)" }
    } catch {
        Escribir-Aviso "No se pudo crear la carpeta '$carpeta': $_. Configúrela luego en Configuración."
    } finally {
        Remove-Item Env:SHELFIE_CARPETA_RESPALDO -ErrorAction SilentlyContinue
    }
}

# --- 7. Firewall ---------------------------------------------------------------------
Escribir-Paso '7. Firewall: puerto 8080 solo para la red privada'
$nombreRegla = 'Shelfie-lite (TCP 8080)'
if (Get-NetFirewallRule -DisplayName $nombreRegla -ErrorAction SilentlyContinue) {
    Set-NetFirewallRule -DisplayName $nombreRegla -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow -Profile Private -Enabled True
    Escribir-Ok 'la regla ya existía: se dejó al día'
} else {
    New-NetFirewallRule -DisplayName $nombreRegla -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow -Profile Private | Out-Null
    Escribir-Ok 'regla creada'
}
$publicas = @(Get-NetConnectionProfile -ErrorAction SilentlyContinue | Where-Object { $_.NetworkCategory -eq 'Public' })
foreach ($red in $publicas) {
    Escribir-Aviso "La red '$($red.Name)' está como Pública: las PC de circulación no podrán entrar."
    Escribir-Info  "Si es la red de la biblioteca: Set-NetConnectionProfile -InterfaceIndex $($red.InterfaceIndex) -NetworkCategory Private"
}

# --- 8. Tareas programadas -----------------------------------------------------------
Escribir-Paso '8. Tareas programadas de Windows'
# Corren como SYSTEM: arrancan con el equipo aunque nadie inicie sesión.
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$argumentos = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$IniciarPs1`""

$accion = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $argumentos -WorkingDirectory $ShelfieBackend
$disparador = New-ScheduledTaskTrigger -AtStartup
# ExecutionTimeLimit cero = sin límite (por defecto Windows la cortaría a los 3 días).
$ajustes = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $TareaServidor -Action $accion -Trigger $disparador -Principal $principal `
    -Settings $ajustes -Description 'Servidor de Shelfie-lite en http://localhost:8080 (uvicorn).' -Force | Out-Null
Escribir-Ok "'$TareaServidor': al iniciar el equipo"

# Respaldo: python -m scripts.respaldar (vía iniciar.ps1 -Respaldo, que deja el log).
$accion = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "$argumentos -Respaldo" -WorkingDirectory $ShelfieBackend
$diario = New-ScheduledTaskTrigger -Daily -At '13:00'
$alIniciar = New-ScheduledTaskTrigger -AtStartup
$alIniciar.Delay = 'PT5M'   # 5 minutos después de encender, con PostgreSQL ya arriba
$ajustes = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName $TareaRespaldo -Action $accion -Trigger @($diario, $alIniciar) -Principal $principal `
    -Settings $ajustes -Description 'Respaldo diario de Shelfie-lite (python -m scripts.respaldar).' -Force | Out-Null
Escribir-Ok "'$TareaRespaldo': todos los días a las 13:00 y 5 minutos después de iniciar el equipo"

# --- 9. Accesos directos -------------------------------------------------------------
Escribir-Paso '9. Accesos directos'
$escritorio = [Environment]::GetFolderPath('CommonDesktopDirectory')
$acceso = "[InternetShortcut]`r`nURL=http://localhost:8080/`r`n"
[System.IO.File]::WriteAllText((Join-Path $escritorio 'Shelfie-lite.url'), $acceso, $Utf8SinBom)
Escribir-Ok "escritorio: Shelfie-lite (http://localhost:8080)"
$equipo = $env:COMPUTERNAME
$accesoCirculacion = "[InternetShortcut]`r`nURL=http://${equipo}:8080/`r`n"
$archivoCirculacion = Join-Path $ShelfieRaiz 'Shelfie-lite (circulación).url'
[System.IO.File]::WriteAllText($archivoCirculacion, $accesoCirculacion, $Utf8SinBom)
Escribir-Ok "para las PC de circulación: copie '$archivoCirculacion' a su escritorio"

# --- 10. Arranque y comprobación -----------------------------------------------------
Escribir-Paso '10. Arranque'
Start-ScheduledTask -TaskName $TareaServidor
if (Esperar-Shelfie 90) {
    Escribir-Ok 'Shelfie-lite responde en http://localhost:8080'
} else {
    Escribir-Aviso "Shelfie-lite no respondió en 90 segundos. Revise el log en $ShelfieLogs"
}
Escribir-Info 'Probando el respaldo (como lo hará la tarea programada)…'
$antes = (Get-ScheduledTaskInfo -TaskName $TareaRespaldo).LastRunTime
Start-ScheduledTask -TaskName $TareaRespaldo
# Start-ScheduledTask vuelve enseguida: hasta que la tarea arranca, el último resultado es el
# de antes (o 267011, «nunca corrió»). Primero se espera a que arranque (pasa por Running o
# cambia LastRunTime; tope de 60 s) y después a que termine (tope de 10 minutos).
$arranco = $false
$limiteArranque = (Get-Date).AddSeconds(60)
do {
    Start-Sleep -Seconds 1
    $estado = (Get-ScheduledTask -TaskName $TareaRespaldo).State
    $ultima = (Get-ScheduledTaskInfo -TaskName $TareaRespaldo).LastRunTime
    $arranco = ($estado -eq 'Running') -or ($ultima -ne $antes)
} while (-not $arranco -and (Get-Date) -lt $limiteArranque)
$limite = (Get-Date).AddMinutes(10)
while ((Get-ScheduledTask -TaskName $TareaRespaldo).State -eq 'Running' -and (Get-Date) -lt $limite) {
    Start-Sleep -Seconds 3
}
$resultado = (Get-ScheduledTaskInfo -TaskName $TareaRespaldo).LastTaskResult
if (-not $arranco) {
    Escribir-Aviso "La tarea de respaldo no arrancó en 60 segundos. Pruébela con 'Respaldar ahora' en Configuración."
} elseif ((Get-ScheduledTask -TaskName $TareaRespaldo).State -eq 'Running') {
    Escribir-Aviso "El respaldo de prueba sigue en curso después de 10 minutos. Revise el resultado en Configuración."
} elseif ($resultado -eq 0) { Escribir-Ok 'respaldo de prueba correcto' }
else { Escribir-Aviso "El respaldo de prueba falló (código $resultado). Detalle en Configuración y en $ShelfieLogs" }

# --- Resumen -------------------------------------------------------------------------
$ips = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
    ForEach-Object { "http://$($_.IPAddress):8080" })
Write-Host ''
Write-Host 'Listo.' -ForegroundColor Green
Write-Host "  En esta PC:          http://localhost:8080"
Write-Host "  Desde circulación:   http://${equipo}:8080"
if ($ips) { Write-Host "  (o por IP:           $($ips -join '  '))" }
Write-Host "  Logs:                $ShelfieLogs"
Write-Host '  Esta PC debe quedar encendida en el horario de atención.'
