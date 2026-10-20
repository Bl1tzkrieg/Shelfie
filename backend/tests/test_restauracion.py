"""Un respaldo sirve si se puede restaurar: base.dump → base nueva → la búsqueda funciona.

Necesita pg_dump y pg_restore, y que el rol de pruebas pueda crear bases (CREATEDB);
si no, se salta, igual que test_migraciones."""

import os
import shutil
import subprocess

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.core import marc_plantillas
from app.services import busqueda, catalogo, ficha, respaldo
from app.schemas import FichaLibro
from tests.conftest import BACKEND_DIR, TEST_DATABASE_URL


def _herramientas():
    pg_dump = respaldo.encontrar_pg_dump()
    if not pg_dump:
        pytest.skip("pg_dump no está disponible")
    pg_restore = os.path.join(os.path.dirname(pg_dump),
                              "pg_restore.exe" if pg_dump.endswith(".exe") else "pg_restore")
    if not os.path.isfile(pg_restore):
        pg_restore = shutil.which("pg_restore")
    if not pg_restore:
        pytest.skip("pg_restore no está disponible")
    return pg_dump, pg_restore


@pytest.fixture()
def bases():
    """Dos bases propias y vacías: la de origen del respaldo y la restaurada."""
    url = make_url(TEST_DATABASE_URL)
    nombres = [f"{url.database}_origen", f"{url.database}_restaurada"]
    servidor = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with servidor.connect() as c:
            for nombre in nombres:
                c.execute(text(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)'))
                c.execute(text(f'CREATE DATABASE "{nombre}"'))
    except (ProgrammingError, OperationalError) as error:
        servidor.dispose()
        pytest.skip(f"el rol de pruebas no puede crear bases (CREATEDB): {error.orig}")
    try:
        yield [url.set(database=n).render_as_string(hide_password=False) for n in nombres]
    finally:
        with servidor.connect() as c:
            for nombre in nombres:
                c.execute(text(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)'))
        servidor.dispose()


def test_base_dump_se_restaura_y_la_busqueda_funciona(bases, tmp_path, monkeypatch):
    _, pg_restore = _herramientas()
    origen, restaurada = bases
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "migrations"))
    cfg.set_main_option("sqlalchemy.url", origen.replace("%", "%%"))
    command.upgrade(cfg, "head")

    motor_origen = create_engine(origen)
    try:
        with Session(motor_origen) as db:
            libro = FichaLibro(cota="616.39 H37", titulo="Bioquímica de Harper",
                               autor="Murray, Robert", otros_autores=["Rodwell, Victor"],
                               materias=["Bioquímica", "Medicina"])
            biblio = models.RegistroBibliografico()
            marc, plantilla = ficha.a_marc(libro), marc_plantillas.obtener(None)
            catalogo.aplicar_marc(biblio, marc, plantilla)
            db.add(biblio)
            db.flush()
            db.add(models.Item(biblio_id=biblio.id, signatura_topografica="616.39 H37",
                               numero_copia="c.1"))
            db.commit()
            monkeypatch.setattr(settings, "DATABASE_URL", origen)
            r = respaldo.ejecutar(db, carpeta=str(tmp_path))
        assert r["ok"] is True, r["mensaje"]
    finally:
        motor_origen.dispose()

    dump = os.path.join(r["carpeta_creada"], "base.dump")
    url = make_url(restaurada)
    entorno = {**os.environ, "PGPASSWORD": url.password or ""}
    args = [pg_restore, "--no-owner", "-w", "-d", url.database]
    if url.host:
        args += ["-h", url.host]
    if url.port:
        args += ["-p", str(url.port)]
    if url.username:
        args += ["-U", url.username]
    corrida = subprocess.run(args + [dump], env=entorno, capture_output=True, timeout=300)
    assert corrida.returncode == 0, corrida.stderr.decode("utf-8", "replace")

    motor = create_engine(restaurada)
    try:
        with Session(motor) as db:
            for q, campo in (("harper", "todo"), ("medicina", "materia"), ("rodwell", "autor"),
                             ("616.39", "cota")):
                hallado = busqueda.buscar(db, q, campo=campo)
                assert hallado["total"] == 1, (q, campo)
                assert hallado["resultados"][0]["ejemplares"] == 1
    finally:
        motor.dispose()
