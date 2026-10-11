import requests, re
s = requests.Session()
s.post("http://127.0.0.1:5001/login",
       data={"correo": "admin@cleoferr.com", "clave": "Admin123!"},
       allow_redirects=False)
r = s.get("http://127.0.0.1:5002/pedidos")
# extraer las celdas de la columna Cliente del listado
filas = re.findall(r"<tr>(.*?)</tr>", r.text, re.S)
vacias = 0
con_nombre = 0
for f in filas:
    tds = re.findall(r"<td[^>]*>(.*?)</td>", f, re.S)
    if len(tds) >= 2:
        celda = re.sub(r"<[^>]+>", "", tds[1]).strip()
        if celda:
            con_nombre += 1
        else:
            vacias += 1
print(f"status={r.status_code} clientes_con_nombre={con_nombre} clientes_vacios={vacias}")
