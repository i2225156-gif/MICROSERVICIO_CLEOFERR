-- ============================================================
-- CLEOFERR – Tablas para flujo de pago completo
-- Ejecutar en el SQL Editor de Supabase (PostgreSQL)
-- Adaptado de la versión MySQL: sin backticks, sin ENGINE/CHARSET,
-- SERIAL en lugar de AUTO_INCREMENT, COALESCE en lugar de IFNULL,
-- ON CONFLICT en lugar de ON DUPLICATE KEY UPDATE.
-- ============================================================

-- 1. Agregar columnas a venta si no existen
ALTER TABLE venta
    ADD COLUMN IF NOT EXISTS metodo_pago VARCHAR(20),
    ADD COLUMN IF NOT EXISTS num_operacion VARCHAR(60);

-- 2. Tabla comprobante (si no existe)
CREATE TABLE IF NOT EXISTS comprobante (
    id_comprobante SERIAL PRIMARY KEY,
    id_venta       INTEGER DEFAULT NULL,
    tipo           VARCHAR(20) DEFAULT 'boleta',
    tipo_boleta    VARCHAR(20) DEFAULT 'simple',
    ruc_cliente    VARCHAR(11),
    numero         VARCHAR(30),
    enviado_correo INTEGER DEFAULT 0,
    fecha_emision  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    serie          VARCHAR(4),
    estado_sunat   VARCHAR(20) DEFAULT 'no_aplica'
);

-- 3. Agregar valores al ENUM de venta usando una tabla auxiliar
-- PostgreSQL no tiene ALTER COLUMN ... TYPE ENUM directamente como MySQL.
-- La tabla venta ya debe tener una columna 'estado' de tipo VARCHAR(20)
-- o se crea como nuevo ENUM si no existe. Si la columna ya existe, actualizamos los valores.
-- Ejemplo: si estado es VARCHAR, actualizamos los valores permitidos en la aplicación.
-- Si se necesita crear el tipo ENUM, descomentar y ejecutar:

-- DO $$
-- BEGIN
--     IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'venta_estado_enum') THEN
--         CREATE TYPE venta_estado_enum AS ENUM('pendiente','confirmado','preparando','listo','entregado','cancelado');
--     END IF;
--     ALTER TABLE venta ALTER COLUMN tipo_venta TYPE venta_estado_enum USING tipo_venta::venta_estado_enum;
-- END
-- $$;

-- 4. Comprobantes de prueba (fase de prueba, sin integración SUNAT real)
--    - serie: B001 (boleta) | F001 (factura), mismo patrón de numeración
--      del flujo existente.
--    - estado_sunat: 'no_aplica' = comprobante interno de prueba; cuando se
--      conecte un PSE (Nubefact/Facturador SUNAT) pasará a 'pendiente'/'enviado'.
INSERT INTO comprobante (id_venta, tipo, tipo_boleta, ruc_cliente, numero, serie, estado_sunat, enviado_correo)
SELECT * FROM (SELECT v.id_venta, 'boleta' AS tipo, 'simple' AS tipo_boleta, NULL AS ruc_cliente, 
       'B' || LPAD(CAST(v.id_venta AS TEXT), 6, '0') || '-' || SUBSTRING(MD5(RANDOM()::TEXT), 1, 4) AS numero,
       'B001' AS serie, 'no_aplica' AS estado_sunat, 0 AS enviado_correo
       FROM venta v LIMIT 3) AS tmp
WHERE NOT EXISTS (SELECT 1 FROM comprobante LIMIT 1);