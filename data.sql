-- Habilitar extensión para UUIDs si es necesario
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==========================================
-- MÓDULO CORE / USUARIOS Y BIBLIOTECAS
-- ==========================================

CREATE TABLE bibliotecas (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(10) UNIQUE NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    direccion TEXT,
    telefono VARCHAR(20)
);

CREATE TABLE categorias_usuario (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(10) UNIQUE NOT NULL, -- e.g., 'EST' (Estudiante), 'DOC' (Docente)
    descripcion VARCHAR(50) NOT NULL,
    max_prestamos INT NOT NULL,
    dias_prestamo INT NOT NULL,
    multa_por_dia NUMERIC(10, 2) NOT NULL
);

CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    nro_carnet VARCHAR(50) UNIQUE NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    apellido VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    categoria_id INT REFERENCES categorias_usuario(id),
    biblioteca_origen_id INT REFERENCES bibliotecas(id),
    activo BOOLEAN DEFAULT TRUE,
    saldo_multas NUMERIC(10, 2) DEFAULT 0.00,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- MÓDULO DE CATALOGACIÓN Y EJEMPLARES
-- ==========================================

CREATE TABLE registros_bibliograficos (
    id SERIAL PRIMARY KEY,
    isbn VARCHAR(20),
    issn VARCHAR(20),
    titulo TEXT NOT NULL,
    autor TEXT,
    -- Estructura MARC21 mapeada a JSONB para flexibilidad total de etiquetas (001-999) y subcampos ($a, $b)
    marc_json JSONB NOT NULL, 
    fecha_insercion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ultima_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tipos_item (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(10) UNIQUE NOT NULL, -- e.g., 'LIB', 'REV', 'CD'
    descripcion VARCHAR(50) NOT NULL,
    es_prestable BOOLEAN DEFAULT TRUE
);

CREATE TABLE items (
    id SERIAL PRIMARY KEY,
    biblio_id INT REFERENCES registros_bibliograficos(id) ON DELETE CASCADE,
    codigo_barras VARCHAR(50) UNIQUE NOT NULL,
    biblioteca_actual_id INT REFERENCES bibliotecas(id),
    biblioteca_origen_id INT REFERENCES bibliotecas(id),
    tipo_item_id INT REFERENCES tipos_item(id),
    signatura_topografica VARCHAR(100), -- Clasificación Dewey/LC para estanterías
    estado VARCHAR(20) DEFAULT 'Disponible', -- 'Disponible', 'Prestado', 'Reservado', 'Dañado', 'Perdido'
    precio_reposicion NUMERIC(10, 2)
);

-- ==========================================
-- MÓDULO DE CIRCULACIÓN (PRÉSTAMOS Y RESERVAS)
-- ==========================================

CREATE TABLE prestamos (
    id SERIAL PRIMARY KEY,
    item_id INT REFERENCES items(id),
    usuario_id INT REFERENCES usuarios(id),
    fecha_prestamo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_vencimiento TIMESTAMP NOT NULL,
    fecha_devolucion TIMESTAMP,
    renovaciones_realizadas INT DEFAULT 0,
    biblioteca_prestamo_id INT REFERENCES bibliotecas(id)
);

CREATE TABLE reservas (
    id SERIAL PRIMARY KEY,
    biblio_id INT REFERENCES registros_bibliograficos(id),
    usuario_id INT REFERENCES usuarios(id),
    fecha_reserva TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_expiracion TIMESTAMP, -- Cuánto tiempo espera la reserva antes de cancelarse
    prioridad INT NOT NULL,      -- Cola de espera (1, 2, 3...)
    estado VARCHAR(20) DEFAULT 'Pendiente' -- 'Pendiente', 'Disponible', 'Completada', 'Cancelada'
);

CREATE TABLE multas (
    id SERIAL PRIMARY KEY,
    prestamo_id INT REFERENCES prestamos(id),
    usuario_id INT REFERENCES usuarios(id),
    monto NUMERIC(10, 2) NOT NULL,
    estado_pago VARCHAR(20) DEFAULT 'Pendiente', -- 'Pendiente', 'Pagado'
    fecha_emision TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- MÓDULO DE ADQUISICIONES
-- ==========================================

CREATE TABLE proveedores (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    contacto_nombre VARCHAR(100),
    email VARCHAR(100),
    telefono VARCHAR(30),
    activo BOOLEAN DEFAULT TRUE
);

CREATE TABLE presupuestos (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE NOT NULL,
    monto_total NUMERIC(12, 2) NOT NULL
);

CREATE TABLE fondos (
    id SERIAL PRIMARY KEY,
    presupuesto_id INT REFERENCES presupuestos(id),
    codigo VARCHAR(20) UNIQUE NOT NULL, -- e.g., 'CIENCIAS-2026'
    monto_asignado NUMERIC(12, 2) NOT NULL,
    monto_gastado NUMERIC(12, 2) DEFAULT 0.00,
    monto_comprometido NUMERIC(12, 2) DEFAULT 0.00
);

CREATE TABLE ordenes_compra (
    id SERIAL PRIMARY KEY,
    proveedor_id INT REFERENCES proveedores(id),
    estado VARCHAR(20) DEFAULT 'Abierta', -- 'Abierta', 'Enviada', 'Cerrada', 'Cancelada'
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE lineas_orden (
    id SERIAL PRIMARY KEY,
    orden_id INT REFERENCES ordenes_compra(id) ON DELETE CASCADE,
    fondo_id INT REFERENCES fondos(id),
    -- Título temporal o definitivo (si ya existe registro bibliográfico previo)
    titulo_sugerido TEXT NOT NULL,
    biblio_id_provisional INT REFERENCES registros_bibliograficos(id), 
    cantidad INT NOT NULL,
    precio_estimado NUMERIC(10, 2) NOT NULL,
    recibido INT DEFAULT 0,
    estado VARCHAR(20) DEFAULT 'Pendiente' -- 'Pendiente', 'Parcial', 'Recibido', 'Cancelado'
);

-- ==========================================
-- MÓDULO DE CONTROL DE SERIALES
-- ==========================================

CREATE TABLE suscripciones_seriales (
    id SERIAL PRIMARY KEY,
    biblio_id INT REFERENCES registros_bibliograficos(id),
    proveedor_id INT REFERENCES proveedores(id),
    fondo_id INT REFERENCES fondos(id),
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE,
    frecuencia VARCHAR(30) NOT NULL, -- 'Mensual', 'Semanal', 'Bimensual'
    -- Patrón predictivo estructurado (e.g., {"frecuencia_dias": 30, "numeracion_formato": "Vol %V, No %N"})
    patron_prediccion JSONB NOT NULL, 
    estado VARCHAR(20) DEFAULT 'Activa' -- 'Activa', 'Expirada', 'Cancelada'
);

CREATE TABLE ejemplares_seriales (
    id SERIAL PRIMARY KEY,
    suscripcion_id INT REFERENCES suscripciones_seriales(id) ON DELETE CASCADE,
    item_id INT REFERENCES items(id), -- Enlazado si ya fue físicamente procesado en inventario
    numero_edicion VARCHAR(50) NOT NULL, -- e.g., "Vol 12, No 4"
    fecha_esperada DATE NOT NULL,
    fecha_recibida DATE,
    estado VARCHAR(20) DEFAULT 'Esperado' -- 'Esperado', 'Recibido', 'Atrasado', 'Faltante'
);

-- Índices avanzados para optimización de búsquedas JSONB y operaciones frecuentes
CREATE INDEX idx_marc_jsonb ON registros_bibliograficos USING gin (marc_json);
CREATE INDEX idx_usuarios_carnet ON usuarios(nro_carnet);
CREATE INDEX idx_items_codigo_barras ON items(codigo_barras);