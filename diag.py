import sys
sys.path.insert(0, r'C:\Users\Usuario\Downloads\automatizacion\MICROSERVICIO_CLEOFERR')
from shared.db_supabase import crear_engine_auth
from sqlalchemy import text

engine = crear_engine_auth()
conn = engine.connect()
cursor = conn.execute(text("SELECT u.id_usuario, u.email, u.contrasena, r.nombre AS rol FROM usuario u INNER JOIN rol r ON u.id_rol = r.id_rol WHERE u.email = :e"), {"e": "admin@cleoferr.com"})
row = cursor.fetchone()
print(f'Row type: {type(row)}')
print(f'Row: {row}')
if row:
    print(f'Row[2]: {row[2]}')
    print(f'Row.email: {row.email}')
    try:
        d = row._asdict()
        print(f'_asdict: {d}')
    except Exception as e:
        print(f'_asdict error: {e}')
conn.close()