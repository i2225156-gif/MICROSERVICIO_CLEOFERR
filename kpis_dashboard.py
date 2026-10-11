from dotenv import load_dotenv
load_dotenv()
from sqlalchemy import text
from db_supabase import engine_tienda, engine_auth
import requests, time, json
from datetime import datetime

resultado = {"generado_en": datetime.now().isoformat(), "categorias": {}}

# --- KPIs tecnicos (disponibilidad / cobertura) ---
s = requests.Session()
s.post("http://127.0.0.1:5001/login",
       data={"correo": "admin@cleoferr.com", "clave": "Admin123!"},
       allow_redirects=False)
rutas = ["/productos", "/pedidos", "/inventario", "/caja", "/alertas",
         "/proveedores", "/reportes", "/ventas/nueva", "/clientes"]
latencias = {}
caidas = 0
for ruta in rutas:
    t0 = time.time()
    try:
        r = s.get(f"http://127.0.0.1:5002{ruta}", timeout=5)
        ms = (time.time() - t0) * 1000
        latencias[ruta] = {"status": r.status_code, "ms": round(ms, 1)}
        if r.status_code >= 500:
            caidas += 1
    except Exception as e:
        latencias[ruta] = {"status": "ERROR", "detalle": str(e)}
        caidas += 1
ms_validos = [v["ms"] for v in latencias.values() if "ms" in v]
resultado["categorias"]["disponibilidad"] = {
    "rutas_probadas": len(rutas),
    "caidas": caidas,
    "disponibilidad_pct": round((len(rutas) - caidas) / len(rutas) * 100, 1),
    "latencia_promedio_ms": round(sum(ms_validos) / max(1, len(ms_validos)), 1),
    "detalle": latencias,
}

# --- KPIs de negocio (ventas), inventario y operacion (BD tienda) ---
with engine_tienda.connect() as conn:
    resultado["categorias"]["ventas"] = {
        "total_historico": conn.execute(text("SELECT COUNT(*) FROM venta")).scalar(),
        "ventas_hoy": conn.execute(text(
            "SELECT COUNT(*) FROM venta WHERE DATE(fecha AT TIME ZONE 'UTC' AT TIME ZONE 'America/Lima') = CURRENT_DATE")).scalar(),
        "ingresos_hoy": float(conn.execute(text("""
            SELECT COALESCE(SUM(d.cantidad*d.precio_unitario),0)
            FROM venta v JOIN detalle_venta d ON d.id_venta = v.id_venta
            WHERE DATE(v.fecha AT TIME ZONE 'UTC' AT TIME ZONE 'America/Lima') = CURRENT_DATE
        """)).scalar()),
        "ticket_promedio": round(float(conn.execute(text(
            "SELECT COALESCE(AVG(t.total),0) FROM (SELECT v.id_venta, SUM(d.cantidad*d.precio_unitario) AS total FROM venta v JOIN detalle_venta d ON d.id_venta = v.id_venta GROUP BY v.id_venta) t"
        )).scalar()), 2),
        "pedidos_pendientes": conn.execute(text(
            "SELECT COUNT(*) FROM venta v JOIN estado_venta ev ON v.id_estado_venta = ev.id_estado_venta WHERE ev.nombre = 'pendiente'")).scalar(),
    }
    resultado["categorias"]["inventario"] = {
        "stock_total_unidades": conn.execute(text(
            "SELECT COALESCE(SUM(stock),0) FROM producto WHERE activo = TRUE")).scalar(),
        "productos_activos": conn.execute(text(
            "SELECT COUNT(*) FROM producto WHERE activo = TRUE")).scalar(),
        "productos_bajo_stock": conn.execute(text(
            "SELECT COUNT(*) FROM producto WHERE activo = TRUE AND stock <= 5")).scalar(),
        "productos_sin_stock": conn.execute(text(
            "SELECT COUNT(*) FROM producto WHERE activo = TRUE AND stock = 0")).scalar(),
    }
    resultado["categorias"]["operacion"] = {
        "alertas_sin_resolver": conn.execute(text(
            "SELECT COUNT(*) FROM alerta WHERE resuelta = FALSE")).scalar(),
        "cajas_abiertas": conn.execute(text(
            "SELECT COUNT(*) FROM caja WHERE estado = 'abierta'")).scalar(),
    }

# --- KPIs de clientes (BD auth) ---
with engine_auth.connect() as conn_a:
    resultado["categorias"]["clientes"] = {
        "clientes_activos": conn_a.execute(text(
            "SELECT COUNT(*) FROM cliente WHERE activo = TRUE")).scalar(),
    }

print(json.dumps(resultado, indent=2, ensure_ascii=False))
with open("kpis_dashboard.json", "w", encoding="utf-8") as f:
    json.dump(resultado, f, indent=2, ensure_ascii=False)
print("\nGuardado en kpis_dashboard.json")
