import requests, re
s = requests.Session()
s.post("http://127.0.0.1:5001/login_cliente",
       data={"correo": "maria.quispe@gmail.com", "contrasena": "Cliente123"},
       allow_redirects=False)
r = s.get("http://127.0.0.1:5002/mis_pedidos")
print("status:", r.status_code, "len:", len(r.text))
print("contiene '58':", "58" in r.text)
print("contiene 'id_pedido':", r.text.count("id_pedido"))
m = re.findall(r"pedido[s]?\s*[:]?\s*.{0,40}", r.text[:3000])
print(m[:5])
# mostrar fragmento donde deberian listarse
i = r.text.find("ped")
print(r.text[i:i+600])
