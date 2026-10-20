#Requires -Version 5.1
#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Restaura la base de Shelfie-lite desde una carpeta de respaldo (shelfie-AAAAMMDD-HHMM).

.DESCRIPTION
    Como administrador:

        powershell -ExecutionPolicy Bypass -File .\instalacion\restaurar.ps1 "D:\Respaldos\shelfie-20261020-1300"

    1. Comprueba que la carpeta tenga base.dump y pide escribir RESTAURAR.
    2. Guarda una copia de la base actual en respaldos-previos\antes-de-restaurar-...\base.dump
       (para deshacer: restaurar.ps1 con esa carpeta).
    3. Detiene el servidor, hace pg_restore --clean --if-exists (en una sola transacción:
       si algo falla, la base queda como estaba), pone el esquema al día y lo vuelve a iniciar.

    Si base.dump no sirve, el catálogo se puede recuperar importando catalogo.mrc
    (Libros → Importar MARC) en una instalación nueva.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Carpeta
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'comun.ps1')

function Iniciar-DeNuevo {
    if (Get-ScheduledTask -TaskName $TareaServidor -ErrorAction SilentlyContinue) {
        Start-ScheduledTask -TaskName $TareaServidor
        if (Esperar-Shelfie 90) { Escribir-Ok 'Shelfie-lite volvió a iniciar: http://localhost:8080' }
        else { Escribir-Aviso "Shelfie-lite no respondió. Revise los logs en $ShelfieLogs" }
    } else {
        Escribir-Aviso "No está la tarea '$TareaServidor': vuelva a ejecutar instalar.ps1 para iniciarlo."
    }
}

Write-Host ''
Write-Host 'Restauración de Shelfie-lite' -ForegroundColor Cyan

# --- Comprobaciones (todavía no se toca nada) -----------------------------------------
$Carpeta = $Carpeta.Trim().Trim('"')
if (-not (Test-Path -LiteralPath $Carpeta -PathType Container)) {
    Detener-ConError "No existe la carpeta '$Carpeta'."
}
$Carpeta = (Resolve-Path -LiteralPath $Carpeta).Path
$Dump = Join-Path $Carpeta 'base.dump'
if (-not (Test-Path -LiteralPath $Dump -PathType Leaf) -or (Get-Item -LiteralPath $Dump).Length -eq 0) {
    Detener-ConError "La carpeta no tiene un base.dump válido: $Carpeta. Elija una carpeta shelfie-AAAAMMDD-HHMM."
}
$Variables = Leer-Env
if (-not $Variables['DATABASE_URL']) { Detener-ConError "No se pudo leer DATABASE_URL de $ShelfieEnv (¿se instaló con instalar.ps1?)." }
$Conexion = Leer-Conexion $Variables['DATABASE_URL']
if (-not $Conexion) { Detener-ConError 'DATABASE_URL de backend\.env no tiene la forma postgresql://usuario:clave@servidor:puerto/base' }
$PgRestore = Buscar-ProgramaPg 'pg_restore'
$PgDump = Buscar-ProgramaPg 'pg_dump'
if (-not $PgRestore -or -not $PgDump) { Detener-ConError 'No se encontraron pg_restore.exe y pg_dump.exe de PostgreSQL.' }
$Comunes = @('-w', '-h', $Conexion.Servidor, '-p', "$($Conexion.Puerto)", '-U', $Conexion.Usuario)

Write-Host ''
Write-Host "  Respaldo:   $Carpeta"
Write-Host "  Archivo:    base.dump ($([math]::Round((Get-Item -LiteralPath $Dump).Length / 1MB, 1)) MB, del $((Get-Item -LiteralPath $Dump).LastWriteTime.ToString('dd/MM/yyyy HH:mm')))"
Write-Host "  Base:       $($Conexion.Base) en $($Conexion.Servidor):$($Conexion.Puerto)"
Write-Host ''
Write-Host '  ATENCIÓN: todo lo que se cargó después de ese respaldo se perderá' -ForegroundColor Yellow
Write-Host '  (libros, ejemplares, usuarios y configuración vuelven a como estaban).' -ForegroundColor Yellow
Write-Host '  Mientras dura, nadie podrá usar Shelfie-lite.' -ForegroundColor Yellow
Write-Host ''
$confirmacion = Read-Host 'Para continuar escriba RESTAURAR (en mayúsculas)'
if ($confirmacion.Trim() -cne 'RESTAURAR') {
    Write-Host 'Cancelado: no se cambió nada.'
    exit 1
}

$env:PGPASSWORD = $Conexion.Clave   # nunca en la línea de comandos
try {
    # --- Copia de lo que hay ahora ------------------------------------------------------
    Escribir-Paso '1. Copia de seguridad de la base actual'
    # Queda como una carpeta de respaldo más: se puede pasar a este mismo script para deshacer.
    $previa = Join-Path $ShelfieRaiz ('respaldos-previos\antes-de-restaurar-{0:yyyyMMdd-HHmmss}' -f (Get-Date))
    New-Item -ItemType Directory -Force -Path $previa | Out-Null
    $copia = Join-Path $previa 'base.dump'
    $r = Ejecutar-Capturando $PgDump ($Comunes + @('-Fc', '-f', $copia, $Conexion.Base))
    if ($r.Codigo -ne 0) {
        Detener-ConError "No se pudo copiar la base actual (no se restauró nada): $($r.Salida)"
    }
    Escribir-Ok "copia guardada en $previa"

    # --- Restauración -------------------------------------------------------------------
    Escribir-Paso '2. Deteniendo Shelfie-lite'
    if (-not (Detener-Shelfie)) { Escribir-Aviso 'El puerto 8080 sigue ocupado; se intenta restaurar igual.' }
    else { Escribir-Ok 'detenido' }

    Escribir-Paso '3. Restaurando base.dump'
    $r = Ejecutar-Capturando $PgRestore ($Comunes + @('--clean', '--if-exists', '--no-owner', '--no-acl',
        '--single-transaction', '-d', $Conexion.Base, $Dump))
    if ($r.Codigo -ne 0) {
        Write-Host $r.Salida
        Escribir-Aviso 'pg_restore falló: la base quedó como estaba antes (todo va en una sola transacción).'
        Escribir-Info  "Si base.dump está dañado, importe catalogo.mrc de la misma carpeta. La copia previa está en $previa"
        Iniciar-DeNuevo
        exit 1
    }
    Escribir-Ok 'base restaurada'

    Escribir-Paso '4. Poniendo el esquema al día (alembic upgrade head)'
    if (Test-Path $ShelfiePython) {
        Set-Location $ShelfieBackend
        & $ShelfiePython -m alembic upgrade head
        if ($LASTEXITCODE -eq 0) { Escribir-Ok 'esquema al día' }
        else { Escribir-Aviso 'alembic upgrade head falló; ejecute instalar.ps1 de nuevo.' }
    } else {
        Escribir-Aviso 'No está backend\.venv: ejecute instalar.ps1 de nuevo.'
    }
} finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}

Escribir-Paso '5. Iniciando Shelfie-lite'
Iniciar-DeNuevo
Write-Host ''
Write-Host "Listo: se restauró el respaldo de $Carpeta." -ForegroundColor Green
Write-Host "Para deshacerlo: restaurar.ps1 `"$previa`""
