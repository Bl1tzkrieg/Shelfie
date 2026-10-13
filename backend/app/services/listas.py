"""Listas de los lectores en el OPAC ("Mis listas" de Koha).

Cada lector arma las suyas. Una lista privada solo la ve su dueño; una pública la ve
cualquiera que tenga el enlace, sin iniciar sesión.
"""

from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.core.errores import NoEncontrado, ReglaIncumplida
from app.core.tiempo import ahora, formatear_fecha
from app.services import busqueda, opac

L, LR = models.Lista, models.ListaRegistro
MAX_LISTAS = 20


def _vista(lista: models.Lista, cantidad: int, contiene: Optional[bool] = None) -> dict:
    datos = {"id": lista.id, "nombre": lista.nombre, "publica": bool(lista.publica),
             "cantidad": cantidad, "creada": formatear_fecha(lista.fecha_creacion)}
    if contiene is not None:
        datos["contiene"] = contiene
    return datos


def mis_listas(db: Session, usuario: models.Usuario, biblio_id: Optional[int] = None) -> List[dict]:
    """Las listas del lector; con `biblio_id`, además si cada una ya tiene ese título."""
    cantidades = dict(db.query(LR.lista_id, func.count()).join(L, L.id == LR.lista_id).filter(
        L.usuario_id == usuario.id).group_by(LR.lista_id).all())
    con_titulo = set()
    if biblio_id is not None:
        con_titulo = {i for (i,) in db.query(LR.lista_id).join(L, L.id == LR.lista_id).filter(
            L.usuario_id == usuario.id, LR.biblio_id == biblio_id)}
    filas = db.query(L).filter(L.usuario_id == usuario.id).order_by(func.lower(L.nombre), L.id)
    return [_vista(l, cantidades.get(l.id, 0),
                   (l.id in con_titulo) if biblio_id is not None else None) for l in filas]


def _propia(db: Session, usuario: models.Usuario, lista_id: int) -> models.Lista:
    lista = db.get(L, lista_id)
    if not lista or lista.usuario_id != usuario.id:
        raise NoEncontrado("Lista no encontrada")
    return lista


def _nombre_libre(db: Session, usuario: models.Usuario, nombre: str,
                  salvo: Optional[int] = None) -> str:
    nombre = (nombre or "").strip()
    if not nombre:
        raise ReglaIncumplida("La lista necesita un nombre")
    repetida = db.query(L).filter(L.usuario_id == usuario.id,
                                  func.lower(L.nombre) == nombre.lower())
    if salvo is not None:
        repetida = repetida.filter(L.id != salvo)
    if repetida.first():
        raise ReglaIncumplida(f"Ya tienes una lista llamada «{nombre}»")
    return nombre


def crear(db: Session, usuario: models.Usuario, nombre: str, publica: bool = False) -> dict:
    if db.query(L).filter(L.usuario_id == usuario.id).count() >= MAX_LISTAS:
        raise ReglaIncumplida(f"Puedes tener hasta {MAX_LISTAS} listas")
    lista = L(usuario_id=usuario.id, nombre=_nombre_libre(db, usuario, nombre),
              publica=bool(publica), fecha_creacion=ahora())
    db.add(lista)
    db.commit()
    return _vista(lista, 0)


def editar(db: Session, usuario: models.Usuario, lista_id: int, datos: dict) -> dict:
    lista = _propia(db, usuario, lista_id)
    if datos.get("nombre") is not None:
        lista.nombre = _nombre_libre(db, usuario, datos["nombre"], salvo=lista.id)
    if datos.get("publica") is not None:
        lista.publica = bool(datos["publica"])
    db.commit()
    return _vista(lista, db.query(LR).filter(LR.lista_id == lista.id).count())


def eliminar(db: Session, usuario: models.Usuario, lista_id: int) -> None:
    db.delete(_propia(db, usuario, lista_id))
    db.commit()


def agregar(db: Session, usuario: models.Usuario, lista_id: int, biblio_id: int) -> dict:
    lista = _propia(db, usuario, lista_id)
    if not db.get(models.RegistroBibliografico, biblio_id):
        raise NoEncontrado("Título no encontrado en el catálogo")
    if not db.get(LR, (lista.id, biblio_id)):
        db.add(LR(lista_id=lista.id, biblio_id=biblio_id, fecha=ahora()))
        db.commit()
    return _vista(lista, db.query(LR).filter(LR.lista_id == lista.id).count(), True)


def quitar(db: Session, usuario: models.Usuario, lista_id: int, biblio_id: int) -> None:
    lista = _propia(db, usuario, lista_id)
    fila = db.get(LR, (lista.id, biblio_id))
    if fila:
        db.delete(fila)
        db.commit()


def ver(db: Session, lista_id: int, usuario: Optional[models.Usuario] = None) -> dict:
    """Una lista con sus títulos. La privada de otro responde 404, como si no existiera."""
    lista = db.get(L, lista_id)
    propia = bool(lista and usuario and lista.usuario_id == usuario.id)
    if not lista or not (lista.publica or propia):
        raise NoEncontrado("Lista no encontrada")
    registros = db.query(models.RegistroBibliografico).join(
        LR, LR.biblio_id == models.RegistroBibliografico.id).filter(
        LR.lista_id == lista.id).order_by(LR.fecha.desc()).all()
    items = busqueda.items_por_titulo(db, [b.id for b in registros])
    dueno = db.get(models.Usuario, lista.usuario_id)
    return {
        **_vista(lista, len(registros)),
        "propia": propia,
        # De una lista pública se muestra solo el nombre de pila de quien la armó.
        "autor": dueno.nombre if dueno else None,
        "titulos": [opac.vista_publica(b, items[b.id]) for b in registros],
    }
