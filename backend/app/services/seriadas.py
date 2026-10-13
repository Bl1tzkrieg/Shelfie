"""Publicaciones seriadas: suscripciones, predicción de números, recepción y reclamos.

Como en Koha, cada suscripción tiene siempre un próximo fascículo **esperado**. Al
recibirlo (o darlo por faltante) se predice el siguiente con el patrón: fecha según la
frecuencia y rótulo según la numeración. Pasados los días de gracia de su fecha, un
fascículo esperado está **atrasado** y se puede reclamar al proveedor.

    Esperado ──▶ Recibido
        │  └──▶ Reclamado ──▶ Recibido
        └──────────┴────────▶ Faltante
"""

import calendar
import re
from datetime import date, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app import models
from app.core import marc_plantillas
from app.core.errores import NoEncontrado, ReglaIncumplida
from app.core.tiempo import ahora, formatear_fecha, hoy
from app.services import marc, traslados
from app.services.catalogo import aplicar_marc, sede_por_defecto

S, F = models.Suscripcion, models.Fasciculo

ESPERADO, RECIBIDO, RECLAMADO, FALTANTE = "Esperado", "Recibido", "Reclamado", "Faltante"
ABIERTOS = (ESPERADO, RECLAMADO)
UNIDADES = ("dia", "semana", "mes", "anio", "irregular")
MARCADORES = {"X", "Y", "ANO", "MES"}
MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre")
TIPO_ITEM_SERIADA = "REV"
NOMBRE_FRECUENCIA = {
    ("dia", 1): "Diaria", ("semana", 1): "Semanal", ("semana", 2): "Quincenal",
    ("mes", 1): "Mensual", ("mes", 2): "Bimestral", ("mes", 3): "Trimestral",
    ("mes", 4): "Cuatrimestral", ("mes", 6): "Semestral", ("anio", 1): "Anual",
}


# --- Patrón de predicción -------------------------------------------------------------

def _sumar_meses(fecha: date, meses: int) -> date:
    total = fecha.month - 1 + meses
    ano, mes = fecha.year + total // 12, total % 12 + 1
    return date(ano, mes, min(fecha.day, calendar.monthrange(ano, mes)[1]))


def sumar(fecha: date, unidad: str, cada: int) -> date:
    if unidad == "dia":
        return fecha + timedelta(days=cada)
    if unidad == "semana":
        return fecha + timedelta(weeks=cada)
    if unidad == "mes":
        return _sumar_meses(fecha, cada)
    if unidad == "anio":
        return _sumar_meses(fecha, 12 * cada)
    raise ReglaIncumplida("Una suscripción irregular no predice fechas")


def validar_patron(unidad: str, cada: int, numeracion: str,
                   numeros_por_volumen: Optional[int]) -> None:
    if unidad not in UNIDADES:
        raise ReglaIncumplida(f"Frecuencia desconocida: {unidad}")
    if cada < 1:
        raise ReglaIncumplida("La frecuencia debe ser al menos 1")
    if numeros_por_volumen is not None and numeros_por_volumen < 1:
        raise ReglaIncumplida("Los números por volumen deben ser al menos 1")
    usados = set(re.findall(r"\{(\w+)\}", numeracion or ""))
    desconocidos = usados - MARCADORES
    if desconocidos:
        raise ReglaIncumplida(
            f"La numeración usa marcadores desconocidos: {', '.join(sorted(desconocidos))} "
            "(valen {X}, {Y}, {ANO} y {MES})")
    if not usados and unidad != "irregular":
        raise ReglaIncumplida("La numeración necesita al menos un marcador, p. ej. Núm. {Y}")
    if "X" in usados and not numeros_por_volumen:
        raise ReglaIncumplida("Con {X} (volumen) indica cuántos números trae cada volumen")


def rotulo(numeracion: str, volumen: int, numero: int, fecha: date) -> str:
    return (numeracion.replace("{X}", str(volumen)).replace("{Y}", str(numero))
            .replace("{ANO}", str(fecha.year)).replace("{MES}", MESES[fecha.month - 1]))


def _avanzar(volumen: int, numero: int, por_volumen: Optional[int]):
    numero += 1
    if por_volumen and numero > por_volumen:
        return volumen + 1, 1
    return volumen, numero


def predecir(unidad: str, cada: int, numeracion: str, numeros_por_volumen: Optional[int],
             volumen: int, numero: int, fecha: date, cantidad: int = 12) -> List[dict]:
    """Los próximos `cantidad` fascículos desde el primero (vista previa del patrón)."""
    validar_patron(unidad, cada, numeracion, numeros_por_volumen)
    if unidad == "irregular":
        return []
    salida = []
    for _ in range(max(1, min(cantidad, 60))):
        salida.append({"numero": rotulo(numeracion, volumen, numero, fecha),
                       "fecha_esperada": fecha.isoformat(), "volumen": volumen,
                       "secuencia": numero})
        volumen, numero = _avanzar(volumen, numero, numeros_por_volumen)
        fecha = sumar(fecha, unidad, cada)
    return salida


def frecuencia_legible(s: models.Suscripcion) -> str:
    if s.frecuencia_unidad == "irregular":
        return "Irregular"
    nombre = NOMBRE_FRECUENCIA.get((s.frecuencia_unidad, s.frecuencia_cada))
    if nombre:
        return nombre
    unidades = {"dia": "días", "semana": "semanas", "mes": "meses", "anio": "años"}
    return f"Cada {s.frecuencia_cada} {unidades[s.frecuencia_unidad]}"


# --- Vistas ---------------------------------------------------------------------------

def _atrasado(f: models.Fasciculo, s: models.Suscripcion) -> Optional[int]:
    if f.estado not in ABIERTOS or not f.fecha_esperada:
        return None
    dias = (hoy() - f.fecha_esperada).days - (s.dias_gracia or 0)
    return dias if dias > 0 else None


def _vista_fasciculo(f: models.Fasciculo, s: models.Suscripcion, codigos: dict) -> dict:
    return {
        "id": f.id,
        "suscripcion_id": f.suscripcion_id,
        "numero": f.numero,
        "fecha_esperada": f.fecha_esperada.isoformat() if f.fecha_esperada else None,
        "fecha_recepcion": formatear_fecha(f.fecha_recepcion),
        "estado": f.estado,
        "recibido": f.estado == RECIBIDO,
        "dias_atraso": _atrasado(f, s),
        "reclamos": f.reclamos or 0,
        "fecha_reclamo": formatear_fecha(f.fecha_reclamo),
        "notas": f.notas,
        "codigo_barras": codigos.get(f.item_id),
    }


def _vista(db: Session, s: models.Suscripcion, fasciculos: List[models.Fasciculo],
           proveedores: dict, sedes: dict, con_fasciculos: bool = False) -> dict:
    proximo = next((f for f in sorted(fasciculos, key=lambda f: (f.fecha_esperada or date.max, f.id))
                    if f.estado in ABIERTOS), None)
    atrasados = [f for f in fasciculos if _atrasado(f, s)]
    proveedor = proveedores.get(s.proveedor_id)
    datos = {
        "id": s.id,
        "biblio_id": s.biblio_id,
        "titulo": s.titulo,
        "issn": s.issn,
        "proveedor_id": s.proveedor_id,
        "proveedor_nombre": proveedor.nombre if proveedor else None,
        "proveedor_email": proveedor.email if proveedor else None,
        "biblioteca_id": s.biblioteca_id,
        "biblioteca": sedes.get(s.biblioteca_id),
        "tipo_item_id": s.tipo_item_id,
        "crear_ejemplares": bool(s.crear_ejemplares),
        "frecuencia_unidad": s.frecuencia_unidad,
        "frecuencia_cada": s.frecuencia_cada,
        "periodicidad": frecuencia_legible(s),
        "numeracion": s.numeracion,
        "numeros_por_volumen": s.numeros_por_volumen,
        "fecha_inicio": s.fecha_inicio.isoformat() if s.fecha_inicio else None,
        "fecha_fin": s.fecha_fin.isoformat() if s.fecha_fin else None,
        "dias_gracia": s.dias_gracia,
        "estado": s.estado,
        "notas": s.notas,
        "fasciculos_recibidos": sum(1 for f in fasciculos if f.estado == RECIBIDO),
        "fasciculos_esperados": len(fasciculos),
        "fasciculos_atrasados": len(atrasados),
        "proximo": {"id": proximo.id, "numero": proximo.numero,
                    "fecha_esperada": proximo.fecha_esperada.isoformat()
                    if proximo.fecha_esperada else None} if proximo else None,
        # Pasó la fecha de fin y no queda nada por llegar: hay que renovarla.
        "por_vencer": bool(s.estado == "Activa" and s.fecha_fin
                           and (s.fecha_fin - hoy()).days <= 30),
    }
    if con_fasciculos:
        codigos = {i.id: i.codigo_barras for i in db.query(models.Item).filter(
            models.Item.id.in_([f.item_id for f in fasciculos if f.item_id]))}
        orden = sorted(fasciculos, key=lambda f: (f.fecha_esperada or date.min, f.id), reverse=True)
        datos["fasciculos"] = [_vista_fasciculo(f, s, codigos) for f in orden]
    return datos


def _contexto(db: Session):
    return ({p.id: p for p in db.query(models.Proveedor).all()},
            {b.id: b.nombre for b in db.query(models.Biblioteca).all()})


def _obtener(db: Session, suscripcion_id: int) -> models.Suscripcion:
    s = db.get(S, suscripcion_id)
    if not s:
        raise NoEncontrado("Suscripción no encontrada")
    return s


def listar(db: Session, estado: Optional[str] = None) -> List[dict]:
    consulta = db.query(S)
    if estado:
        consulta = consulta.filter(S.estado.in_(estado.split(",")))
    suscripciones = consulta.order_by(S.titulo).all()
    ids = [s.id for s in suscripciones]
    fasciculos = db.query(F).filter(F.suscripcion_id.in_(ids)).all() if ids else []
    proveedores, sedes = _contexto(db)
    return [_vista(db, s, [f for f in fasciculos if f.suscripcion_id == s.id], proveedores, sedes)
            for s in suscripciones]


def obtener(db: Session, suscripcion_id: int) -> dict:
    s = _obtener(db, suscripcion_id)
    proveedores, sedes = _contexto(db)
    fasciculos = db.query(F).filter(F.suscripcion_id == s.id).all()
    return _vista(db, s, fasciculos, proveedores, sedes, con_fasciculos=True)


# --- Suscripciones --------------------------------------------------------------------

def _registro_seriado(db: Session, titulo: str, issn: Optional[str],
                      periodicidad: str) -> models.RegistroBibliografico:
    fields = [{"008": marc.campo_008(None)}]
    if issn:
        fields.append({"022": {"ind1": " ", "ind2": " ", "subfields": [{"a": issn}]}})
    fields.append({"245": {"ind1": "0", "ind2": "0", "subfields": [{"a": titulo}]}})
    fields.append({"310": {"ind1": " ", "ind2": " ", "subfields": [{"a": periodicidad}]}})
    canonico, plantilla = marc.preparar(
        {"leader": marc_plantillas.obtener("SER").lider, "fields": fields}, "SER")
    biblio = models.RegistroBibliografico()
    aplicar_marc(biblio, canonico, plantilla)
    db.add(biblio)
    db.flush()
    return biblio


def _tipo_item(db: Session, codigo: Optional[str]) -> Optional[models.TipoItem]:
    if codigo:
        tipo = db.query(models.TipoItem).filter(models.TipoItem.codigo == codigo).first()
        if not tipo:
            raise NoEncontrado(f"Tipo de ítem {codigo} no encontrado")
        return tipo
    return (db.query(models.TipoItem).filter(models.TipoItem.codigo == TIPO_ITEM_SERIADA).first()
            or db.query(models.TipoItem).order_by(models.TipoItem.id).first())


def crear(db: Session, datos: dict) -> dict:
    unidad = datos.get("frecuencia_unidad") or "mes"
    cada = int(datos.get("frecuencia_cada") or 1)
    numeracion = (datos.get("numeracion") or "Núm. {Y}").strip()
    por_volumen = datos.get("numeros_por_volumen")
    validar_patron(unidad, cada, numeracion, por_volumen)

    if datos.get("proveedor_id") and not db.get(models.Proveedor, datos["proveedor_id"]):
        raise NoEncontrado("Proveedor no encontrado")
    if datos.get("biblioteca_id") and not db.get(models.Biblioteca, datos["biblioteca_id"]):
        raise NoEncontrado("Sede no encontrada")
    inicio = datos.get("fecha_inicio") or hoy()
    primero = datos.get("primer_fasciculo") or inicio
    if datos.get("fecha_fin") and datos["fecha_fin"] < inicio:
        raise ReglaIncumplida("La suscripción termina antes de empezar")

    if datos.get("biblio_id"):
        biblio = db.get(models.RegistroBibliografico, datos["biblio_id"])
        if not biblio:
            raise NoEncontrado("Registro bibliográfico no encontrado")
    else:
        titulo = (datos.get("titulo") or "").strip()
        if not titulo:
            raise ReglaIncumplida("Indica el título o elige el registro del catálogo")
        biblio = _registro_seriado(db, titulo, (datos.get("issn") or "").strip() or None,
                                   NOMBRE_FRECUENCIA.get((unidad, cada), "Irregular"))

    s = S(biblio_id=biblio.id, titulo=biblio.titulo,
          issn=(datos.get("issn") or "").strip() or None, proveedor_id=datos.get("proveedor_id"),
          biblioteca_id=datos.get("biblioteca_id") or sede_por_defecto(db),
          tipo_item_id=_tipo_item(db, datos.get("tipo_item_codigo")).id
          if db.query(models.TipoItem).count() else None,
          crear_ejemplares=datos.get("crear_ejemplares", True),
          frecuencia_unidad=unidad, frecuencia_cada=cada, numeracion=numeracion,
          numeros_por_volumen=por_volumen, fecha_inicio=inicio, fecha_fin=datos.get("fecha_fin"),
          dias_gracia=datos["dias_gracia"] if datos.get("dias_gracia") is not None else 15,
          estado="Activa", notas=(datos.get("notas") or "").strip() or None)
    db.add(s)
    db.flush()
    if unidad != "irregular":
        volumen, numero = int(datos.get("volumen_inicial") or 1), int(datos.get("numero_inicial") or 1)
        db.add(F(suscripcion_id=s.id, numero=rotulo(numeracion, volumen, numero, primero),
                 fecha_esperada=primero, estado=ESPERADO, recibido=False, volumen=volumen,
                 secuencia=numero))
    db.commit()
    return obtener(db, s.id)


def actualizar(db: Session, suscripcion_id: int, datos: dict) -> dict:
    s = _obtener(db, suscripcion_id)
    if datos.get("proveedor_id") is not None and not db.get(models.Proveedor, datos["proveedor_id"]):
        raise NoEncontrado("Proveedor no encontrado")
    if datos.get("biblioteca_id") is not None and not db.get(models.Biblioteca, datos["biblioteca_id"]):
        raise NoEncontrado("Sede no encontrada")
    for campo in ("proveedor_id", "biblioteca_id", "fecha_fin", "dias_gracia", "crear_ejemplares",
                  "issn"):
        if campo in datos:
            setattr(s, campo, datos[campo])
    if "notas" in datos:
        s.notas = (datos["notas"] or "").strip() or None
    if datos.get("tipo_item_codigo"):
        s.tipo_item_id = _tipo_item(db, datos["tipo_item_codigo"]).id
    patron = {k: datos[k] for k in ("frecuencia_unidad", "frecuencia_cada", "numeracion",
                                    "numeros_por_volumen") if k in datos}
    if patron:
        # El patrón nuevo rige para los próximos fascículos que se predigan.
        nuevo = {"frecuencia_unidad": s.frecuencia_unidad, "frecuencia_cada": s.frecuencia_cada,
                 "numeracion": s.numeracion, "numeros_por_volumen": s.numeros_por_volumen, **patron}
        validar_patron(nuevo["frecuencia_unidad"], int(nuevo["frecuencia_cada"]),
                       nuevo["numeracion"], nuevo["numeros_por_volumen"])
        for k, v in nuevo.items():
            setattr(s, k, v)
    if s.fecha_fin and s.fecha_inicio and s.fecha_fin < s.fecha_inicio:
        raise ReglaIncumplida("La suscripción termina antes de empezar")
    db.commit()
    return obtener(db, s.id)


def cancelar(db: Session, suscripcion_id: int) -> dict:
    s = _obtener(db, suscripcion_id)
    s.estado = "Cancelada"
    # Lo que se esperaba ya no llegará.
    db.query(F).filter(F.suscripcion_id == s.id, F.estado.in_(ABIERTOS)).update(
        {F.estado: FALTANTE, F.notas: "Suscripción cancelada"}, synchronize_session=False)
    db.commit()
    return obtener(db, s.id)


def reactivar(db: Session, suscripcion_id: int, fecha_fin: Optional[date] = None) -> dict:
    """Renovación: vuelve a estar activa (con nueva fecha de fin) y retoma la predicción."""
    s = _obtener(db, suscripcion_id)
    if fecha_fin is not None:
        if s.fecha_inicio and fecha_fin < s.fecha_inicio:
            raise ReglaIncumplida("La suscripción termina antes de empezar")
        s.fecha_fin = fecha_fin
    s.estado = "Activa"
    db.flush()
    if not db.query(F).filter(F.suscripcion_id == s.id, F.estado.in_(ABIERTOS)).count():
        _predecir_siguiente(db, s)
    db.commit()
    return obtener(db, s.id)


# --- Fascículos -----------------------------------------------------------------------

def _ultimo_predicho(db: Session, s: models.Suscripcion) -> Optional[models.Fasciculo]:
    return db.query(F).filter(F.suscripcion_id == s.id, F.secuencia != None).order_by(  # noqa: E711
        F.fecha_esperada.desc(), F.id.desc()).first()


def _predecir_siguiente(db: Session, s: models.Suscripcion) -> Optional[models.Fasciculo]:
    """El próximo número según el patrón, a partir del último predicho."""
    if s.frecuencia_unidad == "irregular" or s.estado != "Activa":
        return None
    ultimo = _ultimo_predicho(db, s)
    if not ultimo or not ultimo.fecha_esperada:
        return None
    volumen, numero = _avanzar(ultimo.volumen or 1, ultimo.secuencia, s.numeros_por_volumen)
    fecha = sumar(ultimo.fecha_esperada, s.frecuencia_unidad, s.frecuencia_cada)
    if s.fecha_fin and fecha > s.fecha_fin:
        return None
    rot = rotulo(s.numeracion, volumen, numero, fecha)
    if db.query(F).filter(F.suscripcion_id == s.id, F.numero == rot).first():
        return None
    nuevo = F(suscripcion_id=s.id, numero=rot, fecha_esperada=fecha, estado=ESPERADO,
              recibido=False, volumen=volumen, secuencia=numero)
    db.add(nuevo)
    db.flush()
    return nuevo


def _cerrar(db: Session, f: models.Fasciculo, s: models.Suscripcion, estado: str) -> None:
    """Cierra el fascículo; si era el último predicho, se espera el siguiente."""
    era_ultimo = _ultimo_predicho(db, s)
    f.estado = estado
    f.recibido = estado == RECIBIDO
    db.flush()
    if era_ultimo is not None and era_ultimo.id == f.id:
        _predecir_siguiente(db, s)


def _obtener_fasciculo(db: Session, fasciculo_id: int):
    f = db.get(F, fasciculo_id)
    if not f:
        raise NoEncontrado("Fascículo no encontrado")
    return f, db.get(S, f.suscripcion_id)


def registrar_fasciculo(db: Session, suscripcion_id: int, datos: dict) -> dict:
    """Un número fuera del patrón (especial, suplemento) o de una suscripción irregular."""
    s = _obtener(db, suscripcion_id)
    numero = (datos.get("numero") or "").strip()
    if not numero:
        raise ReglaIncumplida("Indica el número del fascículo")
    if db.query(F).filter(F.suscripcion_id == s.id, F.numero == numero).first():
        raise ReglaIncumplida(f"El fascículo {numero} ya está registrado")
    f = F(suscripcion_id=s.id, numero=numero, fecha_esperada=datos.get("fecha_esperada") or hoy(),
          estado=ESPERADO, recibido=False, notas=(datos.get("notas") or "").strip() or None)
    db.add(f)
    db.commit()
    return _vista_fasciculo(f, s, {})


def recibir_fasciculo(db: Session, fasciculo_id: int, datos: Optional[dict] = None,
                      personal_id: Optional[int] = None) -> dict:
    datos = datos or {}
    f, s = _obtener_fasciculo(db, fasciculo_id)
    if f.estado == RECIBIDO:
        raise ReglaIncumplida("El fascículo ya figura como recibido")
    crear = datos.get("crear_ejemplar", s.crear_ejemplares)
    destino = None
    if crear:
        if not s.biblio_id:
            raise ReglaIncumplida("La suscripción no está ligada a un registro del catálogo")
        codigo = (datos.get("codigo_barras") or "").strip() or f"SER{s.id:04d}-{f.id:05d}"
        if db.query(models.Item.id).filter(models.Item.codigo_barras == codigo).first():
            raise ReglaIncumplida(f"Ya existe el código de barras {codigo}")
        sede = s.biblioteca_id or sede_por_defecto(db)
        item = models.Item(biblio_id=s.biblio_id, codigo_barras=codigo,
                           tipo_item_id=s.tipo_item_id, estado="Disponible", enumeracion=f.numero,
                           signatura_topografica=(datos.get("signatura") or "").strip() or None,
                           biblioteca_propia_id=sede, biblioteca_actual_id=sede)
        db.add(item)
        db.flush()
        f.item_id = item.id
        # Alguien pudo reservar la revista: el número nuevo pasa por las reservas.
        destino = traslados.describir(db, traslados.ubicar(db, item, sede, personal_id=personal_id))
    f.fecha_recepcion = ahora()
    if datos.get("notas"):
        f.notas = datos["notas"].strip()
    _cerrar(db, f, s, RECIBIDO)
    db.commit()
    codigos = {f.item_id: db.get(models.Item, f.item_id).codigo_barras} if f.item_id else {}
    return {**obtener(db, s.id), "recibido": _vista_fasciculo(f, s, codigos), "destino": destino}


def marcar_faltante(db: Session, fasciculo_id: int, notas: Optional[str] = None) -> dict:
    f, s = _obtener_fasciculo(db, fasciculo_id)
    if f.estado not in ABIERTOS:
        raise ReglaIncumplida(f"El fascículo ya está {f.estado.lower()}")
    if notas:
        f.notas = notas.strip()
    _cerrar(db, f, s, FALTANTE)
    db.commit()
    return obtener(db, s.id)


def reclamar(db: Session, fasciculo_id: int) -> dict:
    f, s = _obtener_fasciculo(db, fasciculo_id)
    if f.estado not in ABIERTOS:
        raise ReglaIncumplida(f"El fascículo ya está {f.estado.lower()}")
    f.estado = RECLAMADO
    f.reclamos = (f.reclamos or 0) + 1
    f.fecha_reclamo = ahora()
    db.commit()
    return obtener(db, s.id)


def atrasados(db: Session) -> List[dict]:
    """Fascículos esperados o reclamados cuya fecha más los días de gracia ya pasó."""
    filas = db.query(F, S).join(S, S.id == F.suscripcion_id).filter(
        F.estado.in_(ABIERTOS), S.estado == "Activa", F.fecha_esperada != None).order_by(  # noqa: E711
        F.fecha_esperada).all()
    proveedores, _ = _contexto(db)
    resultado = []
    for f, s in filas:
        dias = _atrasado(f, s)
        if not dias:
            continue
        p = proveedores.get(s.proveedor_id)
        resultado.append({**_vista_fasciculo(f, s, {}), "titulo": s.titulo, "issn": s.issn,
                          "proveedor_nombre": p.nombre if p else None,
                          "proveedor_email": p.email if p else None})
    return resultado


def por_recibir(db: Session) -> List[dict]:
    """Lo que se espera de las suscripciones activas, para el mostrador de recepción."""
    filas = db.query(F, S).join(S, S.id == F.suscripcion_id).filter(
        F.estado.in_(ABIERTOS), S.estado == "Activa").order_by(F.fecha_esperada, S.titulo).all()
    return [{**_vista_fasciculo(f, s, {}), "titulo": s.titulo, "issn": s.issn}
            for f, s in filas]
