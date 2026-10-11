from dotenv import load_dotenv
load_dotenv()
from sqlalchemy import text
from db_supabase import engine_tienda

with engine_tienda.connect() as conn:
    rows = conn.execute(text("""
        SELECT v.id_venta AS id_pedido, ev.nombre AS estado,
               COALESCE(SUM(d.cantidad * d.precio_unitario), 0) AS total
        FROM venta v
        LEFT JOIN estado_venta ev ON v.id_estado_venta = ev.id_estado_venta
        LEFT JOIN detalle_venta d ON d.id_venta = v.id_venta
        WHERE v.id_cliente = :idc
        GROUP BY v.id_venta, ev.nombre
        ORDER BY v.id_venta DESC
    """), {"idc": 11}).fetchall()
    print("rows cliente 11:", rows)
