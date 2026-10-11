# Limpieza PASO 0: borra ventas duplicadas 74-77 (conserva 73) y
# devuelve las 4 unidades de stock del Taladro percutor 650W.
# Todo en UNA transaccion: si algo falla, rollback completo.
from sqlalchemy import text
from db_supabase import engine_tienda

IDS = [74, 75, 76, 77]

conn = engine_tienda.connect()
trans = conn.begin()
try:
    # Stock ANTES
    prod = conn.execute(text("""
        SELECT p.id_producto, p.nombre, p.stock
          FROM producto p
          JOIN detalle_venta d ON d.id_producto = p.id_producto
         WHERE d.id_venta = :id
    """), {"id": IDS[0]}).fetchone()._mapping
    unidades = conn.execute(text("""
        SELECT COALESCE(SUM(cantidad),0) AS u FROM detalle_venta
         WHERE id_venta = ANY(:ids)
    """), {"ids": IDS}).scalar()
    print(f"Producto: {prod['nombre']} (id {prod['id_producto']})")
    print(f"Stock ANTES: {prod['stock']}   unidades a devolver: {unidades}")

    borradas = {}
    # movimiento_caja no tiene id_venta: se referencia por concepto
    patrones = [f"Venta local #{i}" for i in IDS]
    r = conn.execute(text(
        "DELETE FROM movimiento_caja WHERE concepto = ANY(:p) RETURNING id_movimiento_caja"),
        {"p": patrones})
    borradas["movimiento_caja"] = len(r.fetchall())
    for tabla in ("pago", "detalle_venta", "venta"):
        r = conn.execute(
            text(f"DELETE FROM {tabla} WHERE id_venta = ANY(:ids) RETURNING id_venta"),
            {"ids": IDS})
        borradas[tabla] = len(r.fetchall())

    r = conn.execute(text("""
        UPDATE producto SET stock = stock + :u
         WHERE id_producto = :pid RETURNING stock
    """), {"u": int(unidades), "pid": prod["id_producto"]})
    stock_despues = r.scalar()

    trans.commit()
    print("\nFilas borradas por tabla:")
    for t, n in borradas.items():
        print(f"  {t}: {n}")
    print(f"\nStock DESPUES: {stock_despues}")
    assert stock_despues == prod["stock"] + int(unidades), "Stock inesperado!"
    print("OK: transaccion confirmada, stock cuadrado.")
except Exception as e:
    trans.rollback()
    print(f"\nERROR — rollback total, nada quedo a medias: {e}")
    raise
finally:
    conn.close()
