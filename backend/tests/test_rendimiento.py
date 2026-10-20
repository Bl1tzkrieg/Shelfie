"""Los listados no hacen una consulta por fila (problema N+1)."""

import pytest
from sqlalchemy import event


@pytest.fixture()
def contar_consultas(engine):
    contador = {"n": 0}

    def _contar(*_):
        contador["n"] += 1

    event.listen(engine, "before_cursor_execute", _contar)
    yield contador
    event.remove(engine, "before_cursor_execute", _contar)


def _consultas(client, contador, ruta):
    contador["n"] = 0
    assert client.get(ruta).status_code == 200
    return contador["n"]


@pytest.mark.parametrize("ruta", ["/api/v1/books", "/api/v1/catalog/search?q=T",
                                  "/api/v1/staff"])
def test_el_numero_de_consultas_no_crece_con_los_datos(client, datos, contar_consultas, ruta):
    datos.ejemplar(datos.titulo("T0", "0"), "E-0")
    datos.personal("P-0", ["catalogo"])
    con_uno = _consultas(client, contar_consultas, ruta)

    for n in range(1, 15):
        datos.ejemplar(datos.titulo(f"T{n}", str(n)), f"E-{n}")
        datos.personal(f"P-{n}", ["catalogo"])
    con_quince = _consultas(client, contar_consultas, ruta)

    assert con_quince == con_uno


def test_ejemplares_de_un_titulo_no_crecen_con_los_datos(client, datos, contar_consultas):
    """B15: antes, dos consultas por ejemplar (préstamo y lector)."""
    libro = datos.titulo()
    datos.ejemplar(libro, "X-0")
    ruta = f"/api/v1/books/{libro.id}"
    con_uno = _consultas(client, contar_consultas, ruta)
    for n in range(1, 10):
        datos.ejemplar(libro, f"X-{n}")
    assert _consultas(client, contar_consultas, ruta) == con_uno
