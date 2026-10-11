import requests
s = requests.Session()
s.post("http://127.0.0.1:5001/login",
       data={"correo": "admin@cleoferr.com", "clave": "Admin123!"},
       allow_redirects=False)
r = s.post(
    "http://127.0.0.1:5001/clientes/registrar_pos",
    json={"tipo": "boleta", "dni": "46581236",
          "nombre": "JOSE RENAN HUAMAN DIAZ", "telefono": "996633225"},
    headers={"Origin": "http://127.0.0.1:5002"})
print("status:", r.status_code)
print("body:", r.text[:500])
