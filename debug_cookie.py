"""Debug: por qué el cookie JWT no llega a :5002/productos."""
import re
import requests

s = requests.Session()
r = s.post("http://127.0.0.1:5001/login",
           data={"correo": "admin@cleoferr.com", "clave": "Admin123!"},
           allow_redirects=False, timeout=10)
print("POST login ->", r.status_code)
print("Set-Cookie crudo:", r.headers.get("Set-Cookie"))
print("Cookies en sesión:", dict(s.cookies))
for c in s.cookies:
    print(f"  cookie: name={c.name!r} domain={c.domain!r} path={c.path!r} secure={c.secure}")

# Preparar la request a 5002 y ver qué cookies se enviarían
req = requests.Request("GET", "http://127.0.0.1:5002/productos")
prep = s.prepare_request(req)
print("Cookie header que se enviaría a :5002:", prep.headers.get("Cookie"))
