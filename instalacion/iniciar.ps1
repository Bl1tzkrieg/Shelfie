#Requires -Version 5.1
<#
.SYNOPSIS
    Arranca el servidor de Shelfie-lite (uvicorn en el puerto 8080) y lo mantiene vivo.
    Con -Respaldo, en cambio, hace un respaldo (python -m scripts.respaldar) y termina.

.DESCRIPTION
    Lo corren las tareas programadas "Shelfie-lite" y "Shelfie-lite respaldo" que registra
    instalar.ps1. Todo lo que escriben uvicorn y el respaldo queda en
    logs\shelfie-AAAAMMDD.log y logs\respaldo-AAAAMMDD.log (un archivo por día; se
    conservan los 14 más recientes de cada uno).

    Si uvicorn se cae, se vuelve a levantar a los 10 segundos.
#>
[CmdletBinding()]
param([switch]$Respaldo)

# Continue: el stderr de Python (donde uvicorn escribe su log) no debe cortar el script.
$ErrorActionPreference = 'Continue'
. (Join-Path $PSScriptRoot 'comun.ps1')

$DiasDeLog = 14
$script:ArchivoActual = $null

function Limpiar-Logs([string]$Prefijo) {
    Get-ChildItem -Path $ShelfieLogs -Filter "$Prefijo-*.log" -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending | Select-Object -Skip $DiasDeLog |
        Remove-Item -Force -ErrorAction SilentlyContinue
}

function Escribir-Log([string]$Prefijo, [string]$Linea) {
    $archivo = Join-Path $ShelfieLogs ('{0}-{1:yyyyMMdd}.log' -f $Prefijo, (Get-Date))
    if ($archivo -ne $script:ArchivoActual) {
        # Cambió el día (o recién arranca): archivo nuevo y se borran los viejos.
        $script:ArchivoActual = $archivo
        Limpiar-Logs $Prefijo
    }
    try { [System.IO.File]::AppendAllText($archivo, $Linea + "`r`n", $Utf8SinBom) } catch { }
}

function Marca { return (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') }

New-Item -ItemType Directory -Force -Path $ShelfieLogs | Out-Null
$prefijo = 'shelfie'
if ($Respaldo) { $prefijo = 'respaldo' }

if (-not (Test-Path $ShelfiePython)) {
    Escribir-Log $prefijo "$(Marca) ERROR: no existe $ShelfiePython. Vuelva a ejecutar instalar.ps1."
    exit 1
}

# backend\.env se lee desde la carpeta actual; Python escribe en UTF-8 y sin búfer.
Set-Location $ShelfieBackend
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUNBUFFERED = '1'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

if ($Respaldo) {
    Escribir-Log $prefijo "$(Marca) Respaldo: python -m scripts.respaldar"
    & $ShelfiePython -m scripts.respaldar 2>&1 | ForEach-Object { Escribir-Log $prefijo "$_" }
    $codigo = $LASTEXITCODE
    Escribir-Log $prefijo "$(Marca) Respaldo terminado (código $codigo)"
    exit $codigo
}

while ($true) {
    Escribir-Log $prefijo "$(Marca) Iniciando Shelfie-lite en http://0.0.0.0:8080"
    & $ShelfiePython -m uvicorn app.main:app --host 0.0.0.0 --port 8080 2>&1 |
        ForEach-Object { Escribir-Log $prefijo "$_" }
    Escribir-Log $prefijo "$(Marca) uvicorn terminó (código $LASTEXITCODE); se reinicia en 10 segundos"
    Start-Sleep -Seconds 10
}
