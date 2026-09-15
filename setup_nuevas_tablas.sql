-- ============================================================
-- CLEOFERR - Script para nuevas tablas: cliente, proveedor, inventario
-- Ejecutar en PhpMyAdmin sobre la BD: tienda_online
-- NOTA: Adaptado para PostgreSQL (Supabase). No usar backticks ni ENGINE/CHARSET de MySQL.
-- ============================================================

-- 1. Asegurarse de que la tabla cliente tenga las columnas necesarias
-- Se asume que la tabla cliente ya existe; solo añadimos columnas si no existen.
ALTER TABLE cliente
    ADD COLUMN IF NOT EXISTS telefono VARCHAR(20),
    ADD COLUMN IF NOT EXISTS direccion VARCHAR(255),
    ADD COLUMN IF NOT EXISTS contrasena VARCHAR(255);

-- 2. Tabla de proveedores
CREATE TABLE IF NOT EXISTS proveedor (
    id_proveedor SERIAL PRIMARY KEY,
    nombre       VARCHAR(150) NOT NULL,
    contacto     VARCHAR(100),
    telefono     VARCHAR(20),
    email        VARCHAR(100),
    direccion    VARCHAR(255),
    creado_en    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Tabla de movimientos de inventario
CREATE TABLE IF NOT EXISTS inventario_movimiento (
    id_movimiento SERIAL PRIMARY KEY,
    tipo         VARCHAR(10) NOT NULL CHECK (tipo IN ('entrada', 'salida')),
    id_producto  INTEGER NOT NULL,
    id_proveedor INTEGER DEFAULT NULL,
    cantidad     INTEGER NOT NULL,
    precio_unitario DECIMAL(10,2) DEFAULT 0.00,
    stock_resultante INTEGER NOT NULL,
    observacion  TEXT DEFAULT NULL,
    id_usuario   INTEGER DEFAULT NULL,
    fecha        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_producto) REFERENCES producto(id_producto) ON DELETE CASCADE,
    FOREIGN KEY (id_proveedor) REFERENCES proveedor(id_proveedor) ON DELETE SET NULL,
    FOREIGN KEY (id_usuario) REFERENCES usuario(id_usuario) ON DELETE SET NULL
);

-- 4. Proveedores de ejemplo
INSERT INTO proveedor (nombre, contacto, telefono, email, direccion)
SELECT * FROM (SELECT 'Ferretería Central SAC' AS nombre, 'Juan Quispe' AS contacto, '987654321' AS telefono, 'jquispe@ferrcentral.pe' AS email, 'Av. Industrial 345, Lima' AS direccion) AS tmp
WHERE NOT EXISTS (SELECT 1 FROM proveedor WHERE nombre = 'Ferretería Central SAC')
UNION ALL
SELECT * FROM (SELECT 'Distribuidora El Constructor' AS nombre, 'María López' AS contacto, '976543210' AS telefono, 'mlopez@elconstructor.pe' AS email, 'Jr. Materiales 123, Lima' AS direccion) AS tmp
WHERE NOT EXISTS (SELECT 1 FROM proveedor WHERE nombre = 'Distribuidora El Constructor')
UNION ALL
SELECT * FROM (SELECT 'Importaciones TecnoFerr' AS nombre, 'Carlos Ramos' AS contacto, '965432109' AS telefono, 'cramos@tecnoferr.pe' AS email, 'Calle Progreso 789, Lima' AS direccion) AS tmp
WHERE NOT EXISTS (SELECT 1 FROM proveedor WHERE nombre = 'Importaciones TecnoFerr');