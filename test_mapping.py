import sys
sys.path.insert(0, r'C:\Users\Usuario\Downloads\automatizacion\MICROSERVICIO_CLEOFERR')
from shared.db_supabase import crear_engine_auth
from sqlalchemy import text

engine = crear_engine_auth()
conn = engine.connect()
cursor = conn.execute(text("SELECT u.id_usuario, u.email, u.contrasena, r.nombre AS rol FROM usuario u INNER JOIN rol r ON u.id_rol = r.id_rol WHERE u.email = 'admin@cleoferr.com'"))
row = cursor.fetchone()
print(f'Row type: {type(row)}')
print(f'Row: {row}')

# Try mappings
cursor2 = conn.execute(text("SELECT u.id_usuario, u.email, u.contrasena, r.nombre AS rol FROM usuario u INNER JOIN rol r ON u.id_rol = r.id_rol WHERE u.email = 'admin@cleoferr.com'"))
row_m = cursor2.mappings().fetchone()
print(f'RowMapping: {row_m}')
if row_m:
    print(f'RowMapping["contrasena"]: {row_m["contrasena"]}')
    print(f'RowMapping.contrasena attr: {row_m.contrasena if hasattr(row_m, "contrasena") else "NO ATTR"}')

# Also try original row
print(f'Row[2]: {row[2]}')
print(f'Row.contrasena attr: {row.contrasena if hasattr(row, "contrasena") else "NO ATTR"}')
conn.close()