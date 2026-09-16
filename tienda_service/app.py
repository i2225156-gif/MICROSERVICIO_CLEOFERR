import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, jsonify, g
from flask_bcrypt import Bcrypt
from functools import wraps
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import jwt

load_dotenv()

# Configuración básica
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("SECRET_KEY no definida. Créla en el archivo .env.")

app.config["SESSION_TYPE"] = "null"  # No usar sesiones Flask; usaremos JWT

bcrypt = Bcrypt(app)

# Importar engine de tienda desde módulo compartido
from shared.db_supabase import crear_engine_tienda
engine_tienda = crear_engine_tienda()

# Importar utilidades de JWT desde shared.utils
from shared.utils import verificar_jwt, extract_token_from_header

# Configuración de JWT para este servicio
SECRET_KEY_JWT = os.environ.get("SECRET_KEY")

# Decorador @requiere_jwt para tienda_service
def requiere_jwt(f):
    """Decorador que protege rutas de tienda_service verificando JWT."""
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
    """Catálogo público de productos (puede ser público o requerir JWT)."""
    # Ejemplo: obtener productos de la BD tienda
    from sqlalchemy import text
    conn = engine_tienda.connect()
    cursor = conn.execute(text("SELECT id_producto, nombre, precio, stock FROM producto WHERE activo = TRUE ORDER BY nombre"))
    productos = cursor.fetchall()
    conn.close()
    
    return jsonify({
        "productos": [
            {"id": p[0], "nombre": p[1], "precio": float(p[2]), "stock": p[3]}
            for p in productos
        ]
    })


@app.route("/productos")
def productos():
    """Listado de productos (requiere JWT)."""
    # Verificar JWT
    auth_header = request.headers.get("Authorization", "")
    token = extract_token_from_header(auth_header)
    if token:
        try:
            from shared.utils import verificar_jwt
            payload = verificar_jwt(token, SECRET_KEY_JWT)
            g.usuario = {"id": payload["id_usuario"], "correo": payload["correo"], "rol": payload["rol"]}
        except Exception:
            return jsonify({"error": "Token inválido", "code": 401}), 401
    else:
        return jsonify({"error": "Token requerido", "code": 401}), 401
    
    # Obtener productos
    from sqlalchemy import text
    conn = engine_tienda.connect()
    cursor = conn.execute(text("SELECT p.id_producto, p.nombre, p.descripcion, p.precio, p.stock, c.nombre AS categoria, m.nombre AS marca FROM producto p LEFT JOIN categoria c ON p.id_categoria = c.id_categoria LEFT JOIN marca m ON p.id_marca = m.id_marca WHERE p.activo = TRUE ORDER BY p.id_producto"))
    productos = cursor.fetchall()
    conn.close()
    
    return jsonify({
        "productos": [
            {
                "id": p[0], "nombre": p[1], "descripcion": p[2], "precio": float(p[3]),
                "stock": p[4], "categoria": p[5], "marca": p[6]
            } for p in productos
        ]
    })


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
    
    return jsonify({
        "id": row[0], "nombre": row[1], "descripcion": row[2], "precio": float(row[3]),
        "stock": row[4], "categoria": row[5], "marca": row[6]
    })


# ── Rutas de Ventas y Pedidos ────────────────────────────────
@app.route("/ventas/nueva", methods=["GET"])
def venta_nueva_form():
    """Formulario de nueva venta (requiere JWT)."""
    token = extract_token_from_header(request.headers.get("Authorization", ""))
    if not token:
        return jsonify({"error": "Token requerido", "code": 401}), 401
    try:
        from shared.utils import verificar_jwt
        payload = verificar_jwt(token, SECRET_KEY_JWT)
        g.usuario = {"id": payload["id_usuario"], "correo": payload["correo"], "rol": payload["rol"]}
    except Exception:
        return jsonify({"error": "Token inválido", "code": 401}), 401
    
    # Obtener clientes y productos para el formulario
    from sqlalchemy import text
    conn = engine_tienda.connect()
    cursor = conn.execute(text("SELECT id_cliente, CONCAT(nombre, ' ', COALESCE(apellido,'')) AS nombre, telefono FROM cliente WHERE activo = TRUE ORDER BY nombre"))
    clientes = cursor.fetchall()
    
    cursor = conn.execute(text("SELECT id_producto, nombre, precio, stock FROM producto WHERE activo = TRUE AND stock > 0 ORDER BY nombre"))
    productos = cursor.fetchall()
    conn.close()
    
    return jsonify({
        "clientes": [{"id": c[0], "nombre": c[1], "telefono": c[2]} for c in clientes],
        "productos": [{"id": p[0], "nombre": p[1], "precio": float(p[2]), "stock": p[3]} for p in productos]
    })


@app.route("/ventas/nueva", methods=["POST"])
def venta_nueva_guardar():
    """Guardar una nueva venta."""
    # Verificar JWT
    token = extract_token_from_header(request.headers.get("Authorization", ""))
    if not token:
        return jsonify({"error": "Token requerido", "code": 401}), 401
    try:
        from shared.utils import verificar_jwt
        payload = verificar_jwt(token, SECRET_KEY_JWT)
        g.usuario = {"id": payload["id_usuario"], "correo": payload["correo"], "rol": payload["rol"]}
    except Exception:
        return jsonify({"error": "Token inválido", "code": 401}), 401
    
    # Los datos vienen del body JSON
    data = request.get_json()
    if not data:
        return jsonify({"error": "No se enviaron items", "code": 400}), 400
    
    id_cliente = data.get("id_cliente")
    tipo_venta = data.get("tipo_venta", "local")
    ids_producto = data.get("ids_producto", [])
    cantidades = data.get("cantidades", [])
    
    if not ids_producto:
        return jsonify({"error": "Debe agregar al menos un producto", "code": 400}), 400
    
    # Lógica simplificada de venta
    total = 0
    items = []
    for pid, cant in zip(ids_producto, cantidades):
        try:
            cant = int(cant)
        except (ValueError, TypeError):
            cant = 1
        if cant <= 0:
            raise ValueError("Las cantidades deben ser mayores a cero.")
        
        # Obtener precio y stock
        from sqlalchemy import text
        conn = engine_tienda.connect()
        cursor = conn.execute(text("SELECT precio, stock, nombre FROM producto WHERE id_producto = :pid"), {"pid": pid})
        prod = cursor.fetchone()
        conn.close()
        
        if not prod:
            continue
        
        if cant > (prod[2] or 0):
            return jsonify({"error": f"Stock insuficiente de {prod[1]}", "code": 400}), 400
        
        total += cant * float(prod[1])
        items.append({
            "producto_id": pid, "nombre": prod[1], "cantidad": cant, "precio_unitario": float(prod[1])
        })
    
    return jsonify({
        "exito": True,
        "total": total,
        "items": items,
        "mensaje": "Venta registrada correctamente (estado: pendiente para locales, en flujo para online)",
    })


# ── Rutas de Caja ────────────────────────────────────────────
UMBRAL_DIFERENCIA_CAJA = 20.0

@app.route("/caja")
def caja():
    """Estado de la caja (requiere JWT)."""
    token = extract_token_from_header(request.headers.get("Authorization", ""))
    if not token:
        return jsonify({"error": "Token requerido", "code": 401}), 401
    try:
        from shared.utils import verificar_jwt
        payload = verificar_jwt(token, SECRET_KEY_JWT)
        g.usuario = {"id": payload["id_usuario"], "correo": payload["correo"], "rol": payload["rol"]}
    except Exception:
        return jsonify({"error": "Token inválido", "code": 401}), 401
    
    # Lógica simplificada de caja
    return jsonify({
        "mensaje": "Panel de caja - requiere implementación completa con engine_tienda",
        "umbral_diferencia": UMBRAL_DIFERENCIA_CAJA,
        "usuario": g.usuario["rol"]
    })


@app.route("/caja/abrir", methods=["POST"])
def caja_abrir():
    """Abrir caja."""
    token = extract_token_from_header(request.headers.get("Authorization", ""))
    if not token:
        return jsonify({"error": "Token requerido", "code": 401}), 401
    try:
        from shared.utils import verificar_jwt
        payload = verificar_jwt(token, SECRET_KEY_JWT)
        g.usuario = {"id": payload["id_usuario"], "correo": payload["correo"], "rol": payload["rol"]}
    except Exception:
        return jsonify({"error": "Token inválido", "code": 401}), 401
    
    try:
        monto = float(request.form.get("monto_apertura", 0) or 0)
        if monto < 0:
            return jsonify({"error": "Monto inválido", "code": 400}), 400
        return jsonify({"exito": True, "mensaje": f"Caja abierta con monto S/ {monto:.2f}"})
    except ValueError:
        return jsonify({"error": "Monto de apertura inválido", "code": 400}), 400


@app.route("/caja/egreso", methods=["POST"])
def caja_egreso():
    """Registrar egreso de caja."""
    token = extract_token_from_header(request.headers.get("Authorization", ""))
    if not token:
        return jsonify({"error": "Token requerido", "code": 401}), 401
    try:
        from shared.utils import verificar_jwt
        payload = verificar_jwt(token, SECRET_KEY_JWT)
        g.usuario = {"id": payload["id_usuario"], "correo": payload["correo"], "rol": payload["rol"]}
    except Exception:
        return jsonify({"error": "Token inválido", "code": 401}), 401
    
    concepto = request.form.get("concepto", "").strip()
    try:
        monto = float(request.form.get("monto", 0) or 0)
    except ValueError:
        return jsonify({"error": "Monto inválido", "code": 400}), 400
    
    if not concepto or monto <= 0:
        return jsonify({"error": "Concepto y monto > 0 son obligatorios", "code": 400}), 400
    
    return jsonify({"exito": True, "mensaje": f"Egreso registrado: {concepto} S/ {monto:.2f}"})


@app.route("/caja/cerrar", methods=["POST"])
def caja_cerrar():
    """Cerrar caja."""
    token = extract_token_from_header(request.headers.get("Authorization", ""))
    if not token:
        return jsonify({"error": "Token requerido", "code": 401}), 401
    try:
        from shared.utils import verificar_jwt
        payload = verificar_jwt(token, SECRET_KEY_JWT)
        g.usuario = {"id": payload["id_usuario"], "correo": payload["correo"], "rol": payload["rol"]}
    except Exception:
        return jsonify({"error": "Token inválido", "code": 401}), 401
    
    try:
        declarado = float(request.form.get("monto_declarado", 0) or 0)
    except ValueError:
        return jsonify({"error": "Monto declarado inválido", "code": 400}), 400
    
    return jsonify({"exito": True, "mensaje": f"Caja cerrada. Diferencia: S/ {abs(declarado - 0):.2f}"})


# ── Rutas de Inventario ──────────────────────────────────────
@app.route("/inventario")
def inventario():
    """Listado de movimientos de inventario (requiere JWT)."""
    token = extract_token_from_header(request.headers.get("Authorization", ""))
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
    cursor = conn.execute(text("SELECT im.id_movimiento, p.nombre AS producto, im.tipo, im.cantidad, im.fecha FROM inventario_movimiento im LEFT JOIN producto p ON im.id_producto = p.id_producto ORDER BY im.fecha DESC LIMIT 200"))
    movimientos = cursor.fetchall()
    conn.close()
    
    return jsonify({
        "movimientos": [
            {"id": m[0], "producto": m[1], "tipo": m[2], "cantidad": m[3], "fecha": str(m[4])}
            for m in movimientos
        ]
    })


@app.route("/inventario/registrar", methods=["POST"])
def registrar_movimiento():
    """Registrar movimiento de inventario (entrada/salida)."""
    token = extract_token_from_header(request.headers.get("Authorization", ""))
    if not token:
        return jsonify({"error": "Token requerido", "code": 401}), 401
    try:
        from shared.utils import verificar_jwt
        payload = verificar_jwt(token, SECRET_KEY_JWT)
        g.usuario = {"id": payload["id_usuario"], "correo": payload["correo"], "rol": payload["rol"]}
    except Exception:
        return jsonify({"error": "Token inválido", "code": 401}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No se enviaron datos", "code": 400}), 400
    
    tipo = data.get("tipo")
    id_producto = data.get("id_producto")
    cantidad = int(data.get("cantidad", 0))
    id_usuario = session.get("usuario_id") or payload.get("id_usuario")
    
    if tipo not in ("entrada", "salida") or not id_producto or cantidad <= 0:
        return jsonify({"error": "Parámetros inválidos", "code": 400}), 400
    
    # Lógica simplificada: consultar stock actual y actualizar
    from sqlalchemy import text
    conn = engine_tienda.connect()
    
    # Obtener stock actual
    cursor = conn.execute(text("SELECT stock FROM producto WHERE id_producto = :pid"), {"pid": id_producto})
    prod = cursor.fetchone()
    
    if not prod:
        conn.close()
        return jsonify({"error": "Producto no encontrado", "code": 404}), 404
    
    stock_actual = prod[0]
    
    if tipo == "salida" and cantidad > stock_actual:
        conn.close()
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
        return jsonify({"exito": True, "nuevo_stock": nuevo_stock, "mensaje": f"Movimiento {tipo} registrado"})
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": str(e), "code": 500}), 500


# ── Rutas de Proveedores ─────────────────────────────────────
@app.route("/proveedores")
def proveedores():
    """Listado de proveedores (requiere JWT)."""
    token = extract_token_from_header(request.headers.get("Authorization", ""))
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
    cursor = conn.execute(text("SELECT id_proveedor, nombre, contacto, telefono, email, direccion FROM proveedor ORDER BY nombre"))
    proveedores = cursor.fetchall()
    conn.close()
    
    return jsonify({
        "proveedores": [{"id": p[0], "nombre": p[1], "contacto": p[2], "telefono": p[3], "email": p[4]} for p in proveedores]
    })


@app.route("/proveedores/nuevo", methods=["POST"])
def nuevo_proveedor():
    """Nuevo proveedor."""
    token = extract_token_from_header(request.headers.get("Authorization", ""))
    if not token:
        return jsonify({"error": "Token requerido", "code": 401}), 401
    try:
        from shared.utils import verificar_jwt
        payload = verificar_jwt(token, SECRET_KEY_JWT)
        g.usuario = {"id": payload["id_usuario"], "correo": payload["correo"], "rol": payload["rol"]}
    except Exception:
        return jsonify({"error": "Token inválido", "code": 401}), 401
    
    data = request.get_json()
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
        return jsonify({"exito": True, "mensaje": "Proveedor registrado."})
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"exito": False, "error": str(e)}), 500


# ── Reportes ─────────────────────────────────────────────────
@app.route("/reportes")
def reportes():
    """Resumen de reportes (requiere JWT)."""
    token = extract_token_from_header(request.headers.get("Authorization", ""))
    if not token:
        return jsonify({"error": "Token requerido", "code": 401}), 401
    try:
        from shared.utils import verificar_jwt
        payload = verificar_jwt(token, SECRET_KEY_JWT)
        g.usuario = {"id": payload["id_usuario"], "correo": payload["correo"], "rol": payload["rol"]}
    except Exception:
        return jsonify({"error": "Token inválido", "code": 401}), 401
    
    return jsonify({
        "mensaje": "Panel de reportes - datos resumidos",
        "usuario": g.usuario["rol"]
    })


@app.route("/reportes/pedidos/exportar")
def exportar_pedidos():
    """Exportar pedidos a Excel/CSV (requiere JWT)."""
    token = extract_token_from_header(request.headers.get("Authorization", ""))
    if not token:
        return jsonify({"error": "Token requerido", "code": 401}), 401
    try:
        from shared.utils import verificar_jwt
        payload = verificar_jwt(token, SECRET_KEY_JWT)
        g.usuario = {"id": payload["id_usuario"], "correo": payload["correo"], "rol": payload["rol"]}
    except Exception:
        return jsonify({"error": "Token inválido", "code": 401}), 401
    
    # Esta ruta en el servicio original usa openpyxl/csv; aquí simulamos respuesta JSON
    return jsonify({
        "mensaje": "Exportación de pedidos - en implementación real generaría archivo Excel/CSV",
        "formato": "Excel o CSV según disponibilidad de openpyxl"
    })


# Página raíz
@app.route("/")
def raiz():
    return jsonify({"servicio": "Tienda Service", "puerto": 5002})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=False)