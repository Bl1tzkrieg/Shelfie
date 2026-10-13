"""Reglas de circulación y calendario."""

from datetime import date

from app.services import reglas


def test_listado_de_reglas_de_general_a_especifica(client, datos):
    filas = client.get("/api/v1/circulation-rules").json()
    assert filas[0]["categoria"] == "Todas" and filas[0]["tipo_item"] == "Todos"
    assert {f["categoria"] for f in filas[1:]} >= {"Estudiante", "Docente", "Personal"}


def test_la_regla_mas_especifica_gana(client, datos, db):
    general = reglas.regla_general(db)
    cuerpo = {"dias_prestamo": 2, "max_prestamos": 1, "max_renovaciones": 0,
              "multa_por_dia": float(general.multa_por_dia)}
    client.put("/api/v1/circulation-rules",
               json={**cuerpo, "categoria_id": datos.est.id, "tipo_item_id": datos.lib.id})

    estudiante_libro = reglas.regla_para(db, datos.est.id, datos.lib.id, None)
    docente_libro = reglas.regla_para(db, datos.doc.id, datos.lib.id, None)
    estudiante_otro = reglas.regla_para(db, datos.est.id, None, None)

    assert estudiante_libro.dias_prestamo == 2
    assert docente_libro.dias_prestamo == 30   # su regla de categoría
    assert estudiante_otro.dias_prestamo == 7


def test_guardar_dos_veces_la_misma_combinacion_actualiza(client, datos):
    cuerpo = {"categoria_id": datos.est.id, "dias_prestamo": 10, "max_prestamos": 4,
              "max_renovaciones": 1, "multa_por_dia": 2}
    a = client.put("/api/v1/circulation-rules", json=cuerpo).json()
    b = client.put("/api/v1/circulation-rules", json={**cuerpo, "dias_prestamo": 12}).json()
    assert a["id"] == b["id"]
    assert b["dias_prestamo"] == 12


def test_la_regla_general_no_se_elimina(client, datos, db):
    general = reglas.regla_general(db)
    assert client.delete(f"/api/v1/circulation-rules/{general.id}").status_code == 400
    especifica = datos.regla_de(datos.doc)
    assert client.delete(f"/api/v1/circulation-rules/{especifica.id}").status_code == 204


def test_reglas_y_calendario_exigen_permiso_de_configuracion(como):
    cliente = como(["circulacion"])
    assert cliente.get("/api/v1/circulation-rules").status_code == 200
    assert cliente.put("/api/v1/circulation-rules", json={
        "dias_prestamo": 1, "max_prestamos": 1, "max_renovaciones": 0,
        "multa_por_dia": 1}).status_code == 403
    assert cliente.post("/api/v1/calendar/holidays",
                        json={"fecha": "2026-12-25", "descripcion": "Navidad"}).status_code == 403


def test_calendario(client, datos):
    c = client.get("/api/v1/calendar").json()
    assert c["dias_cerrados"] == [6]
    assert c["dias_cerrados_nombres"] == ["domingo"]

    c = client.post("/api/v1/calendar/holidays",
                    json={"fecha": "2026-12-25", "descripcion": "Navidad"}).json()
    assert c["feriados"][0]["fecha"] == "2026-12-25"
    assert client.post("/api/v1/calendar/holidays",
                       json={"fecha": "2026-12-25", "descripcion": "Otra"}).status_code == 400

    c = client.delete(f"/api/v1/calendar/holidays/{c['feriados'][0]['id']}").json()
    assert c["feriados"] == []

    assert client.put("/api/v1/calendar/closed-days", json={"dias": [7]}).status_code == 400
    assert client.put("/api/v1/calendar/closed-days",
                      json={"dias": list(range(7))}).status_code == 400
    assert client.put("/api/v1/calendar/closed-days",
                      json={"dias": [5, 6]}).json()["dias_cerrados"] == [5, 6]


def test_calendario_cuenta_habiles():
    from app.services.calendario import Calendario
    cal = Calendario({6}, {date(2026, 10, 12)})  # domingos y un lunes feriado
    sabado = date(2026, 10, 10)
    assert cal.siguiente_habil(date(2026, 10, 11)) == date(2026, 10, 13)  # dom → (lun feriado) → mar
    assert cal.sumar_habiles(sabado, 1) == date(2026, 10, 13)
    assert cal.habiles_entre(sabado, date(2026, 10, 14)) == 2  # mar y mié


def test_opciones_para_el_formulario_de_reglas(client, datos):
    o = client.get("/api/v1/circulation-rules/options").json()
    assert [c["codigo"] for c in o["categorias"]] == ["ADM", "DOC", "EST"]
    assert {"id": datos.lib.id, "codigo": "LIB", "nombre": "Libro"} in o["tipos_item"]
    assert len(o["bibliotecas"]) >= 1
