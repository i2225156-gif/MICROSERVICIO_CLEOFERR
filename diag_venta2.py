# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
from sqlalchemy import text
from db_supabase import engine_tienda

conn = engine_tienda.connect()
try:
    print("tipo_venta:", [dict(r._mapping) for r in conn.execute(text("SELECT * FROM tipo_venta")).fetchall()])
    print("estado_venta:", [dict(r._mapping) for r in conn.execute(text("SELECT * FROM estado_venta")).fetchall()])
    print("detalle 75-77:", [dict(r._mapping) for r in conn.execute(text("SELECT * FROM detalle_venta WHERE id_venta IN (75,76,77)")).fetchall()])
    print("movimientos recientes:", [dict(r._mapping) for r in conn.execute(text("SELECT * FROM movimiento_caja ORDER BY id_movimiento DESC LIMIT 5")).fetchall()])
finally:
    conn.close()
