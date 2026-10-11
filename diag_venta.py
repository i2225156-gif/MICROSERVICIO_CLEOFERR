# -*- coding: utf-8 -*-
"""Verificar última venta registrada."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
from sqlalchemy import text
from db_supabase import engine_tienda

conn = engine_tienda.connect()
try:
    for r in conn.execute(text("SELECT * FROM venta ORDER BY id_venta DESC LIMIT 3")).fetchall():
        print(dict(r._mapping))
    print("--- pagos recientes ---")
    for r in conn.execute(text("SELECT * FROM pago ORDER BY id_pago DESC LIMIT 3")).fetchall():
        print(dict(r._mapping))
finally:
    conn.close()
