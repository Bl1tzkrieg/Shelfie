from datetime import timedelta

from app.core.tiempo import ahora
from app.database import SessionLocal
from app import models
from app.security import hash_password
from app.services import cuentas, marc, reglas

# Requiere el esquema creado: ejecutar `alembic upgrade head` antes del seed.

db = SessionLocal()

try:
    print("Iniciando inserción de datos reales y transacciones para Shelfie...")

    # 1. Sede: la migración 0004 ya crea una si la base no tenía ninguna.
    biblioteca = db.query(models.Biblioteca).order_by(models.Biblioteca.id).first()
    if not biblioteca:
        biblioteca = models.Biblioteca(codigo="BCV", nombre="Biblioteca Central de Venezuela")
        db.add(biblioteca)
        db.flush()

    # 2. Crear Categoria de Usuario (Estudiante)
    categoria = db.query(models.CategoriaUsuario).filter_by(codigo="EST").first()
    if not categoria:
        categoria = models.CategoriaUsuario(
            codigo="EST",
            descripcion="Estudiante Pregrado",
        )
        db.add(categoria)
        db.flush()

    # Docentes y personal: settings.py sincroniza sus políticas por código (DOC/ADM),
    # así que deben existir para poder crear lectores de esas categorías.
    for codigo, descripcion in (("DOC", "Docente"), ("ADM", "Personal Administrativo")):
        if not db.query(models.CategoriaUsuario).filter_by(codigo=codigo).first():
            db.add(models.CategoriaUsuario(codigo=codigo, descripcion=descripcion))
    db.flush()

    # Cada categoría con su regla de circulación (días y tope propios).
    for codigo, dias, maximo in (("EST", 7, 3), ("DOC", 30, 10), ("ADM", 14, 5)):
        reglas.asegurar_regla_de_categoria(
            db, db.query(models.CategoriaUsuario).filter_by(codigo=codigo).one(), dias, maximo)

    # 3. Crear Usuarios de prueba (Manteniendo el tuyo y agregando dos más)
    u1 = db.query(models.Usuario).filter_by(nro_carnet="20260001").first()
    if not u1:
        u1 = models.Usuario(
            nro_carnet="20260001",
            username="douglas.worm",
            password_hash=hash_password("20260001"),
            nombre="Douglas",
            apellido="Worm",
            email="douglas.worm@example.com",
            categoria_id=categoria.id,
            departamento="Ingeniería Agronómica",
            saldo_multas=0.00,
            activo=True,
            # Usuario de ejemplo con acceso total a la intranet (clave = carnet).
            es_personal=True,
            permisos=["superbibliotecario"],
        )
        db.add(u1)

    u2 = db.query(models.Usuario).filter_by(nro_carnet="20260002").first()
    if not u2:
        u2 = models.Usuario(
            nro_carnet="20260002",
            username="carlos.mendoza",
            password_hash=hash_password("20260002"),
            nombre="Carlos",
            apellido="Mendoza López",
            email="carlos.mendoza@example.com",
            categoria_id=categoria.id,
            departamento="Ingeniería Agronómica",
            saldo_multas=0.00,
            activo=True
        )
        db.add(u2)

    u3 = db.query(models.Usuario).filter_by(nro_carnet="20260003").first()
    if not u3:
        u3 = models.Usuario(
            nro_carnet="20260003",
            username="ana.garcia",
            password_hash=hash_password("20260003"),
            nombre="Ana",
            apellido="García Pérez",
            email="ana.garcia@example.com",
            categoria_id=categoria.id,
            departamento="Ingeniería Agronómica",
            saldo_multas=0,
            activo=True
        )
        db.add(u3)

    db.flush()  # Guardar usuarios temporalmente para obtener sus IDs

    # Ana arrastra una multa de ejemplo: se registra en su cuenta, no a mano en el saldo.
    if not db.query(models.MovimientoCuenta).filter_by(usuario_id=u3.id).first():
        cuentas.registrar(db, u3, "MULTA_ATRASO", 3.00, descripcion="Multa de ejemplo del seed")

    # 4. Registros bibliográficos: el MARC es la fuente y las columnas se derivan de él.
    def registro(isbn, titulo, autor, ano, materia):
        existente = db.query(models.RegistroBibliografico).filter_by(isbn=isbn).first()
        if existente:
            return existente
        crudo = marc.desde_columnas(titulo, autor, isbn, ano, materia)
        canonico, _plantilla = marc.preparar(crudo, "BKS")
        nuevo = models.RegistroBibliografico(marc_json=canonico, plantilla="BKS",
                                             **marc.derivar(canonico))
        db.add(nuevo)
        return nuevo

    libro1 = registro("9780307474728", "Cien años de soledad", "García Márquez, Gabriel",
                      1967, "Literatura")
    libro2 = registro("9781111111111", "Fisiología vegetal", "Taiz, Lincoln", 2010, "Fitotecnia")
    libro3 = registro("9782222222222", "Introducción a la ciencia del suelo", "Brady, Nyle C.",
                      2008, "Ciencias del Suelo")

    db.flush()

    # 5. Tipo de Ítem
    tipo_item = db.query(models.TipoItem).filter_by(codigo="LIB").first()
    if not tipo_item:
        tipo_item = models.TipoItem(
            codigo="LIB",
            descripcion="Libros en papel / Monografías",
            es_prestable=True
        )
        db.add(tipo_item)
        db.flush()

    # 6. Crear los ejemplares físicos (Items) asignándoles estados reales
    item1 = db.query(models.Item).filter_by(codigo_barras="SHELFIE-001").first()
    if not item1:
        item1 = models.Item(
            biblio_id=libro1.id,
            codigo_barras="SHELFIE-001",
            tipo_item_id=tipo_item.id,
            signatura_topografica="PQ8180.17.A73",
            biblioteca_propia_id=biblioteca.id,
            biblioteca_actual_id=biblioteca.id,
            estado="Prestado"  # Douglas lo tiene prestado (Activo)
        )
        db.add(item1)

    item2 = db.query(models.Item).filter_by(codigo_barras="SHELFIE-002").first()
    if not item2:
        item2 = models.Item(
            biblio_id=libro2.id,
            codigo_barras="SHELFIE-002",
            tipo_item_id=tipo_item.id,
            signatura_topografica="QK711.2 T35",
            biblioteca_propia_id=biblioteca.id,
            biblioteca_actual_id=biblioteca.id,
            estado="Prestado"  # Carlos lo tiene prestado (Vencido)
        )
        db.add(item2)

    item3 = db.query(models.Item).filter_by(codigo_barras="SHELFIE-003").first()
    if not item3:
        item3 = models.Item(
            biblio_id=libro3.id,
            codigo_barras="SHELFIE-003",
            tipo_item_id=tipo_item.id,
            signatura_topografica="S591 B73",
            biblioteca_propia_id=biblioteca.id,
            biblioteca_actual_id=biblioteca.id,
            estado="Disponible"  # Ya fue devuelto por Ana
        )
        db.add(item3)

    db.flush()

    # 7. Historial de préstamos con fechas relativas a hoy, para que el estado
    #    (activo / vencido / devuelto) sea el mismo sin importar cuándo se siembre.
    hoy = ahora()
    # Préstamo 1: ACTIVO (Prestado hace poco, vence a futuro)
    p1 = db.query(models.Prestamo).filter_by(item_id=item1.id, fecha_devolucion=None).first()
    if not p1:
        p1 = models.Prestamo(
            item_id=item1.id,
            usuario_id=u1.id,
            fecha_prestamo=hoy - timedelta(days=2),
            fecha_vencimiento=hoy + timedelta(days=5),
            fecha_devolucion=None
        )
        db.add(p1)

    # Préstamo 2: VENCIDO (venció hace casi dos semanas)
    p2 = db.query(models.Prestamo).filter_by(item_id=item2.id, fecha_devolucion=None).first()
    if not p2:
        p2 = models.Prestamo(
            item_id=item2.id,
            usuario_id=u2.id,
            fecha_prestamo=hoy - timedelta(days=20),
            fecha_vencimiento=hoy - timedelta(days=13),
            fecha_devolucion=None
        )
        db.add(p2)

    # Préstamo 3: HISTORIAL / DEVUELTO (Tiene registrada su fecha de devolución)
    p3 = db.query(models.Prestamo).filter_by(item_id=item3.id).filter(models.Prestamo.fecha_devolucion != None).first()
    if not p3:
        p3 = models.Prestamo(
            item_id=item3.id,
            usuario_id=u3.id,
            fecha_prestamo=hoy - timedelta(days=30),
            fecha_vencimiento=hoy - timedelta(days=23),
            fecha_devolucion=hoy - timedelta(days=25)
        )
        db.add(p3)

    db.commit()
    print("¡Estructura respetada e inserción completada con éxito! Revisa tu frontend.")
    print("Intranet de ejemplo: usuario 'douglas.worm', clave '20260001' (superbibliotecario).")

except Exception as e:
    db.rollback()
    print(f"Error poblando la base de datos: {e}")
finally:
    db.close()
