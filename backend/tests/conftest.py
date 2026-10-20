"""Infraestructura de pruebas.

Las pruebas corren contra un PostgreSQL real (el esquema usa JSONB), en una base
dedicada que se indica con TEST_DATABASE_URL. Esa base se reconstruye con las
migraciones de Alembic al iniciar la sesión, así que la suite también valida
que las migraciones funcionen.

Cada prueba corre dentro de una transacción que se revierte al final: los
`db.commit()` de los endpoints se convierten en savepoints y nada queda escrito.
"""

import os



def _url_de_pruebas() -> str:
    """TEST_DATABASE_URL si está definida; si no, la gemela `<base>_test` de la
    DATABASE_URL del .env (la que crea scripts.inicializar_bd), con su misma clave."""
    if os.environ.get("TEST_DATABASE_URL"):
        return os.environ["TEST_DATABASE_URL"]
    from dotenv import dotenv_values
    from sqlalchemy.engine import make_url

    env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    base = os.environ.get("DATABASE_URL") or dotenv_values(env).get("DATABASE_URL")
    if not base:
        return "postgresql://shelfie:shelfie@localhost:5432/shelfie_test"
    url = make_url(base)
    return url.set(database=f"{url.database}_test").render_as_string(hide_password=False)


TEST_DATABASE_URL = _url_de_pruebas()
# Debe fijarse antes de importar la app: config.py lee DATABASE_URL al importarse.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
# Una clave de firma fuerte (con la de ejemplo el backend advierte al arrancar).
os.environ["SECRET_KEY"] = "clave-de-pruebas-con-mas-de-treinta-y-dos-bytes"

from sqlalchemy.engine import make_url  # noqa: E402

# La suite BORRA y reconstruye la base de pruebas. Si el nombre no lo deja claro,
# se aborta antes de tocar nada: así nunca se apunta por error a una base real.
if "test" not in (make_url(TEST_DATABASE_URL).database or "").lower():
    raise SystemExit(
        f"TEST_DATABASE_URL apunta a '{make_url(TEST_DATABASE_URL).database}'. "
        "La suite borra esa base: su nombre debe contener 'test' (p. ej. shelfie_test)."
    )

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app import models  # noqa: E402
from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services import configuracion  # noqa: E402

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _verificar_conexion() -> None:
    """Falla con un mensaje claro si la base de pruebas no responde.

    PostgreSQL en español envía los errores de conexión en Latin-1 y psycopg2 los
    convierte en un UnicodeDecodeError ilegible (196 errores iguales en la suite)."""
    import psycopg2

    url = make_url(TEST_DATABASE_URL)
    destino = f"'{url.database}' como '{url.username}' en {url.host}:{url.port or 5432}"
    ayuda = (
        "Revisa la clave en TEST_DATABASE_URL (o en DATABASE_URL del .env) y que la base "
        "exista: `python -m scripts.inicializar_bd` crea <base>_test."
    )
    try:
        psycopg2.connect(
            host=url.host, port=url.port or 5432, dbname=url.database,
            user=url.username, password=url.password, connect_timeout=5,
        ).close()
    except UnicodeDecodeError:
        pytest.exit(
            f"No se pudo conectar a {destino}: PostgreSQL respondió con un error que psycopg2 "
            f"no puede mostrar (casi siempre contraseña incorrecta o base inexistente). {ayuda}",
            returncode=2,
        )
    except psycopg2.OperationalError as error:
        pytest.exit(f"No se pudo conectar a {destino}: {error}\n{ayuda}", returncode=2)


@pytest.fixture(scope="session")
def engine():
    _verificar_conexion()
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "migrations"))
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    # Partir siempre de una base vacía y migrada hasta la última revisión. Se borra el
    # esquema entero (y no `downgrade base`): así sirve aunque la base venga de otra
    # historia de migraciones (p. ej. de Shelfie completo, en 0016).
    eng = create_engine(TEST_DATABASE_URL)
    with eng.begin() as conexion:
        conexion.execute(text("DROP SCHEMA public CASCADE"))
        conexion.execute(text("CREATE SCHEMA public"))
    command.upgrade(cfg, "head")

    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    conexion = engine.connect()
    transaccion = conexion.begin()
    sesion = Session(bind=conexion, join_transaction_mode="create_savepoint")
    try:
        yield sesion
    finally:
        sesion.close()
        transaccion.rollback()
        conexion.close()


@pytest.fixture()
def anonimo(db):
    """Cliente sin sesión."""
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def iniciar_sesion(cliente, usuario, password):
    r = cliente.post("/api/v1/auth/login", json={"username": usuario, "password": password})
    assert r.status_code == 200, r.text
    return cliente


@pytest.fixture()
def como(db, datos):
    """Fábrica de clientes con sesión de personal y los permisos indicados.

        cliente = como(["catalogo"])
    """
    app.dependency_overrides[get_db] = lambda: db
    abiertos = []

    def _crear(permisos, username=None):
        username = username or f"P-{len(abiertos) + 1}"
        datos.personal(username, permisos)
        cliente = TestClient(app)
        abiertos.append(cliente)
        return iniciar_sesion(cliente, username, username)

    yield _crear
    for c in abiertos:
        c.close()
    app.dependency_overrides.clear()


@pytest.fixture()
def client(como):
    """Cliente con sesión de superbibliotecario: prueba la lógica, no los permisos."""
    return como(["superbibliotecario"], username="ADMIN")


# --- Datos de prueba ----------------------------------------------------------

class Datos:
    """Atajos para crear registros mínimos dentro de la transacción de la prueba."""

    def __init__(self, db: Session):
        self.db = db

    def personal(self, username, permisos, **extra):
        """Miembro del personal (clave = username)."""
        u = models.Usuario(
            username=username,
            password_hash=hash_password(extra.pop("password", username)),
            nombre=extra.pop("nombre", "Staff"),
            apellido=extra.pop("apellido", username),
            permisos=list(permisos),
            **extra,
        )
        self.db.add(u)
        self.db.flush()
        return u

    def titulo(self, titulo="Cien años de soledad", isbn="9780307474728", **extra):
        b = models.RegistroBibliografico(
            titulo=titulo, isbn=isbn,
            autor=extra.pop("autor", "Gabriel García Márquez"),
            ano_publicacion=extra.pop("ano", 1967),
            materia=extra.pop("materia", "Literatura"),
            marc_json={"leader": "", "fields": []},
            **extra,
        )
        self.db.add(b)
        self.db.flush()
        return b

    def ejemplar(self, biblio, codigo=None, cota=None, copia=None):
        i = models.Item(biblio_id=biblio.id, codigo_barras=codigo,
                        signatura_topografica=cota, numero_copia=copia)
        self.db.add(i)
        self.db.flush()
        return i


@pytest.fixture()
def datos(db):
    return Datos(db)


@pytest.fixture(autouse=True)
def hashing_rapido(monkeypatch):
    """PBKDF2 con 260k iteraciones hace lenta la suite; el formato guarda las
    iteraciones en el hash, así que verificar sigue funcionando igual."""
    import app.security as security
    monkeypatch.setattr(security, "_ITERACIONES", 1_000)


@pytest.fixture(autouse=True)
def sin_cambio_de_clave_forzado(db):
    """Los datos de prueba usan el username como contraseña: aquí no se fuerza el cambio.

    Las pruebas de ese comportamiento (test_seguridad.py) lo vuelven a encender.
    """
    configuracion.guardar(db, {"seguridad": {"forzar_cambio_clave": False}}, anotar=False)
