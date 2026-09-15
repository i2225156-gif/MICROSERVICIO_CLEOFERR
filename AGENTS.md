# AGENTS.md — MICROSERVICIO CLEOFERR

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
5. **Run**: `python app.py` — defaults to http://127.0.0.1:5000

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
| Run dev server | `python app.py` |
| Test POS client reg | `POST /clientes/registrar_pos` with JSON |
| Login as admin | `POST /login` with `admin@cleoferr.com / Admin123!` |
| Login as client | `POST /login_cliente` with client email / `Cliente123` |
| Export pedidos Excel | `GET /reportes/pedidos/exportar` |
| Open caja | `POST /caja/abrir` with `monto_apertura` |
| Cerrar caja | `POST /caja/cerrar` with `monto_declarado` |