def test_configuracion_por_defecto(client, datos):
    c = client.get("/api/v1/settings").json()
    assert set(c) == {"institucion", "notificaciones", "circulacion", "calendario"}
    assert c["circulacion"]["umbral_bloqueo"] == 5.0
    assert c["calendario"]["dias_cerrados"] == [6]


def test_guardar_mezcla_secciones(client, datos, db):
    r = client.put("/api/v1/settings", json={"institucion": {"nombre": "Biblioteca de Prueba"}})

    assert r.status_code == 200
    c = r.json()
    assert c["institucion"]["nombre"] == "Biblioteca de Prueba"
    assert c["institucion"]["codigo"]  # el resto de la sección conserva sus valores

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


def test_ajustes_de_circulacion_se_validan_y_guardan_parcialmente(client, datos):
    assert client.put("/api/v1/settings",
                      json={"circulacion": {"dias_retiro_reserva": 0}}).status_code == 422
    assert client.put("/api/v1/settings",
                      json={"circulacion": {"umbral_bloqueo": -1}}).status_code == 422

    c = client.put("/api/v1/settings", json={"circulacion": {"umbral_bloqueo": 12.5}}).json()

    assert c["circulacion"]["umbral_bloqueo"] == 12.5
    assert c["circulacion"]["dias_retiro_reserva"] == 3
