# -*- coding: utf-8 -*-
"""Prueba BUG 1: login + abrir caja con submit nativo (sin header JSON)."""
import requests

s = requests.Session()
r_login = s.post("http://127.0.0.1:5001/login",
                 data={"correo": "admin@cleoferr.com", "clave": "Admin123!"},
                 allow_redirects=False)
print("login:", r_login.status_code, "->", r_login.headers.get("Location", "(sin redirect)"))

r = s.post("http://127.0.0.1:5002/caja/abrir",
           data={"monto_apertura": "60"},
           allow_redirects=True)
print("abrir status:", r.status_code)
print("url final:", r.url)
print("es_json_crudo:", r.text.strip().startswith("{"))
print("contenido (primeros 300):", r.text[:300].replace("\n", " "))
