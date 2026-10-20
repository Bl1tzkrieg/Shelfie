#Requires -Version 5.1
<#
    Funciones que comparten instalar.ps1, iniciar.ps1 y restaurar.ps1.
    No se corre sola: los otros scripts la cargan con  . "$PSScriptRoot\comun.ps1"

    Todo tiene que funcionar en Windows PowerShell 5.1 (el que trae Windows 10):
    nada de ??, ?:, && ni ConvertFrom-SecureString -AsPlainText.
#>

$ShelfieRaiz    = Split-Path -Parent $PSScriptRoot
$ShelfieBackend = Join-Path $ShelfieRaiz 'backend'
$ShelfieEnv     = Join-Path $ShelfieBackend '.env'
$ShelfiePython  = Join-Path $ShelfieBackend '.venv\Scripts\python.exe'
$ShelfieLogs    = Join-Path $ShelfieRaiz 'logs'
$ShelfiePuerto  = 8080
$TareaServidor  = 'Shelfie-lite'
$TareaRespaldo  = 'Shelfie-lite respaldo'
# El .env lo lee Python: sin BOM (si no, la primera variable no se reconoce).
$Utf8SinBom     = New-Object System.Text.UTF8Encoding $false

function Escribir-Paso([string]$Texto) { Write-Host ''; Write-Host "== $Texto" -ForegroundColor Cyan }
function Escribir-Ok([string]$Texto)   { Write-Host "   [ok] $Texto" -ForegroundColor Green }
function Escribir-Info([string]$Texto) { Write-Host "   $Texto" }
function Escribir-Aviso([string]$Texto) { Write-Host "   [!] $Texto" -ForegroundColor Yellow }

function Detener-ConError([string]$Texto) {
    Write-Host ''
    Write-Host "ERROR: $Texto" -ForegroundColor Red
    Write-Host 'No se terminó. Corrija lo indicado y vuelva a ejecutar el script (se puede repetir sin riesgo).' -ForegroundColor Red
    exit 1
}

function Ejecutar-Capturando {
    <# Corre un programa y devuelve su código de salida y lo que escribió (stdout y stderr).
       En PowerShell 5.1, redirigir el stderr de un programa con ErrorActionPreference=Stop
       lo convierte en una excepción: aquí se usa Continue solo dentro de la función. #>
    param([string]$Programa, [string[]]$Argumentos = @(), [string]$Entrada = $null)
    $ErrorActionPreference = 'Continue'
    try {
        if ($Entrada) {
            $lineas = $Entrada | & $Programa @Argumentos 2>&1 | ForEach-Object { "$_" }
        } else {
            $lineas = & $Programa @Argumentos 2>&1 | ForEach-Object { "$_" }
        }
        $codigo = $LASTEXITCODE
    } catch {
        $lineas = @("$_")
        $codigo = -1
    }
    return [pscustomobject]@{ Codigo = $codigo; Salida = (@($lineas) -join "`n").Trim() }
}

function Buscar-ProgramaPg([string]$Nombre) {
    <# Igual que encontrar_pg_dump del backend: primero el PATH y luego
       C:\Program Files\PostgreSQL\<versión>\bin, con la versión más alta. #>
    $enElPath = Get-Command "$Nombre.exe" -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($enElPath) { return $enElPath.Source }
    $bases = @($env:ProgramFiles, ${env:ProgramFiles(x86)}) | Where-Object { $_ }
    $candidatos = foreach ($base in $bases) {
        Get-ChildItem -Path (Join-Path $base 'PostgreSQL') -Directory -ErrorAction SilentlyContinue |
            ForEach-Object {
                $exe = Join-Path $_.FullName "bin\$Nombre.exe"
                if (Test-Path $exe) {
                    # Se comparan números («16» > «9.6»), no texto.
                    $numeros = [regex]::Matches($_.Name, '\d+') | ForEach-Object { [int]$_.Value }
                    $version = (@($numeros) + @(0, 0, 0))[0..2]
                    [pscustomobject]@{ Ruta = $exe; Orden = ('{0:D5}.{1:D5}.{2:D5}' -f $version[0], $version[1], $version[2]) }
                }
            }
    }
    $mejor = @($candidatos) | Where-Object { $_ } | Sort-Object Orden -Descending | Select-Object -First 1
    if ($mejor) { return $mejor.Ruta }
    return $null
}

function Leer-Env {
    <# Las variables de backend\.env como tabla (sin comentarios ni líneas vacías). #>
    $valores = @{}
    if (-not (Test-Path $ShelfieEnv)) { return $valores }
    foreach ($linea in [System.IO.File]::ReadAllLines($ShelfieEnv)) {
        $limpia = $linea.Trim().TrimStart([char]0xFEFF)
        if (-not $limpia -or $limpia.StartsWith('#') -or -not $limpia.Contains('=')) { continue }
        $i = $limpia.IndexOf('=')
        $valores[$limpia.Substring(0, $i).Trim()] = $limpia.Substring($i + 1).Trim()
    }
    return $valores
}

function Leer-Conexion([string]$DatabaseUrl) {
    <# postgresql://usuario:clave@servidor:puerto/base → sus partes (la clave sin %XX). #>
    $m = [regex]::Match($DatabaseUrl, '^postgresql(?:\+\w+)?://([^:@/]+)(?::([^@/]*))?@([^:/]+)(?::(\d+))?/([^?]+)')
    if (-not $m.Success) { return $null }
    $puerto = 5432
    if ($m.Groups[4].Success) { $puerto = [int]$m.Groups[4].Value }
    return [pscustomobject]@{
        Usuario  = [Uri]::UnescapeDataString($m.Groups[1].Value)
        Clave    = [Uri]::UnescapeDataString($m.Groups[2].Value)
        Servidor = $m.Groups[3].Value
        Puerto   = $puerto
        Base     = $m.Groups[5].Value
    }
}

function Detener-Shelfie {
    <# Detiene el servidor: la tarea programada, el PowerShell de iniciar.ps1 (que si no
       volvería a levantarlo) y el uvicorn. Devuelve $true si el puerto quedó libre. #>
    if (Get-ScheduledTask -TaskName $TareaServidor -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $TareaServidor -ErrorAction SilentlyContinue
    }
    $procesos = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -and (
            ($_.Name -eq 'powershell.exe' -and $_.CommandLine -like '*iniciar.ps1*' -and $_.CommandLine -notlike '*-Respaldo*') -or
            ($_.Name -like 'python*.exe' -and $_.CommandLine -like '*uvicorn*app.main:app*'))
    })
    # Primero el PowerShell que vigila, después los uvicorn.
    foreach ($p in ($procesos | Sort-Object { $_.Name -ne 'powershell.exe' })) {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    for ($i = 0; $i -lt 30; $i++) {
        if (-not (Get-NetTCPConnection -LocalPort $ShelfiePuerto -State Listen -ErrorAction SilentlyContinue)) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Esperar-Shelfie([int]$Segundos = 90) {
    <# Espera a que http://localhost:8080/ responda. #>
    $limite = (Get-Date).AddSeconds($Segundos)
    while ((Get-Date) -lt $limite) {
        try {
            $r = Invoke-WebRequest -Uri "http://localhost:$ShelfiePuerto/" -UseBasicParsing -TimeoutSec 5
            if ($r.StatusCode -eq 200) { return $true }
        } catch { }
        Start-Sleep -Seconds 2
    }
    return $false
}
