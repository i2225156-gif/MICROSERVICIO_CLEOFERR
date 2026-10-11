# Prueba E2E del dashboard de reportes: carga inicial HTML + generar con rango.
import urllib.request, urllib.error, http.cookiejar, json
from dotenv import load_dotenv
load_dotenv()

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj),
                                     urllib.request.HTTPRedirectHandler())

base_auth = "http://127.0.0.1:5001"
base_t = "http://127.0.0.1:5002"

def req(url, data=None, headers=None, method=None):
    r = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        resp = opener.open(r)
        return resp.status, resp.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")

# login admin (form nativo -> setea cookie jwt_token)
s, b = req(base_auth + "/login",
           urllib.parse.urlencode({"correo": "admin@cleoferr.com", "clave": "Admin123!"}).encode(),
           {"Content-Type": "application/x-www-form-urlencoded"}, "POST")
print("login:", s)

# 1) GET /reportes (carga inicial, HTML completo)
s, b = req(base_t + "/reportes")
es_html = "<html" in b.lower() or "<!doctype" in b.lower()
tiene_kpis = all(x in b for x in ["RESUMEN DE HOY", "VENTAS", "INVENTARIO",
                                  "CLIENTES Y REGISTROS",
                                  "Ventas totales", "Ganancia (margen)",
                                  "Venta promedio por cliente"])
print(f"[1] GET /reportes: status={s} HTML={es_html} KPIs_visibles={tiene_kpis}")

# 2) GET /reportes/generar con rango (recalcula KPIs + tabla)
s, b = req(base_t + "/reportes/generar?tipo=ventas&desde=2026-09-01&hasta=2026-09-25")
es_html = "<html" in b.lower() or "<!doctype" in b.lower()
tiene_tabla = "Detalle del reporte" in b
print(f"[2] GET /reportes/generar: status={s} HTML={es_html} tabla={tiene_tabla}")

# 3) AJAX -> JSON
s, b = req(base_t + "/reportes/generar?tipo=ventas&desde=2026-09-01&hasta=2026-09-25",
           headers={"Accept": "application/json"})
es_json = b.strip().startswith("{")
k = json.loads(b) if es_json else {}
print(f"[3] AJAX: status={s} JSON={es_json} kpis_ok={'kpis' in k}")

# 4) exportar proveedores
s, b = req(base_t + "/reportes/proveedores/exportar")
print(f"[4] export: status={s} es_archivo={len(b) > 100}")

ok = es_html and tiene_kpis and tiene_tabla and es_json and s == 200
print("\nRESULTADO:", "OK" if ok else "FALLA")
