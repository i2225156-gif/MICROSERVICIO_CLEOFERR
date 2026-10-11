from sqlalchemy import text
from dotenv import load_dotenv
load_dotenv()
from db_supabase import engine_tienda

with engine_tienda.connect() as conn:
    conn.execute(text(
        "UPDATE producto SET stock = 50 WHERE nombre ILIKE :n"
    ), {"n": "%Taladro percutor%"})
    conn.commit()
    row = conn.execute(text(
        "SELECT id_producto, nombre, stock FROM producto WHERE nombre ILIKE :n"
    ), {"n": "%Taladro percutor%"}).fetchone()
    print(row)
