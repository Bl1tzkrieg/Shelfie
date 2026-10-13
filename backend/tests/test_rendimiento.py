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


@pytest.mark.parametrize("ruta", ["/api/v1/circulation/loans", "/api/v1/catalog/items",
                                  "/api/v1/catalog/search?q=T", "/api/v1/opac/search?q=T",
                                  "/api/v1/users", "/api/v1/reports/generate?tipo=loans&formato=json&periodo=all"])
def test_el_numero_de_consultas_no_crece_con_los_datos(client, datos, contar_consultas, ruta):
    lector = datos.lector("L-0")
    datos.prestamo(datos.ejemplar(datos.titulo("T0", "0"), "E-0"), lector)
    con_uno = _consultas(client, contar_consultas, ruta)

    for n in range(1, 15):
        datos.prestamo(datos.ejemplar(datos.titulo(f"T{n}", str(n)), f"E-{n}"),
                       datos.lector(f"L-{n}"))
    con_quince = _consultas(client, contar_consultas, ruta)

    assert con_quince == con_uno


def test_reservas_y_traslados_no_crecen_con_los_datos(client, datos, db, contar_consultas):
    from app import models
    norte, sur = datos.sede("NOR"), datos.sede("SUR")

    def crear(n):
        libro = datos.titulo(f"R{n}", f"R{n}")
        item = datos.ejemplar(libro, f"R-{n}", sede=norte, estado="EnTransito")
        datos.ejemplar(libro, f"R-{n}-libre", sede=norte)
        reserva = models.Reserva(biblio_id=libro.id, usuario_id=datos.lector(f"RL-{n}").id,
                                 prioridad=1, estado="EnTransito", item_id=item.id,
                                 biblioteca_retiro_id=sur.id)
        pendiente = models.Reserva(biblio_id=libro.id, usuario_id=datos.lector(f"RP-{n}").id,
                                   prioridad=1, estado="Pendiente", biblioteca_retiro_id=norte.id)
        db.add_all([reserva, pendiente])
        db.flush()
        db.add(models.Traslado(item_id=item.id, desde_id=norte.id, hacia_id=sur.id,
                               motivo="reserva", estado="Enviado", reserva_id=reserva.id))
        db.flush()

    rutas = ["/api/v1/circulation/holds", "/api/v1/circulation/holds/to-pull?todas_las_sedes=true",
             "/api/v1/circulation/transfers?vista=enviados&todas_las_sedes=true"]
    crear(0)
    con_uno = [_consultas(client, contar_consultas, r) for r in rutas]
    for n in range(1, 15):
        crear(n)
    con_quince = [_consultas(client, contar_consultas, r) for r in rutas]

    assert con_quince == con_uno


def test_adquisiciones_no_crecen_con_los_datos(client, datos, contar_consultas):
    A = "/api/v1/acquisitions"
    proveedor = client.post(f"{A}/suppliers", json={"nombre": "P"}).json()
    presupuesto = client.post(f"{A}/budgets", json={
        "nombre": "B", "fecha_inicio": "2026-01-01", "fecha_fin": "2026-12-31",
        "monto_total": 100000}).json()

    def crear(n):
        fondo = client.post(f"{A}/budgets/{presupuesto['id']}/funds", json={
            "codigo": f"F{n}", "nombre": f"F{n}", "monto_asignado": 100}).json()
        pedido = client.post(f"{A}/orders", json={"proveedor_id": proveedor["id"], "lineas": [
            {"titulo": f"T{n}", "precio_unitario": 1, "fondo_id": fondo["id"]}]}).json()
        client.post(f"{A}/orders/{pedido['id']}/close")
        factura = client.post(f"{A}/invoices", json={"proveedor_id": proveedor["id"],
                                                     "numero": f"N{n}"}).json()
        client.post(f"{A}/invoices/{factura['id']}/receive",
                    json={"linea_id": pedido["lineas"][0]["id"]})
        client.post(f"{A}/suggestions", json={"titulo": f"S{n}", "isbn": f"97800000000{n:02d}"})

    rutas = [f"{A}/orders", f"{A}/invoices", f"{A}/budgets", f"{A}/funds", f"{A}/suppliers",
             f"{A}/suggestions"]
    crear(0)
    con_uno = [_consultas(client, contar_consultas, r) for r in rutas]
    for n in range(1, 8):
        crear(n)
    con_ocho = [_consultas(client, contar_consultas, r) for r in rutas]

    assert con_ocho == con_uno


def test_seriadas_no_crecen_con_los_datos(client, datos, contar_consultas):
    S = "/api/v1/serials"

    def crear(n):
        sus = client.post(f"{S}/subscriptions", json={
            "titulo": f"Revista {n}", "numeracion": "Núm. {Y}",
            "primer_fasciculo": "2026-01-01"}).json()
        primero = sus["fasciculos"][0]["id"]
        client.post(f"{S}/issues/{primero}/receive", json={})

    rutas = [f"{S}/subscriptions", f"{S}/issues/late", f"{S}/issues/expected"]
    crear(0)
    con_uno = [_consultas(client, contar_consultas, r) for r in rutas]
    for n in range(1, 8):
        crear(n)
    con_ocho = [_consultas(client, contar_consultas, r) for r in rutas]

    assert con_ocho == con_uno
