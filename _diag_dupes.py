# Diagnostico: ventas posiblemente duplicadas por reintento (BUG 5).
# SOLO LECTURA. Lista ventas del dia con mismo cliente + mismo monto total,
# separadas por pocos segundos/minutos.
from sqlalchemy import text
from db_supabase import engine_tienda

conn = engine_tienda.connect()
rows = conn.execute(text("""
    SELECT v.id_venta, v.fecha, v.id_cliente, v.id_tipo_venta,
           (SELECT SUM(d.cantidad * d.precio_unitario)
              FROM detalle_venta d WHERE d.id_venta = v.id_venta) AS monto,
           (SELECT string_agg(p.nombre || ' x' || d.cantidad, ', ')
              FROM detalle_venta d
              JOIN producto p ON p.id_producto = d.id_producto
             WHERE d.id_venta = v.id_venta) AS productos
      FROM venta v
     WHERE v.fecha::date = CURRENT_DATE
     ORDER BY v.fecha
""")).fetchall()
conn.close()

print(f"{'id':>4} | {'fecha':<19} | cli | tipo | {'monto':>8} | productos")
grupos = {}
for r in rows:
    m = r._mapping
    print(f"{m['id_venta']:>4} | {m['fecha']:%Y-%m-%d %H:%M:%S} | "
          f"{str(m['id_cliente']):>3} | {m['id_tipo_venta']:>4} | "
          f"{(float(m['monto']) if m['monto'] is not None else 0):>8.2f} | {m['productos']}")
    clave = (m['id_cliente'], m['id_tipo_venta'], m['monto'], m['productos'])
    grupos.setdefault(clave, []).append((m['id_venta'], m['fecha']))

print("\n--- Posibles duplicados (mismo cliente+tipo+monto+productos) ---")
hay = False
for clave, ventas in grupos.items():
    if len(ventas) > 1:
        hay = True
        ids = [v[0] for v in ventas]
        fechas = [f"{v[1]:%H:%M:%S}" for v in ventas]
        deltas = [(ventas[i+1][1] - ventas[i][1]).total_seconds()
                  for i in range(len(ventas)-1)]
        print(f"  ids={ids}  horas={fechas}  deltas_seg={deltas}  "
              f"monto={clave[2]}  productos={clave[3]}")
        print(f"    -> candidato a conservar: {ids[0]} ; a borrar: {ids[1:]}")
if not hay:
    print("  (ninguno)")
