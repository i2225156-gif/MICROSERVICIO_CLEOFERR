import requests
s = requests.Session()
s.post("http://127.0.0.1:5001/login",
       data={"correo": "admin@cleoferr.com", "clave": "Admin123!"},
       allow_redirects=False)
print("cookies:", dict(s.cookies))

# Simula exactamente el submit nativo del form venta_form.html
r = s.post("http://127.0.0.1:5002/ventas/nueva", data={
    "id_cliente": "62",
    "tipo_venta": "local",
    "metodo_pago": "efectivo",
    "id_producto[]": ["6", "7"],
    "cantidad[]": ["1", "1"],
}, allow_redirects=False)
print("status:", r.status_code)
print("body:", r.text[:400])
