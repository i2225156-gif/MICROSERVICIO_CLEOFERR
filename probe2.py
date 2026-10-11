import requests
s = requests.Session()
r = s.post("http://127.0.0.1:5001/login_cliente",
           data={"correo": "maria.quispe@gmail.com", "contrasena": "Cliente123"},
           allow_redirects=False)
print("login status:", r.status_code)
print("cookies:", dict(s.cookies))
r = s.get("http://127.0.0.1:5002/mis_pedidos", allow_redirects=False)
print("mis_pedidos status:", r.status_code, "location:", r.headers.get("Location"))
print("len:", len(r.text))
print("contiene '58':", "58" in r.text)
import re
m = re.search(r"No tienes|pedido|Pedido", r.text)
print("primer match:", m.group(0) if m else None)
i = r.text.find("{%") if "{%" in r.text else r.text.find("alert")
