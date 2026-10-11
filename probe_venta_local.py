# -*- coding: utf-8 -*-
"""FIX 1 validacion: abrir caja -> venta local -> mostrar flash -> cerrar caja."""
import sys, os, re, requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from sqlalchemy import text
from db_supabase import engine_tienda

conn = engine_tienda.connect()
prod = conn.execute(text("SELECT id_producto, nombre, stock FROM producto WHERE stock > 0 ORDER BY id_producto LIMIT 1")).fetchone()
conn.close()
pid = prod._mapping["id_producto"]
print("producto:", dict(prod._mapping))

s = requests.Session()
s.post("http://127.0.0.1:5001/login",
       data={"correo": "admin@cleoferr.com", "clave": "Admin123!"},
       allow_redirects=False)

r_abrir = s.post("http://127.0.0.1:5002/caja/abrir", data={"monto_apertura": "60"})
print("abrir caja:", r_abrir.status_code, r_abrir.text[:120].replace("\n", " "))

r = s.post("http://127.0.0.1:5002/ventas/nueva",
           data={"tipo_venta": "local", "metodo_pago": "efectivo",
                 "id_producto[]": str(pid), "cantidad[]": "1"},
           allow_redirects=True)
print("venta status:", r.status_code, "| url:", r.url, "| json_crudo:", r.text.strip().startswith("{"))
# extraer mensajes flash del HTML
flashes = re.findall(r'alert[^>]*>(.*?)</', r.text, re.S)
print("flash:", [f.strip() for f in flashes][:3])

# cerrar la caja abierta para dejar limpio
r_cerrar = s.post("http://127.0.0.1:5002/caja/cerrar", data={"monto_declarado": "249.9"},
                  allow_redirects=True)
print("cerrar caja:", r_cerrar.status_code, "| json_crudo:", r_cerrar.text.strip().startswith("{"))
