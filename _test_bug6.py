# Valida BUG 6: POST /productos/actualizar/<id> multipart con imagen.
# Usa el producto 7 (Taladro). Guarda su imagen previa y la restaura al final.
import os, urllib.request, urllib.error, uuid
import jwt
from dotenv import load_dotenv
from sqlalchemy import text
from db_supabase import engine_tienda

load_dotenv()
token = jwt.encode({"id_usuario": 7, "rol": "administrador", "correo": "a@b.c"},
                   os.environ["SECRET_KEY"], algorithm="HS256")

conn = engine_tienda.connect()
prev = conn.execute(text("SELECT imagen, nombre, precio, stock FROM producto WHERE id_producto = 7")).fetchone()._mapping
print("imagen ANTES:", prev["imagen"])

# PNG de 1x1 minimo real
png = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c626001000000ffff03000006000557bfabd40000000049454e44ae426082")

boundary = uuid.uuid4().hex
def campo(name, val):
    return (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{val}\r\n").encode()
def archivo(name, filename, data):
    return (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; "
            f"filename=\"{filename}\"\r\nContent-Type: image/png\r\n\r\n").encode() + data + b"\r\n"

body = (campo("nombre", prev["nombre"]) + campo("descripcion", "test bug6")
        + campo("precio", str(prev["precio"])) + campo("stock", str(prev["stock"]))
        + archivo("imagen", "test.png", png) + f"--{boundary}--\r\n").encode() \
        if False else \
        campo("nombre", prev["nombre"]) + campo("descripcion", "test bug6") \
        + campo("precio", str(prev["precio"])) + campo("stock", str(prev["stock"])) \
        + archivo("imagen", "test.png", png) + f"--{boundary}--\r\n".encode()

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None
opener = urllib.request.build_opener(NoRedirect)
r = urllib.request.Request("http://127.0.0.1:5002/productos/actualizar/7", data=body,
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
             "Authorization": "Bearer " + token}, method="POST")
try:
    resp = opener.open(r); s, b = resp.status, resp.read().decode()[:150]
except urllib.error.HTTPError as e:
    s, b = e.code, e.read().decode()[:150]
print(f"POST /productos/actualizar/7 multipart -> {s} {b}")

nuevo = conn.execute(text("SELECT imagen FROM producto WHERE id_producto = 7")).scalar()
print("imagen DESPUES:", nuevo)
path = os.path.join("tienda_service", "static", "img", nuevo or "")
print("archivo en disco:", os.path.isfile(path), "| bytes:", os.path.getsize(path) if os.path.isfile(path) else "-")

# Restaurar imagen previa y limpiar archivo de prueba
if nuevo != prev["imagen"]:
    conn.execute(text("UPDATE producto SET imagen = :img WHERE id_producto = 7"), {"img": prev["imagen"]})
    conn.commit()
    if os.path.isfile(path):
        os.remove(path)
    print("restaurado y limpiado OK")
conn.close()
