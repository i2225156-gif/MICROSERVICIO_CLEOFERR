from sqlalchemy import text
from db_supabase import engine_tienda
c = engine_tienda.connect()
for t in ("movimiento_caja", "pago", "detalle_venta", "venta"):
    cols = [r[0] for r in c.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_name=:t"),
        {"t": t})]
    print(t, "->", cols)
c.close()
