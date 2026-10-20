"""Hallazgos de severidad baja de la auditoría de octubre de 2026 (uno o dos tests por hallazgo)."""

from app import models

CAT = "/api/v1/catalog"


# --- Catálogo y MARC ------------------------------------------------------------------

def test_b7_anio_fuera_de_rango(client):
    for ano in (10000, -5):
        r = client.post("/api/v1/books", json={"ficha": {"cota": "1 X", "titulo": "X",
                                                         "ano": ano}})
        assert r.status_code == 422, r.text


def test_b8_marc_json_con_tipos_incorrectos(client):
    for marc in ({"leader": "", "fields": 5}, {"leader": "", "fields": [{"245": {"subfields": True}}]}):
        r = client.post(f"{CAT}/records", json={"plantilla": "BKS", "marc": marc})
        assert r.status_code == 422, r.text


def test_b12_plantilla_desconocida(client):
    r = client.post(f"{CAT}/records", json={"plantilla": "TESIS", "marc": {"leader": "", "fields": []}})
    assert r.status_code == 422


def test_b11_isbn_duplicado_con_otro_formato(client, datos):
    from tests.test_marc import _campo, _registro
    datos.titulo(isbn="9780307474728")
    marc = _registro(_campo("020", ("a", "978-0-307-47472-8")), _campo("245", ("a", "Otra edición")))
    r = client.post(f"{CAT}/records", json={"plantilla": "BKS", "marc": marc})
    assert r.status_code == 400 and "ya está en" in r.json()["detail"]


def test_b18_isbn_con_calificador_pegado():
    from app.services.marc import normalizar_isbn
    assert normalizar_isbn("9780307474728(pbk.)") == "9780307474728"
    assert normalizar_isbn("978-0-307-47472-8 (rústica)") == "978-0-307-47472-8"
    assert normalizar_isbn("84-376-0494-X : 15 €") == "84-376-0494-X"


def test_b10_isbn_repetido_en_el_archivo_igual_en_vista_y_al_aplicar(client, db):
    from tests.test_intercambio_marc import _importar, _libro, _mrc
    archivo = _mrc(_libro("Primero", "9789800000123"), _libro("Segundo", "9789800000123"))
    vista = _importar(client, archivo, modo="vista", duplicados="reemplazar").json()
    hecho = _importar(client, archivo, duplicados="reemplazar").json()
    assert [r["accion"] for r in vista["registros"]] == [r["accion"] for r in hecho["registros"]] \
        == ["nuevo", "omitir"]
    assert db.query(models.RegistroBibliografico).one().titulo == "Primero"


def test_b13_b14_b17_mapeo_del_952_y_campos_ajenos(client, datos, db):
    import pymarc
    from tests.test_intercambio_marc import _importar, _libro
    r = _libro("Con 952 raro", ejemplares=[
        [("p", " R-1 "), ("a", "XYZ"), ("0", "1")],
        [("p", "R-2"), ("7", "1"), ("4", "1")],
        [("p", "R-3"), ("o", "x" * 120)],
    ])
    r.add_field(pymarc.Field(tag="FMT", data="BK"))
    vista = _importar(client, r.as_marc(), modo="vista").json()["registros"][0]
    texto = " | ".join(vista["mensajes"])
    assert vista["accion"] == "nuevo", vista
    assert "no son MARC: FMT" in texto
    assert "signatura ($o) supera los 100" in texto and vista["ejemplares"] == 2

    _importar(client, r.as_marc())
    # El código llega sin los espacios de los costados.
    assert db.query(models.Item).filter_by(codigo_barras="R-1").one()


def test_b19_importacion_demasiado_grande_se_rechaza_antes_de_leerla(client):
    r = client.post(f"{CAT}/import", params={"modo": "vista"}, content=b"x",
                    headers={"Content-Type": "application/octet-stream",
                             "Content-Length": str(30 * 1024 * 1024)})
    assert r.status_code == 400 and "20 MB" in r.json()["detail"]


# --- Autenticación ---------------------------------------------------------------------

def test_b34_salir_anula_el_token_aunque_se_haya_copiado(anonimo, datos):
    from fastapi.testclient import TestClient

    from app.main import app
    from tests.conftest import iniciar_sesion
    datos.personal("P-9", ["catalogo"])
    sesion = iniciar_sesion(TestClient(app), "P-9", "P-9")
    copiada = TestClient(app)
    copiada.cookies.set("shelfie_sesion", sesion.cookies.get("shelfie_sesion"))

    assert sesion.post("/api/v1/auth/logout").status_code == 204
    r = copiada.get("/api/v1/auth/me")
    assert r.status_code == 401 and "se cerró" in r.json()["detail"]
    sesion.close()
    copiada.close()


def test_b35_referer_ajeno_sin_origin_se_rechaza(client):
    libro = {"ficha": {"cota": "1 X", "titulo": "X"}}
    r = client.post("/api/v1/books", json=libro,
                    headers={"Referer": "https://malicioso.example/pagina"})
    assert r.status_code == 403
    r = client.post("/api/v1/books", json=libro,
                    headers={"Referer": "http://localhost:3000/catalogo"})
    assert r.status_code == 201


def test_b32_celda_segura_respeta_numeros():
    from app.core.csv import celda_segura
    assert celda_segura("-12.50") == "-12.50"
    assert celda_segura("+58 212") == "'+58 212"
    assert celda_segura("@SUMA") == "'@SUMA"
    assert celda_segura(5) == 5


# --- Infraestructura ------------------------------------------------------------------

def test_b42_violacion_de_unicidad_da_409():
    """Una restricción que se cuela hasta la base responde 409 con un mensaje, no 500."""
    import json

    from sqlalchemy.exc import IntegrityError

    from app.main import manejar_conflicto
    r = manejar_conflicto(None, IntegrityError("INSERT ...", {}, Exception("duplicate key")))
    assert r.status_code == 409 and "Otro registro" in json.loads(r.body)["detail"]


def test_b42_el_motor_verifica_las_conexiones():
    from app.database import engine
    assert engine.pool._pre_ping is True


