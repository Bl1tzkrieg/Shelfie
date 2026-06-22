from datetime import datetime
from app.database import SessionLocal, Base, engine
from app import models

# Asegurar que las tablas existan
Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    print("Iniciando inserción de datos reales y transacciones para Shelfie...")

    # 1. Crear una Biblioteca Base
    biblioteca = db.query(models.Biblioteca).filter_by(codigo="BCV").first()
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
            max_prestamos=3,
            dias_prestamo=7,
            multa_por_dia=1.50
        )
        db.add(categoria)
        db.flush()

    # 3. Crear Usuarios de prueba (Manteniendo el tuyo y agregando dos más)
    u1 = db.query(models.Usuario).filter_by(nro_carnet="20260001").first()
    if not u1:
        u1 = models.Usuario(
            nro_carnet="20260001",
            username="douglas.worm",
            password_hash="pbkdf2:sha256...",
            nombre="Douglas",
            apellido="Worm",
            email="douglas.worm@example.com",
            categoria_id=categoria.id,
            saldo_multas=0.00,
            activo=True
        )
        db.add(u1)

    u2 = db.query(models.Usuario).filter_by(nro_carnet="20260002").first()
    if not u2:
        u2 = models.Usuario(
            nro_carnet="20260002",
            username="carlos.mendoza",
            password_hash="pbkdf2:sha256...",
            nombre="Carlos",
            apellido="Mendoza López",
            email="carlos.mendoza@example.com",
            categoria_id=categoria.id,
            saldo_multas=0.00,
            activo=True
        )
        db.add(u2)

    u3 = db.query(models.Usuario).filter_by(nro_carnet="20260003").first()
    if not u3:
        u3 = models.Usuario(
            nro_carnet="20260003",
            username="ana.garcia",
            password_hash="pbkdf2:sha256...",
            nombre="Ana",
            apellido="García Pérez",
            email="ana.garcia@example.com",
            categoria_id=categoria.id,
            saldo_multas=3.00,
            activo=True
        )
        db.add(u3)

    db.flush()  # Guardar usuarios temporalmente para obtener sus IDs

    # 4. Crear Registros Bibliográficos (Manteniendo Cien años de soledad y agregando más)
    libro1 = db.query(models.RegistroBibliografico).filter_by(isbn="9780307474728").first()
    if not libro1:
        libro1 = models.RegistroBibliografico(
            isbn="9780307474728",
            titulo="Cien años de soledad",
            autor="Gabriel García Márquez",
            marc_json={
                "leader": "00000cam a22000001a 4500",
                "fields": [
                    {"020": {"subfields": [{"a": "9780307474728"}]}},
                    {"100": {"subfields": [{"a": "García Márquez, Gabriel"}]}},
                    {"245": {"subfields": [{"a": "Cien años de soledad"}]}}
                ]
            }
        )
        db.add(libro1)

    libro2 = db.query(models.RegistroBibliografico).filter_by(isbn="9781111111111").first()
    if not libro2:
        libro2 = models.RegistroBibliografico(
            isbn="9781111111111",
            titulo="Fisiología Vegetal",
            autor="Lincoln Taiz",
            marc_json={
                "leader": "00000cam a22000001a 4500",
                "fields": [
                    {"020": {"subfields": [{"a": "9781111111111"}]}},
                    {"245": {"subfields": [{"a": "Fisiología Vegetal"}]}}
                ]
            }
        )
        db.add(libro2)

    libro3 = db.query(models.RegistroBibliografico).filter_by(isbn="9782222222222").first()
    if not libro3:
        libro3 = models.RegistroBibliografico(
            isbn="9782222222222",
            titulo="Introducción a la Ciencia del Suelo",
            autor="Nyle C. Brady",
            marc_json={
                "leader": "00000cam a22000001a 4500",
                "fields": [
                    {"020": {"subfields": [{"a": "9782222222222"}]}},
                    {"245": {"subfields": [{"a": "Introducción a la Ciencia del Suelo"}]}}
                ]
            }
        )
        db.add(libro3)

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
            estado="Prestado"  # Douglas lo tiene prestado (Activo)
        )
        db.add(item1)

    item2 = db.query(models.Item).filter_by(codigo_barras="SHELFIE-002").first()
    if not item2:
        item2 = models.Item(
            biblio_id=libro2.id,
            codigo_barras="SHELFIE-002",
            tipo_item_id=tipo_item.id,
            estado="Prestado"  # Carlos lo tiene prestado (Vencido)
        )
        db.add(item2)

    item3 = db.query(models.Item).filter_by(codigo_barras="SHELFIE-003").first()
    if not item3:
        item3 = models.Item(
            biblio_id=libro3.id,
            codigo_barras="SHELFIE-003",
            tipo_item_id=tipo_item.id,
            estado="Disponible"  # Ya fue devuelto por Ana
        )
        db.add(item3)

    db.flush()

    # 7. Crear el historial de Préstamos (Circulación) sincronizado al año 2026
    # Préstamo 1: ACTIVO (Prestado hace poco, vence a futuro)
    p1 = db.query(models.Prestamo).filter_by(item_id=item1.id, fecha_devolucion=None).first()
    if not p1:
        p1 = models.Prestamo(
            item_id=item1.id,
            usuario_id=u1.id,
            fecha_prestamo=datetime(2026, 6, 18),
            fecha_vencimiento=datetime(2026, 6, 25),
            fecha_devolucion=None
        )
        db.add(p1)

    # Préstamo 2: VENCIDO (La fecha de vencimiento ya pasó en el calendario de 2026)
    p2 = db.query(models.Prestamo).filter_by(item_id=item2.id, fecha_devolucion=None).first()
    if not p2:
        p2 = models.Prestamo(
            item_id=item2.id,
            usuario_id=u2.id,
            fecha_prestamo=datetime(2026, 5, 10),
            fecha_vencimiento=datetime(2026, 5, 17),
            fecha_devolucion=None
        )
        db.add(p2)

    # Préstamo 3: HISTORIAL / DEVUELTO (Tiene registrada su fecha de devolución)
    p3 = db.query(models.Prestamo).filter_by(item_id=item3.id).filter(models.Prestamo.fecha_devolucion != None).first()
    if not p3:
        p3 = models.Prestamo(
            item_id=item3.id,
            usuario_id=u3.id,
            fecha_prestamo=datetime(2026, 6, 1),
            fecha_vencimiento=datetime(2026, 6, 8),
            fecha_devolucion=datetime(2026, 6, 6)
        )
        db.add(p3)

    db.commit()
    print("¡Estructura respetada e inserción completada con éxito! Revisa tu frontend.")

except Exception as e:
    db.rollback()
    print(f"Error poblando la base de datos: {e}")
finally:
    db.close()