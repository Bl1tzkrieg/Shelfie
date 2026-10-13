def _catalogo(datos):
    lector = datos.lector(nombre="Privado", apellido="Lector")
    novela = datos.titulo()
    datos.prestamo(datos.ejemplar(novela, "A"), lector)
    suelos = datos.titulo("Ciencia del Suelo", "9782222222222", autor="Nyle Brady",
                          ano=2008, materia="Suelos")
    datos.ejemplar(suelos, "B")
    return novela, suelos


def test_busqueda_basica(client, datos):
    _catalogo(datos)
    r = client.get("/api/v1/opac/search?q=suelo").json()
    assert r["total"] == 1
    assert r["resultados"][0]["titulo"] == "Ciencia del Suelo"
    assert client.get("/api/v1/opac/search").json()["total"] == 2


def test_busqueda_avanzada(client, datos):
    _catalogo(datos)
    assert client.get("/api/v1/opac/advanced-search?ano_desde=2000").json()["total"] == 1
    assert client.get("/api/v1/opac/advanced-search?autor=garcía").json()["total"] == 1
    assert client.get("/api/v1/opac/advanced-search?solo_disponibles=true").json()["total"] == 1


def test_ficha_publica_no_expone_datos_personales(client, datos):
    novela, _ = _catalogo(datos)
    ficha = client.get(f"/api/v1/opac/record/{novela.id}")
    assert ficha.status_code == 200
    assert ficha.json()["disponibles"] == 0
    assert "Privado" not in ficha.text
    assert client.get("/api/v1/opac/record/999999").status_code == 404


def test_materias(client, datos):
    _catalogo(datos)
    assert client.get("/api/v1/opac/subjects").json() == ["Literatura", "Suelos"]
