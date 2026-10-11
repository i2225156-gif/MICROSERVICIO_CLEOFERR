import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, jsonify, g, make_response
from flask_bcrypt import Bcrypt
from functools import wraps
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import jwt
import secrets

load_dotenv()

# Configuración básica
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("SECRET_KEY no definida. Créla en el archivo .env.")

app.config["SESSION_TYPE"] = "null"  # No usar sesiones Flask; usaremos JWT
# Nombre de cookie de sesión propio por servicio (las cookies NO se aíslan
# por puerto en 127.0.0.1; sin esto los servicios se pisan entre sí)
app.config["SESSION_COOKIE_NAME"] = "tienda_session"

# Carpeta de imágenes de producto (igual patrón del monolito: uuid + ext)
UPLOAD_FOLDER = os.path.join(app.root_path, "static", "img")
ALLOWED_IMG_EXT = {"jpg", "jpeg", "png", "webp"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def _guardar_imagen_producto(archivo):
    """Guarda request.files['imagen'] con nombre uuid.ext. None si no viene
    o extensión inválida (se ignora en silencio, como el monolito)."""
    import uuid
    if not archivo or not archivo.filename:
        return None
    ext = archivo.filename.rsplit(".", 1)[-1].lower() if "." in archivo.filename else ""
    if ext not in ALLOWED_IMG_EXT:
        return None
    nombre = f"{uuid.uuid4().hex}.{ext}"
    archivo.save(os.path.join(UPLOAD_FOLDER, nombre))
    return nombre

bcrypt = Bcrypt(app)

# Importar engine de tienda desde módulo compartido
from shared.db_supabase import crear_engine_tienda
engine_tienda = crear_engine_tienda()

# Importar utilidades de JWT desde shared.utils
from shared.utils import verificar_jwt, extract_token_from_header

# Configuración de JWT para este servicio
SECRET_KEY_JWT = os.environ.get("SECRET_KEY")

# ── Soporte de sesión para rutas HTML (navegador) ──────────────────────────
# El frontend de tienda sirve sus propios templates. Los templates comparten
# base.html y esperan `session.usuario_id/nombre/rol` y `csrf_token`.
# Se pueblan desde el JWT (cookie jwt_token o header Authorization).
LOGIN_URL = "http://127.0.0.1:5001/login"


@app.before_request
def _cargar_sesion_desde_jwt():
    """Si hay JWT válido (cookie o header), poblar session Flask con sus datos
    para que los templates (base.html) muestren usuario/rol como en el monolito."""
    payload = _obtener_payload_jwt()
    # Flask session es cookie firmada (nombre tienda_session, ver config).
    # No hace falta session server-side: solo exponer los claims al template.
    g.jwt_payload = payload
    if payload:
        session["usuario_id"] = payload.get("id_usuario")
        session["rol"] = payload.get("rol")
        session["nombre"] = payload.get("nombre") or payload.get("correo")
    else:
        for k in ("usuario_id", "rol", "nombre"):
            session.pop(k, None)


@app.context_processor
def _ctx_csrf_tienda():
    # Las templates incluyen '{{ csrf_token|tojson }}' en JS. En tienda_service
    # no validamos CSRF (los POST de la UI pasan por app.py:5000 con su propio
    # CSRF), así que el token aquí es solo un placeholder válido para el JS.
    return {"csrf_token": secrets.token_hex(16)}


def _obtener_payload_jwt():
    """Lee el JWT del header o cookie y devuelve el payload o None."""
    token = extract_token_from_header(request.headers.get("Authorization", ""))
    if not token:
        from shared.utils import extract_token_from_cookie
        token = extract_token_from_cookie(request.cookies.get("jwt_token", ""))
    if not token:
        return None
    try:
        from shared.utils import verificar_jwt
        return verificar_jwt(token, SECRET_KEY_JWT)
    except Exception:
        return None


def _pide_json():
    """True si el cliente pidió explícitamente JSON (API), False si es navegador."""
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return True
    # fetch() suele mandar Content-Type: application/json SIN Accept;
    # tratar body JSON como petición de API (evita BUG 5: 302 a fetch).
    if request.is_json:
        return True
    acepta = request.headers.get("Accept", "")
    return "application/json" in acepta and "text/html" not in acepta


def requiere_jwt(f):
    """Decorador que protege rutas JSON verificando JWT (header o cookie)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Intentar extraer token del header Authorization: Bearer <token>
        auth_header = request.headers.get("Authorization", "")
        token = extract_token_from_header(auth_header)
        
        if not token:
            # Fallback: verificar sesión clásica (para migración gradual)
            if "usuario_id" not in session:
                return jsonify({"error": "Token de autorización requerido", "code": 401}), 401
        
        # Si hay token, verificarlo
        if token:
            try:
                payload = verificar_jwt(token, SECRET_KEY_JWT)
                # Inyectar datos del usuario en g (sin tocar engine_auth)
                g.usuario = {
                    "id": payload["id_usuario"],
                    "correo": payload["correo"],
                    "rol": payload["rol"],
                }
            except Exception as e:
                return jsonify({"error": f"Token inválido o expirado: {str(e)}", "code": 401}), 401
        
        return f(*args, **kwargs)
    return decorated_function


# ── Rutas de Catálogo ────────────────────────────────────────
@app.route("/")
def index():
    """Página principal del servicio tienda."""
    return jsonify({
        "mensaje": "Tienda Service - endpoints disponibles",
        "puerto": 5002
    })


@app.route("/catalogo")
def catalogo():
    """Catálogo de productos.
    - Navegador con JWT válido: renderiza catalogo.html con diseño.
    - API con JWT válido y Accept: application/json: JSON puro.
    - Sin JWT y HTML: redirect a http://127.0.0.1:5001/login.
    - Sin JWT y JSON: 401 Token requerido.
    """
    payload = _obtener_payload_jwt()
    if not payload:
        if _pide_json():
            return jsonify({"error": "Token requerido", "code": 401}), 401
        return redirect("http://127.0.0.1:5001/login")
    from sqlalchemy import text
    conn = engine_tienda.connect()
    cursor = conn.execute(text("""
        SELECT p.id_producto, p.nombre, p.descripcion, p.precio, p.stock, p.imagen,
               c.nombre AS categoria, m.nombre AS marca
        FROM producto p
        LEFT JOIN categoria c ON p.id_categoria = c.id_categoria
        LEFT JOIN marca m ON p.id_marca = m.id_marca
        WHERE p.activo = TRUE
        ORDER BY p.id_producto
    """))
    productos = cursor.fetchall()
    conn.close()

    lista = [
        {"id_producto": p[0], "nombre": p[1], "descripcion": p[2],
         "precio": float(p[3]), "stock": p[4], "imagen": p[5],
         "categoria": p[6], "marca": p[7]}
        for p in productos
    ]
    if _pide_json():
        return jsonify({"exito": True, "productos": lista})
    return render_template("catalogo.html", productos=lista)


@app.route("/productos")
def productos():
    """Productos (protegido por JWT).
    - Navegador sin token válido → 302 a LOGIN_URL.
    - API sin token válido → 401 JSON.
    """
    payload = _obtener_payload_jwt()
    if not payload:
        if _pide_json():
            return jsonify({"error": "Token requerido", "code": 401}), 401
        return redirect(LOGIN_URL)

    from sqlalchemy import text
    conn = engine_tienda.connect()
    cursor = conn.execute(text("SELECT p.id_producto, p.nombre, p.descripcion, p.precio, p.stock, p.imagen, c.nombre AS categoria, m.nombre AS marca FROM producto p LEFT JOIN categoria c ON p.id_categoria = c.id_categoria LEFT JOIN marca m ON p.id_marca = m.id_marca WHERE p.activo = TRUE ORDER BY p.id_producto"))
    productos = cursor.fetchall()

    if _pide_json():
        conn.close()
        return jsonify({
            "productos": [
                {
                    "id": p[0], "nombre": p[1], "descripcion": p[2], "precio": float(p[3]),
                    "stock": p[4], "categoria": p[6], "marca": p[7]
                } for p in productos
            ]
        })

    # Modo HTML: datos extra que espera productos.html (como el monolito)
    prods_lista = [
        {"id_producto": p[0], "nombre": p[1], "descripcion": p[2], "precio": float(p[3]),
         "stock": p[4], "imagen": p[5], "categoria": p[6], "marca": p[7]}
        for p in productos
    ]
    cursor = conn.execute(text("SELECT id_categoria, nombre FROM categoria"))
    categorias = [{"id_categoria": c[0], "nombre": c[1]} for c in cursor.fetchall()]
    cursor = conn.execute(text("SELECT id_marca, nombre FROM marca"))
    marcas = [{"id_marca": m[0], "nombre": m[1]} for m in cursor.fetchall()]

    pedidos_count = 0
    alertas_count = 0
    movimientos_count = 0
    bajo_stock = []
    try:
        cursor = conn.execute(text("SELECT COUNT(*) AS cnt FROM venta"))
        pedidos_count = cursor.fetchone()[0]
    except Exception:
        pass
    try:
        cursor = conn.execute(text("SELECT COUNT(*) AS cnt FROM alerta WHERE resuelta = FALSE"))
        alertas_count = cursor.fetchone()[0]
    except Exception:
        pass
    try:
        cursor = conn.execute(text("SELECT COUNT(*) AS cnt FROM inventario_movimiento WHERE DATE(fecha AT TIME ZONE 'UTC' AT TIME ZONE 'America/Lima') = CURRENT_DATE"))
        movimientos_count = cursor.fetchone()[0]
    except Exception:
        pass
    try:
        cursor = conn.execute(text("SELECT id_producto, nombre, stock, precio FROM producto WHERE stock < 15 ORDER BY stock ASC"))
        bajo_stock = [{"id_producto": b[0], "nombre": b[1], "stock": b[2], "precio": float(b[3])} for b in cursor.fetchall()]
    except Exception:
        pass
    # Datos para graficos del dashboard (series, no solo totales)
    grafico_data = {"ventas_7d": [], "top_productos": [], "estados_pedidos": []}
    try:
        cursor = conn.execute(text("""
            SELECT TO_CHAR(v.fecha AT TIME ZONE 'UTC' AT TIME ZONE 'America/Lima', 'DD/MM') AS dia,
                   COALESCE(SUM(d.cantidad * d.precio_unitario), 0) AS total
            FROM venta v JOIN detalle_venta d ON d.id_venta = v.id_venta
            WHERE v.fecha >= NOW() - INTERVAL '7 days'
            GROUP BY DATE(v.fecha AT TIME ZONE 'UTC' AT TIME ZONE 'America/Lima'), dia
            ORDER BY DATE(v.fecha AT TIME ZONE 'UTC' AT TIME ZONE 'America/Lima')
        """))
        grafico_data["ventas_7d"] = [{"dia": r._mapping["dia"], "total": float(r._mapping["total"])}
                                     for r in cursor.fetchall()]
        cursor = conn.execute(text("""
            SELECT p.nombre, SUM(d.cantidad) AS unidades
            FROM detalle_venta d JOIN producto p ON p.id_producto = d.id_producto
            GROUP BY p.nombre ORDER BY unidades DESC LIMIT 5
        """))
        grafico_data["top_productos"] = [{"nombre": r._mapping["nombre"], "unidades": int(r._mapping["unidades"])}
                                         for r in cursor.fetchall()]
        cursor = conn.execute(text("""
            SELECT ev.nombre AS estado, COUNT(*) AS cantidad
            FROM venta v JOIN estado_venta ev ON v.id_estado_venta = ev.id_estado_venta
            GROUP BY ev.nombre
        """))
        grafico_data["estados_pedidos"] = [{"estado": r._mapping["estado"], "cantidad": int(r._mapping["cantidad"])}
                                           for r in cursor.fetchall()]
    except Exception:
        app.logger.exception("Error calculando graficos del dashboard")
    conn.close()

    return render_template('productos.html',
                           productos=prods_lista, categorias=categorias, marcas=marcas,
                           pedidos_count=pedidos_count, alertas_count=alertas_count,
                           reportes_count=movimientos_count, bajo_stock=bajo_stock,
                           grafico_data=grafico_data)


@app.route("/productos/detalle/<int:id>")
def producto_detalle(id):
    """Detalle de un producto."""
    from sqlalchemy import text
    conn = engine_tienda.connect()
    cursor = conn.execute(text("SELECT p.*, c.nombre AS categoria, m.nombre AS marca FROM producto p LEFT JOIN categoria c ON p.id_categoria = c.id_categoria LEFT JOIN marca m ON p.id_marca = m.id_marca WHERE p.id_producto = :id"), {"id": id})
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return jsonify({"error": "Producto no encontrado", "code": 404}), 404
    
    # Producto detalle
    if not _pide_json():
        prod = _fila_json(row._mapping)
        return render_template("producto_detalle.html", producto=prod, movimientos=[])
    return jsonify({
        "id": row[0], "nombre": row[1], "descripcion": row[2], "precio": float(row[3]),
        "stock": row[4], "categoria": row[5], "marca": row[6]
    })


# ── Rutas de Ventas y Pedidos ────────────────────────────────
@app.route("/ventas/nueva", methods=["GET"])
def venta_nueva_form():
    """Formulario de nueva venta (requiere JWT)."""
    payload = _verificar_jwt_simple()
    if not payload:
        if not _pide_json():
            return redirect(LOGIN_URL)
        return jsonify({"error": "Token requerido", "code": 401}), 401
    g.usuario = {"id": payload["id_usuario"], "correo": payload["correo"], "rol": payload["rol"]}

    # Obtener clientes (BD Auth) y productos (BD Tienda) para el formulario
    from sqlalchemy import text
    from db_supabase import engine_auth as _engine_auth
    conn_auth = _engine_auth.connect()
    clientes = conn_auth.execute(text("SELECT id_cliente, CONCAT(nombre, ' ', COALESCE(apellido,'')) AS nombre, telefono FROM cliente WHERE activo = TRUE ORDER BY nombre")).fetchall()
    conn_auth.close()

    conn = engine_tienda.connect()
    cursor = conn.execute(text("SELECT id_producto, nombre, precio, stock FROM producto WHERE activo = TRUE AND stock > 0 ORDER BY nombre"))
    productos = cursor.fetchall()
    conn.close()

    clientes = [{"id_cliente": c[0], "nombre": c[1], "telefono": c[2]} for c in clientes]
    productos = [{"id_producto": p[0], "nombre": p[1], "precio": float(p[2]), "stock": p[3]}
                 for p in productos]

    if not _pide_json():
        return render_template("venta_form.html", clientes=clientes, productos=productos,
                               venta_token=secrets.token_hex(16))
    return jsonify({
        "clientes": clientes,
        "productos": productos
    })


@app.route("/ventas/nueva", methods=["POST"])
def venta_nueva_guardar():
    """Guardar una nueva venta (persistencia real).

    Replica la lógica del monolito app.py:/ventas/nueva POST:
      - venta 'local'  → exige caja abierta; estado final 'entregado'
      - venta 'online' → no depende de caja; estado 'pendiente'
      - INSERT venta (RETURNING id_venta)
      - Por cada ítem: valida stock, INSERT detalle_venta, UPDATE stock
      - Venta local: INSERT pago confirmado + movimiento_caja 'ingreso'
      - Comprobante opcional (boleta/factura) en savepoint (tabla opcional)

    Diferencias de arquitectura vs. monolito (es API, no vista):
      - id_usuario_vendedor sale del JWT, no de session.
      - El token anti doble-cobro (venta_token) lo maneja el frontend (app.py)
        que es el dueño de la sesión del navegador.
      - El documento del cliente para el comprobante NO se consulta a la BD
        Auth desde aquí (separación de servicios): se acepta por parámetro
        'comp_doc'; si no viene, se genera con documento vacío.
    """
    payload = _verificar_jwt_simple()
    if not payload:
        return jsonify({"error": "Token inválido o requerido", "code": 401}), 401
    id_usuario = payload.get("id_usuario")

    data = request.get_json(silent=True) or request.form
    id_cliente   = data.get("id_cliente") or None
    # Venta online: si no viene id_cliente, usar el id del cliente del JWT
    if not id_cliente and payload.get("rol") == "cliente":
        id_cliente = payload.get("id_usuario")
    tipo_venta   = data.get("tipo_venta", "local")
    metodo_pago  = data.get("metodo_pago", "efectivo")
    metodo_db    = "yape_plin" if metodo_pago == "yape" else (
                   "tarjeta"   if metodo_pago == "tarjeta" else "efectivo")
    ids_producto = data.get("ids_producto") or data.getlist("id_producto[]") \
                   if hasattr(data, "getlist") else (data.get("ids_producto") or [])
    cantidades   = data.get("cantidades") or data.getlist("cantidad[]") \
                   if hasattr(data, "getlist") else (data.get("cantidades") or [])
    comp_tipo    = (data.get("comp_tipo", "") or "").strip().lower()
    comp_doc     = (data.get("comp_doc", "") or "").strip()

    if not ids_producto:
        return jsonify({"ok": False, "error": "Debes agregar al menos un producto."}), 400

    # Las ventas LOCALES (presenciales) requieren una caja abierta;
    # las ventas online no dependen de la caja.
    # Regla de negocio: una venta LOCAL se considera ENTREGADA de inmediato
    # al confirmarse el pago (mostrador). Las ONLINE conservan su flujo
    # (pendiente → ... → entregado).
    estado_nombre = "entregado" if tipo_venta == "local" else "pendiente"

    from sqlalchemy import text
    conn = engine_tienda.connect()
    caja_activa = None
    try:
        if tipo_venta == "local":
            cursor = conn.execute(text("SELECT * FROM caja WHERE estado = 'abierta'"))
            fila_caja = cursor.fetchone()
            if not fila_caja:
                conn.close()
                if not _pide_json():
                    flash("No puedes registrar una venta local sin una caja abierta. Abre caja primero en /caja.", "danger")
                    return redirect("/ventas/nueva")
                return jsonify({
                    "ok": False,
                    "error": "No puedes registrar una venta local sin una caja abierta. "
                             "Abre caja primero en /caja."
                }), 400
            caja_activa = dict(fila_caja._mapping)

        # Crear la venta
        cursor = conn.execute(text("""
            INSERT INTO venta (id_tipo_venta, id_cliente, id_usuario_vendedor, id_estado_venta)
            VALUES ((SELECT id_tipo_venta FROM tipo_venta WHERE nombre = :tipo), :idc,
                    :uid, (SELECT id_estado_venta FROM estado_venta WHERE nombre = :estado))
            RETURNING id_venta
        """), {"tipo": tipo_venta, "idc": id_cliente, "uid": id_usuario,
               "estado": estado_nombre})
        id_venta = cursor.fetchone()._mapping["id_venta"]

        # Insertar cada ítem y descontar stock
        for id_prod, cant in zip(ids_producto, cantidades):
            try:
                cant = int(cant) if cant else 1
            except (TypeError, ValueError):
                cant = 1
            if cant <= 0:
                raise ValueError("Las cantidades deben ser mayores a cero.")
            cursor = conn.execute(text(
                "SELECT precio, stock, nombre FROM producto WHERE id_producto = :pid"),
                {"pid": id_prod})
            fila_prod = cursor.fetchone()
            if not fila_prod:
                continue
            prod = fila_prod._mapping
            # No permitir vender más stock del disponible (evita stock negativo)
            if cant > (prod["stock"] or 0):
                raise ValueError(
                    f"Stock insuficiente de \"{prod['nombre']}\" "
                    f"(disponible: {prod['stock']} unidades). Venta no registrada."
                )
            conn.execute(text("""
                INSERT INTO detalle_venta (id_venta, id_producto, cantidad, precio_unitario)
                VALUES (:idv, :pid, :cant, :precio)
            """), {"idv": id_venta, "pid": id_prod, "cant": cant,
                   "precio": prod["precio"]})
            conn.execute(text("""
                UPDATE producto SET stock = GREATEST(stock - :cant, 0)
                WHERE id_producto = :pid
            """), {"cant": cant, "pid": id_prod})

        # Registrar el pago y el ingreso en caja para ventas locales
        if tipo_venta == "local" and caja_activa:
            conn.execute(text("""
                INSERT INTO pago (id_venta, id_tipo_pago, id_caja, estado)
                VALUES (:idv, (SELECT id_tipo_pago FROM tipo_pago WHERE nombre = :mp),
                        :idcaja, 'confirmado')
            """), {"idv": id_venta, "mp": metodo_db, "idcaja": caja_activa["id_caja"]})
            conn.execute(text("""
                INSERT INTO movimiento_caja (id_caja, tipo, monto, concepto, id_usuario)
                SELECT :idcaja, 'ingreso',
                       COALESCE(SUM(cantidad * precio_unitario), 0), :concepto, :uid
                FROM detalle_venta WHERE id_venta = :idv
            """), {"idcaja": caja_activa["id_caja"],
                   "concepto": f"Venta local #{id_venta}",
                   "uid": id_usuario, "idv": id_venta})

        # ── Comprobante interno (boleta B001 / factura F001) ──
        # Sin integración SUNAT real: estado_sunat = 'no_aplica'.
        # Si este bloque opcional falla, la venta se completa igual (savepoint).
        if comp_tipo in ("boleta", "factura") and (id_cliente or comp_doc):
            import random, string
            serie   = "B001" if comp_tipo == "boleta" else "F001"
            prefijo = "B" if comp_tipo == "boleta" else "F"
            numero  = f"{prefijo}{str(id_venta).zfill(6)}-" \
                      f"{''.join(random.choices(string.digits, k=4))}"
            try:
                conn.execute(text("SAVEPOINT sp_comprobante"))
                conn.execute(text("""
                    INSERT INTO comprobante (id_venta, tipo, tipo_boleta, ruc_cliente,
                                             numero, serie, estado_sunat, enviado_correo)
                    VALUES (:idv, :tipo, :tipo_boleta, NULLIF(:doc, ''), :numero,
                            :serie, 'no_aplica', 0)
                """), {"idv": id_venta, "tipo": comp_tipo,
                       "tipo_boleta": "simple" if comp_tipo == "boleta" else None,
                       "doc": comp_doc, "numero": numero, "serie": serie})
            except Exception as e:
                app.logger.warning(
                    "No se pudo generar el comprobante interno de la venta local %s: %s",
                    id_venta, e)
                conn.execute(text("ROLLBACK TO SAVEPOINT sp_comprobante"))

        conn.commit()
        if not _pide_json():
            flash(f"Venta #{id_venta} registrada correctamente.", "success")
            return redirect("/ventas/nueva")
        return jsonify({
            "ok": True,
            "id_venta": id_venta,
            "mensaje": f"Venta #{id_venta} registrada correctamente."
        })

    except ValueError as e:
        conn.rollback()
        if not _pide_json():
            flash(str(e), "danger")
            return redirect("/ventas/nueva")
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        conn.rollback()
        app.logger.exception("Error al guardar venta: %s", e)
        if not _pide_json():
            flash(f"Error al registrar la venta: {e}", "danger")
            return redirect("/ventas/nueva")
        return jsonify({"ok": False, "error": str(e) or "Error al registrar la venta."}), 500
    finally:
        conn.close()


@app.route("/pedidos")
def pedidos():
    """Listado de pedidos/ventas (requiere JWT). Solo lectura.

    Replica la lógica del monolito app.py:/pedidos:
      - estados válidos leídos de estado_venta (activos, ordenados)
      - filtros de query string: desde, hasta, estado, q (búsqueda por
        id_venta o id_cliente)
      - ventas con total calculado (SUM detalle), LIMIT 200
      - cálculo de idx_actual, progreso y es_local_entregado por pedido

    Diferencia de arquitectura: NO consulta la BD Auth. Devuelve por cada
    pedido id_cliente e id_usuario_vendedor SIN resolver; el frontend (app.py)
    los completa vía auth_service (nombres de usuarios y datos de cliente).
    """
    payload = _verificar_jwt_simple()
    if not payload:
        return jsonify({"error": "Token inválido o requerido", "code": 401}), 401

    from sqlalchemy import text
    conn = engine_tienda.connect()
    try:
        # Estados válidos leídos de la tabla estado_venta (nunca desincronizados del HTML)
        cursor = conn.execute(text(
            "SELECT nombre FROM estado_venta WHERE activo = TRUE ORDER BY orden"))
        lista_estados = [r._mapping["nombre"] for r in cursor.fetchall()]
        PASOS = [e for e in lista_estados if e != "cancelado"]

        # ── Filtros del panel (desde la barra de filtros del template) ──
        f_desde  = (request.args.get("desde") or "").strip()
        f_hasta  = (request.args.get("hasta") or "").strip()
        f_estado = (request.args.get("estado") or "").strip()
        f_q      = (request.args.get("q") or "").strip()

        where  = []
        params = {}
        if f_desde:
            where.append("v.fecha::date >= CAST(:desde AS date)")
            params["desde"] = f_desde
        if f_hasta:
            where.append("v.fecha::date <= CAST(:hasta AS date)")
            params["hasta"] = f_hasta
        if f_estado:
            where.append("ev.nombre = :estado")
            params["estado"] = f_estado
        if f_q:
            where.append("(CAST(v.id_venta AS TEXT) ILIKE :q1 OR v.id_cliente::TEXT ILIKE :q2)")
            params["q1"] = f"%{f_q}%"
            params["q2"] = f"%{f_q}%"
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""

        # Consulta: ventas + total, sin joins cross-BD
        cursor = conn.execute(text(f"""
            SELECT
                v.id_venta      AS id_pedido,
                v.fecha AT TIME ZONE 'UTC' AT TIME ZONE 'America/Lima' AS fecha,
                tv.nombre    AS tipo_venta,
                ev.nombre    AS estado,
                v.id_cliente,
                v.id_usuario_vendedor,
                COALESCE(SUM(d.cantidad * d.precio_unitario), 0) AS total
            FROM venta v
            LEFT JOIN tipo_venta tv ON v.id_tipo_venta = tv.id_tipo_venta
            LEFT JOIN estado_venta ev ON v.id_estado_venta = ev.id_estado_venta
            LEFT JOIN detalle_venta d ON v.id_venta = d.id_venta
            {where_sql}
            GROUP BY v.id_venta, v.fecha, tv.nombre, ev.nombre,
                     v.id_cliente, v.id_usuario_vendedor
            ORDER BY v.fecha DESC
            LIMIT 200
        """), params)
        pedidos_raw = [dict(r._mapping) for r in cursor.fetchall()]

        # Cálculo por pedido (equivalente al monolito): idx_actual, progreso
        # y es_local_entregado. Depende solo del estado y tipo_venta, que ya
        # están en esta BD; no requiere datos de Auth.
        pedidos = []
        for ped in pedidos_raw:
            estado = ped.get("estado") or "pendiente"
            ped["idx_actual"] = PASOS.index(estado) if estado in PASOS else -1
            ped["progreso"] = int((ped["idx_actual"] + 1) * 20) if ped["idx_actual"] >= 0 else 0
            # Venta local ya cobrada: NO aplica el flujo de despacho/entrega.
            ped["es_local_entregado"] = (ped.get("tipo_venta") == "local" and estado == "entregado")
            pedidos.append(ped)
    except Exception as e:
        app.logger.exception("Error en /pedidos: %s", e)
        return jsonify({"error": "Error consultando pedidos", "code": 500}), 500
    finally:
        conn.close()

    # IDs a resolver por el frontend vía auth_service
    ids_clientes = sorted({p["id_cliente"] for p in pedidos if p.get("id_cliente")})
    ids_vendedores = sorted({p["id_usuario_vendedor"] for p in pedidos
                             if p.get("id_usuario_vendedor")})

    # Resolver nombres de cliente via BD Auth (cross-DB, en memoria)
    if ids_clientes:
        from db_supabase import engine_auth as _engine_auth
        conn_a = _engine_auth.connect()
        mapa_clientes = {}
        numeros_clientes = {}
        for r in conn_a.execute(text(
                "SELECT id_cliente, nombre, apellido, telefono FROM cliente WHERE id_cliente = ANY(:ids)"),
                {"ids": ids_clientes}).mappings():
            mapa_clientes[r["id_cliente"]] = f"{r['nombre'] or ''} {r['apellido'] or ''}".strip()
            numeros_clientes[r["id_cliente"]] = r["telefono"] or ""
        conn_a.close()
        for ped in pedidos:
            ped["cliente_nombre"] = mapa_clientes.get(ped.get("id_cliente"), "")
            ped["cliente_telefono"] = numeros_clientes.get(ped.get("id_cliente"), "")

    if not _pide_json():
        return render_template("pedidos.html", pedidos=pedidos, estados=lista_estados)
    return jsonify({
        "exito": True,
        "pedidos": [_fila_json(p) for p in pedidos],
        "estados": lista_estados,
        "ids_clientes": ids_clientes,
        "ids_vendedores": ids_vendedores,
    })


@app.route("/pedidos/detalle/<int:id>")
def pedido_detalle(id):
    """Detalle de un pedido/venta (requiere JWT). Solo lectura.

    Replica la lógica del monolito app.py:/pedidos/detalle/<int:id>:
      - venta + estado + tipo + total (SUM detalle)
      - ítems del detalle con nombre de producto
      - comprobante asociado (si existe, tabla opcional)
      - fases válidas de estado_venta (orden, sin 'cancelado') e idx_actual

    Diferencia de arquitectura: NO consulta la BD Auth. Devuelve los datos
    crudos con id_cliente / id_usuario_vendedor SIN resolver (nombre,
    teléfono, documento, dirección del cliente y nombre del vendedor los
    completa el frontend vía auth_service).

    Pendiente para la reescritura de app.py: el monolito generaba
    url_whatsapp_pedido a partir del teléfono del cliente; ese dato vive en
    la BD Auth, así que lo construirá el frontend cuando resuelva el cliente.
    """
    payload = _verificar_jwt_simple()
    if not payload:
        return jsonify({"error": "Token inválido o requerido", "code": 401}), 401

    from sqlalchemy import text
    conn = engine_tienda.connect()
    pedido = None
    items = []
    comprobante = None
    try:
        # Consulta: venta + total
        cursor = conn.execute(text("""
            SELECT
                v.*,
                ev.nombre AS estado,
                tv.nombre AS tipo_venta,
                COALESCE(SUM(d.cantidad * d.precio_unitario), 0) AS total
            FROM venta v
            LEFT JOIN estado_venta ev ON v.id_estado_venta = ev.id_estado_venta
            LEFT JOIN tipo_venta tv ON v.id_tipo_venta = tv.id_tipo_venta
            LEFT JOIN detalle_venta d ON v.id_venta = d.id_venta
            WHERE v.id_venta = :id
            GROUP BY v.id_venta, ev.nombre, tv.nombre
        """), {"id": id})
        fila = cursor.fetchone()
        if fila:
            pedido = dict(fila._mapping)
            pedido["id_venta"] = pedido.get("id_venta", id)

        if pedido:
            cursor = conn.execute(text("""
                SELECT d.*, p.nombre AS producto_nombre
                FROM detalle_venta d
                LEFT JOIN producto p ON d.id_producto = p.id_producto
                WHERE d.id_venta = :id
            """), {"id": id})
            items = [dict(r._mapping) for r in cursor.fetchall()]

            try:
                cursor = conn.execute(text(
                    "SELECT * FROM comprobante WHERE id_venta = :id LIMIT 1"),
                    {"id": id})
                fila_comp = cursor.fetchone()
                if fila_comp:
                    comprobante = dict(fila_comp._mapping)
            except Exception:
                comprobante = None
    except Exception as e:
        app.logger.exception("Error en /pedidos/detalle/%s: %s", id, e)
        return jsonify({"error": "Error consultando el pedido", "code": 500}), 500

    # Fases válidas leídas de la BD (misma fuente que el panel admin y el
    # cliente), de modo que el timeline siempre muestre nombres consistentes.
    PASOS = []
    try:
        cursor = conn.execute(text(
            "SELECT nombre FROM estado_venta WHERE activo = TRUE ORDER BY orden"))
        PASOS = [r._mapping["nombre"] for r in cursor.fetchall()]
    except Exception:
        PASOS = []
    finally:
        conn.close()

    PASOS = [f for f in PASOS if f != "cancelado"]
    if not PASOS:
        PASOS = ["pendiente", "confirmado", "preparando", "listo", "entregado"]
    # Calcular idx_actual en Python para evitar el error .index() en Jinja2
    estado_actual = (pedido.get("estado") or "pendiente") if pedido else "pendiente"
    idx_actual = PASOS.index(estado_actual) if estado_actual in PASOS else 0

    if not pedido:
        return jsonify({"error": "Pedido no encontrado", "code": 404}), 404

    if not _pide_json():
        return render_template("pedido_detalle.html", pedido=pedido, items=items,
                               comprobante=comprobante, idx_actual=idx_actual,
                               fases_orden=PASOS)
    return jsonify({
        "exito": True,
        "pedido": _fila_json(pedido),
        "items": [_fila_json(i) for i in items],
        "comprobante": _fila_json(comprobante) if comprobante else None,
        "id": id,
        "idx_actual": idx_actual,
        "fases_orden": PASOS,
        "estados": PASOS,
    })


@app.route("/pedidos/<int:id>/estado", methods=["POST"])
def pedido_cambiar_estado(id):
    """Vendedor/Admin cambia el estado (fase) de un pedido (requiere JWT).

    Replica la lógica del monolito app.py:/pedidos/<int:id>/estado:
      - valida que el nuevo estado exista en estado_venta con activo = TRUE
      - un único UPDATE de la columna id_estado_venta
      - SIN máquina de estados (cualquier estado activo es aceptable desde
        cualquier estado actual, igual que el monolito)
      - SIN efectos secundarios (no toca stock, caja, pago ni historial)
      - id_venta inexistente → éxito silencioso (comportamiento del monolito,
        replicado tal cual por decisión del proyecto)

    Siempre responde JSON (es API); el redirect/referrer lo maneja app.py.
    """
    payload = _verificar_jwt_simple()
    if not payload:
        return jsonify({"error": "Token inválido o requerido", "code": 401}), 401

    from sqlalchemy import text
    data = request.get_json(silent=True) or request.form
    es_json = _pide_json()
    nuevo_estado = (data.get("estado", "") or "").strip()

    conn = engine_tienda.connect()
    try:
        # Estados válidos leídos de la BD (misma consulta que el monolito)
        cursor = conn.execute(text(
            "SELECT nombre FROM estado_venta WHERE activo = TRUE ORDER BY orden"))
        estados_validos = tuple(r._mapping["nombre"] for r in cursor.fetchall())

        if nuevo_estado not in estados_validos:
            if not es_json:
                flash(f'Estado "{nuevo_estado}" no es válido.', "danger")
                return redirect("/pedidos")
            return jsonify({"ok": False,
                            "error": f'Estado "{nuevo_estado}" no es válido.'}), 400

        conn.execute(text("""
            UPDATE venta
            SET id_estado_venta = (SELECT id_estado_venta FROM estado_venta WHERE nombre = :estado)
            WHERE id_venta = :id
        """), {"estado": nuevo_estado, "id": id})
        conn.commit()

        if not es_json:
            flash(f'Pedido #{id} actualizado a "{nuevo_estado}".', "success")
            return redirect("/pedidos")
        return jsonify({"ok": True, "estado": nuevo_estado,
                        "mensaje": f'Estado actualizado a "{nuevo_estado}".'})
    except Exception as e:
        conn.rollback()
        app.logger.error("Error al actualizar estado pedido #%s: %s", id, e)
        if not es_json:
            flash(f"Error de base de datos: {e}", "danger")
            return redirect("/pedidos")
        return jsonify({"ok": False, "error": f"Error de base de datos: {e}"}), 500
    finally:
        conn.close()


# ── Rutas de Caja ────────────────────────────────────────────
UMBRAL_DIFERENCIA_CAJA = 20.0


def _fila_json(fila):
    """Convierte una fila (RowMapping) a dict JSON-serializable:
    datetime/date → str ISO, Decimal → float."""
    from datetime import datetime, date
    from decimal import Decimal
    d = {}
    for k, v in dict(fila).items():
        if isinstance(v, (datetime, date)):
            d[k] = str(v)
        elif isinstance(v, Decimal):
            d[k] = float(v)
        else:
            d[k] = v
    return d


def _verificar_jwt_simple():
    """Valida JWT: primero header Authorization: Bearer, si no existe, cookie jwt_token.
    (Las cookies no se aíslan por puerto en 127.0.0.1, por eso la cookie jwt_token
    seteada por auth_service:5001 es visible aquí en :5002.)
    Devuelve el payload o None (comportamiento JSON existente: el caller decide)."""
    token = extract_token_from_header(request.headers.get("Authorization", ""))
    if not token:
        from shared.utils import extract_token_from_cookie
        token = extract_token_from_cookie(request.cookies.get("jwt_token", ""))
    if not token:
        return None
    try:
        from shared.utils import verificar_jwt
        return verificar_jwt(token, SECRET_KEY_JWT)
    except Exception:
        return None


def _verificar_jwt_o_redirect():
    """Para rutas HTML del navegador: token válido → payload; si no → redirect a login.
    Lee header Authorization primero y cookie jwt_token como fallback."""
    token = extract_token_from_header(request.headers.get("Authorization", ""))
    if not token:
        from shared.utils import extract_token_from_cookie
        token = extract_token_from_cookie(request.cookies.get("jwt_token", ""))
    if not token:
        return None, redirect("http://127.0.0.1:5001/login")
    try:
        from shared.utils import verificar_jwt
        return verificar_jwt(token, SECRET_KEY_JWT), None
    except Exception:
        return None, redirect("http://127.0.0.1:5001/login")


@app.route("/caja")
def caja():
    """Estado de la caja (requiere JWT).

    Replica la lógica del monolito app.py:/caja:
      - caja abierta actual + sus movimientos
      - historial de últimas 10 cajas
      - resumen económico: esperado = fondo + ventas_efectivo - egresos
      - pagos digitales (yape_plin, tarjeta) separados, NO suman al esperado
    Devuelve solo id_usuario (sin nombres); el frontend los resuelve vía
    auth_service:/usuarios/nombres.
    """
    payload = _verificar_jwt_simple()
    if not payload:
        if not _pide_json():
            return redirect(LOGIN_URL)
        return jsonify({"error": "Token inválido o requerido", "code": 401}), 401

    from sqlalchemy import text
    conn = engine_tienda.connect()
    caja_abierta = None
    movimientos = []
    historial = []
    resumen = {}
    digitales_por_caja = {}
    uids = set()
    try:
        cursor = conn.execute(text("SELECT * FROM caja WHERE estado = 'abierta' LIMIT 1"))
        fila = cursor.fetchone()
        if fila:
            caja_abierta = dict(fila._mapping)
            cursor = conn.execute(text(
                "SELECT * FROM movimiento_caja WHERE id_caja = :idc ORDER BY fecha DESC"),
                {"idc": caja_abierta["id_caja"]})
            movimientos = [dict(r._mapping) for r in cursor.fetchall()]
            if caja_abierta.get("id_usuario_apertura"):
                uids.add(caja_abierta["id_usuario_apertura"])
            uids.update(m["id_usuario"] for m in movimientos if m.get("id_usuario"))

        cursor = conn.execute(text("SELECT * FROM caja ORDER BY fecha_apertura DESC LIMIT 10"))
        historial = [dict(r._mapping) for r in cursor.fetchall()]
        for h in historial:
            if h.get("id_usuario_apertura"): uids.add(h["id_usuario_apertura"])
            if h.get("id_usuario_cierre"):   uids.add(h["id_usuario_cierre"])

        # ── Resumen económico por caja (ventas LOCALES con pago confirmado) ──
        caja_ids = ([caja_abierta["id_caja"]] if caja_abierta else []) \
                 + [h["id_caja"] for h in historial]
        if caja_ids:
            cursor = conn.execute(text("""
                SELECT p.id_caja, tp.nombre AS metodo,
                       COALESCE(SUM(d.cantidad * d.precio_unitario), 0) AS total
                FROM pago p
                JOIN venta v       ON v.id_venta = p.id_venta
                JOIN tipo_venta tv ON v.id_tipo_venta = tv.id_tipo_venta
                JOIN tipo_pago tp  ON p.id_tipo_pago = tp.id_tipo_pago
                LEFT JOIN detalle_venta d ON d.id_venta = v.id_venta
                WHERE tv.nombre = 'local' AND p.estado = 'confirmado'
                  AND p.id_caja = ANY(:ids)
                GROUP BY p.id_caja, tp.nombre
            """), {"ids": caja_ids})
            ventas_por_caja = {}
            for r in cursor.fetchall():
                m = r._mapping
                ventas_por_caja.setdefault(m["id_caja"], {})[m["metodo"]] = float(m["total"] or 0)

            cursor = conn.execute(text("""
                SELECT id_caja, COALESCE(SUM(monto), 0) AS total
                FROM movimiento_caja
                WHERE id_caja = ANY(:ids) AND tipo = 'egreso'
                GROUP BY id_caja
            """), {"ids": caja_ids})
            egresos_por_caja = {r._mapping["id_caja"]: float(r._mapping["total"] or 0)
                                for r in cursor.fetchall()}

            for row in ([caja_abierta] if caja_abierta else []) + historial:
                met    = ventas_por_caja.get(row["id_caja"], {})
                fondo  = float(row.get("monto_apertura") or 0)
                ven_ef = met.get("efectivo", 0.0)
                yape   = met.get("yape_plin", 0.0)
                tar    = met.get("tarjeta", 0.0)
                egres  = egresos_por_caja.get(row["id_caja"], 0.0)
                esperado = fondo + ven_ef - egres
                digitales_por_caja[str(row["id_caja"])] = {
                    "yape": yape,
                    "tarjeta": tar,
                    "total_digital": yape + tar,
                    "ventas_efectivo": ven_ef,
                }
                if caja_abierta and row["id_caja"] == caja_abierta["id_caja"]:
                    resumen = {
                        "fondo":           fondo,
                        "ventas_efectivo": ven_ef,
                        "yape":            yape,
                        "tarjeta":         tar,
                        "total_ventas":    ven_ef + yape + tar,
                        "egresos":         egres,
                        "esperado":        esperado,
                    }
    except Exception as e:
        app.logger.exception("Error en /caja: %s", e)
        return jsonify({"error": "Error consultando caja", "code": 500}), 500
    finally:
        conn.close()

    if not _pide_json():
        return render_template("caja.html", caja=caja_abierta, movimientos=movimientos,
                               resumen=resumen, digitales=digitales_por_caja,
                               historial=historial, umbral=UMBRAL_DIFERENCIA_CAJA,
                               nombres={})
    return jsonify({
        "exito": True,
        "caja": _fila_json(caja_abierta) if caja_abierta else None,
        "movimientos": [_fila_json(m) for m in movimientos],
        "resumen": resumen,
        "digitales": digitales_por_caja,
        "historial": [_fila_json(h) for h in historial],
        "uids": sorted(uids),
        "umbral": UMBRAL_DIFERENCIA_CAJA,
    })


@app.route("/caja/abrir", methods=["POST"])
def caja_abrir():
    """Abre una caja con un monto inicial (solo puede haber UNA abierta).

    Replica la lógica del monolito app.py:/caja/abrir:
      - valida monto >= 0
      - rechaza si ya existe una caja abierta
      - INSERT en caja (RETURNING id_caja) + movimiento inicial 'ingreso'
    """
    payload = _verificar_jwt_simple()
    if not payload:
        return jsonify({"error": "Token inválido o requerido", "code": 401}), 401
    id_usuario = payload.get("id_usuario")

    data = request.get_json(silent=True) or request.form
    try:
        monto = float(data.get("monto_apertura", "0") or 0)
    except (ValueError, TypeError):
        if not _pide_json():
            flash("Monto de apertura inválido.", "danger")
            return redirect("/caja")
        return jsonify({"ok": False, "error": "Monto de apertura inválido."}), 400
    if monto < 0:
        if not _pide_json():
            flash("El monto de apertura no puede ser negativo.", "danger")
            return redirect("/caja")
        return jsonify({"ok": False, "error": "El monto de apertura no puede ser negativo."}), 400

    from sqlalchemy import text
    conn = engine_tienda.connect()
    try:
        cursor = conn.execute(text("SELECT id_caja FROM caja WHERE estado = 'abierta' LIMIT 1"))
        if cursor.fetchone():
            conn.close()
            if not _pide_json():
                flash("Ya existe una caja abierta. Ciérrala antes de abrir otra.", "warning")
                return redirect("/caja")
            return jsonify({"ok": False, "error": "Ya existe una caja abierta. Ciérrala antes de abrir otra."}), 400

        cursor = conn.execute(text("""
            INSERT INTO caja (id_usuario_apertura, monto_apertura, estado)
            VALUES (:uid, :monto, 'abierta')
            RETURNING id_caja
        """), {"uid": id_usuario, "monto": monto})
        id_caja = cursor.fetchone()._mapping["id_caja"]
        # Movimiento inicial de apertura por el monto de fondo
        # (CHECK de la tabla solo admite 'ingreso'/'egreso'; la apertura es un ingreso)
        conn.execute(text("""
            INSERT INTO movimiento_caja (id_caja, tipo, monto, concepto, id_usuario)
            VALUES (:idc, 'ingreso', :monto, 'Apertura de caja (fondo inicial)', :uid)
        """), {"idc": id_caja, "monto": monto, "uid": id_usuario})
        conn.commit()
        mensaje = f"Caja #{id_caja} abierta con S/ {monto:.2f}."
        if not _pide_json():
            flash(mensaje, "success")
            return redirect("/caja")
        return jsonify({"ok": True, "id_caja": id_caja, "mensaje": mensaje})
    except Exception as e:
        conn.rollback()
        app.logger.exception("Error abriendo caja: %s", e)
        # El índice único parcial idx_caja_una_abierta también protege esto
        if not _pide_json():
            flash("No se pudo abrir la caja (¿ya existe una abierta?).", "danger")
            return redirect("/caja")
        return jsonify({"ok": False, "error": "No se pudo abrir la caja (¿ya existe una abierta?)."}), 500
    finally:
        conn.close()


@app.route("/caja/egreso", methods=["POST"])
def caja_egreso():
    """Registra un EGRESO (gasto/salida de efectivo) de la caja abierta.
    Descuenta del efectivo esperado del cierre.

    Replica la lógica del monolito app.py:/caja/egreso.
    """
    payload = _verificar_jwt_simple()
    if not payload:
        return jsonify({"error": "Token inválido o requerido", "code": 401}), 401
    id_usuario = payload.get("id_usuario")

    data = request.get_json(silent=True) or request.form
    es_json = _pide_json()

    def _responde(ok, payload, status=200):
        if not es_json:
            flash(payload.get("mensaje") or payload.get("error"),
                  "success" if ok else "danger")
            return redirect("/caja")
        return jsonify(payload), status

    concepto = (data.get("concepto", "") or "").strip()
    try:
        monto = float(data.get("monto", "0") or 0)
    except (ValueError, TypeError):
        monto = -1
    if not concepto:
        return _responde(False, {"ok": False, "error": "El concepto del egreso es obligatorio."}, 400)
    if monto <= 0:
        return _responde(False, {"ok": False, "error": "El monto del egreso debe ser mayor que cero."}, 400)

    from sqlalchemy import text
    conn = engine_tienda.connect()
    try:
        cursor = conn.execute(text("SELECT id_caja FROM caja WHERE estado = 'abierta' LIMIT 1"))
        fila = cursor.fetchone()
        if not fila:
            conn.close()
            return _responde(False, {"ok": False, "error": "No hay ninguna caja abierta. Abre la caja para registrar egresos."}, 400)
        id_caja = fila._mapping["id_caja"]

        conn.execute(text("""
            INSERT INTO movimiento_caja (id_caja, tipo, monto, concepto, id_usuario)
            VALUES (:idc, 'egreso', :monto, :concepto, :uid)
        """), {"idc": id_caja, "monto": monto, "concepto": concepto, "uid": id_usuario})
        conn.commit()
        return _responde(True, {"ok": True, "id_caja": id_caja,
                        "mensaje": f"Egreso registrado en la caja #{id_caja}: {concepto} por S/ {monto:.2f}."})
    except Exception as e:
        conn.rollback()
        app.logger.exception("Error registrando egreso de caja: %s", e)
        return _responde(False, {"ok": False, "error": "No se pudo registrar el egreso."}, 500)
    finally:
        conn.close()


@app.route("/caja/cerrar", methods=["POST"])
def caja_cerrar():
    """Cierra la caja abierta: calcula el EFECTIVO esperado
    (fondo + ventas en efectivo − egresos) y registra la diferencia.

    Replica la lógica del monolito app.py:/caja/cerrar.
    """
    payload = _verificar_jwt_simple()
    if not payload:
        return jsonify({"error": "Token inválido o requerido", "code": 401}), 401
    id_usuario = payload.get("id_usuario")

    data = request.get_json(silent=True) or request.form
    try:
        declarado = float(data.get("monto_declarado", "0") or 0)
    except (ValueError, TypeError):
        return jsonify({"ok": False, "error": "Monto declarado inválido."}), 400
    observaciones = (data.get("observaciones", "") or "").strip() or None

    from sqlalchemy import text
    conn = engine_tienda.connect()
    try:
        cursor = conn.execute(text("SELECT * FROM caja WHERE estado = 'abierta' LIMIT 1"))
        fila = cursor.fetchone()
        if not fila:
            conn.close()
            return jsonify({"ok": False, "error": "No hay ninguna caja abierta para cerrar."}), 400
        caja_row = dict(fila._mapping)

        id_caja = caja_row["id_caja"]
        fondo   = float(caja_row.get("monto_apertura") or 0)

        # Ventas LOCALES pagadas en EFECTIVO (el único dinero físico que entra)
        cursor = conn.execute(text("""
            SELECT COALESCE(SUM(d.cantidad * d.precio_unitario), 0) AS total
            FROM pago p
            JOIN venta v       ON v.id_venta = p.id_venta
            JOIN tipo_venta tv ON v.id_tipo_venta = tv.id_tipo_venta
            JOIN tipo_pago tp  ON p.id_tipo_pago = tp.id_tipo_pago
            LEFT JOIN detalle_venta d ON d.id_venta = v.id_venta
            WHERE tv.nombre = 'local' AND p.estado = 'confirmado'
              AND p.id_caja = :idc AND tp.nombre = 'efectivo'
        """), {"idc": id_caja})
        ventas_efectivo = float(cursor.fetchone()._mapping["total"] or 0)

        # Egresos del turno (descuentan del efectivo esperado)
        cursor = conn.execute(text("""
            SELECT COALESCE(SUM(monto), 0) AS total
            FROM movimiento_caja WHERE id_caja = :idc AND tipo = 'egreso'
        """), {"idc": id_caja})
        egresos = float(cursor.fetchone()._mapping["total"] or 0)

        esperado = fondo + ventas_efectivo - egresos
        diferencia = declarado - esperado

        # Pagos DIGITALES del turno (resumen informativo; NO afectan el efectivo)
        cursor = conn.execute(text("""
            SELECT tp.nombre AS metodo, COALESCE(SUM(d.cantidad * d.precio_unitario), 0) AS total
            FROM pago p
            JOIN venta v       ON v.id_venta = p.id_venta
            JOIN tipo_venta tv ON v.id_tipo_venta = tv.id_tipo_venta
            JOIN tipo_pago tp  ON p.id_tipo_pago = tp.id_tipo_pago
            LEFT JOIN detalle_venta d ON d.id_venta = v.id_venta
            WHERE tv.nombre = 'local' AND p.estado = 'confirmado'
              AND p.id_caja = :idc AND tp.nombre IN ('yape_plin', 'tarjeta')
            GROUP BY tp.nombre
        """), {"idc": id_caja})
        digital = {r._mapping["metodo"]: float(r._mapping["total"] or 0) for r in cursor.fetchall()}
        yape, tarjeta = digital.get("yape_plin", 0.0), digital.get("tarjeta", 0.0)

        # El cierre se refleja solo en la fila de caja (sin movimiento_caja 'cierre');
        # los montos quedan en la propia caja y sus movimientos del turno.
        conn.execute(text("""
            UPDATE caja
            SET estado = 'cerrada',
                id_usuario_cierre = :uid,
                fecha_cierre = NOW(),
                monto_cierre_sistema = :esperado,
                monto_cierre_declarado = :declarado,
                diferencia = :diferencia,
                observaciones = :obs
            WHERE id_caja = :idc
        """), {"uid": id_usuario, "esperado": esperado, "declarado": declarado,
               "diferencia": diferencia, "obs": observaciones, "idc": id_caja})
        conn.commit()

        mensaje = (
            f"Caja #{id_caja} cerrada. EFECTIVO: fondo S/ {fondo:.2f} + ventas "
            f"efectivo S/ {ventas_efectivo:.2f} − egresos S/ {egresos:.2f} "
            f"= esperado S/ {esperado:.2f} | "
            f"PAGOS DIGITALES: Yape/Plin S/ {yape:.2f}, Tarjeta S/ {tarjeta:.2f} | "
            f"Diferencia: S/ {diferencia:+.2f}."
        )
        supera_umbral = abs(diferencia) > UMBRAL_DIFERENCIA_CAJA
        if supera_umbral:
            mensaje += f" ⚠ La diferencia supera el umbral (S/ {UMBRAL_DIFERENCIA_CAJA:.0f})."

        if _pide_json():
            return jsonify({
                "ok": True,
                "id_caja": id_caja,
                "fondo": fondo,
                "ventas_efectivo": ventas_efectivo,
                "egresos": egresos,
                "esperado": esperado,
                "declarado": declarado,
                "diferencia": diferencia,
                "yape": yape,
                "tarjeta": tarjeta,
                "supera_umbral": supera_umbral,
                "mensaje": mensaje,
            })
        else:
            categoria = "danger" if supera_umbral else "success"
            flash(mensaje, categoria)
            return redirect("/caja")
    except Exception as e:
        conn.rollback()
        app.logger.exception("Error cerrando caja: %s", e)
        return jsonify({"ok": False, "error": "No se pudo cerrar la caja."}), 500
    finally:
        conn.close()



# ── Rutas de Inventario ──────────────────────────────────────
@app.route("/inventario")
def inventario():
    """Listado de movimientos de inventario (requiere JWT)."""
    payload = _verificar_jwt_simple()
    if not payload:
        if not _pide_json():
            return redirect(LOGIN_URL)
        return jsonify({"error": "Token requerido", "code": 401}), 401
    g.usuario = {"id": payload["id_usuario"], "correo": payload["correo"], "rol": payload["rol"]}
    
    from sqlalchemy import text
    conn = engine_tienda.connect()
    cursor = conn.execute(text("SELECT im.id_movimiento, p.nombre AS producto, im.tipo, im.cantidad, im.fecha FROM inventario_movimiento im LEFT JOIN producto p ON im.id_producto = p.id_producto ORDER BY im.fecha DESC LIMIT 200"))
    movimientos = [dict(r._mapping) for r in cursor.fetchall()]

    if not _pide_json():
        cursor = conn.execute(text("""
            SELECT im.*, p.nombre AS producto_nombre, pr.nombre AS proveedor_nombre
            FROM inventario_movimiento im
            LEFT JOIN producto p ON im.id_producto = p.id_producto
            LEFT JOIN proveedor pr ON im.id_proveedor = pr.id_proveedor
            ORDER BY im.fecha DESC LIMIT 200
        """))
        movimientos = [dict(r._mapping) for r in cursor.fetchall()]
        cursor = conn.execute(text("SELECT id_producto, nombre, stock FROM producto WHERE activo = TRUE ORDER BY nombre"))
        productos = [_fila_json(r._mapping) for r in cursor.fetchall()]
        cursor = conn.execute(text("SELECT id_proveedor, nombre FROM proveedor ORDER BY nombre"))
        proveedores = [_fila_json(r._mapping) for r in cursor.fetchall()]
        # Nombres de usuario vienen de la BD Auth (cross-DB lo resuelve aquí en memoria)
        uids = {m["id_usuario"] for m in movimientos if m.get("id_usuario")}
        vendedores = []
        if uids:
            from db_supabase import engine_auth as _engine_auth
            conn_auth = _engine_auth.connect()
            vendedores = [{"id_usuario": r._mapping["id_usuario"], "nombres": r._mapping["nombres"]}
                          for r in conn_auth.execute(text(
                              "SELECT id_usuario, nombres FROM usuario WHERE id_usuario = ANY(:ids)"),
                              {"ids": sorted(uids)}).fetchall()]
            conn_auth.close()
        nombres_map = {v["id_usuario"]: v["nombres"] for v in vendedores}
        for m in movimientos:
            m["usuario_nombre"] = nombres_map.get(m.get("id_usuario"), "")
        conn.close()
        return render_template("inventario.html", movimientos=movimientos,
                               productos=productos, proveedores=proveedores,
                               vendedores=vendedores)
    conn.close()

    return jsonify({
        "movimientos": [_fila_json(m) for m in movimientos]
    })


@app.route("/inventario/registrar", methods=["POST"])
def registrar_movimiento():
    """Registrar movimiento de inventario (entrada/salida)."""
    payload = _verificar_jwt_simple()
    if not payload:
        if not _pide_json():
            return redirect(LOGIN_URL)
        return jsonify({"error": "Token requerido", "code": 401}), 401
    g.usuario = {"id": payload["id_usuario"], "correo": payload["correo"], "rol": payload["rol"]}
    
    data = request.get_json(silent=True) or request.form
    es_json = _pide_json()
    if not data:
        if not es_json:
            flash("No se enviaron datos", "danger")
            return redirect("/inventario")
        return jsonify({"error": "No se enviaron datos", "code": 400}), 400

    tipo = data.get("tipo")
    id_producto = data.get("id_producto")
    cantidad = int(data.get("cantidad", 0))
    id_usuario = session.get("usuario_id") or payload.get("id_usuario")

    if tipo not in ("entrada", "salida") or not id_producto or cantidad <= 0:
        if not es_json:
            flash("Parámetros inválidos", "danger")
            return redirect("/inventario")
        return jsonify({"error": "Parámetros inválidos", "code": 400}), 400
    
    # Lógica simplificada: consultar stock actual y actualizar
    from sqlalchemy import text
    conn = engine_tienda.connect()
    
    # Obtener stock actual
    cursor = conn.execute(text("SELECT stock FROM producto WHERE id_producto = :pid"), {"pid": id_producto})
    prod = cursor.fetchone()
    
    if not prod:
        conn.close()
        if not es_json:
            flash("Producto no encontrado", "danger")
            return redirect("/inventario")
        return jsonify({"error": "Producto no encontrado", "code": 404}), 404

    stock_actual = prod[0]

    if tipo == "salida" and cantidad > stock_actual:
        conn.close()
        if not es_json:
            flash(f"Stock insuficiente. Disponible: {stock_actual}", "danger")
            return redirect("/inventario")
        return jsonify({"error": f"Stock insuficiente. Disponible: {stock_actual}", "code": 400}), 400
    
    nuevo_stock = stock_actual + cantidad if tipo == "entrada" else stock_actual - cantidad
    
    try:
        conn.execute(text("UPDATE producto SET stock = :ns WHERE id_producto = :pid"), {"ns": nuevo_stock, "pid": id_producto})
        conn.execute(text(
            "INSERT INTO inventario_movimiento (tipo, id_producto, id_usuario, cantidad, fecha) VALUES (:tipo, :pid, :uid, :cant, NOW())",
            {"tipo": tipo, "pid": id_producto, "uid": id_usuario, "cant": cantidad}
        ))
        conn.commit()
        conn.close()
        if not es_json:
            flash(f"Movimiento {tipo} registrado. Nuevo stock: {nuevo_stock}", "success")
            return redirect("/inventario")
        return jsonify({"exito": True, "nuevo_stock": nuevo_stock, "mensaje": f"Movimiento {tipo} registrado"})
    except Exception as e:
        conn.rollback()
        conn.close()
        if not es_json:
            flash(f"Error al registrar movimiento: {e}", "danger")
            return redirect("/inventario")
        return jsonify({"error": str(e), "code": 500}), 500


# ── Rutas de Proveedores ─────────────────────────────────────
@app.route("/proveedores")
def proveedores():
    """Listado de proveedores (requiere JWT)."""
    payload = _verificar_jwt_simple()
    if not payload:
        if not _pide_json():
            return redirect(LOGIN_URL)
        return jsonify({"error": "Token requerido", "code": 401}), 401
    g.usuario = {"id": payload["id_usuario"], "correo": payload["correo"], "rol": payload["rol"]}
    
    from sqlalchemy import text
    conn = engine_tienda.connect()
    cursor = conn.execute(text("SELECT id_proveedor, nombre, contacto, telefono, email, direccion FROM proveedor ORDER BY nombre"))
    proveedores = [_fila_json(r._mapping) for r in cursor.fetchall()]
    conn.close()

    if not _pide_json():
        return render_template("proveedores.html", proveedores=proveedores)
    return jsonify({
        "proveedores": [{"id": p["id_proveedor"], "nombre": p["nombre"], "contacto": p["contacto"],
                         "telefono": p["telefono"], "email": p["email"]} for p in proveedores]
    })


@app.route("/proveedores/nuevo", methods=["POST"])
def nuevo_proveedor():
    """Nuevo proveedor."""
    payload = _verificar_jwt_simple()
    if not payload:
        if not _pide_json():
            return redirect(LOGIN_URL)
        return jsonify({"error": "Token requerido", "code": 401}), 401
    g.usuario = {"id": payload["id_usuario"], "correo": payload["correo"], "rol": payload["rol"]}
    
    data = request.get_json(silent=True) or request.form
    if not data or not data.get("nombre"):
        return jsonify({"error": "Nombre es obligatorio", "code": 400}), 400

    from sqlalchemy import text
    conn = engine_tienda.connect()
    try:
        conn.execute(text(
            "INSERT INTO proveedor (nombre, contacto, telefono, email, direccion) VALUES (:nombre, :contacto, :telefono, :email, :direccion)",
            {"nombre": data["nombre"], "contacto": data.get("contacto", ""), "telefono": data.get("telefono", ""),
             "email": data.get("email", ""), "direccion": data.get("direccion", "")
        }))
        conn.commit()
        conn.close()
        if not _pide_json():
            return redirect("/proveedores")
        return jsonify({"exito": True, "mensaje": "Proveedor registrado."})
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"exito": False, "error": str(e)}), 500


@app.route("/proveedores/editar/<int:id>", methods=["POST"])
def proveedor_editar_guardar(id):
    payload = _verificar_jwt_simple()
    if not payload:
        if not _pide_json():
            return redirect(LOGIN_URL)
        return jsonify({"error": "Token requerido", "code": 401}), 401
    data = request.get_json(silent=True) or request.form
    from sqlalchemy import text
    conn = engine_tienda.connect()
    try:
        conn.execute(text("""
            UPDATE proveedor SET nombre = :nombre, contacto = :contacto,
                   telefono = :telefono, email = :email, direccion = :direccion
            WHERE id_proveedor = :id
        """), {"nombre": data.get("nombre"), "contacto": data.get("contacto", ""),
               "telefono": data.get("telefono", ""), "email": data.get("email", ""),
               "direccion": data.get("direccion", ""), "id": id})
        conn.commit()
        conn.close()
        if not _pide_json():
            return redirect("/proveedores")
        return jsonify({"exito": True, "mensaje": "Proveedor actualizado."})
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"exito": False, "error": str(e)}), 500


# ── Alertas ─────────────────────────────────────────────────
@app.route("/alertas")
def alertas():
    """Listado de alertas + productos con stock bajo (requiere JWT).

    Replica la lógica del monolito app.py:/alertas:
      - productos con stock < 15 (ordenados por stock ascendente)
      - Sincronización automática: por cada producto con stock bajo SIN
        alerta pendiente (id_tipo_alerta = 1 'stock_bajo', resuelta = FALSE),
        crea una nueva alerta (prioridad 'alta' si stock < 5, sino 'media')
      - listado de todas las alertas (más recientes primero, LIMIT 200)

    Nota de comportamiento replicado tal cual: la guarda anti-duplicados es
    SELECT-then-INSERT (sin constraint ni lock). Existe una ventana de race
    condition si dos requests llegan en paralelo exacto — idéntico al monolito,
    replicado por decisión del proyecto (corregirlo requeriría DDL).
    """
    payload = _verificar_jwt_simple()
    if not payload:
        return jsonify({"error": "Token inválido o requerido", "code": 401}), 401

    from sqlalchemy import text
    conn = engine_tienda.connect()
    alertas_lista = []
    bajo_stock = []
    try:
        cursor = conn.execute(text("""
            SELECT id_producto, nombre, stock, precio
            FROM producto WHERE stock < 15 ORDER BY stock ASC
        """))
        bajo_stock = [_fila_json(r._mapping) for r in cursor.fetchall()]

        # Sincronizar: crear alerta en BD para cada producto con stock < 15
        # si no existe ya una sin resolver
        # (esquema real: tabla alerta con id_producto + id_tipo_alerta; 1 = stock_bajo)
        for p in bajo_stock:
            cursor = conn.execute(text("""
                SELECT id_alerta FROM alerta
                WHERE id_tipo_alerta = 1 AND id_producto = :pid AND resuelta = FALSE
                LIMIT 1
            """), {"pid": p["id_producto"]})
            if not cursor.fetchone():
                prioridad = "alta" if p["stock"] < 5 else "media"
                conn.execute(text("""
                    INSERT INTO alerta (id_tipo_alerta, id_producto, descripcion, prioridad, fecha)
                    VALUES (1, :pid, :desc, :prioridad, NOW())
                """), {
                    "pid": p["id_producto"],
                    "desc": f"Stock insuficiente: {p['nombre']} tiene {p['stock']} unidades (mínimo sugerido: 15)",
                    "prioridad": prioridad
                })
        conn.commit()

        cursor = conn.execute(text(
            "SELECT alerta.*, id_alerta AS id FROM alerta ORDER BY fecha DESC LIMIT 200"))
        alertas_raw = [dict(r._mapping) for r in cursor.fetchall()]
        alertas_lista = alertas_raw
    except Exception as e:
        # El monolito devolvía alertas=[] en silencio; aquí se registra en el
        # log (mejora de observabilidad sin cambiar el comportamiento funcional)
        app.logger.exception("Error en /alertas: %s", e)
        alertas_lista = []
    finally:
        conn.close()

    if not _pide_json():
        return render_template("alertas.html", alertas=alertas_lista, bajo_stock=bajo_stock)
    return jsonify({
        "exito": True,
        "alertas": alertas_lista,
        "bajo_stock": bajo_stock,
    })


@app.route("/alertas/resolver/<int:id>", methods=["POST"])
def alertas_resolver(id):
    """Marca una alerta como resuelta (requiere JWT).

    Replica la lógica del monolito app.py:/alertas/resolver/<int:id>:
      - un único UPDATE alerta SET resuelta = TRUE
      - id inexistente → commit silencioso de éxito (mismo criterio que
        /pedidos/<int:id>/estado, consistente con el resto de la migración)
    """
    payload = _verificar_jwt_simple()
    if not payload:
        return jsonify({"error": "Token inválido o requerido", "code": 401}), 401

    from sqlalchemy import text
    conn = engine_tienda.connect()
    try:
        conn.execute(text("UPDATE alerta SET resuelta = TRUE WHERE id_alerta = :id"),
                     {"id": id})
        conn.commit()
        return jsonify({"ok": True, "mensaje": "Alerta marcada como resuelta."})
    except Exception as e:
        conn.rollback()
        app.logger.exception("Error resolviendo alerta %s: %s", id, e)
        return jsonify({"ok": False, "error": "Error al resolver alerta."}), 500
    finally:
        conn.close()


# ── Reportes ─────────────────────────────────────────────────
# (se conserva más abajo la definición de las rutas de reportes existentes)


@app.route("/carrito/confirmar", methods=["POST"])
def carrito_confirmar():
    """Confirma el pedido del carrito (requiere JWT). Persistencia real.

    Réplica exacta de _confirmar_carrito() del monolito app.py:
      - valida que todos los productos del carrito existan y estén activos
        (el carrito puede traer IDs obsoletos si el catálogo cambió)
      - INSERT venta (tipo 'online', estado 'pendiente', num_operacion)
      - INSERT pago en savepoint sp_pago (tabla opcional; si falla no
        aborta la venta). Estado del pago: 'pendiente' (NO 'confirmado').
        Se asocia a la caja abierta del momento si existe.
      - por ítem: valida cantidad y stock, INSERT detalle_venta con precio
        de BD (nunca el que envía el cliente), UPDATE stock con GREATEST
      - INSERT comprobante en savepoint sp_comprobante (tabla opcional)
      - rollback explícito en los retornos temprano de validación (cantidad
        inválida / stock insuficiente) para igualar el comportamiento
        observable del monolito (que dependía del rollback implícito de
        finally: conn.close() en psycopg2)

    Diferencias de arquitectura (API, no vista):
      - id_cliente sale del JWT (payload["id_usuario"]), no de session.
      - El carrito mismo (session['carrito'], session['ultimo_pedido'])
        vive en app.py, dueño de la sesión del navegador. Aquí solo llegan
        los ítems ya armados.
      - Se valida rol 'cliente' desde el JWT (payload["rol"]), igual que el
        monolito lo hacía vía session: tienda_service se defiende por su
        cuenta ante llamadas directas sin pasar por app.py.
    """
    payload = _verificar_jwt_simple()
    if not payload:
        return jsonify({"error": "Token inválido o requerido", "code": 401}), 401
    if payload.get("rol") != "cliente":
        return jsonify({"ok": False,
                        "error": "Solo clientes pueden confirmar pedidos"}), 403
    id_cliente = payload.get("id_usuario")

    import random, string
    from sqlalchemy import text

    data = request.get_json(silent=True) or request.form.to_dict()
    items            = data.get("items") or []
    metodo_pago      = data.get("metodo_pago") or data.get("metodo") or "efectivo"
    tipo_comprobante = data.get("tipo_comprobante") or "boleta_simple"
    ruc              = (data.get("ruc") or "").strip() or None
    num_operacion    = (data.get("num_operacion") or "").strip() or None

    if not items:
        return jsonify({"ok": False, "error": "Carrito vacío"}), 400

    # Validar que todos los productos del carrito existan y estén activos
    # (el carrito vive en localStorage del navegador y puede traer IDs
    # obsoletos si el catálogo cambió desde que se agregaron los ítems)
    ids_items = {int(it.get("id_producto") or it.get("id") or 0) for it in items}
    conn_val = engine_tienda.connect()
    try:
        cursor_val = conn_val.execute(text(
            "SELECT id_producto, nombre, precio, stock FROM producto "
            "WHERE id_producto = ANY(:ids) AND activo = TRUE"),
            {"ids": list(ids_items)})
        prods_validos = {r._mapping["id_producto"]: dict(r._mapping)
                         for r in cursor_val.fetchall()}
    finally:
        conn_val.close()

    ids_validos = set(prods_validos)
    ids_faltantes = ids_items - ids_validos
    if ids_faltantes:
        nombres_bad = []
        for it in items:
            pid = int(it.get("id_producto") or it.get("id") or 0)
            if pid in ids_faltantes:
                nombres_bad.append(it.get("nombre") or f"producto #{pid}")
        return jsonify({"ok": False, "error": (
            "Este producto ya no está disponible: " + ", ".join(nombres_bad)
            + ". Eliminalo del carrito para continuar."
        )}), 400

    tipo_comp_db = "factura" if (ruc and len(ruc) == 11 and ruc.startswith("20")) else "boleta"
    metodo_db    = "yape_plin" if metodo_pago == "yape" else (
                   "tarjeta"   if metodo_pago == "tarjeta" else "efectivo")

    conn = engine_tienda.connect()
    try:
        # El esquema real de venta usa FKs: id_tipo_venta e id_estado_venta.
        # El método de pago se registra en la tabla pago (id_tipo_pago).
        cursor = conn.execute(text("""
            INSERT INTO venta (id_tipo_venta, id_cliente, id_estado_venta, num_operacion)
            VALUES ((SELECT id_tipo_venta FROM tipo_venta WHERE nombre = 'online'),
                    :idc,
                    (SELECT id_estado_venta FROM estado_venta WHERE nombre = 'pendiente'),
                    :numop)
            RETURNING id_venta
        """), {"idc": id_cliente, "numop": num_operacion})
        id_venta = cursor.fetchone()._mapping["id_venta"]

        try:
            # Pago en savepoint: si la tabla pago/tipo_pago no existe o falla,
            # se revierte SOLO este bloque sin abortar la venta ni el detalle.
            conn.execute(text("SAVEPOINT sp_pago"))
            cursor = conn.execute(text(
                "SELECT id_caja FROM caja WHERE estado = 'abierta' LIMIT 1"))
            fila_caja = cursor.fetchone()
            id_caja_a = fila_caja._mapping["id_caja"] if fila_caja else None
            conn.execute(text("""
                INSERT INTO pago (id_venta, id_tipo_pago, id_caja, estado)
                VALUES (:idv, (SELECT id_tipo_pago FROM tipo_pago WHERE nombre = :mp),
                        :idcaja, 'pendiente')
            """), {"idv": id_venta, "mp": metodo_db, "idcaja": id_caja_a})
        except Exception as e:
            app.logger.warning(
                "No se pudo registrar el pago del pedido %s (tabla opcional): %s",
                id_venta, e)
            conn.execute(text("ROLLBACK TO SAVEPOINT sp_pago"))

        for it in items:
            id_producto = int(it.get("id_producto") or it.get("id") or 0)
            cantidad    = int(it.get("cantidad", 1) or 1)
            if cantidad <= 0:
                # Rollback explícito: iguala el rollback implícito que el
                # monolito obtenía de finally: conn.close() (psycopg2)
                conn.rollback()
                return jsonify({"ok": False, "error": "Cantidad inválida en el carrito."}), 400
            prod_info = prods_validos.get(id_producto)
            if prod_info is None:
                continue
            if cantidad > (prod_info["stock"] or 0):
                conn.rollback()
                return jsonify({"ok": False,
                        "error": f"Stock insuficiente de \"{prod_info['nombre']}\" "
                                 f"(disponible: {prod_info['stock']} unidades)."}), 400
            # Precio del catálogo en BD (nunca el que envía el cliente)
            precio_unit = float(prod_info["precio"])
            conn.execute(text("""
                INSERT INTO detalle_venta (id_venta, id_producto, cantidad, precio_unitario)
                VALUES (:idv, :pid, :cant, :precio)
            """), {"idv": id_venta, "pid": id_producto, "cant": cantidad,
                   "precio": precio_unit})
            conn.execute(text("""
                UPDATE producto SET stock = GREATEST(stock - :cant, 0)
                WHERE id_producto = :pid
            """), {"cant": cantidad, "pid": id_producto})

        # Generar número de comprobante y guardarlo
        num_comp = "B" + str(id_venta).zfill(6) + "-" + "".join(random.choices(string.digits, k=4))
        try:
            conn.execute(text("SAVEPOINT sp_comprobante"))
            conn.execute(text("""
                INSERT INTO comprobante (id_venta, id_tipo_comprobante, numero, ruc)
                VALUES (:idv, (SELECT id_tipo_comprobante FROM tipo_comprobante
                               WHERE nombre = :tipo), :num, :ruc)
            """), {"idv": id_venta, "tipo": tipo_comp_db, "num": num_comp, "ruc": ruc})
        except Exception as e:
            app.logger.warning(
                "No se pudo generar el comprobante del pedido %s (tabla opcional): %s",
                id_venta, e)
            conn.execute(text("ROLLBACK TO SAVEPOINT sp_comprobante"))

        conn.commit()
        # session['carrito'] = {} y session['ultimo_pedido'] los gestiona app.py
        return jsonify({"ok": True, "id_pedido": id_venta})

    except Exception as e:
        conn.rollback()
        app.logger.exception("Error carrito_confirmar: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        conn.close()


# ── Reportes ─────────────────────────────────────────────────
def _resolver_rango_periodo(desde=None, hasta=None, periodo=None):
    """Resuelve (desde, hasta) segun el periodo global del dashboard.

    - 'semanal'      : ultimos 7 dias (hoy-6 .. hoy)
    - 'mensual'      : mes calendario actual (dia 1 .. hoy)
    - 'anual'        : ano actual (1 ene .. hoy)
    - 'personalizado': usa desde/hasta que vienen; si faltan, 30 dias
    Devuelve (d1: date, d2: date, periodo_normalizado: str).
    """
    from datetime import date, timedelta
    d2 = date.fromisoformat(hasta) if hasta else date.today()
    if periodo == "semanal":
        return d2 - timedelta(days=6), d2, "semanal"
    if periodo == "mensual":
        return d2.replace(day=1), d2, "mensual"
    if periodo == "anual":
        return d2.replace(month=1, day=1), d2, "anual"
    # personalizado (o sin parametro): 30 dias por defecto
    d1 = date.fromisoformat(desde) if desde else (d2 - timedelta(days=29))
    if d1 > d2:
        d1, d2 = d2, d1
    return d1, d2, "personalizado"


def _kpis_verificacion(d1, d2):
    """Dashboard de Verificacion de cuentas: % usado (TRUE) vs no usado
    (FALSE) por dia, sobre tabla verificacion_cuenta (engine_auth).

    Query que alimenta este bloque:
        SELECT creado_en::date, usado, COUNT(*)
        FROM verificacion_cuenta
        WHERE creado_en::date BETWEEN d1 AND d2
        GROUP BY 1, 2

    KPIs resumen:
      - tasa_global   = TRUE total / total del periodo * 100
      - total_codigos = TRUE + FALSE del periodo
      - sin_usar      = FALSE del periodo (codigos expirados/abandonados)
    """
    from sqlalchemy import text
    from db_supabase import engine_auth as _engine_auth

    blk = {"tasa_global": 0.0, "total_codigos": 0, "sin_usar": 0,
           "por_dia": []}  # {dia, total, t_n, t_pct, f_n, f_pct}
    conn = _engine_auth.connect()
    try:
        filas = conn.execute(text("""
            SELECT creado_en::date AS dia, usado, COUNT(*) AS n
            FROM verificacion_cuenta
            WHERE creado_en::date BETWEEN :d1 AND :d2
            GROUP BY 1, 2 ORDER BY 1
        """), {"d1": d1, "d2": d2}).fetchall()

        dias = {}
        for dia, usado, n in filas:
            key = str(dia)
            acc = dias.setdefault(key, {"dia": key, "total": 0,
                                        "t_n": 0, "t_pct": 0.0,
                                        "f_n": 0, "f_pct": 0.0})
            acc["total"] += n
            if usado:
                acc["t_n"] += n
            else:
                acc["f_n"] += n
            blk["total_codigos"] += n
        for acc in dias.values():
            if acc["total"]:
                acc["t_pct"] = round(acc["t_n"] / acc["total"] * 100, 1)
                acc["f_pct"] = round(acc["f_n"] / acc["total"] * 100, 1)
        blk["por_dia"] = list(dias.values())
        t_total = sum(x["t_n"] for x in blk["por_dia"])
        blk["sin_usar"] = blk["total_codigos"] - t_total
        blk["tasa_global"] = (round(t_total / blk["total_codigos"] * 100, 1)
                              if blk["total_codigos"] else 0.0)
        conn.close()
    except Exception:
        conn.close()
        app.logger.exception("Error calculando KPIs de verificacion")
    return blk


def _kpis_reportes(desde=None, hasta=None, periodo=None):
    """KPIs de negocio para el dashboard de Reportes, todos con SQL real
    filtrado por rango de fechas (America/Lima) y con variación % vs el
    periodo anterior de igual duración.

    Queries que alimentan cada KPI (engine_tienda):
      - Ventas totales / ticket promedio:
          SUM(d.cantidad*d.precio_unitario) y COUNT(DISTINCT v.id_venta)
          por venta en rango (tipo 'local' u 'online').
      - Margen de utilidad:
          margen = SUM( cantidad * (precio_venta - costo_promedio_entradas) )
          costo_promedio = AVG(precio_unitario) de inventario_movimiento
          (solo entradas) por producto. Margen% = margen / ventas * 100.
      - Rotación de inventario:
          unidades_vendidas_periodo / stock_actual_promedio (SUM(stock) actual
          de activos). Sin costo histórico de stock se aproxima con el stock
          vigente; el periodo anterior usa las mismas unidades de referencia.
      - Gráficos: ventas por día (línea), margen por categoría (barras),
        estado de inventario por stock_minimo (dona: sin stock / bajo / ok).
    Rango: resuelto por _resolver_rango_periodo (semanal/mensual/anual/
    personalizado). El dict incluye 'periodo' (la clave elegida) y
    'verificacion' (_kpis_verificacion, dashboard de codigos OTP).
    """
    from datetime import date, timedelta
    from sqlalchemy import text

    d1, d2, periodo = _resolver_rango_periodo(desde, hasta, periodo)
    if d1 > d2:
        d1, d2 = d2, d1
    dias = (d2 - d1).days + 1
    p2 = d1 - timedelta(days=1)          # fin del periodo anterior
    p1 = p2 - timedelta(days=dias - 1)   # inicio del periodo anterior

    k = {"desde": str(d1), "hasta": str(d2), "dias": dias,
         "periodo": periodo,
         "ventas": 0.0, "ticket": 0.0, "margen": 0.0, "margen_pct": 0.0,
         "rotacion": 0.0, "ventas_delta": None, "ticket_delta": None,
         "margen_delta": None, "rotacion_delta": None,
         "ventas_serie": [], "margen_cat": [], "inv_dona": [],
         "ventas_cat": [], "top_productos": [],
         "top_margen_max": [], "top_margen_min": [],
         "dias_stock": None, "margen_cobertura": 0.0}
    conn = engine_tienda.connect()
    try:
        def _totales(a, b):
            """(total_ventas, num_ventas, unidades) en [a, b]."""
            r = conn.execute(text("""
                SELECT COALESCE(SUM(d.cantidad * d.precio_unitario), 0) AS total,
                       COUNT(DISTINCT d.id_venta) AS n_ventas,
                       COALESCE(SUM(d.cantidad), 0) AS unidades
                FROM detalle_venta d JOIN venta v ON v.id_venta = d.id_venta
                WHERE (v.fecha AT TIME ZONE 'UTC' AT TIME ZONE 'America/Lima')::date
                      BETWEEN :a AND :b
            """), {"a": a, "b": b}).fetchone()
            return float(r[0]), int(r[1]), float(r[2])

        def _margen(a, b):
            """Margen bruto en [a, b]: precio_venta - costo promedio entradas.
            Devuelve (margen_total, margen_pct_cubierto): el % se calcula SOLO
            sobre las lineas que tienen costo de compra registrado — si un
            producto no tiene costo, contarlo como ganancia 100% inflaria el
            margen (eso producia el '99.7%' irreal)."""
            r = conn.execute(text("""
                SELECT COALESCE(SUM(d.cantidad *
                       (d.precio_unitario - COALESCE(x.costo, 0))), 0) AS margen_total,
                       COALESCE(SUM(d.cantidad * (d.precio_unitario - x.costo))
                           FILTER (WHERE x.costo IS NOT NULL), 0) AS margen_cubierto,
                       COALESCE(SUM(d.cantidad * d.precio_unitario)
                           FILTER (WHERE x.costo IS NOT NULL), 0) AS ventas_cubiertas
                FROM detalle_venta d
                JOIN venta v ON v.id_venta = d.id_venta
                LEFT JOIN (
                    SELECT id_producto, AVG(precio_unitario) AS costo
                    FROM inventario_movimiento
                    WHERE tipo = 'entrada' AND precio_unitario IS NOT NULL
                    GROUP BY id_producto
                ) x ON x.id_producto = d.id_producto
                WHERE (v.fecha AT TIME ZONE 'UTC' AT TIME ZONE 'America/Lima')::date
                      BETWEEN :a AND :b
            """), {"a": a, "b": b}).fetchone()
            margen_total = float(r[0] or 0)
            ventas_cub = float(r[2] or 0)
            margen_pct = (float(r[1]) / ventas_cub * 100) if ventas_cub else 0.0
            return margen_total, margen_pct

        v_act, n_act, u_act = _totales(d1, d2)
        v_prev, n_prev, u_prev = _totales(p1, p2)
        m_act, m_act_pct = _margen(d1, d2)
        m_prev, m_prev_pct = _margen(p1, p2)

        # Cobertura de costos: % de lineas vendidas que tienen costo de compra
        # registrado. Si es < 100%, el margen incluye productos sin costo
        # (contados como ganancia completa) -> la interfaz lo aclara.
        rc = conn.execute(text("""
            SELECT COUNT(*) FILTER (WHERE x.costo IS NOT NULL) AS con_costo,
                   COUNT(*) AS total
            FROM detalle_venta d
            JOIN venta v ON v.id_venta = d.id_venta
            LEFT JOIN (
                SELECT id_producto, AVG(precio_unitario) AS costo
                FROM inventario_movimiento
                WHERE tipo = 'entrada' AND precio_unitario IS NOT NULL
                GROUP BY id_producto
            ) x ON x.id_producto = d.id_producto
            WHERE (v.fecha AT TIME ZONE 'UTC' AT TIME ZONE 'America/Lima')::date
                  BETWEEN :a AND :b
        """), {"a": d1, "b": d2}).fetchone()
        k["margen_cobertura"] = (round(rc[0] / rc[1] * 100, 1)
                                 if rc and rc[1] else 0.0)

        stock_actual = float(conn.execute(text(
            "SELECT COALESCE(SUM(stock), 0) FROM producto WHERE activo = TRUE")).scalar() or 0)
        rot_act = (u_act / stock_actual) if stock_actual else 0.0
        rot_prev = (u_prev / stock_actual) if stock_actual else 0.0

        # Dias para vender todo el stock actual (mas intuitivo que "vueltas"):
        # stock_actual / (unidades vendidas por dia del periodo).
        # Si no hubo ventas en el periodo -> None (en pantalla se muestra "N/A").
        udia = u_act / dias if dias else 0
        k["dias_stock"] = round(stock_actual / udia) if udia > 0 else None

        def _delta(actual, previo):
            if previo:
                return round((actual - previo) / abs(previo) * 100, 1)
            return None  # sin base de comparación

        k.update({
            "ventas": round(v_act, 2),
            "ticket": round(v_act / n_act, 2) if n_act else 0.0,
            "margen": round(m_act, 2),
            "margen_pct": round(m_act_pct, 1),
            "rotacion": round(rot_act, 2),
            "ventas_delta": _delta(v_act, v_prev),
            "ticket_delta": _delta(v_act / n_act if n_act else 0,
                                   v_prev / n_prev if n_prev else 0),
            "margen_delta": _delta(m_act, m_prev),
            "rotacion_delta": _delta(rot_act, rot_prev),
        })

        # Serie: ventas por día del periodo (línea)
        k["ventas_serie"] = [
            {"dia": str(r[0]), "total": float(r[1])}
            for r in conn.execute(text("""
                SELECT (v.fecha AT TIME ZONE 'UTC' AT TIME ZONE 'America/Lima')::date AS dia,
                       COALESCE(SUM(d.cantidad * d.precio_unitario), 0)
                FROM detalle_venta d JOIN venta v ON v.id_venta = d.id_venta
                WHERE (v.fecha AT TIME ZONE 'UTC' AT TIME ZONE 'America/Lima')::date
                      BETWEEN :a AND :b
                GROUP BY 1 ORDER BY 1
            """), {"a": d1, "b": d2}).fetchall()]

        # Barras: margen por categoría del periodo
        k["margen_cat"] = [
            {"categoria": r[0] or "Sin categoría", "margen": float(r[1])}
            for r in conn.execute(text("""
                SELECT c.nombre,
                       COALESCE(SUM(d.cantidad *
                          (d.precio_unitario - COALESCE(x.costo, 0))), 0)
                FROM detalle_venta d
                JOIN venta v ON v.id_venta = d.id_venta
                JOIN producto p ON p.id_producto = d.id_producto
                LEFT JOIN categoria c ON c.id_categoria = p.id_categoria
                LEFT JOIN (
                    SELECT id_producto, AVG(precio_unitario) AS costo
                    FROM inventario_movimiento
                    WHERE tipo = 'entrada' AND precio_unitario IS NOT NULL
                    GROUP BY id_producto
                ) x ON x.id_producto = d.id_producto
                WHERE (v.fecha AT TIME ZONE 'UTC' AT TIME ZONE 'America/Lima')::date
                      BETWEEN :a AND :b
                GROUP BY c.nombre ORDER BY 2 DESC
            """), {"a": d1, "b": d2}).fetchall()]

        # Dona: estado del inventario actual por stock_minimo
        r = conn.execute(text("""
            SELECT COUNT(*) FILTER (WHERE stock <= 0) AS sin_stock,
                   COUNT(*) FILTER (WHERE stock > 0 AND stock <= COALESCE(stock_minimo, 5)) AS bajo,
                   COUNT(*) FILTER (WHERE stock > COALESCE(stock_minimo, 5)) AS ok
            FROM producto WHERE activo = TRUE
        """)).fetchone()
        k["inv_dona"] = [{"estado": "Sin stock", "n": int(r[0])},
                         {"estado": "Stock bajo", "n": int(r[1])},
                         {"estado": "Stock OK", "n": int(r[2])}]

        # ── Dashboard VENTAS: ingresos por categoría del periodo ──
        k["ventas_cat"] = [
            {"categoria": r[0] or "Sin categoría", "total": float(r[1])}
            for r in conn.execute(text("""
                SELECT c.nombre, COALESCE(SUM(d.cantidad * d.precio_unitario), 0)
                FROM detalle_venta d
                JOIN venta v ON v.id_venta = d.id_venta
                JOIN producto p ON p.id_producto = d.id_producto
                LEFT JOIN categoria c ON c.id_categoria = p.id_categoria
                WHERE (v.fecha AT TIME ZONE 'UTC' AT TIME ZONE 'America/Lima')::date
                      BETWEEN :a AND :b
                GROUP BY c.nombre ORDER BY 2 DESC
            """), {"a": d1, "b": d2}).fetchall()]

        # Dashboard VENTAS: top productos mas vendidos del periodo
        k["top_productos"] = [
            {"nombre": r[0], "unidades": int(r[1]), "ingreso": float(r[2])}
            for r in conn.execute(text("""
                SELECT p.nombre, SUM(d.cantidad) AS unidades,
                       SUM(d.cantidad * d.precio_unitario) AS ingreso
                FROM detalle_venta d
                JOIN venta v ON v.id_venta = d.id_venta
                JOIN producto p ON p.id_producto = d.id_producto
                WHERE (v.fecha AT TIME ZONE 'UTC' AT TIME ZONE 'America/Lima')::date
                      BETWEEN :a AND :b
                GROUP BY p.nombre ORDER BY unidades DESC LIMIT 8
            """), {"a": d1, "b": d2}).fetchall()]

        # Dashboard MARGEN: productos con mayor y menor margen del periodo
        # (margen = SUM cantidad * (precio_venta - costo_promedio_entradas))
        _q_margen_prod = """
            SELECT p.nombre,
                   SUM(d.cantidad * (d.precio_unitario - COALESCE(x.costo, 0))) AS margen
            FROM detalle_venta d
            JOIN venta v ON v.id_venta = d.id_venta
            JOIN producto p ON p.id_producto = d.id_producto
            LEFT JOIN (
                SELECT id_producto, AVG(precio_unitario) AS costo
                FROM inventario_movimiento
                WHERE tipo = 'entrada' AND precio_unitario IS NOT NULL
                GROUP BY id_producto
            ) x ON x.id_producto = d.id_producto
            WHERE (v.fecha AT TIME ZONE 'UTC' AT TIME ZONE 'America/Lima')::date
                  BETWEEN :a AND :b
            GROUP BY p.nombre ORDER BY margen {orden} LIMIT 5
        """
        k["top_margen_max"] = [
            {"nombre": r[0], "margen": float(r[1])}
            for r in conn.execute(text(_q_margen_prod.format(orden="DESC")),
                                  {"a": d1, "b": d2}).fetchall()]
        k["top_margen_min"] = [
            {"nombre": r[0], "margen": float(r[1])}
            for r in conn.execute(text(_q_margen_prod.format(orden="ASC")),
                                  {"a": d1, "b": d2}).fetchall()]

        # ── Dashboard CANAL DE VENTA (online vs tienda fisica) ──
        # Fuente: venta.id_tipo_venta -> tipo_venta (1='local', 2='online').
        # Query: SUM(cantidad*precio) por canal, filtrado por rango de fechas.
        # Ayuda al propietario a ver si vende mas por web o por mostrador.
        canales = {"online": {"monto": 0.0, "n": 0},
                   "local":  {"monto": 0.0, "n": 0}}
        for r in conn.execute(text("""
            SELECT tv.nombre AS canal,
                   COALESCE(SUM(d.cantidad * d.precio_unitario), 0) AS monto,
                   COUNT(DISTINCT v.id_venta) AS n
            FROM venta v
            JOIN tipo_venta tv ON tv.id_tipo_venta = v.id_tipo_venta
            LEFT JOIN detalle_venta d ON d.id_venta = v.id_venta
            WHERE (v.fecha AT TIME ZONE 'UTC' AT TIME ZONE 'America/Lima')::date
                  BETWEEN :a AND :b
            GROUP BY tv.nombre
        """), {"a": d1, "b": d2}).fetchall():
            if r[0] in canales:
                canales[r[0]] = {"monto": float(r[1]), "n": int(r[2])}
        total_canal = canales["online"]["monto"] + canales["local"]["monto"]
        for clave in ("online", "local"):
            c = canales[clave]
            c["pct"] = round(c["monto"] / total_canal * 100, 1) if total_canal else 0.0
            c["ticket"] = round(c["monto"] / c["n"], 2) if c["n"] else 0.0
        k["canal"] = canales

        # Canal por dia (evolucion dentro del periodo) para el detalle
        k["canal_dia"] = [
            {"dia": str(r[0]), "online": float(r[1]), "local": float(r[2])}
            for r in conn.execute(text("""
                SELECT (v.fecha AT TIME ZONE 'UTC' AT TIME ZONE 'America/Lima')::date AS dia,
                       COALESCE(SUM(d.cantidad * d.precio_unitario)
                           FILTER (WHERE tv.nombre = 'online'), 0) AS online,
                       COALESCE(SUM(d.cantidad * d.precio_unitario)
                           FILTER (WHERE tv.nombre = 'local'), 0) AS local
                FROM venta v
                JOIN tipo_venta tv ON tv.id_tipo_venta = v.id_tipo_venta
                LEFT JOIN detalle_venta d ON d.id_venta = v.id_venta
                WHERE (v.fecha AT TIME ZONE 'UTC' AT TIME ZONE 'America/Lima')::date
                      BETWEEN :a AND :b
                GROUP BY 1 ORDER BY 1
            """), {"a": d1, "b": d2}).fetchall()]
        conn.close()
    except Exception:
        conn.close()
        app.logger.exception("Error calculando KPIs de reportes")

    # Dashboard de verificacion de cuentas (BD Auth): % usado vs no usado por dia
    k["verificacion"] = _kpis_verificacion(d1, d2)
    return k


@app.route("/reportes")
def reportes():
    """Dashboard de KPIs de negocio + reportes (requiere JWT).

    Renderiza SIEMPRE HTML (reportes.html) para el navegador: tarjetas de
    KPI, gráficos SVG y tabla de resultados. Responde JSON solo a
    fetch/AJAX (para recalcular dinámicamente al cambiar el rango)."""
    payload = _verificar_jwt_simple()
    if not payload:
        if not _pide_json():
            return redirect(LOGIN_URL)
        return jsonify({"error": "Token requerido", "code": 401}), 401
    g.usuario = {"id": payload["id_usuario"], "correo": payload["correo"], "rol": payload["rol"]}

    desde = request.args.get("desde") or None
    hasta = request.args.get("hasta") or None
    periodo = request.args.get("periodo") or "personalizado"
    kpis = _kpis_reportes(desde, hasta, periodo)

    resumen = {"ventas_hoy": 0, "stock_total": 0, "alertas": 0}
    try:
        from sqlalchemy import text
        conn = engine_tienda.connect()
        resumen["ventas_hoy"] = conn.execute(text(
            "SELECT COUNT(*) FROM venta WHERE DATE(fecha AT TIME ZONE 'UTC' AT TIME ZONE 'America/Lima') = CURRENT_DATE")).fetchone()[0]
        resumen["stock_total"] = conn.execute(text(
            "SELECT COALESCE(SUM(stock),0) FROM producto WHERE activo = TRUE")).fetchone()[0]
        resumen["alertas"] = conn.execute(text(
            "SELECT COUNT(*) FROM alerta WHERE resuelta = FALSE")).fetchone()[0]
        conn.close()
    except Exception:
        app.logger.exception("Error calculando resumen de reportes")

    if _pide_json():
        return jsonify({"exito": True, "kpis": kpis, "resumen": resumen})
    return render_template("reportes.html", reportes=None, resumen=resumen,
                           kpis=kpis, tipo="", desde=kpis["desde"],
                           hasta=kpis["hasta"], export_url=None)


@app.route("/reportes/pedidos/exportar")
def exportar_pedidos():
    """Exportar pedidos a Excel/CSV (requiere JWT)."""
    payload = _verificar_jwt_simple()
    if not payload:
        if not _pide_json():
            return redirect(LOGIN_URL)
        return jsonify({"error": "Token requerido", "code": 401}), 401
    g.usuario = {"id": payload["id_usuario"], "correo": payload["correo"], "rol": payload["rol"]}
    
    # Esta ruta en el servicio original usa openpyxl/csv; aquí simulamos respuesta JSON
    return jsonify({
        "mensaje": "Exportación de pedidos - en implementación real generaría archivo Excel/CSV",
        "formato": "Excel o CSV según disponibilidad de openpyxl"
    })


# ── Rutas HTML adicionales (sirven templates del frontend) ───
@app.route("/carrito")
def carrito_page():
    payload = _obtener_payload_jwt()
    if not payload:
        return redirect("http://127.0.0.1:5001/login_cliente")
    return render_template("carrito.html")


@app.route("/pago")
def pago_page():
    return render_template("pago.html", p=None, productos=[])


@app.route("/mis_pedidos")
def mis_pedidos_page():
    payload = _obtener_payload_jwt()
    if not payload:
        return redirect("http://127.0.0.1:5001/login_cliente")
    from sqlalchemy import text
    conn = engine_tienda.connect()
    cursor = conn.execute(text("""
        SELECT v.id_venta, ev.nombre AS estado,
               v.fecha AT TIME ZONE 'UTC' AT TIME ZONE 'America/Lima' AS fecha_peru,
               COALESCE(SUM(d.cantidad * d.precio_unitario), 0) AS total
        FROM venta v
        LEFT JOIN estado_venta ev ON v.id_estado_venta = ev.id_estado_venta
        LEFT JOIN detalle_venta d ON d.id_venta = v.id_venta
        WHERE v.id_cliente = :idc
        GROUP BY v.id_venta, ev.nombre
        ORDER BY v.id_venta DESC
    """), {"idc": payload["id_usuario"]})
    pedidos = [dict(r._mapping) for r in cursor.fetchall()]
    cursor = conn.execute(text("SELECT nombre FROM estado_venta WHERE activo = TRUE ORDER BY orden"))
    PASOS = [x._mapping["nombre"] for x in cursor.fetchall() if x._mapping["nombre"] != "cancelado"] or \
            ["pendiente", "confirmado", "preparando", "listo", "entregado"]
    for ped in pedidos:
        estado = ped.get("estado") or "pendiente"
        ped["idx_actual"] = PASOS.index(estado) if estado in PASOS else 0
        ped["progreso"] = int((ped["idx_actual"] + 1) * 20)
    conn.close()
    return render_template("mis_pedidos.html", pedidos=pedidos, fases_orden=PASOS)


@app.route("/productos/nuevo", methods=["GET"])
def producto_nuevo_page():
    payload, _redir = _verificar_jwt_o_redirect()
    if _redir:
        return _redir
    from sqlalchemy import text
    conn = engine_tienda.connect()
    categorias = [_fila_json(r._mapping) for r in conn.execute(text("SELECT id_categoria, nombre FROM categoria")).fetchall()]
    marcas = [_fila_json(r._mapping) for r in conn.execute(text("SELECT id_marca, nombre FROM marca")).fetchall()]
    conn.close()
    return render_template("producto_form.html", producto=None,
                           categorias=categorias, marcas=marcas)


@app.route("/productos/editar/<int:id>", methods=["GET"])
def producto_editar_page(id):
    payload, _redir = _verificar_jwt_o_redirect()
    if _redir:
        return _redir
    from sqlalchemy import text
    conn = engine_tienda.connect()
    row = conn.execute(text("SELECT * FROM producto WHERE id_producto = :id"), {"id": id}).fetchone()
    categorias = [_fila_json(r._mapping) for r in conn.execute(text("SELECT id_categoria, nombre FROM categoria")).fetchall()]
    marcas = [_fila_json(r._mapping) for r in conn.execute(text("SELECT id_marca, nombre FROM marca")).fetchall()]
    conn.close()
    if not row:
        return jsonify({"error": "Producto no encontrado", "code": 404}), 404
    return render_template("producto_form.html", producto=_fila_json(row._mapping),
                           categorias=categorias, marcas=marcas)


# ── CRUD productos guardar/actualizar/eliminar (form HTML) ─────
@app.route("/productos/guardar", methods=["POST"])
def producto_guardar():
    payload, _redir = _verificar_jwt_o_redirect()
    if _redir:
        return _redir
    from sqlalchemy import text
    f = request.form
    img = _guardar_imagen_producto(request.files.get("imagen"))
    conn = engine_tienda.connect()
    conn.execute(text("""
        INSERT INTO producto (nombre, descripcion, precio, stock, id_categoria, id_marca, imagen, activo)
        VALUES (:n, :d, :p, :s, :c, :m, :img, TRUE)
    """), {"n": f.get("nombre"), "d": f.get("descripcion") or "",
           "p": f.get("precio") or 0, "s": f.get("stock") or 0,
           "c": f.get("id_categoria") or None, "m": f.get("id_marca") or None,
           "img": img})
    conn.commit()
    conn.close()
    return redirect("/productos")


@app.route("/productos/actualizar/<int:id>", methods=["POST"])
def producto_actualizar(id):
    payload, _redir = _verificar_jwt_o_redirect()
    if _redir:
        return _redir
    from sqlalchemy import text
    f = request.form
    img = _guardar_imagen_producto(request.files.get("imagen"))
    conn = engine_tienda.connect()
    if img:
        conn.execute(text("""
            UPDATE producto SET nombre = :n, descripcion = :d, precio = :p,
                   stock = :s, id_categoria = :c, id_marca = :m, imagen = :img
            WHERE id_producto = :id
        """), {"n": f.get("nombre"), "d": f.get("descripcion") or "",
               "p": f.get("precio") or 0, "s": f.get("stock") or 0,
               "c": f.get("id_categoria") or None, "m": f.get("id_marca") or None,
               "img": img, "id": id})
    else:
        conn.execute(text("""
            UPDATE producto SET nombre = :n, descripcion = :d, precio = :p,
                   stock = :s, id_categoria = :c, id_marca = :m
            WHERE id_producto = :id
        """), {"n": f.get("nombre"), "d": f.get("descripcion") or "",
               "p": f.get("precio") or 0, "s": f.get("stock") or 0,
               "c": f.get("id_categoria") or None, "m": f.get("id_marca") or None,
               "id": id})
    conn.commit()
    conn.close()
    return redirect("/productos")


@app.route("/productos/eliminar/<int:id>")
def producto_eliminar(id):
    payload, _redir = _verificar_jwt_o_redirect()
    if _redir:
        return _redir
    from sqlalchemy import text
    conn = engine_tienda.connect()
    conn.execute(text("UPDATE producto SET activo = FALSE WHERE id_producto = :id"), {"id": id})
    conn.commit()
    conn.close()
    return redirect("/productos")


# ── CRUD proveedores (form HTML) ───────────────────────────────
@app.route("/proveedores/nuevo")
def proveedor_nuevo_page():
    payload, _redir = _verificar_jwt_o_redirect()
    if _redir:
        return _redir
    return render_template("proveedor_form.html", proveedor=None)


@app.route("/proveedores/editar/<int:id>")
def proveedor_editar_page(id):
    payload, _redir = _verificar_jwt_o_redirect()
    if _redir:
        return _redir
    from sqlalchemy import text
    conn = engine_tienda.connect()
    row = conn.execute(text("SELECT * FROM proveedor WHERE id_proveedor = :id"), {"id": id}).fetchone()
    conn.close()
    if not row:
        return redirect("/proveedores")
    return render_template("proveedor_form.html", proveedor=dict(row._mapping))


@app.route("/proveedores/eliminar/<int:id>", methods=["POST"])
def proveedor_eliminar(id):
    payload, _redir = _verificar_jwt_o_redirect()
    if _redir:
        return _redir
    from sqlalchemy import text
    conn = engine_tienda.connect()
    conn.execute(text("DELETE FROM proveedor WHERE id_proveedor = :id"), {"id": id})
    conn.commit()
    conn.close()
    return redirect("/proveedores")


# ── Clientes (panel admin; datos viven en BD Auth) ─────────────
@app.route("/clientes")
def clientes_page():
    payload, _redir = _verificar_jwt_o_redirect()
    if _redir:
        return _redir
    from sqlalchemy import text
    from db_supabase import engine_auth as _engine_auth
    conn = _engine_auth.connect()
    clientes = [dict(r._mapping) for r in conn.execute(text(
        "SELECT id_cliente, nombre, apellido, email, telefono, direccion, nro_documento "
        "FROM cliente WHERE activo = TRUE ORDER BY nombre LIMIT 300")).fetchall()]
    conn.close()
    return render_template("clientes.html", clientes=clientes)


# ── Reportes: generator + export XLSX ──────────────────────────
def _reporte_datos(tipo, desde=None, hasta=None):
    """Devuelve (nombre, columnas, filas) segun el tipo de reporte."""
    from sqlalchemy import text
    if tipo == "clientes":
        from db_supabase import engine_auth as _engine_auth
        conn = _engine_auth.connect()
        filas = conn.execute(text(
            "SELECT id_cliente, nombre, apellido, email, telefono FROM cliente WHERE activo = TRUE ORDER BY nombre")).fetchall()
        conn.close()
        return "clientes", ["id_cliente", "nombre", "apellido", "email", "telefono"], [tuple(r) for r in filas]

    conn = engine_tienda.connect()
    try:
        if tipo in ("pedidos", "ventas"):
            filas = conn.execute(text("""
                SELECT v.id_venta, v.fecha::date, ev.nombre AS estado,
                       COALESCE(SUM(d.cantidad * d.precio_unitario),0) AS total
                FROM venta v LEFT JOIN estado_venta ev ON v.id_estado_venta = ev.id_estado_venta
                LEFT JOIN detalle_venta d ON d.id_venta = v.id_venta
                WHERE v.fecha::date BETWEEN :d1 AND :d2
                GROUP BY v.id_venta, v.fecha, ev.nombre ORDER BY v.fecha DESC
            """), {"d1": desde or "2000-01-01", "d2": hasta or "2100-12-31"}).fetchall()
            return "pedidos", ["id_venta", "fecha", "estado", "total"], [tuple(r) for r in filas]
        if tipo == "dia":
            filas = conn.execute(text("""
                SELECT v.id_venta, tv.nombre, ev.nombre,
                       COALESCE(SUM(d.cantidad * d.precio_unitario),0)
                FROM venta v LEFT JOIN tipo_venta tv ON v.id_tipo_venta = tv.id_tipo_venta
                LEFT JOIN estado_venta ev ON v.id_estado_venta = ev.id_estado_venta
                LEFT JOIN detalle_venta d ON d.id_venta = v.id_venta
                WHERE v.fecha::date = CURRENT_DATE
                GROUP BY v.id_venta, tv.nombre, ev.nombre
            """)).fetchall()
            return "ventas_hoy", ["id_venta", "tipo", "estado", "total"], [tuple(r) for r in filas]
        if tipo == "productos":
            filas = conn.execute(text(
                "SELECT id_producto, nombre, precio, stock FROM producto WHERE activo = TRUE ORDER BY nombre")).fetchall()
            return "productos", ["id_producto", "nombre", "precio", "stock"], [tuple(r) for r in filas]
        if tipo == "proveedores":
            filas = conn.execute(text(
                "SELECT id_proveedor, nombre, contacto, telefono, email FROM proveedor ORDER BY nombre")).fetchall()
            return "proveedores", ["id_proveedor", "nombre", "contacto", "telefono", "email"], [tuple(r) for r in filas]
        if tipo == "inventario":
            filas = conn.execute(text("""
                SELECT im.id_movimiento, p.nombre, im.tipo, im.cantidad, im.fecha
                FROM inventario_movimiento im LEFT JOIN producto p ON im.id_producto = p.id_producto
                ORDER BY im.fecha DESC LIMIT 500
            """)).fetchall()
            return "inventario", ["id_movimiento", "producto", "tipo", "cantidad", "fecha"], [tuple(r) for r in filas]
        return None, None, None
    finally:
        conn.close()


def _exportar_xlsx(nombre, columnas, filas):
    import io
    from flask import Response
    try:
        from openpyxl import Workbook
    except ImportError:
        # Fallback a CSV (mismo criterio que el monolito _excel_response):
        # openpyxl no está instalado en este entorno.
        buf = io.StringIO()
        import csv
        w = csv.writer(buf)
        w.writerow(list(columnas))
        for f in filas:
            w.writerow([str(c) for c in f])
        return Response(buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition":
                                 f"attachment; filename={nombre}.csv"})
    wb = Workbook()
    ws = wb.active
    ws.title = nombre[:31]
    ws.append(list(columnas))
    for f in filas:
        ws.append([str(c) for c in f])
    for i, col in enumerate(columnas):
        ws.column_dimensions[chr(65 + i)].width = max(12, len(col) + 4)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(buf.getvalue(),
                    mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename={nombre}.xlsx"})


@app.route("/reportes/generar")
def reportes_generar():
    """Genera el reporte y lo muestra en la tabla Resultados de reportes.html
    (NO descarga archivo; el boton Exportar es el que descarga el .xlsx).
    Recalcula TODOS los KPIs y graficos con el rango elegido; la respuesta
    sigue siendo HTML completo (JSON solo para fetch/AJAX)."""
    payload, _redir = _verificar_jwt_o_redirect()
    if _redir:
        return _redir
    tipo = (request.args.get("tipo") or "pedidos").strip()
    desde = request.args.get("desde") or ""
    hasta = request.args.get("hasta") or ""
    periodo = (request.args.get("periodo") or "personalizado").strip()
    nombre, columnas, filas = _reporte_datos(tipo, desde or None, hasta or None)
    if nombre is None:
        if not _pide_json():
            flash(f"Tipo de reporte no soportado: {tipo}", "danger")
            return redirect("/reportes")
        return jsonify({"error": f"Tipo de reporte no soportado: {tipo}", "code": 400}), 400
    reportes = {"headers": columnas, "rows": [[str(c) for c in f] for f in filas]}
    export_url = f"/reportes/{tipo}/exportar?desde={desde}&hasta={hasta}"
    kpis = _kpis_reportes(desde or None, hasta or None, periodo)
    resumen = {"ventas_hoy": 0, "stock_total": 0, "alertas": 0}
    try:
        from sqlalchemy import text
        conn = engine_tienda.connect()
        resumen["ventas_hoy"] = conn.execute(text(
            "SELECT COUNT(*) FROM venta WHERE DATE(fecha AT TIME ZONE 'UTC' AT TIME ZONE 'America/Lima') = CURRENT_DATE")).fetchone()[0]
        resumen["stock_total"] = conn.execute(text(
            "SELECT COALESCE(SUM(stock),0) FROM producto WHERE activo = TRUE")).fetchone()[0]
        resumen["alertas"] = conn.execute(text(
            "SELECT COUNT(*) FROM alerta WHERE resuelta = FALSE")).fetchone()[0]
        conn.close()
    except Exception:
        app.logger.exception("Error calculando resumen de reportes")
    if _pide_json():
        return jsonify({"exito": True, "kpis": kpis, "resumen": resumen,
                        "reportes": reportes, "export_url": export_url})
    return render_template("reportes.html", reportes=reportes,
                           resumen=resumen, kpis=kpis, tipo=tipo,
                           desde=desde or kpis["desde"], hasta=hasta or kpis["hasta"],
                           export_url=export_url)


@app.route("/reportes/<tipo>/exportar")
@app.route("/reportes/exportar", defaults={"tipo": "pedidos"})
def reportes_exportar(tipo):
    payload, _redir = _verificar_jwt_o_redirect()
    if _redir:
        return _redir
    desde = request.args.get("desde") or None
    hasta = request.args.get("hasta") or None
    nombre, columnas, filas = _reporte_datos(tipo, desde, hasta)
    if nombre is None:
        return jsonify({"error": f"Tipo de reporte no soportado: {tipo}", "code": 400}), 400
    return _exportar_xlsx(nombre, columnas, filas)


# Reporte inventario la plantilla enlaza /reportes/inventario (vista) -> redirige a export CSV
@app.route("/reportes/inventario")
def reportes_inventario_view():
    payload, _redir = _verificar_jwt_o_redirect()
    if _redir:
        return _redir
    return redirect("/reportes/inventario/exportar")


@app.route("/alertas/programar")
def alertas_programar():
    payload, _redir = _verificar_jwt_o_redirect()
    if _redir:
        return _redir
    return redirect("/alertas")


# Compat: sincronizacion de carrito desde catalogo (opcional; el carrito real es localStorage)
@app.route("/carrito/agregar", methods=["POST"])
def carrito_agregar_api():
    return jsonify({"ok": True})


@app.route("/pedido_aceptado")
def pedido_aceptado_page():
    return render_template("pedido_aceptado.html", id_pedido=request.args.get("id", ""))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5002, debug=False)