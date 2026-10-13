"""Alta, edición y baja de sedes. La migración 0004 deja creada la sede principal."""

BRANCHES = "/api/v1/settings/branches"


def _principal(client):
    return next(b for b in client.get(BRANCHES).json() if b["codigo"] == "PRINC")


def test_crear_listar_y_editar(client):
    r = client.post(BRANCHES, json={"codigo": " nor ", "nombre": "Sede Norte",
                                    "telefono": "0212-555"})
    assert r.status_code == 201, r.text
    sede = r.json()
    assert (sede["codigo"], sede["punto_retiro"], sede["direccion"]) == ("NOR", True, None)

    editada = client.put(f"{BRANCHES}/{sede['id']}", json={"direccion": "Av. Principal"}).json()
    assert editada["direccion"] == "Av. Principal" and editada["nombre"] == "Sede Norte"

    con_uso = {b["codigo"]: b for b in client.get(f"{BRANCHES}?con_uso=true").json()}
    assert con_uso["NOR"]["ejemplares"] == 0 and con_uso["NOR"]["lectores"] == 0


def test_validaciones(client):
    client.post(BRANCHES, json={"codigo": "NOR", "nombre": "Norte"})
    for cuerpo, texto in [
        ({"codigo": "NOR", "nombre": "Otra"}, "Ya existe"),
        ({"codigo": "con espacio", "nombre": "X"}, "código"),
        ({"codigo": "SUR", "nombre": "  "}, "nombre"),
        ({"nombre": "Sin código"}, "código"),
    ]:
        r = client.post(BRANCHES, json=cuerpo)
        assert r.status_code == 400 and texto in r.json()["detail"], (cuerpo, r.text)


def test_queda_al_menos_un_punto_de_retiro(client):
    norte = client.post(BRANCHES, json={"codigo": "NOR", "nombre": "Norte"}).json()
    sur = client.post(BRANCHES, json={"codigo": "SUR", "nombre": "Sur"}).json()

    for sede in (sur, _principal(client)):
        r = client.put(f"{BRANCHES}/{sede['id']}", json={"punto_retiro": False})
        assert r.status_code == 200, r.text
    r = client.put(f"{BRANCHES}/{norte['id']}", json={"punto_retiro": False})
    assert r.status_code == 400 and "al menos una" in r.json()["detail"]
    assert client.delete(f"{BRANCHES}/{norte['id']}").status_code == 400


def test_no_se_borra_una_sede_en_uso(client, datos):
    sede = datos.sede("NOR", "Norte")
    datos.ejemplar(datos.titulo(), sede=sede)
    vacia = datos.sede("VAC", "Vacía")

    r = client.delete(f"{BRANCHES}/{sede.id}")
    assert r.status_code == 400 and "1 ejemplar(es)" in r.json()["detail"]
    assert client.delete(f"{BRANCHES}/{vacia.id}").status_code == 200
    assert client.delete(f"{BRANCHES}/{vacia.id}").status_code == 404


def test_solo_configuracion_gestiona_sedes(como):
    consulta = como(["circulacion"])
    assert consulta.get(BRANCHES).status_code == 200
    assert consulta.post(BRANCHES, json={"codigo": "X", "nombre": "X"}).status_code == 403
    assert como(["configuracion"]).post(
        BRANCHES, json={"codigo": "X", "nombre": "X"}).status_code == 201
