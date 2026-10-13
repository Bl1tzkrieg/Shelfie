import pytest


def test_estadisticas_mensuales(client, datos):
    lector = datos.lector()
    datos.prestamo(datos.ejemplar(datos.titulo()), lector)
    s = client.get("/api/v1/reports/stats").json()
    assert s["total_items"] == 1
    assert s["total_users"] == 2  # lector + administrador del cliente
    assert s["loans_this_month"] >= 0
    assert s["growth_percentage"].endswith("%")


def test_reportes_disponibles_cuentan_filas(client, datos):
    lector = datos.lector()
    datos.prestamo(datos.ejemplar(datos.titulo()), lector)
    filas = {r["id"]: r["rows"] for r in client.get("/api/v1/reports/available").json()}
    assert filas == {"loans": 1, "returns": 0, "overdue": 0, "users": 2, "catalog": 1}


def test_generar_reporte_json_y_csv(client, datos):
    datos.prestamo(datos.ejemplar(datos.titulo()), datos.lector())

    j = client.get("/api/v1/reports/generate?tipo=loans&periodo=month&formato=json").json()
    assert j["tipo"] == "loans"
    assert len(j["filas"]) == 1

    c = client.get("/api/v1/reports/generate?tipo=catalog&periodo=all&formato=csv")
    assert c.headers["content-type"].startswith("text/csv")
    assert c.text.startswith("﻿id,titulo")


@pytest.mark.parametrize("query", [
    "tipo=xx", "tipo=loans&periodo=siglo", "tipo=loans&formato=pdf",
])
def test_parametros_invalidos(client, datos, query):
    assert client.get(f"/api/v1/reports/generate?{query}").status_code == 400


def test_reporte_de_vencidos_incluye_prestamos_anteriores_al_periodo(client, datos):
    # Prestado hace 40 días (fuera del mes) con 14 de plazo: venció hace 26, dentro del mes.
    datos.prestamo(datos.ejemplar(datos.titulo()), datos.lector(), dias_desde=40, dias_hasta=14)
    j = client.get("/api/v1/reports/generate?tipo=overdue&periodo=month&formato=json").json()
    assert len(j["filas"]) == 1


def test_reporte_de_devoluciones_usa_la_fecha_de_devolucion(client, datos, db):
    from datetime import timedelta
    from app.core.tiempo import ahora
    prestamo = datos.prestamo(datos.ejemplar(datos.titulo()), datos.lector(), dias_desde=60,
                              devuelto=True)
    prestamo.fecha_devolucion = ahora() - timedelta(days=2)
    db.flush()
    j = client.get("/api/v1/reports/generate?tipo=returns&periodo=week&formato=json").json()
    assert len(j["filas"]) == 1
