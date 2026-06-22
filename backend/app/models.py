from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Numeric, DateTime, ForeignKey, Text, Date
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.database import Base

class Biblioteca(Base):
    __tablename__ = "bibliotecas"
    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(10), unique=True, nullable=False)
    nombre = Column(String(100), nullable=False)

class CategoriaUsuario(Base):
    __tablename__ = "categorias_usuario"
    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(10), unique=True, nullable=False)
    descripcion = Column(String(50), nullable=False)
    max_prestamos = Column(Integer, nullable=False)
    dias_prestamo = Column(Integer, nullable=False)
    multa_por_dia = Column(Numeric(10, 2), nullable=False)

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nro_carnet = Column(String(50), unique=True, nullable=False, index=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False, unique=True)  # <-- AGREGA ESTA LÍNEA EXACTAMENTE AQUÍ
    categoria_id = Column(Integer, ForeignKey("categorias_usuario.id"))
    saldo_multas = Column(Numeric(10, 2), default=0.00)
    activo = Column(Boolean, default=True)

class RegistroBibliografico(Base):
    __tablename__ = "registros_bibliograficos"
    id = Column(Integer, primary_key=True, index=True)
    isbn = Column(String(20), nullable=True)
    titulo = Column(Text, nullable=False)
    autor = Column(Text, nullable=True)
    marc_json = Column(JSONB, nullable=False)  # Estructura de etiquetas MARC21 variable

class TipoItem(Base):
    __tablename__ = "tipos_item"
    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(10), unique=True, nullable=False, index=True)
    descripcion = Column(String(100), nullable=False)  # <-- AGREGA ESTA LÍNEA EXACTAMENTE AQUÍ
    es_prestable = Column(Boolean, default=True)

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    biblio_id = Column(Integer, ForeignKey("registros_bibliograficos.id", ondelete="CASCADE"))
    codigo_barras = Column(String(50), unique=True, nullable=False, index=True)
    tipo_item_id = Column(Integer, ForeignKey("tipos_item.id"))
    estado = Column(String(20), default="Disponible")  # Disponible, Prestado, Reservado

class Prestamo(Base):
    __tablename__ = "prestamos"
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"))
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    fecha_prestamo = Column(DateTime, default=datetime.utcnow)
    fecha_vencimiento = Column(DateTime, nullable=False)
    fecha_devolucion = Column(DateTime, nullable=True)

class Reserva(Base):
    __tablename__ = "reservas"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    biblio_id = Column(Integer, ForeignKey("registros_bibliograficos.id"))
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    prioridad = Column(Integer, nullable=False)
    estado = Column(String(20), default="Pendiente") # Pendiente, Completada

class Multa(Base):
    __tablename__ = "multas"
    id = Column(Integer, primary_key=True, index=True)
    prestamo_id = Column(Integer, ForeignKey("prestamos.id"))
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    monto = Column(Numeric(10, 2), nullable=False)
    estado_pago = Column(String(20), default="Pendiente")