"""Lectores: alta, edición, suspensión, padrón e importación masiva."""

from typing import List, Optional

from sqlalchemy import func

from sqlalchemy.orm import Session

from app import models
from app.core.errores import ErrorDeNegocio, NoEncontrado, ReglaIncumplida
from app.core.tiempo import ahora
from app.security import hash_password
from app.services import cuentas


def vista_de_usuario(db: Session, u: models.Usuario, *, conteos: Optional[dict] = None,
                     categorias: Optional[dict] = None, umbral=None) -> dict:
    """Ficha del lector. Al listar se pasan conteos, categorías y umbral ya cargados."""
    if conteos is None:
        conteos = _conteos_de_prestamos(db, [u.id])
    activos, total = conteos.get(u.id, (0, 0))

    categoria = None
    if u.categoria_id:
        categoria = (categorias.get(u.categoria_id) if categorias is not None
                     else db.get(models.CategoriaUsuario, u.categoria_id))
    if umbral is None:
        umbral = cuentas.umbral_de_bloqueo(db)

    return {
        "nro_carnet": u.nro_carnet,
        "nombre": u.nombre,
        "apellido": u.apellido,
        "email": u.email,
        "activo": u.activo,
        "saldo_multas": float(u.saldo_multas or 0),
        "departamento": u.departamento,
        "fecha_creacion": u.fecha_creacion,
        "categoria": categoria,
        "prestamos_activos_count": activos,
        "total_prestamos_count": total,
        "es_personal": bool(u.es_personal),
        "permisos": list(u.permisos or []),
        "bloqueado_por_deuda": cuentas.esta_bloqueado(u.saldo_multas or 0, umbral),
        "biblioteca_id": u.biblioteca_id,
    }


def _conteos_de_prestamos(db: Session, ids: List[int]) -> dict:
    """{usuario_id: (activos, total)} con una sola consulta."""
    P = models.Prestamo
    filas = db.query(
        P.usuario_id,
        func.count(P.id).filter(P.fecha_devolucion == None),  # noqa: E711
        func.count(P.id),
    ).filter(P.usuario_id.in_(ids)).group_by(P.usuario_id).all()
    return {uid: (activos, total) for uid, activos, total in filas}


def listar_vistas(db: Session, usuarios: List[models.Usuario]) -> List[dict]:
    conteos = _conteos_de_prestamos(db, [u.id for u in usuarios])
    categorias = {c.id: c for c in db.query(models.CategoriaUsuario).all()}
    umbral = cuentas.umbral_de_bloqueo(db)
    return [vista_de_usuario(db, u, conteos=conteos, categorias=categorias, umbral=umbral)
            for u in usuarios]


def obtener_por_carnet(db: Session, nro_carnet: str) -> models.Usuario:
    usuario = db.query(models.Usuario).filter(models.Usuario.nro_carnet == nro_carnet).first()
    if not usuario:
        raise NoEncontrado("Usuario no encontrado")
    return usuario


def buscar_por_identificador(db: Session, identificador: str):
    """Username o número de carnet, en ese orden."""
    usuario = db.query(models.Usuario).filter(models.Usuario.username == identificador).first()
    if not usuario:
        usuario = db.query(models.Usuario).filter(
            models.Usuario.nro_carnet == identificador).first()
    return usuario


def listar(db: Session) -> List[dict]:
    return listar_vistas(db, db.query(models.Usuario).order_by(models.Usuario.id).all())


def crear(db: Session, datos) -> dict:
    if db.query(models.Usuario).filter(models.Usuario.nro_carnet == datos.nro_carnet).first():
        raise ReglaIncumplida(f"Ya existe un usuario con el carnet {datos.nro_carnet}")

    if db.query(models.Usuario).filter(models.Usuario.email == datos.email).first():
        raise ReglaIncumplida("Ese email ya está registrado")

    # Si no se indica username se deriva del carnet, que es único.
    username = datos.username or f"u{datos.nro_carnet}"
    if db.query(models.Usuario).filter(models.Usuario.username == username).first():
        raise ReglaIncumplida(f"El username '{username}' ya está tomado")

    categoria = db.query(models.CategoriaUsuario).filter(
        models.CategoriaUsuario.codigo == datos.categoria_codigo).first()
    if not categoria:
        raise ReglaIncumplida(f"No existe la categoría de usuario '{datos.categoria_codigo}'")

    usuario = models.Usuario(
        nro_carnet=datos.nro_carnet,
        username=username,
        # Sin contraseña explícita se usa el carnet como clave inicial.
        password_hash=hash_password(datos.password or datos.nro_carnet),
        nombre=datos.nombre,
        apellido=datos.apellido,
        email=datos.email,
        departamento=datos.departamento,
        categoria_id=categoria.id,
        saldo_multas=0,
        activo=True,
        fecha_creacion=ahora(),
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return vista_de_usuario(db, usuario)


def editar(db: Session, nro_carnet: str, datos) -> dict:
    usuario = obtener_por_carnet(db, nro_carnet)

    if datos.email and datos.email != usuario.email:
        if db.query(models.Usuario).filter(models.Usuario.email == datos.email).first():
            raise ReglaIncumplida("Ese email ya está registrado")
        usuario.email = datos.email

    if datos.nombre:
        usuario.nombre = datos.nombre
    if datos.apellido:
        usuario.apellido = datos.apellido
    if datos.departamento is not None:
        usuario.departamento = datos.departamento

    if datos.categoria_codigo:
        categoria = db.query(models.CategoriaUsuario).filter(
            models.CategoriaUsuario.codigo == datos.categoria_codigo).first()
        if not categoria:
            raise ReglaIncumplida(f"No existe la categoría '{datos.categoria_codigo}'")
        usuario.categoria_id = categoria.id

    db.commit()
    db.refresh(usuario)
    return vista_de_usuario(db, usuario)


def cambiar_estado(db: Session, nro_carnet: str, activo: bool) -> dict:
    """Suspende o reactiva. No se suspende a quien tiene préstamos sin devolver."""
    usuario = obtener_por_carnet(db, nro_carnet)

    if not activo:
        activos = db.query(models.Prestamo).filter(
            models.Prestamo.usuario_id == usuario.id,
            models.Prestamo.fecha_devolucion == None).count()  # noqa: E711
        if activos:
            raise ReglaIncumplida(
                f"No se puede suspender: el usuario tiene {activos} préstamo(s) sin devolver")

    usuario.activo = activo
    db.commit()
    db.refresh(usuario)
    return vista_de_usuario(db, usuario)


def filas_padron(db: Session) -> List[dict]:
    filas = []
    for d in listar(db):
        filas.append({
            "nro_carnet": d["nro_carnet"],
            "nombre": d["nombre"],
            "apellido": d["apellido"],
            "email": d["email"],
            "departamento": d["departamento"] or "",
            "categoria": d["categoria"].descripcion if d["categoria"] else "",
            "activo": "Sí" if d["activo"] else "No",
            "saldo_multas": f"{d['saldo_multas']:.2f}",
            "prestamos_activos": d["prestamos_activos_count"],
            "total_prestamos": d["total_prestamos_count"],
        })
    return filas


def importar(db: Session, filas: list) -> dict:
    """Alta masiva. Informa fila por fila qué se creó y qué se omitió."""
    creados, omitidos = 0, []
    for i, fila in enumerate(filas, start=1):
        try:
            crear(db, fila)
            creados += 1
        except ErrorDeNegocio as e:
            db.rollback()
            omitidos.append({"fila": i, "carnet": fila.nro_carnet, "motivo": e.mensaje})
    return {"creados": creados, "omitidos": omitidos, "total": len(filas)}


def categorias(db: Session):
    return db.query(models.CategoriaUsuario).order_by(models.CategoriaUsuario.codigo).all()
