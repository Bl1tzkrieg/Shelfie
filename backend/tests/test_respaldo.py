"""Respaldo diario: base, MARC y CSV en una carpeta con sello, rotación y aviso."""

import os
import subprocess
import time
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.engine import make_url

from app import models
from app.core.tiempo import ahora
from app.services import configuracion, respaldo
from app.config import settings

AHORA = datetime(2026, 10, 20, 15, 30, tzinfo=timezone.utc)  # 11:30 en Caracas
CARPETA_DEL_AHORA = "shelfie-20261020-1130"


def _config(db, **valores):
    configuracion.guardar(db, {"respaldo": valores}, anotar=False)


def _falso_pg_dump(monkeypatch, *, codigo=0, stderr="", capturado=None):
    """Sustituye pg_dump: escribe un base.dump pequeño donde se le pida (-f)."""
    monkeypatch.setattr(respaldo, "encontrar_pg_dump", lambda configurado=None: "/falso/pg_dump")

    def correr(args, **opciones):
        if capturado is not None:
            capturado.update(args=args, **opciones)
        if codigo == 0:
            with open(args[args.index("-f") + 1], "wb") as f:
                f.write(b"PGDMP")
        return subprocess.CompletedProcess(args, codigo, stdout=b"", stderr=stderr.encode())

    monkeypatch.setattr(respaldo.subprocess, "run", correr)


def _carpetas(destino):
    return sorted(p.name for p in destino.iterdir())


def test_respaldo_completo(db, datos, tmp_path):
    if respaldo.encontrar_pg_dump() is None:
        pytest.skip("pg_dump no está disponible")
    b = datos.titulo("=HYPERLINK(\"http://x\")")
    datos.ejemplar(b, codigo="L-1", cota="616.39 H37")
    db.commit()

    r = respaldo.ejecutar(db, carpeta=str(tmp_path), ahora=AHORA)

    assert r["ok"] is True, r["mensaje"]
    creada = tmp_path / CARPETA_DEL_AHORA
    assert r["carpeta_creada"] == str(creada)
    assert sorted(p.name for p in creada.iterdir()) == [
        "LEEME.txt", "base.dump", "catalogo.csv", "catalogo.mrc", "catalogo.xml"]
    assert (creada / "base.dump").stat().st_size > 0
    assert (creada / "catalogo.mrc").stat().st_size > 0
    csv = (creada / "catalogo.csv").read_text(encoding="utf-8-sig")
    assert csv.splitlines()[0].startswith("cota,titulo")
    assert "'=HYPERLINK" in csv  # celda_segura
    assert "restaurar.ps1" in (creada / "LEEME.txt").read_text(encoding="utf-8")
    assert r["tamano"] == sum(p.stat().st_size for p in creada.iterdir())
    assert _carpetas(tmp_path) == [CARPETA_DEL_AHORA]  # sin carpeta temporal

    e = respaldo.estado(db, ahora=AHORA)
    assert e["alerta"] is False and e["ultimo"]["ok"] is True
    assert e["ultimo_ok"] == e["ultimo"]["fecha"]
    anotacion = db.query(models.RegistroAccion).filter_by(modulo="respaldo").one()
    assert anotacion.accion == "respaldo"


def test_pg_dump_sin_clave_en_la_linea_de_comandos(db, tmp_path, monkeypatch):
    capturado = {}
    _falso_pg_dump(monkeypatch, capturado=capturado)
    monkeypatch.setattr(settings, "DATABASE_URL",
                        "postgresql://ana:S3cr3t0-raro@db.local:5433/mibase")
    url = make_url(settings.DATABASE_URL)

    r = respaldo.ejecutar(db, carpeta=str(tmp_path), ahora=AHORA)

    assert r["ok"] is True, r["mensaje"]
    args = capturado["args"]
    assert isinstance(args, list) and capturado.get("shell") in (None, False)
    assert capturado["timeout"] > 0
    assert args[0] == "/falso/pg_dump" and "-Fc" in args and url.database in args
    assert args[args.index("-h") + 1] == "db.local" and args[args.index("-p") + 1] == "5433"
    assert args[args.index("-U") + 1] == "ana"
    assert "S3cr3t0-raro" not in " ".join(args)
    assert capturado["env"]["PGPASSWORD"] == "S3cr3t0-raro"


def test_mismo_minuto_agrega_sufijo(db, tmp_path, monkeypatch):
    _falso_pg_dump(monkeypatch)

    respaldo.ejecutar(db, carpeta=str(tmp_path), ahora=AHORA)
    respaldo.ejecutar(db, carpeta=str(tmp_path), ahora=AHORA)
    r = respaldo.ejecutar(db, carpeta=str(tmp_path), ahora=AHORA)

    assert _carpetas(tmp_path) == [CARPETA_DEL_AHORA, CARPETA_DEL_AHORA + "-2",
                                   CARPETA_DEL_AHORA + "-3"]
    assert r["carpeta_creada"].endswith("-3")


def test_usa_la_carpeta_configurada(db, tmp_path, monkeypatch):
    _falso_pg_dump(monkeypatch)
    _config(db, carpeta=str(tmp_path))

    assert respaldo.ejecutar(db, ahora=AHORA)["ok"] is True
    assert _carpetas(tmp_path) == [CARPETA_DEL_AHORA]


def test_sin_carpeta_configurada(db, monkeypatch):
    _falso_pg_dump(monkeypatch)

    r = respaldo.ejecutar(db, ahora=AHORA)

    assert r["ok"] is False and r["mensaje"] == "No hay carpeta de respaldo configurada"
    assert r["carpeta_creada"] is None and r["tamano"] is None
    assert respaldo.estado(db, ahora=AHORA)["alerta"] is True


def test_rota_a_30(db, tmp_path, monkeypatch):
    _falso_pg_dump(monkeypatch)
    for dia in range(1, 31):
        (tmp_path / f"shelfie-202609{dia:02d}-0300").mkdir()
    for n in (1, 2):
        (tmp_path / f"shelfie-20261001-0300-{n}").mkdir()  # con sufijo: también cuentan
    (tmp_path / "mis-fotos").mkdir()
    (tmp_path / "shelfie-20261001-0300.txt").write_text("no es carpeta")
    antes = [p.name for p in tmp_path.iterdir() if p.is_dir() and p.name.startswith("shelfie-")]
    assert len(antes) == 32

    r = respaldo.ejecutar(db, carpeta=str(tmp_path), ahora=AHORA)

    assert r["ok"] is True
    cuenta = sorted(p.name for p in tmp_path.iterdir()
                    if p.is_dir() and p.name.startswith("shelfie-"))
    assert len(cuenta) == 30
    assert CARPETA_DEL_AHORA in cuenta  # la nueva nunca se borra
    assert "shelfie-20260901-0300" not in cuenta  # se van las más viejas
    assert (tmp_path / "mis-fotos").is_dir()
    assert (tmp_path / "shelfie-20261001-0300.txt").exists()


def test_respaldo_destino_inexistente(db, como, tmp_path, monkeypatch):
    _falso_pg_dump(monkeypatch)
    ausente = tmp_path / "pendrive-desconectado"
    admin = como(["superbibliotecario"], username="ADM")
    admin.put("/api/v1/settings", json={"respaldo": {"carpeta": str(ausente)}})

    r = admin.post("/api/v1/settings/backup")

    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["ok"] is False and "pendrive-desconectado" in cuerpo["mensaje"]
    assert not ausente.exists()
    e = admin.get("/api/v1/settings/backup").json()
    assert e["alerta"] is True and e["ultimo"]["ok"] is False
    assert e["motivo"].startswith("El último respaldo falló: ")


def test_respaldo_sin_pg_dump(db, tmp_path, monkeypatch):
    monkeypatch.setattr(respaldo, "encontrar_pg_dump", lambda configurado=None: None)

    r = respaldo.ejecutar(db, carpeta=str(tmp_path), ahora=AHORA)

    assert r["ok"] is False and "pg_dump" in r["mensaje"]
    assert _carpetas(tmp_path) == []
    assert respaldo.estado(db, ahora=AHORA)["alerta"] is True


def test_falla_pg_dump_no_deja_carpeta_a_medias(db, tmp_path, monkeypatch):
    _falso_pg_dump(monkeypatch)
    _config(db, ultimo_ok="2026-10-19T12:00:00+00:00")
    _falso_pg_dump(monkeypatch, codigo=1, stderr="pg_dump: error: password authentication failed " + "x" * 900)

    r = respaldo.ejecutar(db, carpeta=str(tmp_path), ahora=AHORA)

    assert r["ok"] is False
    assert "password authentication failed" in r["mensaje"]
    assert len(r["mensaje"]) < 700
    assert _carpetas(tmp_path) == []  # ni la temporal
    e = respaldo.estado(db, ahora=AHORA)
    assert e["ultimo"]["ok"] is False and e["ultimo"]["tamano"] is None
    assert e["ultimo_ok"] == "2026-10-19T12:00:00+00:00"  # el último correcto se conserva
    assert e["alerta"] is True


def test_tiempo_agotado_queda_como_fallido(db, tmp_path, monkeypatch):
    monkeypatch.setattr(respaldo, "encontrar_pg_dump", lambda configurado=None: "/falso/pg_dump")

    def lento(args, **opciones):
        raise subprocess.TimeoutExpired(args, opciones["timeout"])

    monkeypatch.setattr(respaldo.subprocess, "run", lento)

    r = respaldo.ejecutar(db, carpeta=str(tmp_path), ahora=AHORA)

    assert r["ok"] is False and "tard" in r["mensaje"]
    assert _carpetas(tmp_path) == []


def test_alerta_por_antiguedad(db):
    def con_ultimo_ok(hace):
        fecha = (AHORA - hace).isoformat()
        _config(db, ultimo={"fecha": fecha, "ok": True, "mensaje": "ok", "tamano": 10},
                ultimo_ok=fecha)
        return respaldo.estado(db, ahora=AHORA)

    assert con_ultimo_ok(timedelta(days=8))["alerta"] is True
    assert con_ultimo_ok(timedelta(days=8))["motivo"] == "El último respaldo es de hace 8 días"
    e = con_ultimo_ok(timedelta(days=6))
    assert e["alerta"] is False and e["motivo"] is None


def test_alerta_si_nunca_hubo_respaldo(db):
    e = respaldo.estado(db, ahora=AHORA)

    assert e == {"ultimo": None, "ultimo_ok": None, "alerta": True,
                 "motivo": "Nunca se hizo un respaldo"}


def test_encontrar_pg_dump_orden_de_busqueda(tmp_path, monkeypatch):
    for version in ("9.6", "16", "15"):
        exe = tmp_path / version / "bin" / "pg_dump.exe"
        exe.parent.mkdir(parents=True)
        exe.write_text("")
    propio = tmp_path / "propio.exe"
    propio.write_text("")

    # 1. la ruta configurada, si existe
    assert respaldo.encontrar_pg_dump(str(propio), base_windows=str(tmp_path)) == str(propio)
    # 2. el PATH
    monkeypatch.setattr(respaldo.shutil, "which", lambda nombre: "/usr/bin/pg_dump")
    assert respaldo.encontrar_pg_dump(str(tmp_path / "no-existe"),
                                      base_windows=str(tmp_path)) == "/usr/bin/pg_dump"
    # 3. Program Files, la versión más alta
    monkeypatch.setattr(respaldo.shutil, "which", lambda nombre: None)
    assert respaldo.encontrar_pg_dump(None, base_windows=str(tmp_path)) == str(
        tmp_path / "16" / "bin" / "pg_dump.exe")
    assert respaldo.encontrar_pg_dump(None, base_windows=str(tmp_path / "nada")) is None


def test_solo_admin(como, anonimo):
    catalogador = como(["catalogo"])

    assert catalogador.get("/api/v1/settings/backup").status_code == 403
    assert catalogador.post("/api/v1/settings/backup").status_code == 403
    assert anonimo.post("/api/v1/settings/backup").status_code == 401


def test_detectar_pg_dump(como, monkeypatch):
    admin, catalogador = como(["superbibliotecario"], username="ADM"), como(["catalogo"])
    llamadas = []

    def falso(configurado=None, **_):
        llamadas.append(configurado)
        return "/usr/bin/pg_dump"

    monkeypatch.setattr(respaldo, "encontrar_pg_dump", falso)

    r = admin.get("/api/v1/settings/backup/pg_dump")
    assert r.status_code == 200
    assert r.json() == {"ruta": "/usr/bin/pg_dump"}
    assert llamadas == [None]  # ignora lo configurado
    assert catalogador.get("/api/v1/settings/backup/pg_dump").status_code == 403

    monkeypatch.setattr(respaldo, "encontrar_pg_dump", lambda *a, **k: None)
    assert admin.get("/api/v1/settings/backup/pg_dump").json() == {"ruta": None}


def test_me_avisa_solo_al_administrador(como, db, tmp_path):
    admin, catalogador = como(["superbibliotecario"], username="ADM"), como(["catalogo"])

    assert admin.get("/api/v1/auth/me").json()["alerta_respaldo"] is True  # nunca hubo uno
    assert not catalogador.get("/api/v1/auth/me").json().get("alerta_respaldo")

    fecha = ahora().isoformat()
    _config(db, ultimo={"fecha": fecha, "ok": True, "mensaje": "ok", "tamano": 1}, ultimo_ok=fecha)
    assert admin.get("/api/v1/auth/me").json()["alerta_respaldo"] is False


def test_el_cliente_no_escribe_ultimo(client):
    client.put("/api/v1/settings", json={"respaldo": {"ultimo_ok": "2026-10-20T00:00:00+00:00",
                                                       "ultimo": {"ok": True}}})

    assert client.get("/api/v1/settings/backup").json()["alerta"] is True


def test_script_sale_con_codigo_segun_resultado(db, monkeypatch):
    from scripts import respaldar

    llamadas = []
    monkeypatch.setattr(respaldar, "SessionLocal", lambda: db)
    monkeypatch.setattr(respaldar, "limpiar", lambda sesion: llamadas.append("limpiar") or {})
    monkeypatch.setattr(respaldar.respaldo, "ejecutar",
                        lambda sesion: {"ok": False, "mensaje": "x", "carpeta_creada": None,
                                        "tamano": None})
    assert respaldar.main([]) == 1
    monkeypatch.setattr(respaldar.respaldo, "ejecutar",
                        lambda sesion: {"ok": True, "mensaje": "x", "carpeta_creada": "c",
                                        "tamano": 1})
    assert respaldar.main([]) == 0
    assert llamadas == ["limpiar", "limpiar"]  # limpia aunque el respaldo falle


def test_la_rotacion_no_borra_el_respaldo_nuevo_con_el_reloj_atrasado(db, tmp_path, monkeypatch):
    _falso_pg_dump(monkeypatch)
    for dia in range(1, 31):
        (tmp_path / f"shelfie-202609{dia:02d}-0300").mkdir()
    atrasado = datetime(2000, 1, 1, 4, 0, tzinfo=timezone.utc)  # BIOS sin pila

    r = respaldo.ejecutar(db, carpeta=str(tmp_path), ahora=atrasado)

    assert r["ok"] is True
    carpetas = _carpetas(tmp_path)
    assert "shelfie-20000101-0000" in carpetas and len(carpetas) == 30
    assert "shelfie-20260901-0300" not in carpetas  # se fue la más vieja de las otras
    assert os.path.isdir(r["carpeta_creada"])


def test_quita_temporales_huerfanos_de_mas_de_un_dia(db, tmp_path, monkeypatch):
    _falso_pg_dump(monkeypatch)
    viejo, reciente = tmp_path / ".respaldo-viejo", tmp_path / ".respaldo-reciente"
    ajeno = tmp_path / ".otra-cosa"
    for carpeta in (viejo, reciente, ajeno):
        carpeta.mkdir()
    dos_dias = time.time() - 2 * 86400
    os.utime(viejo, (dos_dias, dos_dias))
    os.utime(ajeno, (dos_dias, dos_dias))

    assert respaldo.ejecutar(db, carpeta=str(tmp_path), ahora=AHORA)["ok"] is True

    assert _carpetas(tmp_path) == sorted([".otra-cosa", ".respaldo-reciente", CARPETA_DEL_AHORA])


def test_acepta_rutas_entre_comillas(db, tmp_path, monkeypatch):
    _falso_pg_dump(monkeypatch)

    assert respaldo.ejecutar(db, carpeta=f'  "{tmp_path}" ', ahora=AHORA)["ok"] is True
    assert _carpetas(tmp_path) == [CARPETA_DEL_AHORA]

    _config(db, carpeta=f'"{tmp_path}"')
    assert respaldo.ejecutar(db, ahora=AHORA)["ok"] is True
    assert _carpetas(tmp_path) == [CARPETA_DEL_AHORA, CARPETA_DEL_AHORA + "-2"]


def test_pg_dump_configurado_entre_comillas(tmp_path):
    exe = tmp_path / "pg_dump.exe"
    exe.write_text("")

    assert respaldo.encontrar_pg_dump(f'"{exe}"', base_windows=str(tmp_path / "nada")) == str(exe)
