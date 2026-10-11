# -*- coding: utf-8 -*-
"""Diagnóstico: cajas abiertas en la BD de tienda."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from sqlalchemy import text
from db_supabase import engine_tienda

conn = engine_tienda.connect()
try:
    rows = conn.execute(text("SELECT * FROM caja ORDER BY id_caja DESC LIMIT 5")).fetchall()
    print("columnas:", list(rows[0]._mapping.keys()) if rows else "(sin filas)")
    for r in rows:
        print(dict(r._mapping))
finally:
    conn.close()
