# -*- coding: utf-8 -*-
"""Fix 1: permitir id_cliente NULL en venta (coherente con monolito/microservicio)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
from sqlalchemy import text
from db_supabase import engine_tienda

conn = engine_tienda.connect()
try:
    conn.execute(text("ALTER TABLE venta ALTER COLUMN id_cliente DROP NOT NULL"))
    conn.commit()
    chk = conn.execute(text("""
        SELECT is_nullable FROM information_schema.columns
        WHERE table_name = 'venta' AND column_name = 'id_cliente'
    """)).fetchone()
    print("venta.id_cliente is_nullable ahora:", chk._mapping["is_nullable"])
finally:
    conn.close()
