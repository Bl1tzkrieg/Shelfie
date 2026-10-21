"""CSV del sistema: punto y coma (Excel con configuración regional de Venezuela), BOM y celdas seguras."""

import csv
import io

from app.core.csv import BOM, SEPARADOR, Texto, celda_segura, texto_csv


def test_separador_punto_y_coma_con_bom_y_celdas_seguras():
    filas = [{"titulo": "=SUMA(1;2)", "autor": "Murray, Robert K.", "materias": "A | B"}]
    texto = texto_csv(filas)
    assert SEPARADOR == ";" and texto.startswith(BOM)
    lineas = texto[len(BOM):].splitlines()
    assert lineas[0] == "titulo;autor;materias"
    leidas = list(csv.DictReader(io.StringIO(texto[len(BOM):]), delimiter=";"))
    assert leidas == [{"titulo": "'=SUMA(1;2)", "autor": "Murray, Robert K.", "materias": "A | B"}]
    assert "\"'=SUMA(1;2)\"" in lineas[1]  # el «;» dentro de la celda va entre comillas


def test_registro_de_acciones_tambien_usa_punto_y_coma(client, datos):
    libro = datos.titulo()
    item = datos.ejemplar(libro, "B-1")
    client.delete(f"/api/v1/books/{libro.id}/copies/{item.id}")
    r = client.get("/api/v1/logs/export", params={"modulo": "catalogo"})
    assert r.status_code == 200
    texto = r.content.decode("utf-8-sig")
    filas = list(csv.reader(io.StringIO(texto), delimiter=";"))
    assert len(filas[0]) > 3 and any("Eliminó el ejemplar B-1" in c for c in filas[1])


def _celdas(filas, columnas):
    texto = texto_csv(filas, columnas)
    return list(csv.reader(io.StringIO(texto[len(BOM):]), delimiter=";"))[1]


def test_texto_se_escribe_como_cadena_de_excel():
    assert _celdas([{"a": Texto("025.32"), "b": Texto("9789800000014")}], ["a", "b"]) == [
        '="025.32"', '="9789800000014"']


def test_texto_duplica_las_comillas_y_no_ejecuta_formulas():
    celdas = _celdas([{"a": Texto('A"B'), "b": Texto('=HYPERLINK("x")')}], ["a", "b"])
    assert celdas == ['="A""B"', '="=HYPERLINK(""x"")"']
    assert celda_segura(Texto("=1+1")) == "=1+1"  # literal de cadena: no hay que prefijarlo


def test_texto_vacio_queda_vacio():
    assert _celdas([{"a": Texto(""), "b": ""}], ["a", "b"]) == ["", ""]
