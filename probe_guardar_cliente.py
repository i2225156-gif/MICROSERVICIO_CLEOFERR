import requests

s = requests.Session()
s.post("http://127.0.0.1:5001/login",
       data={"correo": "admin@cleoferr.com", "clave": "Admin123!"},
       allow_redirects=False)

# 1) Preflight exacto como el navegador (desde la pagina :5002)
pre = s.options(
    "http://127.0.0.1:5001/clientes/registrar_pos",
    headers={
        "Origin": "http://127.0.0.1:5002",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
print("PREFLIGHT:", pre.status_code, "|", pre.headers.get("Access-Control-Allow-Origin"),
      "|", pre.headers.get("Access-Control-Allow-Credentials"))

# 2) POST real con Origin + cookie (como el fetch del navegador)
r = s.post(
    "http://127.0.0.1:5001/clientes/registrar_pos",
    json={"tipo": "boleta", "dni": "45781236",
          "nombre": "JULIO CESAR JUAREZ YNGA", "telefono": "996633225"},
    headers={"Origin": "http://127.0.0.1:5002"})
print("POST:", r.status_code, "|", r.text[:300])
print("ACAO:", r.headers.get("Access-Control-Allow-Origin"))
