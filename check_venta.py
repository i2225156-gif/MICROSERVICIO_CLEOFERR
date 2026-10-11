from dotenv import load_dotenv
load_dotenv()
from sqlalchemy import text
from db_supabase import engine_tienda, engine_auth

with engine_tienda.connect() as conn:
    row = conn.execute(text(
        "SELECT id_venta, id_cliente, id_usuario_vendedor, id_tipo_venta FROM venta WHERE id_venta = 58"
    )).fetchone()
    print("VENTA:", row)

with engine_auth.connect() as conn_a:
    clientes = conn_a.execute(text(
        "SELECT id_cliente, nombre, email FROM cliente"
    )).fetchall()
    print("CLIENTES (tabla auth):")
    for c in clientes:
        print(" ", c)
