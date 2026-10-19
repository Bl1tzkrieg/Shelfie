"""Lectores: alta, edición, suspensión, padrón e importación masiva."""

from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import models
from app.core.errores import ErrorDeNegocio, NoEncontrado, ReglaIncumplida
from app.core.tiempo import ahora
from app.security import hash_password
from app.services import cuentas, registro


def _debe_cambiar(db: Session, u: models.Usuario) -> bool:
    if not u.debe_cambiar_clave:
        return False
    from app.services.autenticacion import tiene_que_cambiar_clave
    return tiene_que_cambiar_clave(db, u)


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
        "debe_cambiar_clave": _debe_cambiar(db, u),
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


def _sede_valida(db: Session, sede_id: Optional[int]) -> Optional[int]:
    if sede_id is not None and not db.get(models.Biblioteca, sede_id):
        raise NoEncontrado("Sede no encontrada")
    return sede_id


def crear(db: Session, datos) -> dict:
    from app.services.autenticacion import validar_clave_nueva

    carnet = datos.nro_carnet.strip()
    email = datos.email.strip().lower()
    if not carnet:
        raise ReglaIncumplida("El carnet no puede quedar vacío")
    if db.query(models.Usuario).filter(models.Usuario.nro_carnet == carnet).first():
        raise ReglaIncumplida(f"Ya existe un usuario con el carnet {carnet}")

    if db.query(models.Usuario).filter(func.lower(models.Usuario.email) == email).first():
        raise ReglaIncumplida("Ese email ya está registrado")

    # Si no se indica username se deriva del carnet, que es único.
    username = (datos.username or "").strip() or f"u{carnet}"
    if db.query(models.Usuario).filter(models.Usuario.username == username).first():
        raise ReglaIncumplida(f"El username '{username}' ya está tomado")

    categoria = db.query(models.CategoriaUsuario).filter(
        models.CategoriaUsuario.codigo == datos.categoria_codigo).first()
    if not categoria:
        raise ReglaIncumplida(f"No existe la categoría de usuario '{datos.categoria_codigo}'")

    usuario = models.Usuario(
        nro_carnet=carnet,
        username=username,
        nombre=datos.nombre.strip(),
        apellido=datos.apellido.strip(),
        email=email,
        departamento=datos.departamento,
        categoria_id=categoria.id,
        biblioteca_id=_sede_valida(db, getattr(datos, "biblioteca_id", None)),
        saldo_multas=0,
        activo=True,
        fecha_creacion=ahora(),
        # La clave la eligió otro (o es el carnet): al entrar se pide una propia.
        debe_cambiar_clave=True,
    )
    if datos.password:
        validar_clave_nueva(usuario, datos.password)
    # Sin contraseña explícita se usa el carnet como clave inicial.
    usuario.password_hash = hash_password(datos.password or carnet)
    db.add(usuario)
    db.flush()
    registro.anotar(db, "lectores", "alta", f"Alta de {registro.nombre(usuario)} ({categoria.descripcion})",
                    lector=usuario, objeto=("usuario", usuario.id))
    db.commit()
    db.refresh(usuario)
    return vista_de_usuario(db, usuario)


_CAMPOS_FICHA = ("nombre", "apellido", "email", "departamento", "biblioteca_id", "categoria_id")


def editar(db: Session, nro_carnet: str, datos) -> dict:
    usuario = obtener_por_carnet(db, nro_carnet)
    antes = {c: getattr(usuario, c) for c in _CAMPOS_FICHA}

    if datos.email and datos.email.lower() != usuario.email.lower():
        if db.query(models.Usuario).filter(
                func.lower(models.Usuario.email) == datos.email.lower()).first():
            raise ReglaIncumplida("Ese email ya está registrado")
        usuario.email = datos.email.strip().lower()

    if datos.nombre:
        usuario.nombre = datos.nombre
    if datos.apellido:
        usuario.apellido = datos.apellido
    if datos.departamento is not None:
        usuario.departamento = datos.departamento
    if "biblioteca_id" in datos.model_fields_set:
        usuario.biblioteca_id = _sede_valida(db, datos.biblioteca_id)

    if datos.categoria_codigo:
        categoria = db.query(models.CategoriaUsuario).filter(
            models.CategoriaUsuario.codigo == datos.categoria_codigo).first()
        if not categoria:
            raise ReglaIncumplida(f"No existe la categoría '{datos.categoria_codigo}'")
        usuario.categoria_id = categoria.id

    cambios = registro.diferencias(antes, {c: getattr(usuario, c) for c in _CAMPOS_FICHA})
    if cambios:
        registro.anotar(db, "lectores", "edicion",
                        f"Cambió {', '.join(cambios)} de {registro.nombre(usuario)}",
                        lector=usuario, objeto=("usuario", usuario.id), datos={"cambios": cambios})
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

    if usuario.activo != activo:
        registro.anotar(db, "lectores", "reactivacion" if activo else "suspension",
                        f"{'Reactivó' if activo else 'Suspendió'} la cuenta de {registro.nombre(usuario)}",
                        lector=usuario, objeto=("usuario", usuario.id))
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
            # El código es lo que lee la importación: así el archivo exportado se reimporta tal cual.
            "categoria_codigo": d["categoria"].codigo if d["categoria"] else "",
            "activo": "Sí" if d["activo"] else "No",
            "saldo_multas": f"{d['saldo_multas']:.2f}",
            "prestamos_activos": d["prestamos_activos_count"],
            "total_prestamos": d["total_prestamos_count"],
        })
    return filas


def _fila_de_importacion(db: Session, crudo: dict, categorias_por_nombre: dict):
    """Valida una fila suelta: un email malo omite esa fila, no rechaza todo el lote."""
    from pydantic import ValidationError

    from app.schemas import NuevoUsuarioRequest
    datos = {k: (v.strip() if isinstance(v, str) else v) for k, v in crudo.items()
             if v not in (None, "")}
    if not datos.get("categoria_codigo") and datos.get("categoria"):
        # El CSV exportado trae la descripción («Estudiante»); también vale el código.
        codigo = categorias_por_nombre.get(str(datos["categoria"]).lower())
        if not codigo:
            raise ReglaIncumplida(f"Categoría desconocida: {datos['categoria']}")
        datos["categoria_codigo"] = codigo
    try:
        return NuevoUsuarioRequest(**{k: v for k, v in datos.items()
                                      if k in NuevoUsuarioRequest.model_fields})
    except ValidationError as error:
        campos = ", ".join(f"{e['loc'][-1]}: {e['msg']}" for e in error.errors())
        raise ReglaIncumplida(f"Datos inválidos ({campos})") from error


def importar(db: Session, filas: list) -> dict:
    """Alta masiva. Informa fila por fila qué se creó y qué se omitió."""
    creados, omitidos = 0, []
    categorias_por_nombre = {}
    for c in db.query(models.CategoriaUsuario).all():
        categorias_por_nombre[c.codigo.lower()] = c.codigo
        categorias_por_nombre[c.descripcion.lower()] = c.codigo
    for i, crudo in enumerate(filas, start=1):
        fila = None
        try:
            fila = (crudo if not isinstance(crudo, dict)
                    else _fila_de_importacion(db, crudo, categorias_por_nombre))
            crear(db, fila)
            creados += 1
        except ErrorDeNegocio as e:
            db.rollback()
            omitidos.append({"fila": i, "carnet": _carnet(fila, crudo), "motivo": e.mensaje})
        except SQLAlchemyError as e:
            # Una carrera o un dato que la base rechaza: se informa esa fila y se sigue.
            db.rollback()
            omitidos.append({"fila": i, "carnet": _carnet(fila, crudo),
                             "motivo": f"La base rechazó la fila ({type(e).__name__})"})
    registro.anotar(db, "lectores", "importacion",
                    f"Importación de lectores: {creados} creados y {len(omitidos)} omitidos "
                    f"de {len(filas)} filas", datos={"omitidos": omitidos[:100]})
    db.commit()
    return {"creados": creados, "omitidos": omitidos, "total": len(filas)}


def _carnet(fila, crudo) -> str:
    if fila is not None:
        return fila.nro_carnet
    return str(crudo.get("nro_carnet") or "") if isinstance(crudo, dict) else ""


def categorias(db: Session):
    return db.query(models.CategoriaUsuario).order_by(models.CategoriaUsuario.codigo).all()
