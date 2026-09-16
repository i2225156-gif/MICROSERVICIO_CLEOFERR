import re

with open('tienda_service\\app.py', 'r') as f:
    content = f.read()
lines = content.split('\n')

print("=== TODAS las lineas con 'contrasena' o patterns diccionario en tienda_service ===")
for i, line in enumerate(lines, 1):
    lower = line.lower()
    if 'contrasena' in lower or 'usuario[' in lower or 'row\[' in lower or '\[\"' in lower:
        print(f'L{i}: {line.strip()}')