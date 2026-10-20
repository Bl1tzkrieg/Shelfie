from app.database import SessionLocal
from app import models
from app.core.signaturas import normalizar_cota
from app.security import hash_password
from app.services import marc

# Requiere el esquema creado: ejecutar `alembic upgrade head` antes del seed.

db = SessionLocal()

try:
    print("Iniciando inserción de datos de ejemplo para Shelfie-lite...")

    # 1. Personal de ejemplo: un administrador y un catalogador (clave = usuario).
    for username, nombre, apellido, permisos in (
            ("douglas.worm", "Douglas", "Worm", ["superbibliotecario"]),
            ("ana.garcia", "Ana", "García Pérez", ["catalogo"])):
        if not db.query(models.Usuario).filter_by(username=username).first():
            db.add(models.Usuario(username=username, password_hash=hash_password(username),
                                  nombre=nombre, apellido=apellido,
                                  email=f"{username}@example.com", permisos=permisos))
    db.flush()

    # 2. Registros bibliográficos: el MARC es la fuente y las columnas se derivan de él.
    def registro(isbn, titulo, autor, ano, materia, cota):
        existente = db.query(models.RegistroBibliografico).filter_by(isbn=isbn).first()
        if existente:
            return existente
        crudo = marc.desde_columnas(titulo, autor, isbn, ano, materia)
        canonico, _plantilla = marc.preparar(crudo, "BKS")
        nuevo = models.RegistroBibliografico(marc_json=canonico, plantilla="BKS",
                                             cota=normalizar_cota(cota),
                                             **marc.derivar(canonico))
        db.add(nuevo)
        db.flush()
        return nuevo

    libros = [
        (registro("9780307474728", "Cien años de soledad", "García Márquez, Gabriel",
                  1967, "Literatura", "863 G16"), "SHELFIE-001"),
        (registro("9781111111111", "Fisiología vegetal", "Taiz, Lincoln", 2010, "Fitotecnia",
                  "571.2 T35"), "SHELFIE-002"),
        (registro("9782222222222", "Introducción a la ciencia del suelo", "Brady, Nyle C.",
                  2008, "Ciencias del Suelo", "631.4 B73"), "SHELFIE-003"),
    ]

    # 3. Un ejemplar de cada uno.
    for libro, codigo in libros:
        if not db.query(models.Item).filter_by(codigo_barras=codigo).first():
            db.add(models.Item(biblio_id=libro.id, codigo_barras=codigo,
                               signatura_topografica=libro.cota, numero_copia="c.1"))

    db.commit()
    print("¡Inserción completada con éxito!")
    print("Intranet de ejemplo: usuario 'douglas.worm' (administrador) y 'ana.garcia' "
          "(catalogador); la clave es el mismo usuario.")

except Exception as e:
    db.rollback()
    print(f"Error poblando la base de datos: {e}")
finally:
    db.close()
