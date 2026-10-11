# MICROSERVICIO_CLEOFERR - Sistema de Ferretería

## Descripción general

Sistema completo de gestión para Ferretería CLEOFERR, con arquitectura híbrida:
- **App principal** (`app.py`): Flask monolítico con rutas web, formularios y lógica de negocio.
- **auth_service** (puerto 5001): Servicio Flask separado para autenticación JWT, login de clientes y endpoints `/clientes`.
- **tienda_service** (puerto 5002): Servicio Flask separado para catálogo, ventas, inventario, caja, proveedores y reportes.
- **Base de datos**: Dos instancias PostgreSQL en Supabase:
  - `DATABASE_URI_AUTH`: Usuarios, clientes, roles, sesiones, tablas OTP (`verificacion_cuenta`, `recuperacion_contrasena`).
  - `DATABASE_URI_TIENDA`: Productos, ventas, inventario, caja, proveedores, reportes.

## 📦 Dependencias e instalación

```bash
# Activar entorno virtual (recomendado)
python -m venv .venv
.\.venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Instalar Alembic (ya incluido en la verificación)
pip install alembic
```

## 🔧 Configuración de variables de entorno

Copie el archivo `.env` y complete los valores. Es obligatorio:

| Variable | Descripción | Obligatoria |
|----------|-------------|------------|
| `SECRET_KEY` | Clave secreta Flask (32 chars hex mínimo) | ✓ |
| `DATABASE_URI_AUTH` | URI PostgreSQL para BD de autenticación | ✓ |
| `DATABASE_URI_TIENDA` | URI PostgreSQL para BD de la tienda | ✓ |
| `SMTP_USER` | Usuario Gmail para envío de correos | opcional |
| `SMTP_PASS` | Contraseña de aplicación Gmail | opcional |
| `SESSION_COOKIE_SECURE` | `1` para HTTPS, `0` para HTTP local | por defecto `0` |
| `FLASK_DEBUG` | `1` para modo debug, `0` para producción | por defecto `0` |

Ejemplo `.env`:
```env
SECRET_KEY=23b97e9475e14d961858445015753e7228d83806cec1446dba368dc4b7a70693
DATABASE_URI_AUTH=postgresql://user:password@localhost:5432/dbname
DATABASE_URI_TIENDA=postgresql://user:password@localhost:5432/dbname
SMTP_USER=dulpozomel27@gmail.com
SMTP_PASS=ROTA_ESTA_CONTRASENA_DE_APLICACION
FLASK_DEBUG=0
```

## 📦 Flujo de despliegue (NUEVO - con Alembic)

Siga estos pasos en orden. **No ejecute `python app.py` hasta haber completado todos los pasos previos.**

### Paso 1: Activar entorno virtual y instalar dependencias

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### Paso 2: Aplicar migraciones de esquema (Alembic)

```bash
# Aplicar migraciones al esquema baseline (solo versionado, sin cambios DDL contra BD)
# Dado que esta es una BD compartida, las migraciones están marcadas como baseline
# y no ejecutan DDL automático. Se usan como documentación del esquema.

# Para BD Auth:
alembic -c migrations_auth\\alembic.ini upgrade head --sql

# Para BD Tienda:
alembic -c migrations_tienda\\alembic.ini upgrade head --sql
```

**Nota importante:** Las migraciones en `migrations_auth/versions/` y `migrations_tienda/versions/` son migraciones **baseline** (snapshot del esquema actual). Contienen `upgrade()` y `downgrade()` tipo no-op (vacíos) porque:
- No se puede saber el estado exacto de la BD compartida sin correr riesgo
- El código original (`_inicializar_schema_auth`) ya no se ejecuta en el arranque
- Sirven como documentación y punto de partida para futuras migraciones versionadas

Si en el futuro se necesita añadir cambios reales al esquema, crear nuevas migraciones numeradas sobre el baseline `001_baseline_*.py`.

### Paso 3: Cargar datos de prueba (solo en desarrollo/testing)

```bash
# Solo ejecutar en entornos locales de desarrollo o testing.
# En producción, los datos deben insertarse manualmente o mediante migraciones propias.

python seed_data.py
```

El script `seed_data.py` es idempotente: verifica la existencia de cada registro antes de insertar e imprime un resumen al final.

### Paso 4: Iniciar la aplicación

```bash
python app.py
```

La aplicación iniciará con una verificación de solo lectura del esquema (en lugar de ejecutar DDL automático). Si faltan tablas o columnas críticas, se registran advertencias en los logs pero **no bloquea el arranque**, ya que la BD puede ser compartida con otros sistemas.

## 🔧 Arquitectura y flujos principales

### Arranque del esquema (modificado)

**Lo viejo (antiguo):** `_inicializar_schema_auth()` corría `ALTER TABLE`, `CREATE TABLE IF NOT EXISTS` en cada `python app.py`, lo que causaba inconsistencias de esquema entre entornos.

**Lo nuevo:** `_verificar_schema_solo_lectura()` solo hace `SELECT` a `information_schema` para comprobar que las tablas y columnas esperadas existen. Nunca ejecuta DDL. Si falta algo, emite un warning en los logs pero permite el arranque.

### Rutas protegidas y CSRF

- CSRF tokens generados por sesión y inyectados automáticamente por el contexto de Flask.
- Validación activa solo en endpoints definidos en `_CSRF_PROTEGIDAS`: `login`, `login_cliente`, `registro_cliente`, `verificar_registro`, `recuperar_contrasena`, `restablecer_contrasena`, `cambiar_clave`, `procesar_pago`, `carrito_confirmar_v2`, `carrito_agregar`, `registrar_pos`.
- Todas las solicitudes POST/PUT/PATCH/DELETE deben incluir `csrf_token` como field de form o header `X-CSRFToken`.

### Rate-limiting de login

- Límite de 5 intentos fallidos por clave `IP + correo` en ventana de 15 minutos.
- Después de 5 fallos, el bloqueo dura 15 minutos.
- Controlado en memoria (`_FALLOS_LOGIN` dict).

### Caja (cash register)

- Solo una caja puede estar abierta a la vez (índice único parcial `idx_caja_una_abierta`).
- `/caja/abrir` — requiere monto positivo, inserta movimiento `ingreso`.
- `/caja/egreso` — registra gasto, resta del efectivo esperado.
- `/caja/cerrar` — calcula `esperado = fondo + ventas_efectivo - egresos`, compara con `monto_declarado`.
  - Diferencia > `UMBRAL_DIFERENCIA_CAJA` (S/ 20.0) → warning.
  - Pagos digitales (Yape/Plin/Tarjeta) son **resumen only**, **NO** forman parte del efectivo esperado.
- Solo rastrean transacciones **locales** (caja/POS). Ventas online son separadas.

### Exportación a Excel/CSV

- Helper `_excel_response()` en `app.py:678-724`.
- Intenta `openpyxl` primero; si no está disponible, fallback a CSV automáticamente.
- Rutas de exportación: `/reportes/pedidos/exportar`, `/reportes/productos/exportar`, `/reportes/clientes/exportar`, `/reportes/proveedores/exportar`, `/reportes/inventario/exportar`, `/reportes/dia/exportar`.

### Autenticación doble BD

- `get_connection_auth()` → `db_supabase.engine_auth` (tablas: usuario, cliente, rol, sesion, verificacion_cuenta).
- `get_connection_tienda()` → `db_supabase.engine_tienda` (tabla: producto, venta, inventario, etc.).
- **Nunca mezclan tablas** de ambas BDs en una sola consulta. El app hace *memory-join* across connections.

## 📁 Estructura de carpetas relevante

```
/MICROSERVICIO_CLEOFERR/
├── app.py                  # Aplicación Flask principal (routes, logic, schema verification)
├── requirements.txt        # Dependencias Python
├── .env                    # Variables de entorno (SECRET_KEY, DB URIs, SMTP)
├── alembic.ini           # Configuración Alembic (raíz, heredado)
├── migrations/           # Árbol Alembic raíz (heredado, desplazado por migraciones_auth/ y migrations_tienda/)
├── migrations_auth/      # Migraciones Auth BD (2 árboles separados)
│   ├── alembic.ini
│   ├── env.py
│   └── versions/
│       └── 001_baseline_auth.py  # Baseline snapshot, upgrade/downgrade no-op
├── migrations_tienda/    # Migraciones Tienda BD (2 árboles separados)
│   ├── alembic.ini
│   ├── env.py
│   └── versions/
│       └── 001_baseline_tienda.py  # Baseline snapshot, upgrade/downgrade no-op
├── auth_service/         # Servicio Flask port 5001 (auth, clientes JWT)
├── tienda_service/       # Servicio Flask port 5002 (catálogo, ventas, inventario, etc.)
├── db.py                 # SQLAlchemy() instance base
├── db_supabase.py        # Two NullPool engines: engine_auth, engine_tienda
├── shared/               # Módulos compartidos (db_supabase.py, utils.py)
├── seed_data.py          # Datos de prueba idempotentes
├── migracion_verificacion.sql   # SQL migración original (referencia)
├── setup_nuevas_tablas.sql    # Script tablas adicionales
├── test_*.py             # Pruebas unitarias/e2e
├── templates/            # 24 plantillas HTML
└── static/img/           # Uploads de imágenes
```

## ⚠️ Notas importantes y restricciones

1. **BD compartida:** Las tablas `cliente`, `verificacion_cuenta`, `recuperacion_contrasena` en la BD Auth pueden ser usadas por otro sistema externo. **No se ejecutan DDL automáticos** que puedan afectar ese otro sistema.

2. **Arquitectura fragmentada:** El proyecto tiene tres componentes (app.py monolito, auth_service, tienda_service) que se superponen en algunas rutas. Se recomienda definir una arquitectura definitiva y refactorizar con el tiempo.

3. **Schema baseline:** Las migraciones baseline (`001_baseline_*.py`) son de solo versiónado. No ejecutan CREATE/ALTER contra la BD. Si se necesita cambiar el esquema, crear nuevas migraciones numeradas `002_*, 003_*, etc.` sobre el baseline.

4. **Tests:** Los archivos `test_*.py` asumen que los servicios corren en puertos 5001 y 5002. Ejecutar `python test_full_flow.py` después de iniciar ambos servicios.

5. **CDT (Customer Data Transfer):** Si el otro sistema transfiere datos de clientes, verifique que el esquema de la tabla `cliente` sea compatible antes de insertar. Las columnas `email`, `contrasena`, `telefono`, `direccion` pueden ser NULL (designado para clientes POS).

## 🛠 Comandos útiles

```bash
# Ver estado actual de migraciones (solo muestra, no ejecuta DDL)
alembic -c migrations_auth\\alembic.ini current
alembic -c migrations_tienda\\alembic.ini current

# Ver qué migrations están pending (solo versionado)
alembic -c migrations_auth\\alembic.ini heads
alembic -c migrations_tienda\\alembic.ini heads

# Mostrar SQL que una migration ejecutaría (sin ejecutar)
alembic -c migrations_auth\\alembic.ini upgrade head --sql > auth_migration_sql.txt
alembic -c migrations_tienda\\alembic.ini upgrade head --sql > tienda_migration_sql.txt
```