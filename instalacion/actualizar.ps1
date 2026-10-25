#Requires -Version 5.1
#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Actualiza Shelfie-lite con un zip nuevo (shelfie-lite-<versión>.zip) en un solo paso.

.DESCRIPTION
    Como administrador, desde la carpeta donde está el zip:

        powershell -ExecutionPolicy Bypass -File C:\Shelfie-lite\instalacion\actualizar.ps1

    o indicando el zip:

        powershell -ExecutionPolicy Bypass -File C:\Shelfie-lite\instalacion\actualizar.ps1 -Zip "D:\shelfie-lite-abc1234.zip"

    1. Busca el zip (sin -Zip: el shelfie-lite-*.zip más nuevo de la carpeta actual o de
       Descargas), lo compara con su .sha256 si lo tiene al lado y comprueba que sea un
       paquete de empaquetar.sh (backend, frontend\out e instalacion). Todavía no toca nada.
    2. Hace un respaldo con la tarea programada, antes de cambiar nada.
    3. Detiene el servidor y deja backend, frontend e instalacion iguales a los del zip (lo
       que la versión nueva ya no trae se borra). Se conservan backend\.env (la clave de la
       base), backend\.venv, logs y respaldos-previos.
    4. Ejecuta el instalar.ps1 nuevo: dependencias, alembic upgrade head, permisos, tareas,
       arranque y respaldo de prueba. A la base solo le llega el alembic upgrade head.

    Se puede repetir sin riesgo: si se corta a mitad, vuelva a ejecutarlo con el mismo zip.

.PARAMETER Zip
    El zip de la versión nueva.

.PARAMETER Destino
    La instalación que se actualiza. Por defecto, la carpeta de este script si es una
    instalación y, si no (p. ej. corriendo el actualizar.ps1 de un zip descomprimido),
    C:\Shelfie-lite.

.PARAMETER Si
    No pide confirmación. Si el respaldo previo falla, se detiene sin actualizar.

.PARAMETER PermitirPythonDeUsuario
    Se pasa a instalar.ps1. Hace falta si la instalación usa un Python instalado solo para
    un usuario (se instaló con esa opción).

.PARAMETER SuperusuarioPg
    Se pasa a instalar.ps1 (solo se usa si hubiera que crear la base de nuevo).

.PARAMETER PuertoPg
    Se pasa a instalar.ps1.
#>
[CmdletBinding()]
param(
    [string]$Zip,
    [string]$Destino,
    [switch]$Si,
    [switch]$PermitirPythonDeUsuario,
    [string]$SuperusuarioPg = 'postgres',
    [int]$PuertoPg = 5432
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'comun.ps1')

# Las tres carpetas que trae el paquete; todo lo demás de la instalación queda como está.
$CarpetasDelPaquete = @('backend', 'frontend', 'instalacion')
$Temporal = $null
$RespaldoPausado = $false
$ServidorDetenido = $false
$ArchivosTocados = $false
$Terminado = $false

function Es-Instalacion([string]$Ruta) {
    return (Test-Path -LiteralPath (Join-Path $Ruta 'backend\.env')) -and
        (Test-Path -LiteralPath (Join-Path $Ruta 'backend\app\main.py'))
}

function Leer-Version([string]$Raiz) {
    <# instalacion\VERSION.txt lo escribe empaquetar.sh; una instalación anterior no lo tiene. #>
    $archivo = Join-Path $Raiz 'instalacion\VERSION.txt'
    if (Test-Path -LiteralPath $archivo) { return ([System.IO.File]::ReadAllText($archivo)).Trim() }
    return 'sin dato'
}

function Borrar-Temporal {
    if ($script:Temporal -and (Test-Path -LiteralPath $script:Temporal)) {
        Remove-Item -LiteralPath $script:Temporal -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Reactivar-Respaldo {
    if ($script:RespaldoPausado) {
        Enable-ScheduledTask -TaskName $TareaRespaldo -ErrorAction SilentlyContinue | Out-Null
        $script:RespaldoPausado = $false
    }
}

function Al-Terminar {
    <# Corre siempre al salir (error, exit, Ctrl+C): nada queda pausado ni a medias sin aviso. #>
    Reactivar-Respaldo
    Borrar-Temporal
    if ($script:Terminado) { return }
    if ($script:ServidorDetenido -and -not $script:ArchivosTocados) {
        # Todavía no se cambió ningún archivo: se vuelve a levantar la versión que estaba.
        Start-ScheduledTask -TaskName $TareaServidor -ErrorAction SilentlyContinue
        Write-Host 'Shelfie-lite se volvió a iniciar con la versión que ya estaba.' -ForegroundColor Yellow
    } elseif ($script:ArchivosTocados -and
              -not (Get-NetTCPConnection -LocalPort $ShelfiePuerto -State Listen -ErrorAction SilentlyContinue)) {
        Write-Host ('Shelfie-lite quedó DETENIDO con la actualización a medias. Vuelva a ejecutar ' +
            'actualizar.ps1 con el mismo zip (se puede repetir).') -ForegroundColor Red
    }
}

function Cancelar([string]$Texto = 'Cancelado: no se cambió nada.') {
    Write-Host $Texto
    exit 1
}

function Copiar-Espejo([string]$Origen, [string]$Hacia, [string[]]$Excluir = @()) {
    <# robocopy /MIR: deja $Hacia igual a $Origen (borra lo que sobra), salvo los nombres de
       $Excluir, que ni se copian ni se borran. Devuelve $null o el mensaje de error. #>
    $argumentos = @($Origen, $Hacia, '/MIR', '/R:2', '/W:2', '/NFL', '/NDL', '/NJH', '/NJS', '/NP')
    if ($Excluir.Count -gt 0) { $argumentos += @('/XD') + $Excluir + @('/XF') + $Excluir }
    $r = Ejecutar-Capturando 'robocopy.exe' $argumentos
    # robocopy: de 0 a 7 es éxito (1 = copió, 2 = había de más y se borró…); 8 o más, error.
    if ($r.Codigo -lt 0 -or $r.Codigo -ge 8) { return "robocopy hacia $Hacia (código $($r.Codigo)): $($r.Salida)" }
    return $null
}

function Base-DelVenv([string]$Raiz) {
    <# La carpeta del Python con el que se creó backend\.venv (línea "home" de pyvenv.cfg). #>
    $cfg = Join-Path $Raiz 'backend\.venv\pyvenv.cfg'
    if (-not (Test-Path -LiteralPath $cfg)) { return $null }
    foreach ($linea in [System.IO.File]::ReadAllLines($cfg)) {
        $m = [regex]::Match($linea, '^\s*home\s*=\s*(.+?)\s*$')
        if ($m.Success) { return $m.Groups[1].Value }
    }
    return $null
}

try {
    Write-Host ''
    Write-Host 'Actualización de Shelfie-lite' -ForegroundColor Cyan

    # --- Comprobaciones (todavía no se toca nada) -----------------------------------------
    if (-not $Destino) {
        if (Es-Instalacion $ShelfieRaiz) { $Destino = $ShelfieRaiz } else { $Destino = 'C:\Shelfie-lite' }
    }
    $Destino = $Destino.Trim().Trim('"')
    if (-not (Test-Path -LiteralPath $Destino -PathType Container)) {
        Detener-ConError "No existe la carpeta '$Destino'. Para instalar por primera vez use instalar.ps1."
    }
    $Destino = (Resolve-Path -LiteralPath $Destino).Path.TrimEnd('\')
    if (-not (Es-Instalacion $Destino)) {
        Detener-ConError "$Destino no es una instalación de Shelfie-lite (falta backend\.env o backend\app\main.py). Para instalar por primera vez use instalar.ps1."
    }
    if ((Es-RaizDeUnidad $Destino) -or (Esta-Dentro $Destino $CarpetaPerfiles)) {
        Detener-ConError "La instalación está en $Destino; instalar.ps1 no la acepta ahí. Muévala a una carpeta fija como C:\Shelfie-lite."
    }

    # Sin -PermitirPythonDeUsuario, instalar.ps1 se detendría a mitad: se avisa antes de empezar.
    $baseVenv = Base-DelVenv $Destino
    if ($baseVenv -and (Esta-Dentro $baseVenv $CarpetaPerfiles) -and -not $PermitirPythonDeUsuario) {
        Detener-ConError ("La instalación usa un Python instalado solo para un usuario ($baseVenv). " +
            'Vuelva a ejecutar con -PermitirPythonDeUsuario (como se instaló), o reinstale Python ' +
            '"for all users" y ejecute instalar.ps1.')
    }

    if (-not $Zip) {
        $carpetas = @((Get-Location).Path)
        $descargas = Join-Path $env:USERPROFILE 'Downloads'
        if (Test-Path -LiteralPath $descargas) { $carpetas += $descargas }
        $candidato = $carpetas |
            ForEach-Object { Get-ChildItem -LiteralPath $_ -Filter 'shelfie-lite-*.zip' -File -ErrorAction SilentlyContinue } |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if (-not $candidato) {
            Detener-ConError "No hay ningún shelfie-lite-*.zip en $($carpetas -join ' ni en '). Indique el archivo: -Zip ""ruta\shelfie-lite-xxxxxxx.zip""."
        }
        $Zip = $candidato.FullName
    }
    $Zip = $Zip.Trim().Trim('"')
    if (-not (Test-Path -LiteralPath $Zip -PathType Leaf)) { Detener-ConError "No existe el archivo '$Zip'." }
    $Zip = (Resolve-Path -LiteralPath $Zip).Path
    $archivoHash = "$Zip.sha256"
    if (Test-Path -LiteralPath $archivoHash) {
        $esperado = (([System.IO.File]::ReadAllText($archivoHash)).Trim() -split '\s+')[0].ToLowerInvariant()
        $real = (Get-FileHash -LiteralPath $Zip -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($esperado -ne $real) {
            Detener-ConError "El zip no coincide con su .sha256: está incompleto o dañado. Vuelva a copiarlo."
        }
        $integridad = 'coincide con su .sha256'
    } else {
        $integridad = 'sin .sha256 al lado: no se comprobó'
    }

    # Se descomprime dentro de la instalación: hereda sus permisos (solo los administradores
    # pueden cambiar lo que después se copia y ejecuta como SYSTEM).
    $Temporal = Join-Path $Destino ('.actualizacion-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    try {
        Expand-Archive -LiteralPath $Zip -DestinationPath $Temporal -Force
    } catch {
        Detener-ConError "No se pudo descomprimir el zip: $_"
    }
    foreach ($necesario in @('backend\app\main.py', 'backend\requirements.txt', 'frontend\out\index.html',
                             'instalacion\instalar.ps1', 'instalacion\comun.ps1', 'instalacion\iniciar.ps1')) {
        if (-not (Test-Path -LiteralPath (Join-Path $Temporal $necesario))) {
            Detener-ConError "El zip no es un paquete de Shelfie-lite: falta $necesario. Use el zip que genera scripts/empaquetar.sh, no una copia del repositorio."
        }
    }
    if ((Test-Path -LiteralPath (Join-Path $Temporal 'backend\.env')) -or (Test-Path -LiteralPath (Join-Path $Temporal 'backend\.venv'))) {
        Detener-ConError 'El zip trae backend\.env o backend\.venv: no es un paquete de empaquetar.sh y pisaría la configuración.'
    }

    # Un zip más viejo que lo instalado no trae las migraciones nuevas: /MIR las borraría y
    # alembic upgrade head fallaría con el servidor ya detenido.
    $migracionesNuevas = @(Get-ChildItem -LiteralPath (Join-Path $Temporal 'backend\migrations\versions') -Filter '*.py' -File -ErrorAction SilentlyContinue | ForEach-Object { $_.Name })
    $faltan = @(Get-ChildItem -LiteralPath (Join-Path $Destino 'backend\migrations\versions') -Filter '*.py' -File -ErrorAction SilentlyContinue |
        Where-Object { $migracionesNuevas -notcontains $_.Name } | ForEach-Object { $_.Name })
    if ($faltan.Count -gt 0) {
        Detener-ConError "El zip es de una versión anterior a la instalada (no trae $($faltan -join ', ')). Use el zip más nuevo."
    }

    # instalar.ps1 descarga dependencias con pip: sin internet se cortaría con todo ya copiado.
    # Se prueba con el Python del venv (TLS y certificados como los de pip; Invoke-WebRequest
    # de PowerShell 5.1 puede no tener TLS 1.2 y fallar aunque haya conexión).
    $pythonVenv = Join-Path $Destino 'backend\.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $pythonVenv) {
        $r = Ejecutar-Capturando $pythonVenv @('-c', "import urllib.request; urllib.request.urlopen('https://pypi.org/simple/pip/', timeout=20)")
        if ($r.Codigo -ne 0) {
            $detalle = ($r.Salida -split "`n")[-1]
            Detener-ConError "Sin conexión con pypi.org ($detalle). instalar.ps1 necesita internet para las dependencias de Python. Conecte la PC y vuelva a ejecutar: no se cambió nada."
        }
    }

    $versionActual = Leer-Version $Destino
    $versionNueva = Leer-Version $Temporal
    Write-Host ''
    Write-Host "  Instalación:  $Destino (versión $versionActual)"
    Write-Host "  Paquete:      $Zip"
    Write-Host "                versión $versionNueva, del $((Get-Item -LiteralPath $Zip).LastWriteTime.ToString('dd/MM/yyyy HH:mm')), $integridad"
    if ($versionNueva -ne 'sin dato' -and $versionNueva -eq $versionActual) {
        Escribir-Aviso 'Es la misma versión que ya está instalada: se vuelve a instalar igual.'
    }
    Write-Host '  Se conservan backend\.env, backend\.venv, logs y respaldos-previos; a la base solo'
    Write-Host '  le llega alembic upgrade head. Mientras dura (unos minutos) Shelfie-lite no responde.'
    Write-Host ''
    if (-not $Si) {
        $respuesta = Read-Host '¿Actualizar ahora? [S/n]'
        if ($respuesta.Trim().ToLower() -eq 'n') { Cancelar }
    }

    # --- 1. Respaldo previo ----------------------------------------------------------------
    Escribir-Paso '1. Respaldo antes de actualizar'
    $infoRespaldo = Get-ScheduledTask -TaskName $TareaRespaldo -ErrorAction SilentlyContinue
    if ($infoRespaldo) {
        # Una ejecución anterior cortada a mitad pudo dejarla desactivada.
        if ($infoRespaldo.State -eq 'Disabled') { Enable-ScheduledTask -TaskName $TareaRespaldo | Out-Null }
        $resultado = Correr-TareaDeRespaldo
        if ($resultado -eq 'en-curso') {
            Cancelar 'El respaldo sigue en curso después de 10 minutos: espere a que termine y vuelva a ejecutar. No se cambió nada.'
        }
        if ($resultado -eq 'ok') {
            Escribir-Ok 'respaldo correcto (en la carpeta configurada en Configuración)'
        } else {
            Escribir-Aviso "El respaldo previo no salió bien ($resultado). Detalle en $(Join-Path $Destino 'logs')."
            if ($Si) { Detener-ConError 'No se actualizó porque el respaldo previo falló. Revíselo, o ejecute sin -Si para decidir.' }
            $respuesta = Read-Host '   ¿Actualizar de todos modos, sin respaldo de hoy? [s/N]'
            if ($respuesta.Trim().ToLower() -ne 's') { Cancelar }
        }
    } else {
        Escribir-Aviso "No existe la tarea '$TareaRespaldo': se sigue sin respaldo previo (instalar.ps1 la vuelve a crear)."
    }

    # --- 2. Detener ------------------------------------------------------------------------
    Escribir-Paso '2. Detener Shelfie-lite'
    # Que el respaldo diario no arranque mientras se reemplazan los archivos. instalar.ps1 vuelve
    # a registrar la tarea (activa); si algo falla antes, Al-Terminar la reactiva.
    if (Get-ScheduledTask -TaskName $TareaRespaldo -ErrorAction SilentlyContinue) {
        Disable-ScheduledTask -TaskName $TareaRespaldo | Out-Null
        $RespaldoPausado = $true
    }
    $ServidorDetenido = $true
    if (-not (Detener-Shelfie)) {
        Detener-ConError "El puerto 8080 sigue ocupado por otro programa. Ciérrelo (netstat -ano | findstr :8080) y vuelva a ejecutar."
    }
    Escribir-Ok 'servidor detenido'

    # --- 3. Copiar -------------------------------------------------------------------------
    Escribir-Paso '3. Copiar la versión nueva'
    $ArchivosTocados = $true
    foreach ($carpeta in $CarpetasDelPaquete) {
        $excluir = @()
        if ($carpeta -eq 'backend') { $excluir = @('.env', '.venv') }
        $problema = Copiar-Espejo (Join-Path $Temporal $carpeta) (Join-Path $Destino $carpeta) $excluir
        if ($problema) {
            Detener-ConError "La copia no terminó: $problema"
        }
        Escribir-Ok "$carpeta al día"
    }
    Borrar-Temporal

    # --- 4. instalar.ps1 de la versión nueva -----------------------------------------------
    Escribir-Paso '4. instalar.ps1 de la versión nueva'
    $argumentos = @('-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', (Join-Path $Destino 'instalacion\instalar.ps1'),
        '-SuperusuarioPg', $SuperusuarioPg, '-PuertoPg', "$PuertoPg", '-Actualizacion')
    if ($PermitirPythonDeUsuario) { $argumentos += '-PermitirPythonDeUsuario' }
    & powershell.exe @argumentos
    $codigo = $LASTEXITCODE
    if ($codigo -ne 0) {
        Detener-ConError "instalar.ps1 no terminó (código $codigo). Corrija lo que indica arriba."
    }
    # instalar.ps1 registró de nuevo la tarea de respaldo (activa) y levantó el servidor.
    $RespaldoPausado = $false
    $Terminado = $true

    Write-Host ''
    Write-Host "Shelfie-lite actualizado a la versión $versionNueva." -ForegroundColor Green
} finally {
    Al-Terminar
}
