"""Instalación en Windows: los scripts de instalacion/ y el empaquetado.

No se corren (son para Windows), pero se revisa que nombren lo acordado en la §12 del
spec, que PowerShell los pueda analizar sin errores y que estén guardados como los
necesita Windows PowerShell 5.1: UTF-8 con BOM (si no, los acentos se leen mal) y CRLF.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
INSTALACION = RAIZ / "instalacion"
SCRIPTS = ["instalar.ps1", "iniciar.ps1", "restaurar.ps1", "comun.ps1"]
BOM = b"\xef\xbb\xbf"


def _texto(nombre: str) -> str:
    return (INSTALACION / nombre).read_text(encoding="utf-8-sig")


def test_scripts_existen_y_nombran_lo_acordado():
    for nombre in SCRIPTS + ["LEEME.md"]:
        assert (INSTALACION / nombre).is_file(), nombre
    instalar = _texto("instalar.ps1")
    for esperado in ["8080", "shelfie_lite", "Register-ScheduledTask", "New-NetFirewallRule",
                     "-Profile Private", "respaldar", "alembic", "upgrade", "head",
                     "scripts.crear_admin", "ENTORNO=produccion", "SECRET_KEY",
                     "RandomNumberGenerator", "#Requires -RunAsAdministrator",
                     "13:00", "PT5M", "localhost:8080", "$TareaServidor", "$TareaRespaldo"]:
        assert esperado in instalar, esperado
    comun = _texto("comun.ps1")
    assert "$TareaServidor  = 'Shelfie-lite'" in comun
    assert "$TareaRespaldo  = 'Shelfie-lite respaldo'" in comun
    iniciar = _texto("iniciar.ps1")
    for esperado in ["uvicorn", "app.main:app", "0.0.0.0", "8080", "shelfie-"]:
        assert esperado in iniciar, esperado
    restaurar = _texto("restaurar.ps1")
    for esperado in ["RESTAURAR", "base.dump", "pg_restore", "--clean", "--if-exists",
                     "PGPASSWORD"]:
        assert esperado in restaurar, esperado


def test_la_clave_de_postgres_no_se_escribe_en_archivos():
    """La clave del superusuario se pide una vez y solo viaja por PGPASSWORD."""
    instalar = _texto("instalar.ps1")
    assert "Read-Host" in instalar and "-AsSecureString" in instalar
    assert "Remove-Item Env:PGPASSWORD" in instalar
    restaurar = _texto("restaurar.ps1")
    assert "Remove-Item Env:PGPASSWORD" in restaurar
    # pg_restore nunca recibe la clave en la línea de comandos.
    assert "--password" not in restaurar and "-W " not in restaurar


@pytest.mark.parametrize("nombre", SCRIPTS)
def test_ps_utf8_con_bom_y_crlf(nombre):
    datos = (INSTALACION / nombre).read_bytes()
    assert datos.startswith(BOM), "falta el BOM: Windows PowerShell 5.1 leería mal los acentos"
    sin_crlf = datos.replace(b"\r\n", b"")
    assert b"\n" not in sin_crlf and b"\r" not in sin_crlf, "hay finales de línea que no son CRLF"


def test_leeme_cuenta_lo_que_hay_que_saber():
    leeme = _texto("LEEME.md")
    for esperado in ["instalar.ps1", "restaurar.ps1", "RESTAURAR", "8080",
                     "PostgreSQL 16", "Python 3.12",
                     # Regla de la Tarea 7: qué se conserva del 952 al exportar a Koha.
                     "952", "$a $b $o $p $t $y $z",
                     # Regla de la Tarea 9: desarrollo contra uvicorn en :8000, sin /api/v1.
                     "NEXT_PUBLIC_API_URL=http://localhost:8000"]:
        assert esperado in leeme, esperado


def test_empaquetar_excluye_lo_que_no_va():
    script = (RAIZ / "scripts" / "empaquetar.sh").read_text(encoding="utf-8")
    for esperado in ["npm ci", "npm run build", "git describe --tags --always", "dist/",
                     ".env", "__pycache__", "tests", "frontend/out", "instalacion"]:
        assert esperado in script, esperado
    assert "dist/" in (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()


def _pwsh() -> str:
    pwsh = shutil.which("pwsh")
    if not pwsh:
        pytest.skip("pwsh no está instalado")
    return pwsh


def test_ps_sintaxis():
    pwsh = _pwsh()
    rutas = ",".join(f"'{INSTALACION / n}'" for n in SCRIPTS)
    comando = (
        f"$errores = @(); foreach ($r in @({rutas})) {{"
        " $t = $null; $e = $null;"
        " [void][System.Management.Automation.Language.Parser]::ParseFile($r, [ref]$t, [ref]$e);"
        " foreach ($x in $e) { $errores += \"${r}:$($x.Extent.StartLineNumber): $($x.Message)\" } };"
        " $errores | ConvertTo-Json -AsArray"
    )
    salida = subprocess.run([pwsh, "-NoProfile", "-NonInteractive", "-Command", comando],
                            capture_output=True, text=True, timeout=120, check=True).stdout
    assert json.loads(salida or "[]") == []


def test_ps_compatible_con_windows_powershell_51():
    """El parser de pwsh 7 acepta `??`, `&&` o el ternario; Windows 10 trae 5.1, que no."""
    pwsh = _pwsh()
    hay = subprocess.run([pwsh, "-NoProfile", "-NonInteractive", "-Command",
                          "if (Get-Module -ListAvailable PSScriptAnalyzer) { 'si' }"],
                         capture_output=True, text=True, timeout=120, check=False).stdout.strip()
    if hay != "si":
        pytest.skip("PSScriptAnalyzer no está instalado")
    comando = (
        f"Invoke-ScriptAnalyzer -Path '{INSTALACION}' -Severity Error,Warning"
        " -Settings @{ IncludeRules = @('PSUseCompatibleSyntax');"
        " Rules = @{ PSUseCompatibleSyntax = @{ Enable = $true;"
        " TargetVersions = @('5.1', '7.0') } } }"
        " | ForEach-Object { \"$($_.ScriptName):$($_.Line): $($_.Message)\" }"
        " | ConvertTo-Json -AsArray"
    )
    salida = subprocess.run([pwsh, "-NoProfile", "-NonInteractive", "-Command", comando],
                            capture_output=True, text=True, timeout=300, check=True).stdout
    assert json.loads(salida or "[]") == []


def test_funciones_comunes():
    """Leer-Conexion parte DATABASE_URL (clave con %XX, puerto por defecto) y
    Ejecutar-Capturando recoge stdout, stderr y el código aunque el llamador use Stop."""
    pwsh = _pwsh()
    comando = (
        "$ErrorActionPreference = 'Stop';"
        f" . '{INSTALACION / 'comun.ps1'}';"
        " $a = Leer-Conexion 'postgresql://shelfie_lite:ab%40c@localhost:5433/shelfie_lite';"
        " $b = Leer-Conexion 'postgresql://u:k@servidor/base';"
        " $c = Leer-Conexion 'mysql://u@x/y';"
        " $r = Ejecutar-Capturando 'sh' @('-c', 'echo hola; echo malo >&2; exit 3');"
        " $s = Ejecutar-Capturando 'sh' @('-c', 'cat') 'por la entrada';"
        " @{ a = $a; b = $b; c = ($null -eq $c); codigo = $r.Codigo; salida = $r.Salida;"
        "    entrada = $s.Salida } | ConvertTo-Json -Depth 3"
    )
    corrida = subprocess.run([pwsh, "-NoProfile", "-NonInteractive", "-Command", comando],
                             capture_output=True, text=True, timeout=120, check=False)
    assert corrida.returncode == 0, corrida.stderr
    datos = json.loads(corrida.stdout)
    assert datos["a"] == {"Usuario": "shelfie_lite", "Clave": "ab@c", "Servidor": "localhost",
                          "Puerto": 5433, "Base": "shelfie_lite"}
    assert datos["b"]["Puerto"] == 5432 and datos["b"]["Servidor"] == "servidor"
    assert datos["c"] is True
    assert datos["codigo"] == 3
    assert "hola" in datos["salida"] and "malo" in datos["salida"]
    assert datos["entrada"] == "por la entrada"


def test_permisos_seguros():
    """Lo que corre como SYSTEM y los volcados de la base no los puede tocar cualquier usuario:
    Administradores y SYSTEM control total, Usuarios solo lectura (SID conocidos)."""
    comun = _texto("comun.ps1")
    for esperado in ["'*S-1-5-32-544'", "'*S-1-5-18'", "'*S-1-5-32-545'",
                     ":(OI)(CI)F", ":(OI)(CI)RX", "/inheritance:r", "/grant:r", "/setowner",
                     "/reset", "icacls.exe", "$r.Codigo -ne 0"]:
        assert esperado in comun, esperado
    instalar = _texto("instalar.ps1")
    # La raíz (usuarios solo leen), respaldos-previos y la carpeta de respaldo (solo admins),
    # y el .env al final, porque /reset de la raíz le quita sus permisos propios.
    raiz = instalar.index("Proteger-Carpeta $ShelfieRaiz -UsuariosLeen")
    previos = instalar.index("Proteger-Carpeta $respaldosPrevios\n")
    env = instalar.index("$problema = Proteger-Env")
    assert raiz < previos < env
    assert "Proteger-CarpetaDeRespaldo $carpeta" in instalar
    assert "Proteger-CarpetaDeRespaldo $env:SHELFIE_CARPETA_RESPALDO" in instalar
    assert "Es-RaizDeUnidad $ShelfieRaiz" in instalar
    restaurar = _texto("restaurar.ps1")
    assert restaurar.index("Proteger-Carpeta $previos") < restaurar.index("$PgDump ($Comunes")
    leeme = _texto("LEEME.md")
    for esperado in ["*S-1-5-32-544", "*S-1-5-18", "*S-1-5-32-545", "Duplicar archivos",
                     "sesión abierta", "Respaldar ahora"]:
        assert esperado in leeme, esperado


def test_postgres_16_se_exige_antes_de_crear_nada():
    instalar = _texto("instalar.ps1")
    assert instalar.index("Exigir-Pg16 (Version-Pg $r.Salida)") < instalar.index("ALTER ROLE")
    assert instalar.index("ALTER ROLE") < instalar.index("'scripts.inicializar_bd'")


def test_restaurar_detiene_todo_o_no_toca_nada():
    restaurar = _texto("restaurar.ps1")
    for esperado in ["Stop-ScheduledTask -TaskName $TareaRespaldo",
                     "Disable-ScheduledTask -TaskName $TareaRespaldo",
                     "Enable-ScheduledTask -TaskName $TareaRespaldo"]:
        assert esperado in restaurar, esperado
    detener = restaurar.index("if (-not (Detener-Shelfie)) {")
    assert "Detener-ConError" in restaurar[detener:detener + 120]
    # Se detiene antes de copiar y de restaurar.
    assert detener < restaurar.index("$PgDump ($Comunes") < restaurar.index("$PgRestore ($Comunes")


def test_python_de_la_store_no_sirve():
    instalar = _texto("instalar.ps1")
    assert instalar.count("WindowsApps") >= 2
    assert instalar.index("'py -3.12'") < instalar.index("'python'")


def test_empaquetar_deja_next_env_como_estaba():
    script = (RAIZ / "scripts" / "empaquetar.sh").read_text(encoding="utf-8")
    assert "next-env.d.ts" in script and "trap limpiar EXIT" in script
