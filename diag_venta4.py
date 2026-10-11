# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
from sqlalchemy import text
from db_supabase import engine_tienda

conn = engine_tienda.connect()
try:
    print("ultima venta:")
    for r in conn.execute(text("SELECT id_venta, id_tipo_venta, id_cliente, id_usuario_vendedor, id_estado_venta FROM venta ORDER BY id_venta DESC LIMIT 2")).fetchall():
        print(dict(r._mapping))
    print("ultimo pago:")
    for r in conn.execute(text("SELECT * FROM pago ORDER BY id_pago DESC LIMIT 2")).fetchall():
        print(dict(r._mapping))
    print("ultimos movimientos_caja:")
    for r in conn.execute(text("SELECT * FROM movimiento_caja ORDER BY id_movimiento_caja DESC LIMIT 4")).fetchall():
        print(dict(r._mapping))
    print("caja 22:")
    print(dict(conn.execute(text("SELECT id_caja, estado, monto_cierre_sistema, monto_cierre_declarado, diferencia FROM caja WHERE id_caja = 22")).fetchone()._mapping))
    abiertas = conn.execute(text("SELECT COUNT(*) AS n FROM caja WHERE estado = 'abierta'")).fetchone()
    print("cajas abiertas restantes:", abiertas._mapping["n"])
finally:
    conn.close()
