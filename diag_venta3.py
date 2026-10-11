# -*- coding: utf-8 -*-
"""Verificar últimas ventas, pagos y movimientos de caja."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
from sqlalchemy import text
from db_supabase import engine_tienda

conn = engine_tienda.connect()
try:
    print("--- ventas recientes ---")
    for r in conn.execute(text("SELECT id_venta, fecha, id_tipo_venta, id_cliente, id_usuario_vendedor, id_estado_venta FROM venta ORDER BY id_venta DESC LIMIT 3")).fetchall():
        print(dict(r._mapping))
    print("--- pagos recientes ---")
    for r in conn.execute(text("SELECT * FROM pago ORDER BY id_pago DESC LIMIT 3")).fetchall():
        print(dict(r._mapping))
    print("--- columnas movimiento_caja ---")
    print([dict(r._mapping) for r in conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='movimiento_caja' ORDER BY ordinal_position")).fetchall()])
finally:
    conn.close()
