# -*- coding: utf-8 -*-
"""Confirmar NOT NULL en venta.id_cliente."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
from sqlalchemy import text
from db_supabase import engine_tienda

conn = engine_tienda.connect()
try:
    rows = conn.execute(text("""
        SELECT column_name, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'venta'
        ORDER BY ordinal_position
    """)).fetchall()
    for r in rows:
        print(dict(r._mapping))
finally:
    conn.close()
