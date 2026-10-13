def test_configuracion_por_defecto(client, datos):
    c = client.get("/api/v1/settings").json()
    assert set(c) == {"institucion", "politicas_prestamo", "notificaciones", "circulacion",
                      "calendario"}
    assert c["circulacion"]["umbral_bloqueo"] == 5.0
    assert c["calendario"]["dias_cerrados"] == [6]
    assert c["politicas_prestamo"]["renovaciones_permitidas"] == 2


def test_guardar_mezcla_secciones_y_sincroniza_categorias(client, datos, db):
    r = client.put("/api/v1/settings", json={
        "institucion": {"nombre": "Biblioteca de Prueba"},
        "politicas_prestamo": {"dias_docente": 45, "max_estudiante": 4, "multa_por_dia": 2},
    })

    assert r.status_code == 200
    c = r.json()
    assert c["institucion"]["nombre"] == "Biblioteca de Prueba"
    assert c["institucion"]["codigo"]  # el resto de la sección conserva sus valores
    # Desde la Fase 3 las políticas viven en las reglas de circulación.
    assert datos.regla_de(datos.doc).dias_prestamo == 45
    assert datos.regla_de(datos.est).max_prestamos == 4
    assert float(datos.regla_de(datos.est).multa_por_dia) == 2.0
    assert c["politicas_prestamo"]["dias_docente"] == 45  # y se leen desde ahí

    # Un segundo guardado parcial no borra lo anterior.
    client.put("/api/v1/settings", json={"institucion": {"telefono": "0212"}})
    c = client.get("/api/v1/settings").json()
    assert c["institucion"]["nombre"] == "Biblioteca de Prueba"
    assert c["institucion"]["telefono"] == "0212"


def test_informacion_del_sistema(client, datos):
    datos.ejemplar(datos.titulo())
    info = client.get("/api/v1/settings/system-info").json()
    assert info["total_registros"] == 1
    assert info["total_ejemplares"] == 1


def test_politicas_basicas_no_pisan_reglas_por_tipo_de_item(client, datos):
    client.put("/api/v1/circulation-rules", json={
        "tipo_item_id": datos.lib.id, "dias_prestamo": 3, "max_prestamos": 2,
        "max_renovaciones": 0, "multa_por_dia": 0.5})

    client.put("/api/v1/settings", json={
        "politicas_prestamo": {"renovaciones_permitidas": 4, "multa_por_dia": 3}})

    reglas = {(r["categoria_id"], r["tipo_item_id"]): r
              for r in client.get("/api/v1/circulation-rules").json()}
    por_tipo = reglas[(None, datos.lib.id)]
    assert (por_tipo["max_renovaciones"], por_tipo["multa_por_dia"]) == (0, 0.5)
    assert reglas[(None, None)]["max_renovaciones"] == 4
    assert reglas[(datos.est.id, None)]["multa_por_dia"] == 3.0


def test_ajustes_de_circulacion_se_validan_y_guardan_parcialmente(client, datos):
    assert client.put("/api/v1/settings",
                      json={"circulacion": {"dias_retiro_reserva": 0}}).status_code == 422
    assert client.put("/api/v1/settings",
                      json={"circulacion": {"umbral_bloqueo": -1}}).status_code == 422

    c = client.put("/api/v1/settings", json={"circulacion": {"umbral_bloqueo": 12.5}}).json()

    assert c["circulacion"]["umbral_bloqueo"] == 12.5
    assert c["circulacion"]["dias_retiro_reserva"] == 3
