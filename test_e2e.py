# Test E2E de microservicios Cleoferr (navegador simulado via cookies)
# Ejecutar: python test_e2e.py  (requiere auth_service:5001 y tienda_service:5002 corriendo)
import requests

AUTH = "http://127.0.0.1:5001"
TIENDA = "http://127.0.0.1:5002"

resultados = []

def check(nombre, ok, detalle=""):
    resultados.append((nombre, ok, detalle))
    print(f"  [{'OK' if ok else 'FAIL'}] {nombre} {detalle}")

def es_html(r):
    return "text/html" in r.headers.get("Content-Type", "")

print("== FLUJO ADMIN ==")
s = requests.Session()
r = s.post(AUTH + "/login", data={"correo": "admin@cleoferr.com", "clave": "Admin123!"},
           allow_redirects=False)
check("login admin (redirect+cookie)", r.status_code in (200, 302) and "jwt_token" in r.headers.get("Set-Cookie", ""))

rutas_admin = ["/productos", "/pedidos", "/inventario", "/caja",
               "/alertas", "/proveedores", "/reportes", "/ventas/nueva", "/productos/nuevo"]
for ruta in rutas_admin:
    rr = s.get(TIENDA + ruta, allow_redirects=True)
    ok = rr.status_code == 200 and es_html(rr) and "<" in rr.text
    sidebar = "sidebar-modulos" in rr.text
    check(f"GET {ruta}", ok, f"({rr.status_code}, sidebar={'SI' if sidebar else 'NO'})")

print("== FLUJO CLIENTE ==")
s2 = requests.Session()
r = s2.post(AUTH + "/login_cliente",
            data={"correo": "maria.quispe@gmail.com", "contrasena": "Cliente123"},
            allow_redirects=False)
check("login cliente (cookie)", r.status_code in (200, 302))

rr = s2.get(TIENDA + "/catalogo")
check("GET /catalogo HTML", es_html(rr) and "prod-card" in rr.text, f"({rr.status_code})")

rr = s2.get(TIENDA + "/carrito")
check("GET /carrito HTML", es_html(rr), f"({rr.status_code})")
fetch_ok = "/ventas/nueva" in rr.text and "confirmar_v2" not in rr.text
check("carrito fetch apunta a /ventas/nueva", fetch_ok)

# Hijack product list via API (mismo token de sesion)
prods = s2.get(TIENDA + "/productos", headers={"Accept": "application/json"}).json()["productos"]
con_stock = [p for p in prods if p["stock"] > 0]
if len(con_stock) < 2:
    check("POST /ventas/nueva (online)", False, "(menos de 2 productos con stock)")
else:
    p1 = p2 = None
con_stock = [p for p in prods if p["stock"] > 0]
if len(con_stock) < 2:
    check("POST /ventas/nueva (online)", False, "(menos de 2 productos con stock)")
else:
    p1, p2 = con_stock[0], con_stock[1]
    v = s2.post(TIENDA + "/ventas/nueva", json={
        "tipo_venta": "online", "metodo_pago": "efectivo",
        "ids_producto": [p1["id"], p2["id"]], "cantidades": [1, 2],
        "comp_tipo": "boleta", "comp_doc": "12345678"})
    ok_venta = v.status_code == 200 and v.json().get("ok")
    check("POST /ventas/nueva (online)", ok_venta, f"({v.status_code}: {v.json().get('mensaje') or v.json().get('error')})")

if ok_venta:
    rr = s2.get(TIENDA + "/mis_pedidos")
    check("GET /mis_pedidos HTML con pedido", rr.status_code == 200 and es_html(rr) and str(v.json()["id_venta"]) in rr.text, f"({rr.status_code})")
    rr = s2.get(TIENDA + "/pedidos/detalle/%d" % v.json()["id_venta"])
    check("GET /pedidos/detalle HTML", rr.status_code == 200 and es_html(rr), f"({rr.status_code})")

print("== RESUMEN ==")
ok_total = sum(1 for _, ok, _ in resultados if ok)
print(f"{ok_total}/{len(resultados)} OK")
for nombre, ok, detalle in resultados:
    if not ok:
        print(f"  FAIL: {nombre} {detalle}")
