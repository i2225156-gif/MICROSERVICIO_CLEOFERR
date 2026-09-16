import os
import sys
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, jsonify, g, make_response
from flask_bcrypt import Bcrypt
from functools import wraps
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from sqlalchemy import text
import jwt as pyjwt

load_dotenv()

# Configuración básica
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("SECRET_KEY no definida. Créla en el archivo .env.")

app.config["SESSION_TYPE"] = "null"
bcrypt = Bcrypt(app)

from shared.db_supabase import crear_engine_auth
engine_auth = crear_engine_auth()

from shared.utils import verificar_jwt, extract_token_from_header, extract_token_from_cookie

SECRET_KEY_JWT = os.environ.get("SECRET_KEY")


def generar_token_jwt(usuario_id, correo, rol):
    from datetime import datetime, timedelta, timezone
    ahora = datetime.now(timezone.utc)
    if rol and rol.lower() in ("administrador", "vendedor"):
        expiracion = ahora + timedelta(hours=8)
    else:
        expiracion = ahora + timedelta(hours=24)
    payload = {
        "id_usuario": usuario_id,
        "correo": correo,
        "rol": rol,
        "exp": expiracion,
        "iat": ahora,
    }
    token = pyjwt.encode(payload, SECRET_KEY_JWT, algorithm="HS256")
    return token


def login_requerido(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = extract_token_from_header(auth_header)
        # Also check cookie as fallback
        if not token:
            cookie_token = extract_token_from_cookie(request.cookies.get('jwt_token', ''))
            if cookie_token:
                token = cookie_token
        
        if token:
            try:
                payload = verificar_jwt(token, SECRET_KEY_JWT)
                g.usuario = {
                    "id": payload["id_usuario"],
                    "correo": payload["correo"],
                    "rol": payload["rol"],
                }
            except Exception:
                pass
        if not hasattr(g, "usuario") or g.usuario is None:
            if "usuario_id" not in session:
                return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        correo = request.form["correo"]
        clave = request.form["clave"]
        conn = engine_auth.connect()
        cursor = conn.execute(text(
            "SELECT u.id_usuario, u.email, u.contrasena, r.nombre AS rol "
            "FROM usuario u "
            "INNER JOIN rol r ON u.id_rol = r.id_rol "
            "WHERE u.email = :e"), {"e": correo.lower()})
        usuario = cursor.mappings().fetchone()
        conn.close()
        
        # Detect if this is a normal HTML form post or an API call
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
        accepts_json = "application/json" in request.headers.get("Accept", "")
        
        if usuario and bcrypt.check_password_hash(usuario["contrasena"], clave):
            token = generar_token_jwt(usuario.id_usuario, usuario.email, usuario.rol)
            
            if is_ajax or accepts_json:
                # API/json response: return JSON with token
                return jsonify({
                    "exito": True,
                    "token": token,
                    "mensaje": "Login exitoso",
                    "rol": usuario.rol
                })
            else:
                # HTML form response: set cookie and redirect
                resp = make_response(redirect(url_for("index")))
                resp.set_cookie('jwt_token', token, httponly=True, secure=False, samesite='Lax')
                return resp
        
        # Failure case - detect type and respond appropriately
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
        accepts_json = "application/json" in request.headers.get("Accept", "")
        
        if is_ajax or accepts_json:
            return jsonify({
                "exito": False,
                "error": "Credenciales incorrectas",
            }), 401
        else:
            # Redirigir de vuelta al login con error (Flash no fácil en jsonify,
            # así que usamos query param)
            return redirect(url_for("login") + "?error=credenciales_incorrectas")
    
    # GET request - show login form
    return render_template("login.html")


@app.route("/login_cliente", methods=["GET", "POST"])
def login_cliente():
    if request.method == "POST":
        correo = request.form["correo"]
        contrasena = request.form["contrasena"]
        conn = engine_auth.connect()
        cursor = conn.execute(text("SELECT id_usuario, email, contrasena FROM usuario WHERE email = :e"), {"e": correo.lower()})
        usuario = cursor.mappings().fetchone()
        conn.close()
        
        # Same HTML vs API detection
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
        accepts_json = "application/json" in request.headers.get("Accept", "")
        
        if usuario and Bcrypt.check_password_hash(usuario.contrasena, contrasena):
            token = generar_token_jwt(usuario.id_usuario, usuario.email, "cliente")
            
            if is_ajax or accepts_json:
                return jsonify({
                    "exito": True,
                    "token": token,
                    "mensaje": "Login cliente exitoso",
                })
            else:
                resp = make_response(redirect(url_for("index")))
                resp.set_cookie('jwt_token', token, httponly=True, secure=False, samesite='Lax')
                return resp
        
        if is_ajax or accepts_json:
            return jsonify({
                "exito": False,
                "error": "Credenciales incorrectas o cuenta no verificada",
            }), 401
        else:
            return redirect(url_for("login") + "?error=credenciales_incorrectas")
    
    return render_template("login_cliente.html")


@app.route("/logout")
def logout():
    resp = make_response(redirect(url_for("index")))
    resp.set_cookie('jwt_token', '', httponly=True, secure=False, samesite='Lax', expires=0)
    return resp


@app.route("/cambiar_clave", methods=["GET", "POST"])
def cambiar_clave():
    if request.method == "POST":
        nueva = request.form["nueva"]
        confirmar = request.form["confirmar"]
        if nueva != confirmar:
            return jsonify({"exito": False, "error": "Las contraseñas no coinciden"}, 400)
        return jsonify({"exito": True, "mensaje": "Clave actualizada"})
    return render_template("cambiar_clave.html")


@app.route("/clientes")
def clientes_list():
    auth_header = request.headers.get("Authorization", "")
    token = extract_token_from_header(auth_header)
    if not token:
        # Also check cookie
        cookie_token = extract_token_from_cookie(request.cookies.get('jwt_token', ''))
        if cookie_token:
            token = cookie_token
    
    if not token:
        return jsonify({"error": "Token requerido", "code": 401}), 401
    try:
        payload = verificar_jwt(token, SECRET_KEY_JWT)
        g.usuario = {"id": payload["id_usuario"], "correo": payload["correo"], "rol": payload["rol"]}
    except Exception:
        return jsonify({"error": "Token inválido", "code": 401}), 401
    return jsonify({"exito": True, "clientes": [], "mensaje": "Listado de clientes"})


@app.route("/clientes/registrar_pos", methods=["POST"])
def registrar_pos():
    data = request.get_json(silent=True) or {}
    tipo = (data.get("tipo") or "boleta").strip().lower()
    if tipo not in ("boleta", "factura"):
        return jsonify({"ok": False, "error": "Tipo de comprobante inválido."}), 400
    nombre = (data.get("nombre") or "").strip()
    telefono = (data.get("telefono") or "").strip()
    apellido = (data.get("apellido") or "").strip()
    direccion = (data.get("direccion") or "").strip()
    if tipo == "boleta":
        doc = (data.get("dni") or "").strip()
        if not doc.isdigit() or len(doc) != 8:
            return jsonify({"ok": False, "error": "El DNI debe tener exactamente 8 dígitos."}), 400
        if len(nombre) < 3:
            return jsonify({"ok": False, "error": "El nombre del cliente es obligatorio (mínimo 3 caracteres)."}), 400
    else:
        doc = (data.get("ruc") or "").strip()
        if not doc.isdigit() or len(doc) != 11 or doc[:2] not in ("10", "20"):
            return jsonify({"ok": False, "error": "El RUC debe tener 11 dígitos y comenzar con 10 o 20."}), 400
        if len(nombre) < 3:
            return jsonify({"ok": False, "error": "La razón social es obligatoria (mínimo 3 caracteres)."}), 400
        if len(direccion) < 5:
            return jsonify({"ok": False, "error": "La dirección fiscal es obligatoria para factura (mínimo 5 caracteres)."}), 400
    if telefono and (not telefono.isdigit() or len(telefono) != 9):
        return jsonify({"ok": False, "error": "El teléfono debe tener exactamente 9 dígitos."}), 400
    id_tipo_doc = 1 if tipo == "boleta" else 6
    conn = engine_auth.connect()
    try:
        cursor = conn.execute(text(
            "SELECT id_cliente, nombre, apellido, telefono FROM cliente WHERE id_tipo_documento = %s AND nro_documento = %s",
            (id_tipo_doc, doc)))
        existente = cursor.mappings().fetchone()
        if existente:
            if telefono and not (existente.telefono or "").strip():
                conn.execute(text("UPDATE cliente SET telefono = :tel WHERE id_cliente = :id"), {"tel": telefono, "id": existente.id_cliente})
            nombre_existente = f"{existente.nombre or ''} {existente.apellido or ''}".strip()
            conn.commit()
            conn.close()
            return jsonify({"ok": True, "id_cliente": existente.id_cliente, "nombre": nombre_existente, "ya_existia": True})
    except Exception as e:
        conn.rollback()
        conn.close()
        import logging
        app.logger.error("Error al registrar cliente desde el POS: %s", e)
        return jsonify({"ok": False, "error": "No se pudo guardar el cliente (error interno)."}), 500
    id_tipo_doc = 1 if tipo == "boleta" else 6
    nombre_db = nombre
    apellido_db = apellido
    if not apellido_db and tipo == "boleta":
        partes = nombre.split()
        if len(partes) >= 2:
            nombre_db = partes[0]
            apellido_db = " ".join(partes[1:])
    try:
        conn.execute(text(
            "INSERT INTO cliente (nombre, apellido, email, telefono, id_tipo_documento, nro_documento, direccion, contrasena, activo, origen) VALUES (%s, %s, NULL, %s, %s, %s, %s, NULL, TRUE, 'pos')",
            (nombre_db, apellido_db, telefono or None, id_tipo_doc, doc, direccion or None)))
        conn.commit()
        id_cliente = conn.execute(text("SELECT id_cliente FROM cliente WHERE nro_documento = %s AND id_tipo_documento = %s"), (doc, id_tipo_doc)).scalar()
        conn.close()
        nombre_mostrar = f"{nombre_db} {apellido_db}".strip()
        return jsonify({"ok": True, "id_cliente": id_cliente, "nombre": nombre_mostrar, "ya_existia": False})
    except Exception as e:
        conn.rollback()
        conn.close()
        app.logger.error("Error al registrar cliente desde el POS: %s", e)
        return jsonify({"ok": False, "error": "No se pudo guardar el cliente (error interno)."}), 500


@app.route("/clientes/nuevo", methods=["GET", "POST"])
def nuevo_cliente():
    if request.method == "POST":
        nombre = request.form["nombre"]
        email = request.form["email"]
        telefono = request.form.get("telefono", "")
        direccion = request.form.get("direccion", "")
        contrasena = request.form.get("contrasena")
        if not contrasena:
            return jsonify({
                "exito": False,
                "error": "La contraseña es obligatoria para el registro web.",
            }), 400
        hash_pw = Bcrypt.generate_password_hash(contrasena).decode("utf-8")
        conn = engine_auth.connect()
        try:
            conn.execute(text("INSERT INTO cliente (nombre, email, telefono, direccion, contrasena, activo) VALUES (%s, %s, %s, %s, %s, TRUE)"), (nombre, email, telefono or None, direccion or None, hash_pw))
            conn.commit()
            return jsonify({"exito": True, "mensaje": "Cliente registrado correctamente."})
        except Exception as e:
            conn.rollback()
            return jsonify({"exito": False, "error": f"Error al registrar cliente: {str(e)}"}), 500
        finally:
            try: conn.close()
            except: pass
    return render_template("cliente_form.html")


@app.route("/clientes/editar/<int:id>", methods=["GET", "POST"])
def editar_cliente(id):
    if request.method == "POST":
        nombre = request.form["nombre"]
        email = request.form["email"]
        telefono = request.form.get("telefono", "")
        direccion = request.form.get("direccion", "")
        conn = engine_auth.connect()
        try:
            conn.execute(text("UPDATE cliente SET nombre = %s, email = %s, telefono = %s, direccion = %s WHERE id_cliente = %s"), (nombre, email, telefono or None, direccion or None, id))
            conn.commit()
            return jsonify({"exito": True, "mensaje": "Cliente actualizado."})
        except Exception as e:
            conn.rollback()
            return jsonify({"exito": False, "error": str(e)}), 500
        finally:
            try: conn.close()
            except: pass
    return jsonify({"mensaje": "Formulario de edición (implementar vista)"})


@app.route("/clientes/eliminar/<int:id>")
def eliminar_cliente(id):
    conn = engine_auth.connect()
    try:
        conn.execute(text("DELETE FROM cliente WHERE id_cliente = %s"), (id,))
        conn.commit()
        return jsonify({"exito": True, "mensaje": "Cliente eliminado."})
    except Exception as e:
        conn.rollback()
        return jsonify({"exito": False, "error": str(e)}), 500
    finally:
        try: conn.close()
        except: pass


@app.route("/")
def index():
    return jsonify({
        "mensaje": "Auth Service - endpoints: /login, /login_cliente, /logout, /cambiar_clave, /clientes",
        "puerto": 5001,
        "jwt_cookie": "Si accediste via form HTML, el token fue guardado en cookie jwt_token"
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)