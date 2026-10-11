# Prueba BUG 7 contra el servidor real en :5001.
# 1) Submit nativo (form-urlencoded, sin Accept/JSON) de /registro_cliente
#    -> debe devolver HTML de verificacion, NO JSON crudo.
# 2) Lo mismo via fetch JSON -> debe seguir devolviendo JSON.
# 3) Limpieza: borra el cliente de prueba creado.
import urllib.request, urllib.parse, urllib.error
from dotenv import load_dotenv
from sqlalchemy import text
load_dotenv()

BASE = "http://127.0.0.1:5001"
CORREO = "cliente_bug7@noexiste.com"

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None
opener = urllib.request.build_opener(NoRedirect)

form = urllib.parse.urlencode({
    "nombre": "Prueba Bug7", "apellido": "Test", "correo": CORREO,
    "telefono": "999999999", "direccion": "Av Test 123",
    "contrasena": "Clave123", "confirmar": "Clave123"}).encode()

# 1) nativo
r = urllib.request.Request(BASE + "/registro_cliente", data=form,
    headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
try:
    resp = opener.open(r); s1, b1 = resp.status, resp.read().decode(errors="replace")
except urllib.error.HTTPError as e:
    s1, b1 = e.code, e.read().decode(errors="replace")
es_html1 = "Verifica tu correo" in b1 or "verificar" in b1.lower()
print(f"[1] nativo: status={s1} esHTML={es_html1} esJSON={b1.strip().startswith('{')}")

# 2) JSON
import json
r2 = urllib.request.Request(BASE + "/registro_cliente", data=json.dumps({
    "nombre": "Prueba Bug7", "correo": CORREO, "direccion": "Av Test 123",
    "contrasena": "Clave123", "confirmar": "Clave123"}).encode(),
    headers={"Content-Type": "application/json"}, method="POST")
try:
    resp = opener.open(r2); s2, b2 = resp.status, resp.read().decode()
except urllib.error.HTTPError as e:
    s2, b2 = e.code, e.read().decode()
print(f"[2] JSON:   status={s2} body={b2[:150]}")

# 3) verificar_registro nativo con codigo malo -> HTML con error, no JSON
form2 = urllib.parse.urlencode({"correo": CORREO, "codigo": "000000"}).encode()
r3 = urllib.request.Request(BASE + "/verificar_registro", data=form2,
    headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
try:
    resp = opener.open(r3); s3, b3 = resp.status, resp.read().decode(errors="replace")
except urllib.error.HTTPError as e:
    s3, b3 = e.code, e.read().decode(errors="replace")
print(f"[3] verificar nativo: status={s3} esHTML={'<html' in b3 or '<!doctype' in b3.lower()} esJSON={b3.strip().startswith('{')}")

# limpieza
from shared.db_supabase import crear_engine_auth
conn = crear_engine_auth().connect()
row = conn.execute(text("SELECT id_cliente FROM cliente WHERE email=:e"), {"e": CORREO}).fetchone()
if row:
    conn.execute(text("DELETE FROM verificacion_cuenta WHERE id_cliente=:i"), {"i": row[0]})
    conn.execute(text("DELETE FROM cliente WHERE id_cliente=:i"), {"i": row[0]})
    conn.commit()
    print("limpieza: cliente de prueba eliminado")
conn.close()

ok = (s1 == 200 and es_html1) and (s2 == 200 and '"exito":true' in b2) and (not b3.strip().startswith('{'))
print("\nRESULTADO:", "OK" if ok else "FALLA")
