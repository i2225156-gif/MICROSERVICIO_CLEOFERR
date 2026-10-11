# AGENTS.md — MICROSERVICIO CLEOFERR

## Arquitectura de puertos (3 procesos independientes, comunicación HTTP + JWT)

| Componente | Archivo | Puerto | ¿Sirve HTML para el navegador? | Rol |
|---|---|---|---|---|
| **Auth service (entrada del usuario)** | `auth_service/app.py` | **5001** | ✅ SÍ — `/login`, `/login_cliente` renderizan HTML con diseño | **URL de entrada: http://127.0.0.1:5001/login** |
| **Tienda service** | `tienda_service/app.py` | **5002** | ✅ SÍ — `/productos`, `/catalogo` renderizan HTML con CSS (también JSON si `Accept: application/json` o `X-Requested-With`) | Panel/catálogo tras login |
| App.py raíz (gateway legacy) | `app.py` | 5000 | ⚠️ Solo redirección — `/` y `/login` redirigen a :5001/login | Redirección + rutas legacy sin usar |

Flujo de sesión:
1. Navegador → `http://127.0.0.1:5001/login` (HTML con diseño).
2. POST correcto → auth_service setea **cookie `jwt_token`** (HttpOnly, SameSite=Lax, path=/, max_age=8h) y redirige 302 a `http://127.0.0.1:5002/productos`.
3. tienda_service valida el JWT leyendo **primero el header `Authorization: Bearer` y si no hay, la cookie `jwt_token`**.
4. Sin token o token inválido: si el cliente pide HTML → redirect a `http://127.0.0.1:5001/login`; si pide JSON o no es navegador → 401 JSON `{"code":401,"error":"Token requerido"}`.
5. `http://127.0.0.1:5001/logout` borra la cookie y redirige al login.

⚠️ **Nombres de cookie de sesión distintos por servicio** (`auth_session`, `tienda_session`, `front_session`): las cookies **no se aíslan por puerto** en 127.0.0.1 — cualquier app en 127.0.0.1 recibe las cookies de las demás.
⚠️ La cookie `jwt_token` viaja a cualquier app en 127.0.0.1 (cualquier puerto). Por eso los links cross-servicio en templates deben ser **URL absolutas** (`http://127.0.0.1:5001/...`, `http://127.0.0.1:5002/...`, `http://127.0.0.1:5000/...`), nunca relativas.
- Las tres apps leen el mismo `SECRET_KEY` desde `.env` — si no coincide, las rutas migradas fallan con 401.
- Ninguna usa `debug=True` por defecto (sin reloader ni prompts interactivos, requisito para pruebas en background).

## Quickstart

1. **Activate venv** and ensure `.env` exists at repo root with:
   - `SECRET_KEY` (random 32-char hex)
   - `DATABASE_URI_AUTH` — Supabase auth DB URI
   - `DATABASE_URI_TIENDA` — Supabase tienda DB URI
   - Optional: `SMTP_USER`, `SMTP_PASS` for email
2. **Install deps**: `pip install -r requirements.txt` (if present) or at minimum:
   `pip install flask flask-bcrypt pymysql sqlalchemy python-dotenv`
3. **Initialize DB schema** (run once or on fresh deploy):
   - `python app.py` — the app calls `_inicializar_schema_auth()` on startup, which:
     - Creates `verificacion_cuenta` and `recuperacion_contrasena` tables
     - Adds `origen` column to `cliente`
     - Drops NOT NULL on `cliente.email`, `contrasena`, `telefono`, `direccion`
     - Creates unique index `uq_cliente_documento` (partial, excludes NULL/'')
4. **Seed test data**: `python seed_data.py` — inserts roles, users, clients, categories, brands, products
5. **Run**: `python app.py` — defaults to http://127.0.0.1:5000. Ejecuta 3 procesos independientes:
   - `python auth_service\app.py` (puerto 5001)
   - `python tienda_service\app.py` (puerto 5002)
   - `python app.py` (puerto 5000, solo redirección)

## Database two-connection pattern

- `get_connection_auth()` → `db_supabase.engine_auth` (users, cliente, rol, sesion)
- `get_connection_tienda()` → `db_supabase.engine_tienda` (producto, venta, inventario, etc.)
- **Never mix tables** from both DBs in a single query. The app resolves this by doing a memory-join across connections.
- `NullPool` is used so every connection is fresh; no pool recycling gotchas.

## Critical startup behavior

- `_inicializar_schema_auth()` in `app.py:85-183` runs **within** `with app.app_context():` on every launch.
- It is **idempotent** (IF NOT EXISTS / ALTER COLUMN ... DROP NOT NULL only if currently NOT NULL).
- If the `verificacion_cuenta` table is missing, client registration will silently fail with "No se pudo iniciar el registro". The bootstrap creates it.
- The POS columns (`origen`, NULL on email/contrasena/telefono/direccion) are aligned here automatically.

## POS client registration (`/clientes/registrar_pos`)

- POST JSON: `{tipo: 'boleta'|'factura', nombre, apellido?, telefono, dni|ruc, direccion?}`
- DNI: 8 digits. RUC: 11 digits starting with 10 or 20.
- Reuses existing client by `id_tipo_documento` + `nro_documento` (no duplicate).
- Clients created via POS get `origen='pos'`, `email=NULL`, `contrasena=NULL`.
- **Important**: The bootstrap `_inicializar_schema_auth()` must have run; otherwise `ALTER TABLE cliente ALTER COLUMN ... DROP NOT NULL` will fail and the INSERT in `registrar_pos` will crash on NOT NULL violation.

## Rate-limiting login

- `_LIMITE_LOGIN=5`, `_VENTANA_LOGIN=900` (15 min) in memory.
- Tracked per `IP + correo` clave.
- `_bloqueado_login()`, `_registrar_error_login()`, `_resetear_login()`.
- After 5 failed attempts from an IP+email, block for 15 min.

## CSRF protection

- Tokens generated per session (`secrets.token_hex(32)`) and injected via `@app.context_processor `_ctx_csrf_token`.
- Validated **only** on these protected endpoints (defined in `_CSRF_PROTEGIDAS` set):
  `login`, `login_cliente`, `registro_cliente`, `verificar_registro`, `recuperar_contrasena`, `restablecer_contrasena`, `cambiar_clave`, `procesar_pago`, `carrito_confirmar_v2`, `carrito_agregar`, `registrar_pos`
- All POST/PUT/PATCH/DELETE requests must include `csrf_token` field or `X-CSRFToken` header.
- `_validar_csrf()` in `app.py:299-310` aborts with 400 if invalid.

## Excel/CSV export

- Main helper: `_excel_response()` at `app.py:678-724`.
- Tries `openpyxl` first; falls back to CSV if not installed.
- All export routes (`/reportes/pedidos/exportar`, `/reportes/productos/exportar`, `/reportes/clientes/exportar`, `/reportes/proveedores/exportar`, `/reportes/inventario/exportar`, `/reportes/dia/exportar`) use this helper.
- If `openpyxl` is unavailable, the app degrades to CSV automatically.

## Caja (cash register) flow

- Only **one** caja can be open at a time (unique index `idx_caja_una_abierta`).
- `/caja/abrir` — requires positive `monto_apertura`, inserts `movimiento_caja` ingreso.
- `/caja/egreso` — records gasto, subtrae del efectivo esperado.
- `/caja/cerrar` — computes `esperado = fondo + ventas_efectivo - egresos`, compares with `monto_declarado`.
  - Difference > `UMBRAL_DIFERENCIA_CAJA` (20.0) → warning.
  - Pago digital (Yape/Plin/Tarjeta) are **resumen only**, NOT part of efectivo expected.
- The caja only tracks **local** (caja/POS) transactions. Online ventas are separate.

## Authentication DB schema gotcha

- `migracion_verificacion.sql` defines `verificacion_cuenta` (PostgreSQL/Supabase).
- `app.py:_inicializar_schema_auth()` creates this table if missing **and** aligns `cliente` columns for POS.
- If your Supabase DB already has `verificacion_registro` (old wrong name), the app will still create `verificacion_cuenta` successfully (it's independent). But any code referencing `verificacion_cuenta` will work.

## Testing / seed

- `seed_data.py` is idempotent — checks existence before inserting.
- Prints a summary at the end: `insertados: N   ya existian: M` per table.
- Credenciales de prueba (after seeding):
  - `admin@cleoferr.com / Admin123!` (administrador)
  - `vendedor@cleoferr.com / Vendedor123` (vendedor)
  - `maria.quispe@gmail.com / Cliente123` (cliente)

## File layout overview

| File | Purpose |
|------|---------|
| `app.py` | Main Flask app, all routes, bootstrap, CSRF, rate-limiting |
| `db.py` | `SQLAlchemy()` instance (imported as `db`) |
| `db_supabase.py` | Two `NullPool` engines: `engine_auth`, `engine_tienda` |
| `seed_data.py` | Seed test data into both DBs |
| `migracion_verificacion.sql` | Supabase migration: `verificacion_cuenta` + `recuperacion_contrasena` |
| `setup_nuevas_tablas.sql` | MySQL script: `cliente` columns, `proveedor`, `inventario_movimiento` |
| `nuevas_tablas_pago.sql` | MySQL: `venta` metodo_pago/num_operacion, `comprobante` table |
| `.env` | `SECRET_KEY`, `DATABASE_URI_AUTH`, `DATABASE_URI_TIENDA`, optionally `SMTP_USER`/`SMTP_PASS` |

## Commands cheat sheet

| Action | Command |
|--------|---------|
| Install deps | `pip install flask flask-bcrypt pymysql sqlalchemy python-dotenv` |
| Init/verify schema | Run `python app.py` (bootstrap runs automatically) |
| Seed test data | `python seed_data.py` |
| Run auth service | `python auth_service\app.py` |
| Run tienda service | `python tienda_service\app.py` |
| Run root app | `python app.py` (solo redirección) |
| Test POS client reg | `POST /clientes/registrar_pos` with JSON |
| Login as admin | `POST /login` con `admin@cleoferr.com / Admin123!` |
| Login as client | `POST /login_cliente` con client email / `Cliente123` |
| Export pedidos Excel | `GET /reportes/pedidos/exportar` |
| Open caja | `POST /caja/abrir` con `monto_apertura` |
| Cerrar caja | `POST /caja/cerrar` con `monto_declarado` |

## Rutas del puerto 5000 (app.py raíz)

Las siguientes rutas quedaron **sin uso activo** al pasar a la arquitectura de microservicios, solo redirección:

- `GET /` — redirige a `http://127.0.0.1:5001/login` (única función activa)
- `GET /login` — redirige a `http://127.0.0.1:5001/login` (única función activa)
- Cualquier otra ruta definida en `app.py` que intente renderizar templates o servir HTML no será alcanzada por el navegador en el flujo actual; deben llamarse directamente a los microservicios en :5001 y :5002.

Rutas que aún se conservan (no eliminadas, solo inactivas en el flujo normal):
- `GET /login_gateway_obsoleto` — migrado a auth_service:5001, disponible para compatibilidad
- Rutas legacy de clientes, pedidos, caja, reportes, etc. que consultan BD directamente desde app.py:5000 no son la entrada; úsalos llamando a los microservicios correspondientes.

## Rutas HTML por servicio

| Ruta | Servicio | Comentario |
|------|----------|----------|
| `http://127.0.0.1:5001/login` | auth_service | Formulario de login administrativo/vendedor |
| `http://127.0.0.1:5001/login_cliente` | auth_service | Formulario de login de cliente |
| `http://127.0.0.1:5001/logout` | auth_service | Cierra sesión y borra cookie jwt_token |
| `http://127.0.0.1:5002/productos` | tienda_service | Catálogo de productos (requiere JWT), renderiza productos.html con CSS |
| `http://127.0.0.1:5002/catalogo` | tienda_service | Catálogo público de productos, renderiza catalogo.html con CSS |
| `http://127.0.0.1:5001/cambiar_clave` | auth_service | Cambio de contraseña |
| `http://127.0.0.1:5001/recuperar_contrasena` | auth_service | Recuperación de contraseña OTP |
| `http://127.0.0.1:5001/registrar_pos` | auth_service | Registro de cliente desde POS |

## Enlaces entre servicios: URLs absolutas obligatorias

Todo link del menú que apunte a otro servicio debe ser **URL absoluta** (`http://127.0.0.1:5001/logout`, `http://127.0.0.1:5002/catalogo...`). Los relativos se quedan en el mismo puerto y se rompen porque las cookies no se aíslan por puerto en 127.0.0.1.

En `tienda_service\templates\base.html` los ejemplos ya usan URLs absolutas:
- `href="http://127.0.0.1:5001/cambiar_clave"`
- `href="http://127.0.0.1:5001/logout"`
- `href="http://127.0.0.1:5000/clientes"` etc.

Verificar que todos los enlaces en templates usen esquema `http://127.0.0.1:puerto` y no `{{ url_for(...) }}` relativos.