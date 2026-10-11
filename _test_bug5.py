# Valida BUG 5: POST /ventas/nueva con los MISMOS headers que carrito.html
# (Content-Type json + Bearer, SIN Accept ni X-Requested-With).
# Esperado tras el fix: 200 + JSON, NO 302.
import json, os, urllib.request
import jwt
from dotenv import load_dotenv

load_dotenv()
token = jwt.encode(
    {"id_usuario": 11, "rol": "cliente"},
    os.environ["SECRET_KEY"], algorithm="HS256")

req = urllib.request.Request(
    "http://127.0.0.1:5002/ventas/nueva",
    data=json.dumps({
        "tipo_venta": "online", "metodo_pago": "yape",
        "ids_producto": [], "cantidades": []   # vacio a proposito:
        # si responde 400 JSON {"error": "Debes agregar..."} el fix anda
        # y NO se crea ninguna venta de prueba en BD.
    }).encode(),
    headers={"Content-Type": "application/json",
             "Authorization": "Bearer " + token},
    method="POST")

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None

opener = urllib.request.build_opener(NoRedirect)
try:
    r = opener.open(req)
    print("status:", r.status, "| body:", r.read().decode()[:300])
except urllib.error.HTTPError as e:
    print("status:", e.code, "| body:", e.read().decode()[:300])
