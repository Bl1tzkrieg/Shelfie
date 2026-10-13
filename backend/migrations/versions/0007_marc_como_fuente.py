"""MARC como fuente del registro bibliográfico (Fase 4)

- `registros_bibliograficos.plantilla`: plantilla de catalogación (BKS, SER, TES, ERE).
- Los registros existentes traían un MARC mínimo (020/100/245) o incompleto. Se
  completa con lo que dicen las columnas (008, 100, 245, 264, 650, 020) sin pisar
  nada de lo que ya estuviera, para que derivar las columnas desde el MARC dé lo
  mismo que hoy. Los campos de datos sin indicadores reciben "  ".

Revision ID: 0007_marc
Revises: 0006_busqueda
"""
import json
from datetime import date
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_marc"
down_revision: Union[str, None] = "0006_busqueda"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LIDER_LIBRO = "00000nam a22000007i 4500"


def _008(ano):
    fecha1 = f"{ano:04d}" if ano else "    "
    return f"{date.today():%y%m%d}s{fecha1}    ve " + " " * 17 + "spa d"


def _completar(marc, titulo, autor, isbn, ano, materia):
    marc = marc if isinstance(marc, dict) else {}
    lider = str(marc.get("leader") or "").ljust(24)[:24]
    if not lider.strip() or not lider[5:10].strip():
        lider = LIDER_LIBRO
    campos = []
    for campo in marc.get("fields") or []:
        if not isinstance(campo, dict) or len(campo) != 1:
            continue
        tag, valor = next(iter(campo.items()))
        if str(tag) < "010":
            campos.append({str(tag): str(valor)})
        elif isinstance(valor, dict):
            campos.append({str(tag): {"ind1": valor.get("ind1") or " ",
                                      "ind2": valor.get("ind2") or " ",
                                      "subfields": valor.get("subfields") or []}})
    tags = {next(iter(c)) for c in campos}

    def agregar(tag, ind1, ind2, subs):
        campos.append({tag: {"ind1": ind1, "ind2": ind2, "subfields": subs}})

    if "008" not in tags:
        campos.append({"008": _008(ano)})
    if isbn and "020" not in tags:
        agregar("020", " ", " ", [{"a": isbn}])
    if autor and not tags & {"100", "110", "111"}:
        agregar("100", "1", " ", [{"a": autor}])
    if "245" not in tags:
        agregar("245", "1" if autor else "0", "0", [{"a": titulo or "Sin título"}])
    if ano and not tags & {"260", "264"}:
        agregar("264", " ", "1", [{"c": str(ano)}])
    if materia and "650" not in tags:
        agregar("650", " ", "4", [{"a": materia}])
    campos.sort(key=lambda c: next(iter(c)))
    return {"leader": lider, "fields": campos}


def upgrade() -> None:
    op.add_column("registros_bibliograficos",
                  sa.Column("plantilla", sa.String(length=10), nullable=False,
                            server_default="BKS"))
    conexion = op.get_bind()
    filas = conexion.execute(sa.text(
        "SELECT id, titulo, autor, isbn, ano_publicacion, materia, marc_json "
        "FROM registros_bibliograficos")).all()
    for f in filas:
        marc = _completar(f.marc_json, f.titulo, f.autor, f.isbn, f.ano_publicacion, f.materia)
        conexion.execute(sa.text(
            "UPDATE registros_bibliograficos SET marc_json = CAST(:m AS jsonb) WHERE id = :id"),
            {"m": json.dumps(marc, ensure_ascii=False), "id": f.id})


def downgrade() -> None:
    # El MARC completado se conserva: es un superconjunto del anterior.
    op.drop_column("registros_bibliograficos", "plantilla")
