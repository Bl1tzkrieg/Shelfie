"""Fase 8: inventario (Inventory de Koha)."""

from app import models
from app.services.inventario import clave_signatura

INV = "/api/v1/inventories"


def _estante(datos, sede):
    """Tres libros en el tramo 600-699 de Norte, uno fuera del tramo y uno de otra sede."""
    libro = datos.titulo()
    en_tramo = [datos.ejemplar(libro, f"N-{n}", sede=sede) for n in (1, 2, 3)]
    for item, signatura in zip(en_tramo, ("630 R6", "631.4 A1", "699.5 X")):
        item.signatura_topografica = signatura
    fuera = datos.ejemplar(libro, "N-9", sede=sede)
    fuera.signatura_topografica = "863 G16"
    return libro, en_tramo, fuera


def test_ordenar_signaturas_como_en_el_estante():
    assert clave_signatura("92 B") < clave_signatura("630 R6") < clave_signatura("863 G2")
    assert clave_signatura(" 630   r6 ") == clave_signatura("630 R6")


def test_inventario_completo(client, datos, db):
    norte, sur = datos.sede("NOR", "Norte"), datos.sede("SUR", "Sur")
    libro, en_tramo, fuera = _estante(datos, norte)
    otra_sede = datos.ejemplar(libro, "S-1", sede=sur)
    otra_sede.signatura_topografica = "640 Z"
    prestado = datos.ejemplar(libro, "N-P", sede=norte, estado="Prestado")
    prestado.signatura_topografica = "650 P"
    datos.prestamo(prestado, datos.lector("L-1"))
    db.commit()

    r = client.post(INV, json={"biblioteca_id": norte.id, "signatura_desde": "600",
                               "signatura_hasta": "699"})
    assert r.status_code == 201, r.text
    inv = r.json()
    assert inv["esperados"] == 3 and inv["faltantes_total"] == 3 and inv["estado"] == "Abierto"
    assert "Norte" in inv["nombre"]

    r = client.post(f"{INV}/{inv['id']}/scan",
                    json={"codigos": ["n-1", "N-2", "N-9", "S-1", "N-P", "NO-EXISTE", "N-1"]})
    assert r.status_code == 200, r.text
    assert [l["resultado"] for l in r.json()["lecturas"]] == [
        "ok", "ok", "fuera_de_lugar", "fuera_de_lugar", "prestado", "desconocido", "repetido"]
    lecturas = {l["codigo_barras"]: l for l in r.json()["lecturas"]}
    assert "fuera del tramo" in lecturas["N-9"]["detalle"]
    assert "Sur" in lecturas["S-1"]["detalle"]
    assert "Devoluciones" in lecturas["N-P"]["detalle"]

    vista = client.get(f"{INV}/{inv['id']}").json()
    assert (vista["esperados_leidos"], vista["faltantes_total"], vista["avance"]) == (2, 1, 67)
    assert [f["codigo_barras"] for f in vista["faltantes"]] == ["N-3"]
    assert vista["conteos"]["fuera_de_lugar"] == 2
    db.refresh(en_tramo[0])
    assert en_tramo[0].fecha_ultimo_inventario is not None
    assert en_tramo[2].fecha_ultimo_inventario is None

    fuera_de_lugar = client.get(f"{INV}/{inv['id']}", params={"resultado": "fuera_de_lugar"}).json()
    assert {l["codigo_barras"] for l in fuera_de_lugar["ultimas_lecturas"]} == {"N-9", "S-1"}

    csv = client.get(f"{INV}/{inv['id']}/missing.csv")
    assert csv.status_code == 200 and "N-3" in csv.text and "N-1" not in csv.text

    cerrado = client.post(f"{INV}/{inv['id']}/close").json()
    assert cerrado["estado"] == "Cerrado" and cerrado["faltantes_total"] == 1
    assert client.post(f"{INV}/{inv['id']}/scan", json={"codigos": ["N-3"]}).status_code == 400
    # Cerrado, el resumen ya no cambia aunque cambien los ejemplares.
    en_tramo[2].estado = "Perdido"
    db.commit()
    assert client.get(f"{INV}/{inv['id']}").json()["esperados"] == 3
    assert [a.accion for a in db.query(models.RegistroAccion).filter_by(accion="inventario")] \
        == ["inventario", "inventario"]


def test_devolver_solos_los_prestados_que_aparecen(client, datos, db):
    norte = datos.sede("NOR", "Norte")
    datos.sin_dias_cerrados()
    libro = datos.titulo()
    prestado = datos.ejemplar(libro, "P-1", sede=norte, estado="Prestado")
    datos.prestamo(prestado, datos.lector("L-1"))
    db.commit()
    inv = client.post(INV, json={"biblioteca_id": norte.id, "devolver_prestados": True}).json()

    [lectura] = client.post(f"{INV}/{inv['id']}/scan", json={"codigos": ["P-1"]}).json()["lecturas"]

    assert lectura["resultado"] == "devuelto"
    db.refresh(prestado)
    assert prestado.estado == "Disponible"
    assert db.query(models.Prestamo).filter_by(item_id=prestado.id).one().fecha_devolucion is not None


def test_estados_que_no_corresponden_al_estante(client, datos, db):
    libro = datos.titulo()
    for codigo, estado in (("X-1", "Perdido"), ("X-2", "Retirado"), ("X-3", "Reservado"),
                           ("X-4", "EnTransito")):
        datos.ejemplar(libro, codigo, estado=estado)
    db.commit()
    inv = client.post(INV, json={}).json()
    r = client.post(f"{INV}/{inv['id']}/scan", json={"codigos": ["X-1", "X-2", "X-3", "X-4"]}).json()
    assert [l["resultado"] for l in r["lecturas"]] == ["perdido", "retirado", "reservado", "en_transito"]
    assert inv["esperados"] == 0


def test_validaciones_y_permisos(client, como, datos):
    assert client.post(INV, json={"signatura_desde": "700", "signatura_hasta": "600"}).status_code == 400
    assert client.post(INV, json={"tipo_item_codigo": "NO"}).status_code == 400
    assert client.post(INV, json={"biblioteca_id": 999}).status_code == 404
    inv = client.post(INV, json={}).json()
    assert client.post(f"{INV}/{inv['id']}/scan", json={"codigos": ["  ", ""]}).status_code == 400
    circulacion = como(["circulacion"])
    assert circulacion.get(INV).status_code == 200
    assert circulacion.post(INV, json={}).status_code == 403
    assert circulacion.post(f"{INV}/{inv['id']}/scan", json={"codigos": ["A"]}).status_code == 403


def test_la_ficha_muestra_cuando_se_vio(client, datos, db):
    libro = datos.titulo()
    datos.ejemplar(libro, "V-1")
    db.commit()
    inv = client.post(INV, json={}).json()
    client.post(f"{INV}/{inv['id']}/scan", json={"codigos": ["V-1"]})
    [ejemplar] = client.get(f"/api/v1/catalog/items/{libro.id}/ejemplares").json()
    assert ejemplar["lastSeen"]


def test_el_prestado_vencido_dice_cuanto_atraso_lleva(client, datos, db):
    libro = datos.titulo()
    al_dia = datos.ejemplar(libro, "A-1", estado="Prestado")
    vencido = datos.ejemplar(libro, "A-2", estado="Prestado")
    lector = datos.lector("L-1")
    datos.prestamo(al_dia, lector, dias_hasta=7)
    datos.prestamo(vencido, lector, dias_desde=16, dias_hasta=7)
    db.commit()
    inv = client.post(INV, json={}).json()

    lecturas = client.post(f"{INV}/{inv['id']}/scan", json={"codigos": ["A-1", "A-2"]}).json()["lecturas"]

    assert "vence el" in lecturas[0]["detalle"] and "atraso" not in lecturas[0]["detalle"]
    assert "venció el" in lecturas[1]["detalle"] and "(9 días de atraso)" in lecturas[1]["detalle"]


def test_el_repetido_recuerda_lo_que_salio_la_primera_vez(client, datos, db):
    libro = datos.titulo()
    prestado = datos.ejemplar(libro, "R-1", estado="Prestado")
    datos.ejemplar(libro, "R-2")
    datos.prestamo(prestado, datos.lector("L-1"))
    db.commit()
    inv = client.post(INV, json={}).json()
    client.post(f"{INV}/{inv['id']}/scan", json={"codigos": ["R-1", "R-2", "NADA"]})

    # Otro envío: la primera lectura ya está guardada, no en el mismo lote.
    lecturas = client.post(f"{INV}/{inv['id']}/scan",
                           json={"codigos": ["R-1", "R-2", "NADA"]}).json()["lecturas"]

    assert [l["resultado"] for l in lecturas] == ["repetido"] * 3
    assert "figura prestado" in lecturas[0]["detalle"] and "pásalo por Devoluciones" in lecturas[0]["detalle"]
    assert lecturas[1]["detalle"] == "Antes: en su lugar"
    assert "código desconocido" in lecturas[2]["detalle"]


def test_al_releer_lo_que_cambio_se_clasifica_de_nuevo(client, datos, db):
    datos.sin_dias_cerrados()
    libro = datos.titulo()
    prestado = datos.ejemplar(libro, "C-1", estado="Prestado")
    perdido = datos.ejemplar(libro, "C-2", estado="Perdido")
    datos.prestamo(prestado, datos.lector("L-1"))
    db.commit()
    inv = client.post(INV, json={}).json()
    client.post(f"{INV}/{inv['id']}/scan", json={"codigos": ["C-1", "C-2", "C-NUEVO"]})

    # En el mostrador: se devuelve el prestado y se da de alta el código que no existía.
    assert client.post("/api/v1/circulation/checkin", json={"codigo_barras": "C-1"}).status_code == 200
    datos.ejemplar(libro, "C-NUEVO")
    db.commit()

    lecturas = client.post(f"{INV}/{inv['id']}/scan",
                           json={"codigos": ["C-1", "C-2", "C-NUEVO", "C-1"]}).json()["lecturas"]

    assert [l["resultado"] for l in lecturas] == ["ok", "repetido", "ok", "repetido"]
    assert lecturas[0]["detalle"] == "Antes: figura prestado"
    assert lecturas[3]["detalle"] == "Antes: en su lugar"
    vista = client.get(f"{INV}/{inv['id']}").json()
    # Lo resuelto ya no cuenta como prestado ni como desconocido; el perdido sigue pendiente.
    assert (vista["conteos"]["prestado"], vista["conteos"]["desconocido"]) == (0, 0)
    assert (vista["conteos"]["ok"], vista["conteos"]["perdido"]) == (2, 1)
    viejas = [l for l in vista["ultimas_lecturas"] if not l["vigente"]]
    assert {l["resultado"] for l in viejas} == {"prestado", "desconocido"}
    assert client.get(f"{INV}/{inv['id']}", params={"resultado": "prestado"}).json()["ultimas_lecturas"] == []
