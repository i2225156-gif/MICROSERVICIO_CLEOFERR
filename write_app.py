import os

content = r'''import os
import sys
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, jsonify, g
from flask_bcrypt import Bcrypt
from functools import wraps
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import pyjwt as jwt

load_dotenv()

# Configuración básica
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("SECRET_KEY no definida. Créla en el archivo .env.")

app.config["SESSION_TYPE"] = "null"
bcrypt = Bcrypt(app)

from shared.db_supabase import crear_engine_tienda
engine_tienda = crear_engine_tienda()

from shared.utils import verificar_jwt, extract_token_from_header, extract_token_from_cookie, login_requerido

SECRET_KEY_JWT = os.environ.get("SECRET_KEY")

def requiere_jwt(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = extract_token_from_header(auth_header)
        if not token:
            cookie_token = extract_token_from_cookie(request.cookies.get('jwt_token', ''))
            if cookie_token:
                token = cookie_token
        if not token:
            return jsonify({"error": "Token de autorización requerido", "code": 401}), 401
        try:
            payload = verificar_jwt(token, SECRET_KEY_JWT)
            g.usuario = {
                "id": payload["id_usuario"],
                "correo": payload["correo"],
                "rol": payload["rol"],
            }
        except Exception as e:
            return jsonify({"error": f"Token inválido o expirado: {str(e)}", "code": 401}), 401
        return f(*args, **kwargs)
    return decorated_function


@app.route("/")
def index():
    return jsonify({"mensaje": "Tienda Service - endpoints disponibles", "puerto": 5002})


@app.route("/catalogo")
def catalogo():
    token = extract_token_from_header(request.headers.get("Authorization", ""))
    if not token:
        cookie_token = extract_token_from_cookie(request.cookies.get('jwt_token', ''))
        if token:
            pass
    if not token:
        return jsonify({"error": "Token requerido", "code": 401}), 401
    try:
        from shared.utils import verificar_jwt
        payload = verificar_jwt(token, SECRET_KEY_JWT)
        g.usuario = {"id": payload["id_usuario"], "correo": payload["correo"], "rol": payload["rol"]}
    except Exception:
        return jsonify({"error": "Token inválido", "code": 401}), 401
    from sqlalchemy import text
    conn = engine_tienda.connect()
    cursor = conn.execute(text("SELECT id_producto, nombre, precio, stock FROM producto WHERE activo = TRUE ORDER BY nombre"))
    productos = cursor.fetchall()
    conn.close()
    return jsonify({"productos": [{"id": p[0], "nombre": p[1], "precio": float(p[2]), "stock": p[3]} for p in productos]})
'''

with open('tienda_service\\app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Parte 1 escrita")
'