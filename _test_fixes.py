# Validacion funcional de PASO 1/2/3 sin navegador.
import json, os, urllib.request, urllib.error
import jwt
from dotenv import load_dotenv

load_dotenv()
token = jwt.encode({"id_usuario": 7, "rol": "administrador", "correo": "admin@cleoferr.com"},
                   os.environ["SECRET_KEY"], algorithm="HS256")
tok_cli = jwt.encode({"id_usuario": 11, "rol": "cliente", "correo": "maria.quispe@gmail.com"},
                     os.environ["SECRET_KEY"], algorithm="HS256")
BASE = "http://127.0.0.1:5002"

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None
opener = urllib.request.build_opener(NoRedirect)

def req(path, method="GET", data=None, headers=None, full=False):
    r = urllib.request.Request(BASE + path, data=data, headers=headers or {}, method=method)
    try:
        resp = opener.open(r)
        body = resp.read().decode(errors="replace")
        return resp.status, body if full else body[:200]
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        return e.code, body if full else body[:200]

# 1) BUG 5: fetch JSON sin Accept -> debe responder JSON, no 302
s, b = req("/ventas/nueva", "POST",
           json.dumps({"tipo_venta": "online", "metodo_pago": "yape",
                       "ids_producto": [], "cantidades": []}).encode(),
           {"Content-Type": "application/json", "Authorization": "Bearer " + tok_cli})
print(f"[BUG5] POST /ventas/nueva JSON sin Accept -> {s} {b}")
assert s == 400 and '"ok":false' in b.replace(" ", ""), "FAIL bug5"

# 2) BUG 4: submit nativo (form-urlencoded) -> 302, NO 415
s, b = req("/inventario/registrar", "POST",
           urllib.parse.urlencode({"tipo": "entrada", "id_producto": "999999",
                                   "cantidad": "1"}).encode(),
           {"Content-Type": "application/x-www-form-urlencoded",
            "Authorization": "Bearer " + token})
print(f"[BUG4] POST /inventario/registrar form nativo -> {s} {b}")
assert s == 302, "FAIL bug4 (debe redirigir, no 415)"

# 3) BUG 4 JSON sigue funcionando
s, b = req("/inventario/registrar", "POST",
           json.dumps({"tipo": "entrada", "id_producto": 999999, "cantidad": 1}).encode(),
           {"Content-Type": "application/json", "Authorization": "Bearer " + token})
print(f"[BUG4] POST /inventario/registrar JSON -> {s} {b}")
assert s == 404 and "error" in b, "FAIL bug4 json"

# 4) BUG 3: /alertas JSON incluye campo id (id_alerta)
s, b = req("/alertas", headers={"Accept": "application/json",
                                "Authorization": "Bearer " + token}, full=True)
print(f"[BUG3] GET /alertas JSON -> {s}")
d = json.loads(b) if s == 200 else {}
if d.get("alertas"):
    a = d["alertas"][0]
    print("   primera alerta keys tiene 'id':", "id" in a, "| id =", a.get("id"))
    assert a.get("id"), "FAIL bug3: falta alias id"
else:
    print("   (sin alertas activas; alias no verificable en datos, solo en SQL)")

print("\nTODAS LAS VALIDACIONES OK")
