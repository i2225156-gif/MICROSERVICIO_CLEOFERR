import re

with open('auth_service\\app.py', 'r') as f:
    content = f.read()
lines = content.split('\n')

print("=== Patron usuario[\"campo\"] en auth_service ===")
for i, line in enumerate(lines, 1):
    if 'usuario[' in line and '\"' in line:
        print(f'L{i}: {line.strip()}')

print("\n=== Patron .contrasena, .email, .rol en auth_service ===")
for i, line in enumerate(lines, 1):
    for var in ['usuario', 'row', 'usuario_obj']:
        for attr in ['contrasena', 'email', 'rol', 'id']:
            if f'{var}.{attr}' in line:
                print(f'L{i}: {line.strip()}')

print("\n=== TODAS las lineas con 'contrasena' ===")
for i, line in enumerate(lines, 1):
    if 'contrasena' in line.lower():
        print(f'L{i}: {line.strip()}')