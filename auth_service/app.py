import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
app.secret_key = os.environ.get("JWT_SECRET_KEY") or os.environ.get("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("JWT_SECRET_KEY o SECRET_KEY no definida. Créala en el archivo .env.")

app.config["SESSION_TYPE"] = "null"
# Nombre de cookie de sesión propio por servicio (las cookies NO se aíslan
# por puerto en 127.0.0.1; sin esto los servicios se pisan entre sí)
app.config["SESSION_COOKIE_NAME"] = "auth_session"
bcrypt = Bcrypt(app)

# CORS: los POST del frontend servido en :5002 (ej. /clientes/registrar_pos
# desde venta_form.html) son cross-origin; permitir solo origenes conocidos.
from flask_cors import CORS
CORS(app, supports_credentials=True,
     origins=["http://127.0.0.1:5002", "http://localhost:5002",
              "http://127.0.0.1:5001", "http://localhost:5001"])

from shared.db_supabase import crear_engine_auth
engine_auth = crear_engine_auth()

from shared.utils import verificar_jwt, extract_token_from_header, extract_token_from_cookie

SECRET_KEY_JWT = os.environ.get("JWT_SECRET_KEY") or os.environ.get("SECRET_KEY")


def _pide_json():
    """True si el cliente pidió explícitamente JSON (API/fetch), False si es
    submit nativo de formulario HTML (navegador). Misma regla que
    tienda_service._pide_json (incluye Content-Type: application/json)."""
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return True
    if request.is_json:
        return True
    acepta = request.headers.get("Accept", "")
    return "application/json" in acepta and "text/html" not in acepta


# ── Correo (portado del monolito app.py, misma lógica SMTP Gmail) ───────────
def enviar_correo(destino, asunto, cuerpo_html, cuerpo_texto=None):
    smtp_user = os.environ.get('SMTP_USER', '').strip()
    smtp_pass = os.environ.get('SMTP_PASS', '').strip()
    if not smtp_user or not smtp_pass:
        app.logger.warning("SMTP no configurado (faltan SMTP_USER/SMTP_PASS en .env).")
        return 'smtp_no_configurado'
    try:
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        import smtplib

        msg = MIMEMultipart('alternative')
        msg['Subject'] = asunto
        msg['From']    = f'Ferretería CLEOFERR <{smtp_user}>'
        msg['To']      = destino
        msg.attach(MIMEText(cuerpo_texto or '', 'plain', 'utf-8'))
        msg.attach(MIMEText(cuerpo_html, 'html', 'utf-8'))

        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=10)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [destino], msg.as_string())
        server.quit()
        app.logger.info(f"Correo enviado a {destino} (asunto: {asunto})")
        return None
    except smtplib.SMTPAuthenticationError:
        app.logger.error("Gmail SMTP: error de autenticación. "
                         "Verifica SMTP_USER y SMTP_PASS (usa contraseña de aplicación).")
        return 'smtp_auth'
    except Exception as e:
        app.logger.error(f"Error enviando correo a {destino}: {e}")
        return 'error'


def _correo_html_codigo(nombre, codigo, motivo):
    """HTML estándar (marca CLEOFERR) para correos que contienen un código."""
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;border:1px solid #ddd;border-radius:12px;overflow:hidden">
      <div style="background:linear-gradient(135deg,#1A1A2E,#4682B4);padding:24px;text-align:center">
        <h2 style="color:white;margin:0;font-size:1.4rem">🔧 Ferretería Inversiones CLEOFERR</h2>
      </div>
      <div style="padding:28px">
        <p style="color:#333;font-size:1rem">Hola <strong>{nombre}</strong>,</p>
        <p style="color:#555">{motivo}</p>
        <div style="text-align:center;margin:24px 0">
          <span style="font-size:2.8rem;font-weight:900;letter-spacing:12px;color:#4682B4;
                       background:#f0f6ff;padding:16px 24px;border-radius:12px;
                       display:inline-block;border:2px dashed #4682B4">{codigo}</span>
        </div>
        <p style="color:#888;font-size:0.85rem;text-align:center">
          ⏱ Este código es válido por <strong>10 minutos</strong>.
        </p>
        <hr style="border:none;border-top:1px solid #eee;margin:20px 0">
        <p style="color:#aaa;font-size:0.78rem;text-align:center">
          Si no solicitaste este código, puedes ignorar este mensaje.
        </p>
      </div>
    </div>
    """



def generar_token_jwt(usuario_id, correo, rol, nombre=None):
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
    if nombre:
        payload["nombre"] = nombre
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
            "SELECT u.id_usuario, u.nombres, u.email, u.contrasena, r.nombre AS rol "
            "FROM usuario u "
            "INNER JOIN rol r ON u.id_rol = r.id_rol "
            "WHERE u.email = :e"), {"e": correo.lower()})
        usuario = cursor.mappings().fetchone()
        conn.close()
        
        # Detect if this is a normal HTML form post or an API call
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
        accepts_json = "application/json" in request.headers.get("Accept", "")
        
        if usuario and bcrypt.check_password_hash(usuario["contrasena"], clave):
            token = generar_token_jwt(usuario["id_usuario"], usuario["email"], usuario["rol"],
                                      nombre=usuario.get("nombres"))
            
            if is_ajax or accepts_json:
                # API/json response: return JSON with token (+ cookie para navegador)
                resp = make_response(jsonify({
                    "exito": True,
                    "token": token,
                    "mensaje": "Login exitoso",
                    "rol": usuario.rol,
                    "usuario_id": usuario.id_usuario,
                    "nombre": usuario.nombres,
                }))
                resp.set_cookie('jwt_token', token, httponly=True, secure=False,
                                samesite='Lax', path='/', max_age=8 * 3600)
                return resp
            else:
                # HTML form response: set cookie and redirect
                # Redirect to tienda_service based on user role
                host_sin_puerto = request.host.split(':')[0]
                base_tienda = f"http://{host_sin_puerto}:5002"
                if usuario.rol and usuario.rol.lower() == "cliente":
                    redirect_url = f"{base_tienda}/catalogo"
                elif usuario.rol and usuario.rol.lower() in ("administrador", "vendedor"):
                    redirect_url = f"{base_tienda}/productos"
                else:
                    redirect_url = f"{base_tienda}/catalogo"
                resp = make_response(redirect(redirect_url))
                resp.set_cookie('jwt_token', token, httponly=True, secure=False,
                                samesite='Lax', path='/', max_age=8 * 3600)
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
        # Los clientes viven en la tabla cliente (no usuario) — igual que el monolito
        cursor = conn.execute(text(
            "SELECT id_cliente, nombre, apellido, email, contrasena, activo "
            "FROM cliente WHERE email = :e"), {"e": correo.lower()})
        cliente = cursor.mappings().fetchone()
        conn.close()

        # Same HTML vs API detection
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
        accepts_json = "application/json" in request.headers.get("Accept", "")

        # Cuenta registrada pero sin verificar su correo (igual que el monolito)
        if cliente and not cliente["activo"]:
            return jsonify({
                "exito": False,
                "error": "Tu cuenta aún no está verificada. Completa el registro "
                         "con el código enviado a tu correo.",
                "cuenta_no_verificada": True,
            }), 403

        # Instancia bcrypt (no la clase) — corrección de bug
        ok = False
        if cliente:
            stored = cliente["contrasena"] or ""
            try:
                ok = bcrypt.check_password_hash(stored, contrasena)
            except (ValueError, TypeError):
                ok = False

        if ok:
            nombre_cliente = cliente["nombre"] or cliente["email"]
            token = generar_token_jwt(cliente["id_cliente"], cliente["email"], "cliente",
                                      nombre=nombre_cliente)

            if is_ajax or accepts_json:
                resp = make_response(jsonify({
                    "exito": True,
                    "token": token,
                    "mensaje": "Login cliente exitoso",
                    "usuario_id": cliente["id_cliente"],
                    "nombre": nombre_cliente,
                    "rol": "cliente",
                }))
                resp.set_cookie('jwt_token', token, httponly=True, secure=False,
                                samesite='Lax', path='/', max_age=8 * 3600)
                return resp
            else:
                resp = make_response(redirect("http://127.0.0.1:5002/catalogo"))
                resp.set_cookie('jwt_token', token, httponly=True, secure=False,
                                samesite='Lax', path='/', max_age=8 * 3600)
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
    # Borra la cookie JWT y devuelve al login del auth_service
    resp = make_response(redirect("http://127.0.0.1:5001/login"))
    resp.set_cookie('jwt_token', '', httponly=True, secure=False, samesite='Lax',
                    path='/', expires=0, max_age=0)
    return resp


@app.route("/cambiar_clave", methods=["GET", "POST"])
def cambiar_clave():
    """GET: renderiza el formulario. POST: cambia la contraseña (JWT requerido)."""
    if request.method == "GET":
        return render_template("cambiar_clave.html", error=None)

    # POST: Cambia la contraseña del usuario autenticado (JWT requerido).
    # - La clave_actual es OBLIGATORIA y se verifica contra el hash bcrypt.
    # - Tabla destino segun rol del JWT: rol 'cliente' → tabla cliente,
    #   otro → tabla usuario.
    # Codigos HTTP: 200 OK, 400 campos faltantes/no coinciden,
    # 401 token invalido o clave actual incorrecta, 404 cuenta no encontrada,
    # 500 error de BD.
    auth_header = request.headers.get("Authorization", "")
    token = extract_token_from_header(auth_header)
    if not token:
        cookie_token = extract_token_from_cookie(request.cookies.get('jwt_token', ''))
        if cookie_token:
            token = cookie_token
    if not token:
        return jsonify({"error": "Token requerido", "code": 401}), 401
    try:
        payload = verificar_jwt(token, SECRET_KEY_JWT)
    except Exception:
        return jsonify({"error": "Token inválido", "code": 401}), 401
    id_cuenta = payload.get("id_usuario")
    rol = (payload.get("rol") or "").lower()
    es_cliente = rol == "cliente"

    data = request.get_json(silent=True) or request.form
    es_json = _pide_json()

    def _resp_error_clave(msg, code):
        if not es_json:
            return render_template("cambiar_clave.html", error=msg, mensaje=None), code
        return jsonify({"ok": False, "error": msg}), code

    clave_actual = data.get("clave_actual") or ""
    clave_nueva  = data.get("clave_nueva") or data.get("nueva") or ""
    confirmar    = data.get("confirmar") or clave_nueva

    if not clave_actual or not clave_nueva:
        return _resp_error_clave("Campos requeridos: clave_actual, clave_nueva", 400)
    if clave_nueva != confirmar:
        return _resp_error_clave("Las contraseñas no coinciden", 400)

    conn = engine_auth.connect()
    try:
        # Seleccionar tabla según rol (cliente o usuario), como el monolito
        if es_cliente:
            cursor = conn.execute(text(
                "SELECT id_cliente, contrasena FROM cliente WHERE id_cliente = :id"),
                {"id": id_cuenta})
        else:
            cursor = conn.execute(text(
                "SELECT id_usuario, contrasena FROM usuario WHERE id_usuario = :id"),
                {"id": id_cuenta})
        cuenta = cursor.fetchone()
        if not cuenta:
            return _resp_error_clave("Cuenta no encontrada", 404)

        # Validar clave actual contra el hash bcrypt almacenado
        hash_actual = cuenta._mapping["contrasena"] or ""
        try:
            coincide = bcrypt.check_password_hash(hash_actual, clave_actual)
        except (ValueError, TypeError):
            coincide = False
        if not coincide:
            return _resp_error_clave("Contraseña actual incorrecta", 401)

        # Hashear y guardar la nueva contraseña
        nuevo_hash = bcrypt.generate_password_hash(clave_nueva).decode("utf-8")
        if es_cliente:
            conn.execute(text(
                "UPDATE cliente SET contrasena = :h WHERE id_cliente = :id"),
                {"h": nuevo_hash, "id": id_cuenta})
        else:
            conn.execute(text(
                "UPDATE usuario SET contrasena = :h WHERE id_usuario = :id"),
                {"h": nuevo_hash, "id": id_cuenta})
        conn.commit()
        if not es_json:
            return render_template("cambiar_clave.html", error=None,
                                   mensaje="Contraseña actualizada correctamente.")
        return jsonify({"ok": True, "mensaje": "Contraseña actualizada"}), 200
    except Exception as e:
        conn.rollback()
        app.logger.error("Error en /cambiar_clave: %s", e)
        return _resp_error_clave("Error interno al actualizar la contraseña", 500)
    finally:
        conn.close()


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

    # Implementación real: consulta la tabla cliente de DATABASE_URI_AUTH
    # (reemplaza el placeholder anterior que devolvía [] hardcodeado)
    conn = engine_auth.connect()
    try:
        cursor = conn.execute(text("""
            SELECT id_cliente, nombre, apellido, email, telefono, direccion,
                   id_tipo_documento, nro_documento, activo, origen
            FROM cliente
            ORDER BY id_cliente DESC
        """))
        clientes = []
        for r in cursor.fetchall():
            f = r._mapping
            clientes.append({
                "id_cliente": f["id_cliente"],
                "nombre": f["nombre"],
                "apellido": f["apellido"],
                "email": f["email"],
                "telefono": f["telefono"],
                "direccion": f["direccion"],
                "id_tipo_documento": f["id_tipo_documento"],
                "nro_documento": f["nro_documento"],
                "activo": f["activo"],
                "origen": f["origen"],
            })
        return jsonify({"exito": True, "clientes": clientes,
                        "total": len(clientes)}), 200
    except Exception as e:
        app.logger.error("Error en /clientes: %s", e)
        return jsonify({"error": "Error al consultar clientes", "code": 500}), 500
    finally:
        conn.close()


@app.route("/usuarios/nombres")
def usuarios_nombres():
    """Devuelve {id_usuario: nombres} para una lista de IDs separados por coma.

    Uso: GET /usuarios/nombres?ids=1,2,3
    Solo lectura (SELECT) contra la tabla usuario de DATABASE_URI_AUTH.
    Pensado para que el frontend (app.py) resuelva nombres a partir de los
    id_usuario que devuelven los endpoints de tienda_service (caja, pedidos,
    inventario), sin mezclar engines entre servicios.
    """
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

    # Parsear ids=1,2,3 → lista de enteros (ignora valores no numéricos)
    ids_raw = request.args.get("ids", "")
    ids = []
    for parte in ids_raw.split(","):
        parte = parte.strip()
        if parte.isdigit():
            ids.append(int(parte))
    if not ids:
        return jsonify({"exito": True, "nombres": {}})

    conn = engine_auth.connect()
    try:
        cursor = conn.execute(
            text("SELECT id_usuario, nombres FROM usuario WHERE id_usuario = ANY(:ids)"),
            {"ids": ids})
        nombres = {str(row._mapping["id_usuario"]): row._mapping["nombres"]
                   for row in cursor.fetchall()}
        return jsonify({"exito": True, "nombres": nombres})
    except Exception as e:
        app.logger.error("Error en /usuarios/nombres: %s", e)
        return jsonify({"error": "Error al consultar usuarios", "code": 500}), 500
    finally:
        conn.close()


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
            "SELECT id_cliente, nombre, apellido, telefono FROM cliente WHERE id_tipo_documento = :td AND nro_documento = :doc"),
            {"td": id_tipo_doc, "doc": doc})
        existente = cursor.mappings().fetchone()
        if existente:
            if telefono and not (existente["telefono"] or "").strip():
                conn.execute(text("UPDATE cliente SET telefono = :tel WHERE id_cliente = :id"), {"tel": telefono, "id": existente["id_cliente"]})
            nombre_existente = f"{existente['nombre'] or ''} {existente['apellido'] or ''}".strip()
            conn.commit()
            conn.close()
            return jsonify({"ok": True, "id_cliente": existente["id_cliente"], "nombre": nombre_existente, "ya_existia": True})
    except Exception as e:
        conn.rollback()
        conn.close()
        app.logger.error("Error al registrar cliente desde el POS: %s", e)
        return jsonify({"ok": False, "error": "No se pudo guardar el cliente (error interno)."}), 500
    nombre_db = nombre
    apellido_db = apellido
    if not apellido_db and tipo == "boleta":
        partes = nombre.split()
        if len(partes) >= 2:
            nombre_db = partes[0]
            apellido_db = " ".join(partes[1:])
    try:
        cursor = conn.execute(text(
            "INSERT INTO cliente (nombre, apellido, email, telefono, id_tipo_documento, nro_documento, direccion, contrasena, activo, origen) VALUES (:nom, :ape, NULL, :tel, :td, :doc, :dir, NULL, TRUE, 'pos') RETURNING id_cliente"),
            {"nom": nombre_db, "ape": apellido_db, "tel": telefono or None,
             "td": id_tipo_doc, "doc": doc, "dir": direccion or None})
        id_cliente = cursor.mappings().fetchone()["id_cliente"]
        conn.commit()
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
        # Instancia bcrypt (no la clase) — corrección de bug
        hash_pw = bcrypt.generate_password_hash(contrasena).decode("utf-8")
        conn = engine_auth.connect()
        try:
            conn.execute(text(
                "INSERT INTO cliente (nombre, email, telefono, direccion, contrasena, activo) "
                "VALUES (:nom, :email, :tel, :dir, :pw, TRUE)"),
                {"nom": nombre, "email": email, "tel": telefono or None,
                 "dir": direccion or None, "pw": hash_pw})
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
            conn.execute(text(
                "UPDATE cliente SET nombre = :nom, email = :email, telefono = :tel, direccion = :dir WHERE id_cliente = :id"),
                {"nom": nombre, "email": email, "tel": telefono or None,
                 "dir": direccion or None, "id": id})
            conn.commit()
            return jsonify({"exito": True, "mensaje": "Cliente actualizado."})
        except Exception as e:
            conn.rollback()
            return jsonify({"exito": False, "error": str(e)}), 500
        finally:
            try: conn.close()
            except: pass
    return jsonify({"mensaje": "Formulario de edición (implementar vista)"})


@app.route("/clientes/<int:id>")
def cliente_detalle(id):
    """Devuelve un cliente por ID (para el formulario de edición del frontend)."""
    auth_header = request.headers.get("Authorization", "")
    token = extract_token_from_header(auth_header)
    if not token:
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

    conn = engine_auth.connect()
    try:
        cursor = conn.execute(text(
            "SELECT id_cliente, nombre, apellido, email, telefono, direccion, "
            "id_tipo_documento, nro_documento, activo, origen "
            "FROM cliente WHERE id_cliente = :id"), {"id": id})
        fila = cursor.mappings().fetchone()
        if not fila:
            return jsonify({"error": "Cliente no encontrado", "code": 404}), 404
        return jsonify({"exito": True, "cliente": dict(fila)}), 200
    except Exception as e:
        app.logger.error("Error en /clientes/%s: %s", id, e)
        return jsonify({"error": "Error al consultar cliente", "code": 500}), 500
    finally:
        conn.close()


@app.route("/clientes/eliminar/<int:id>")
def eliminar_cliente(id):
    conn = engine_auth.connect()
    try:
        conn.execute(text("DELETE FROM cliente WHERE id_cliente = :id"), {"id": id})
        conn.commit()
        return jsonify({"exito": True, "mensaje": "Cliente eliminado."})
    except Exception as e:
        conn.rollback()
        return jsonify({"exito": False, "error": str(e)}), 500
    finally:
        try: conn.close()
        except: pass


# ═══════════════════════════════════════════════════════════════════
# OTP — Registro y recuperación de contraseña (portados del monolito)
# ═══════════════════════════════════════════════════════════════════
# Persistencia: tablas reales verificacion_cuenta / recuperacion_contrasena
# (hash bcrypt del OTP, expiración 10 min, máx 5 intentos fallidos,
# invalidación de códigos anteriores). Cero DDL.
# Estos 4 endpoints son PÚBLICOS (sin JWT): el usuario aún no tiene sesión.


@app.route("/registro_cliente", methods=["POST"])
def registro_cliente():
    """Registro de nuevo cliente: crea la cuenta con activo=FALSE y guarda el
    hash del código OTP en verificacion_cuenta.

    Réplica del monolito app.py:/registro_cliente. Responde JSON:
      200 {"exito": True, ...} (con "codigo_visible" si no hay SMTP)
      400 campos faltantes / dirección < 5 / contraseñas no coinciden
      409 correo ya registrado y activo
      500 error interno
    """
    import random

    data = request.get_json(silent=True) or request.form
    es_json = _pide_json()

    def _resp_error_registro(msg, code):
        if not es_json:
            return render_template("login_cliente.html",
                                   registro_activo=True, error=msg), code
        return jsonify({"exito": False, "error": msg}), code

    def _resp_exito_registro(codigo_visible=None, aviso_smtp=False, aviso_smtp_motivo=None):
        payload = {"exito": True, "correo": correo,
                   "mensaje": "Se envió el código de verificación a tu correo."}
        if not es_json:
            return render_template("login_cliente.html",
                                   verificar_activo=True, correo_verificar=correo,
                                   codigo_visible=codigo_visible,
                                   aviso_smtp=aviso_smtp,
                                   aviso_smtp_motivo=aviso_smtp_motivo)
        if codigo_visible:
            payload["codigo_visible"] = codigo_visible
            payload["aviso_smtp"] = True
            if aviso_smtp_motivo:
                payload["aviso_smtp_motivo"] = aviso_smtp_motivo
        return jsonify(payload), 200

    nombre     = (data.get("nombre") or "").strip()
    apellido   = (data.get("apellido") or "").strip()
    correo     = (data.get("correo") or data.get("email") or "").strip()
    telefono   = (data.get("telefono") or "").strip()
    direccion  = (data.get("direccion") or "").strip()
    contrasena = data.get("contrasena") or ""
    confirmar  = data.get("confirmar") or ""

    if not nombre or not correo or not contrasena:
        return _resp_error_registro("Nombre, correo y contraseña son obligatorios.", 400)
    if len(direccion) < 5:
        return _resp_error_registro(
            "La dirección es obligatoria para registrarte (mínimo 5 caracteres).", 400)
    if contrasena != confirmar:
        return _resp_error_registro("Las contraseñas no coinciden.", 400)

    codigo      = str(random.randint(100000, 999999))
    hash_pw     = bcrypt.generate_password_hash(contrasena).decode("utf-8")
    codigo_hash = bcrypt.generate_password_hash(codigo).decode("utf-8")

    conn = engine_auth.connect()
    try:
        # ¿Ya existe el correo?
        cursor = conn.execute(text(
            "SELECT id_cliente, activo FROM cliente WHERE email = :e"), {"e": correo})
        existente = cursor.mappings().fetchone()
        if existente and existente["activo"]:
            return _resp_error_registro(
                "Este correo ya está registrado. Inicia sesión.", 409)

        if existente:
            # Registro pendiente de verificación: actualizar datos del formulario
            id_cliente = existente["id_cliente"]
            conn.execute(text(
                "UPDATE cliente SET nombre = :nom, apellido = :ape, telefono = :tel, "
                "contrasena = :pw, direccion = :dir WHERE id_cliente = :id"),
                {"nom": nombre, "ape": apellido or "", "tel": telefono or None,
                 "pw": hash_pw, "dir": direccion, "id": id_cliente})
        else:
            # id_tipo_documento=1 (DNI) y nro_documento vacío ('') por defecto;
            # el formulario web no pide documento todavía
            cursor = conn.execute(text(
                "INSERT INTO cliente (nombre, apellido, email, telefono, contrasena, "
                "id_tipo_documento, nro_documento, direccion, activo) "
                "VALUES (:nom, :ape, :email, :tel, :pw, 1, '', :dir, FALSE) "
                "RETURNING id_cliente"),
                {"nom": nombre, "ape": apellido or "", "email": correo,
                 "tel": telefono or None, "pw": hash_pw, "dir": direccion})
            id_cliente = cursor.mappings().fetchone()["id_cliente"]

        # Invalidar códigos anteriores de este cliente y guardar el nuevo (solo el hash)
        conn.execute(text(
            "UPDATE verificacion_cuenta SET usado = TRUE "
            "WHERE id_cliente = :id AND usado = FALSE"), {"id": id_cliente})
        conn.execute(text(
            "INSERT INTO verificacion_cuenta (id_cliente, codigo_hash, creado_en, expira_en, usado) "
            "VALUES (:id, :hash, NOW(), NOW() + INTERVAL '10 minutes', FALSE)"),
            {"id": id_cliente, "hash": codigo_hash})
        conn.commit()
    except Exception as e:
        conn.rollback()
        import traceback
        app.logger.error(
            "Error en registro_cliente (correo=%s): %s\n%s",
            correo, e, traceback.format_exc()
        )
        if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
            msg = "Este correo o teléfono ya está registrado. Intenta iniciar sesión."
            code = 409
        elif "not null" in str(e).lower():
            msg = "Faltan datos obligatorios para crear la cuenta. Completa todos los campos."
            code = 400
        elif "verificacion_cuenta" in str(e).lower() or "relation" in str(e).lower():
            msg = "Error interno: la tabla de verificación no existe. Contacta al administrador."
            code = 500
        else:
            msg = "No se pudo iniciar el registro (error interno). Contacta al administrador."
            code = 500
        return _resp_error_registro(msg, code)
    finally:
        conn.close()

    resultado = enviar_correo(
        correo,
        f"Tu código de verificación CLEOFERR: {codigo}",
        _correo_html_codigo(nombre, codigo, "Tu código de verificación para crear tu cuenta es:"),
        f"Hola {nombre},\n\nTu código de verificación es: {codigo}\n\nVálido por 10 minutos."
    )

    if resultado == "smtp_no_configurado":
        # SMTP no configurado: modo desarrollo, mostrar el código en pantalla
        return _resp_exito_registro(codigo_visible=codigo, aviso_smtp=True)
    if resultado in ("smtp_auth", "smtp_error", "error"):
        # El código YA quedó almacenado en BD (transacción confirmada arriba).
        # Se muestra el código para no bloquear al usuario, con aviso.
        app.logger.error("No se pudo enviar el correo de verificación a %s "
                         "(resultado: %s). El código se expone al frontend.", correo, resultado)
        motivo = ("Credenciales SMTP inválidas (revisa SMTP_USER/SMTP_PASS "
                  "usando una contraseña de aplicación de Gmail)."
                  if resultado == "smtp_auth"
                  else "El servicio de correo presentó un error. Revisa el log del backend.")
        return _resp_exito_registro(codigo_visible=codigo,
                                    aviso_smtp=True, aviso_smtp_motivo=motivo)

    return _resp_exito_registro()


@app.route("/verificar_registro", methods=["POST"])
def verificar_registro():
    """Verifica el código OTP contra verificacion_cuenta y activa la cuenta.

    Réplica del monolito app.py:/verificar_registro. Responde JSON:
      200 cuenta verificada
      400 falta correo/codigo
      401 código incorrecto (incluye intentos restantes) / bloqueado
      404 no hay registro pendiente para ese correo
      410 código expirado o sin código activo
      500 error interno
    """
    data = request.get_json(silent=True) or request.form
    es_json = _pide_json()
    codigo_ingresado = (data.get("codigo") or "").strip()
    correo = (data.get("correo") or "").strip()

    def _resp_error_verif(msg, code):
        if not es_json:
            return render_template("login_cliente.html",
                                   verificar_activo=True, correo_verificar=correo,
                                   error=msg), code
        d = {"exito": False, "error": msg}
        return jsonify(d), code

    if not correo or not codigo_ingresado:
        return _resp_error_verif("Correo y código son obligatorios.", 400)

    conn = engine_auth.connect()
    try:
        # Cliente pendiente de verificación
        cursor = conn.execute(text(
            "SELECT id_cliente FROM cliente WHERE email = :e"), {"e": correo})
        cliente = cursor.mappings().fetchone()
        if not cliente:
            return _resp_error_verif("No hay un registro pendiente para este correo.", 404)
        id_cliente = cliente["id_cliente"]

        # Último código vigente no usado para ese cliente
        cursor = conn.execute(text(
            "SELECT id_verificacion, codigo_hash, expira_en, intentos_fallidos "
            "FROM verificacion_cuenta "
            "WHERE id_cliente = :id AND usado = FALSE "
            "ORDER BY creado_en DESC LIMIT 1"), {"id": id_cliente})
        verif = cursor.mappings().fetchone()

        if not verif:
            return _resp_error_verif("No hay un código activo. Solicita uno nuevo desde el registro.", 410)

        from datetime import datetime, timezone
        if verif["expira_en"] < datetime.now(timezone.utc):
            return _resp_error_verif("El código expiró. Regístrate de nuevo para recibir uno nuevo.", 410)

        # Bloqueo tras 5 intentos fallidos (mismo criterio que la recuperación)
        if verif["intentos_fallidos"] >= 5:
            conn.execute(text(
                "UPDATE verificacion_cuenta SET usado = TRUE WHERE id_verificacion = :id"),
                {"id": verif["id_verificacion"]})
            conn.commit()
            return _resp_error_verif(
                "Demasiados intentos fallidos. Regístrate de nuevo para recibir un código nuevo.", 401)

        try:
            coincide = bcrypt.check_password_hash(verif["codigo_hash"], codigo_ingresado)
        except (ValueError, TypeError):
            coincide = False

        if not coincide:
            intentos = verif["intentos_fallidos"] + 1
            conn.execute(text(
                "UPDATE verificacion_cuenta "
                "SET intentos_fallidos = :n, usado = (CASE WHEN :n >= 5 THEN TRUE ELSE usado END) "
                "WHERE id_verificacion = :id"),
                {"n": intentos, "id": verif["id_verificacion"]})
            conn.commit()
            msg = ("Demasiados intentos fallidos. Regístrate de nuevo "
                   "para recibir un código nuevo." if intentos >= 5
                   else f"Código incorrecto. Te quedan {5 - intentos} intentos.")
            if not es_json:
                return render_template("login_cliente.html",
                                       verificar_activo=True, correo_verificar=correo,
                                       error=msg), 401
            return jsonify({"exito": False, "error": msg,
                            "intentos_restantes": max(0, 5 - intentos),
                            "bloqueado": intentos >= 5}), 401

        # Código correcto: marcarlo usado y activar la cuenta
        conn.execute(text(
            "UPDATE verificacion_cuenta SET usado = TRUE WHERE id_verificacion = :id"),
            {"id": verif["id_verificacion"]})
        conn.execute(text(
            "UPDATE cliente SET activo = TRUE WHERE id_cliente = :id"),
            {"id": id_cliente})
        conn.commit()
        if not es_json:
            return render_template(
                "login_cliente.html",
                success="¡Cuenta creada y verificada! Ya puedes iniciar sesión.")
        return jsonify({"exito": True, "correo": correo,
                        "mensaje": "¡Cuenta creada y verificada! Ya puedes iniciar sesión."}), 200
    except Exception as e:
        conn.rollback()
        app.logger.error("Error en verificar_registro: %s", e)
        return _resp_error_verif("Error al verificar el código. Intenta de nuevo.", 500)
    finally:
        conn.close()


def _buscar_cuenta_por_correo(conn, correo):
    """Busca el correo en usuario y en cliente (BD Auth).
    Devuelve (tipo, dict) donde tipo es 'usuario' o 'cliente', o (None, None)."""
    cursor = conn.execute(text(
        "SELECT id_usuario, nombres FROM usuario WHERE email = :e"), {"e": correo})
    u = cursor.mappings().fetchone()
    if u:
        return "usuario", dict(u)
    cursor = conn.execute(text(
        "SELECT id_cliente, nombre FROM cliente WHERE email = :e"), {"e": correo})
    c = cursor.mappings().fetchone()
    if c:
        return "cliente", dict(c)
    return None, None


@app.route("/recuperar_contrasena", methods=["GET", "POST"])
def recuperar_contrasena():
    if request.method == "GET":
        return render_template("recuperar_contrasena.html")

    """Paso 1: recibe el correo y genera un código OTP de 6 dígitos.

    Réplica del monolito app.py:/recuperar_contrasena, incluida la regla
    anti-enumeración: SIEMPRE responde éxito genérico (200), exista o no
    la cuenta. Solo envía correo (y guarda OTP) si la cuenta existe.
      200 {"exito": True, ...} (con "codigo_visible" si no hay SMTP)
      400 falta correo
      500 error interno al procesar
    """
    import random

    data = request.get_json(silent=True) or request.form
    es_json = _pide_json()
    correo = (data.get("correo") or data.get("email") or "").strip()

    def _resp_error_rec(msg, code):
        if not es_json:
            return render_template("recuperar_contrasena.html", error=msg), code
        return jsonify({"exito": False, "error": msg}), code

    def _vista_codigo_rec(codigo_visible=None):
        """Vista del paso 2 (ingresar código) para submit nativo."""
        return render_template("recuperar_contrasena.html",
                               verificar_activo=True, correo_verificar=correo,
                               codigo_visible=codigo_visible,
                               aviso_smtp=bool(codigo_visible))

    if not correo:
        return _resp_error_rec("Ingresa tu correo electrónico.", 400)

    exito_generico = {"exito": True, "correo": correo,
                      "mensaje": "Si el correo está registrado, recibirás un código de recuperación."}

    conn = engine_auth.connect()
    try:
        tipo, cuenta = _buscar_cuenta_por_correo(conn, correo)
        if not cuenta:
            # Anti-enumeración: mensaje genérico, sin revelar si el correo existe
            if not es_json:
                return _vista_codigo_rec()
            return jsonify(exito_generico), 200

        nombre = cuenta.get("nombres") or cuenta.get("nombre") or correo
        codigo = str(random.randint(100000, 999999))
        codigo_hash = bcrypt.generate_password_hash(codigo).decode("utf-8")

        id_usuario = cuenta["id_usuario"] if tipo == "usuario" else None
        id_cliente = cuenta["id_cliente"] if tipo == "cliente" else None

        # Invalidar códigos anteriores de esta cuenta
        conn.execute(text(
            "UPDATE recuperacion_contrasena SET usado = TRUE "
            "WHERE COALESCE(id_usuario, -1) = COALESCE(:uid, -1) "
            "  AND COALESCE(id_cliente, -1) = COALESCE(:cid, -1) "
            "  AND usado = FALSE"), {"uid": id_usuario, "cid": id_cliente})
        conn.execute(text(
            "INSERT INTO recuperacion_contrasena "
            "    (id_usuario, id_cliente, codigo_hash, creado_en, expira_en, usado, ip_solicitud) "
            "VALUES (:uid, :cid, :hash, NOW(), NOW() + INTERVAL '10 minutes', FALSE, :ip)"),
            {"uid": id_usuario, "cid": id_cliente, "hash": codigo_hash,
             "ip": request.remote_addr})
        conn.commit()
    except Exception as e:
        conn.rollback()
        app.logger.error("Error en recuperar_contrasena: %s", e)
        return _resp_error_rec("No se pudo procesar la solicitud. Intenta de nuevo.", 500)
    finally:
        conn.close()

    resultado = enviar_correo(
        correo,
        f"Tu código para recuperar tu contraseña CLEOFERR: {codigo}",
        _correo_html_codigo(nombre, codigo, "Tu código para restablecer tu contraseña es:"),
        f"Hola {nombre},\n\nTu código para recuperar tu contraseña es: {codigo}\n\nVálido por 10 minutos."
    )
    if resultado == "smtp_no_configurado":
        if not es_json:
            return _vista_codigo_rec(codigo_visible=codigo)
        exito_generico["codigo_visible"] = codigo
        exito_generico["aviso_smtp"] = True
        return jsonify(exito_generico), 200
    if resultado == "smtp_auth":
        return _resp_error_rec("Error de autenticación con el correo. Contacta al administrador.", 500)
    if resultado:
        return _resp_error_rec("No se pudo enviar el correo. Intenta de nuevo.", 500)

    if not es_json:
        return _vista_codigo_rec()
    return jsonify(exito_generico), 200


@app.route("/restablecer_contrasena", methods=["POST"])
def restablecer_contrasena():
    """Paso 2: valida el OTP y cambia la contraseña (usuario o cliente).

    Réplica del monolito app.py:/restablecer_contrasena. Público (sin JWT):
    el usuario no tiene sesión. Responde JSON:
      200 contraseña actualizada (incluye "tipo_cuenta": usuario|cliente)
      400 campos faltantes / no coinciden / nueva < 6 caracteres
      401 código incorrecto (incluye intentos restantes) / bloqueado
      410 código expirado o sin código activo
      404 solicitud no válida (cuenta no encontrada)
      500 error interno
    """
    data = request.get_json(silent=True) or request.form
    es_json = _pide_json()
    correo    = (data.get("correo") or data.get("email") or "").strip()
    codigo    = (data.get("codigo") or "").strip()
    nueva     = data.get("nueva") or data.get("contrasena_nueva") or ""
    confirmar = data.get("confirmar") or ""
    origen    = (data.get("origen") or "").strip()

    def _resp_error_rest(msg, code):
        if not es_json:
            return render_template("recuperar_contrasena.html",
                                   verificar_activo=True, correo_verificar=correo,
                                   recuperar_origen=origen, error=msg), code
        return jsonify({"exito": False, "error": msg}), code

    if not correo or not codigo or not nueva:
        return _resp_error_rest("Todos los campos son obligatorios.", 400)
    if nueva != confirmar:
        return _resp_error_rest("Las contraseñas no coinciden.", 400)
    if len(nueva) < 6:
        return _resp_error_rest("La contraseña debe tener al menos 6 caracteres.", 400)

    conn = engine_auth.connect()
    try:
        tipo, cuenta = _buscar_cuenta_por_correo(conn, correo)
        if not cuenta:
            return _resp_error_rest("Solicitud no válida. Vuelve a solicitar el código.", 404)

        id_usuario = cuenta["id_usuario"] if tipo == "usuario" else None
        id_cliente = cuenta["id_cliente"] if tipo == "cliente" else None

        cursor = conn.execute(text(
            "SELECT id_recuperacion, codigo_hash, expira_en, intentos_fallidos "
            "FROM recuperacion_contrasena "
            "WHERE COALESCE(id_usuario, -1) = COALESCE(:uid, -1) "
            "  AND COALESCE(id_cliente, -1) = COALESCE(:cid, -1) "
            "  AND usado = FALSE "
            "ORDER BY creado_en DESC LIMIT 1"),
            {"uid": id_usuario, "cid": id_cliente})
        rec = cursor.mappings().fetchone()

        if not rec:
            return _resp_error_rest("No hay un código activo. Solicita uno nuevo.", 410)

        from datetime import datetime, timezone
        if rec["expira_en"] < datetime.now(timezone.utc):
            return _resp_error_rest("El código expiró. Solicita uno nuevo.", 410)

        if rec["intentos_fallidos"] >= 5:
            conn.execute(text(
                "UPDATE recuperacion_contrasena SET usado = TRUE WHERE id_recuperacion = :id"),
                {"id": rec["id_recuperacion"]})
            conn.commit()
            return _resp_error_rest("Demasiados intentos fallidos. Solicita un nuevo código.", 401)

        try:
            coincide = bcrypt.check_password_hash(rec["codigo_hash"], codigo)
        except (ValueError, TypeError):
            coincide = False

        if not coincide:
            intentos = rec["intentos_fallidos"] + 1
            conn.execute(text(
                "UPDATE recuperacion_contrasena "
                "SET intentos_fallidos = :n, usado = (CASE WHEN :n >= 5 THEN TRUE ELSE usado END) "
                "WHERE id_recuperacion = :id"),
                {"n": intentos, "id": rec["id_recuperacion"]})
            conn.commit()
            if intentos >= 5:
                return _resp_error_rest("Demasiados intentos fallidos. Solicita un nuevo código.", 401)
            return _resp_error_rest(f"Código incorrecto. Te quedan {5 - intentos} intentos.", 401)

        # Código correcto: cambiar contraseña y marcar código como usado
        nuevo_hash = bcrypt.generate_password_hash(nueva).decode("utf-8")
        if tipo == "usuario":
            conn.execute(text(
                "UPDATE usuario SET contrasena = :pw, fecha_ultimo_cambio_pwd = NOW() "
                "WHERE id_usuario = :id"), {"pw": nuevo_hash, "id": id_usuario})
        else:
            conn.execute(text(
                "UPDATE cliente SET contrasena = :pw, fecha_ultimo_cambio_pwd = NOW() "
                "WHERE id_cliente = :id"), {"pw": nuevo_hash, "id": id_cliente})
        conn.execute(text(
            "UPDATE recuperacion_contrasena SET usado = TRUE WHERE id_recuperacion = :id"),
            {"id": rec["id_recuperacion"]})
        conn.commit()

        if not es_json:
            vista = "login.html" if origen == "admin" else "login_cliente.html"
            return render_template(
                vista, success="Contraseña actualizada. Inicia sesión con tu nueva clave.")
        return jsonify({"exito": True, "tipo_cuenta": tipo,
                        "mensaje": "Contraseña actualizada. Inicia sesión con tu nueva clave."}), 200
    except Exception as e:
        conn.rollback()
        app.logger.error("Error en restablecer_contrasena: %s", e)
        return _resp_error_rest("Error al actualizar la contraseña. Intenta de nuevo.", 500)
    finally:
        conn.close()


@app.route("/")
def index():
    return jsonify({
        "mensaje": "Auth Service - endpoints: /login, /login_cliente, /logout, /cambiar_clave, /clientes",
        "puerto": 5001,
        "jwt_cookie": "Si accediste via form HTML, el token fue guardado en cookie jwt_token"
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)