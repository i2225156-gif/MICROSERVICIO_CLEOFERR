import requests
s = requests.Session()
s.post("http://127.0.0.1:5001/login",
       data={"correo": "admin@cleoferr.com", "clave": "Admin123!"},
       allow_redirects=False)

acciones = [
    ("GET",  ":5002", "/productos"),
    ("GET",  ":5002", "/productos/nuevo"),
    ("GET",  ":5002", "/productos/detalle/6"),
    ("GET",  ":5002", "/productos/editar/6"),
    ("GET",  ":5002", "/pedidos"),
    ("GET",  ":5002", "/pedidos/detalle/60"),
    ("GET",  ":5002", "/inventario"),
    ("GET",  ":5002", "/caja"),
    ("GET",  ":5002", "/alertas"),
    ("GET",  ":5002", "/alertas/programar"),
    ("GET",  ":5002", "/proveedores"),
    ("GET",  ":5002", "/proveedores/nuevo"),
    ("GET",  ":5002", "/proveedores/editar/2"),
    ("GET",  ":5002", "/clientes"),
    ("GET",  ":5002", "/reportes"),
    ("GET",  ":5002", "/reportes/generar?tipo=ventas&desde=2026-01-01&hasta=2026-12-31"),
    ("GET",  ":5002", "/reportes/pedidos/exportar"),
    ("GET",  ":5002", "/reportes/productos/exportar"),
    ("GET",  ":5002", "/reportes/clientes/exportar"),
    ("GET",  ":5002", "/reportes/proveedores/exportar"),
    ("GET",  ":5002", "/reportes/inventario/exportar"),
    ("GET",  ":5002", "/reportes/dia/exportar"),
    ("GET",  ":5002", "/ventas/nueva"),
    ("GET",  ":5001", "/cambiar_clave"),
    ("GET",  ":5001", "/clientes"),
    ("GET",  ":5001", "/clientes/nuevo"),
    ("GET",  ":5001", "/recuperar_contrasena"),
]
for metodo, puerto, ruta in acciones:
    r = s.request(metodo, f"http://127.0.0.1{puerto}{ruta}", allow_redirects=False)
    extra = ""
    if r.status_code in (200,) and "text/html" in r.headers.get("Content-Type", ""):
        extra = "HTML"
    elif r.status_code in (302,):
        extra = f"redirect -> {r.headers.get('Location')}"
    print(f"{metodo} {puerto}{ruta} -> {r.status_code} {extra}")
