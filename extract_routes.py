import re
import os

os.chdir(r'C:\Users\Usuario\Downloads\automatizacion\MICROSERVICIO_CLEOFERR')

with open('auth_service/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find all @app.route decorators
routes = []
for m in re.finditer(r'@app\.route\([\"\\']([^\"\\']+)[\"\\']', content):
    path = m.group(1)
    start = m.end() + 1  # Position after the decorator
    # Find the function definition
    lines = content[start:].split('\n')
    func_name = ''
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('def '):
            func_name = stripped.split()[1]
            break
    
    routes.append((path, func_name))

# Remove duplicates and sort
unique_routes = []
seen = set()
for path, name in routes:
    key = (path, name)
    if key not in seen:
        seen.add(key)
        unique_routes.append((path, name))

print("=== RUTAS DE auth_service/app.py ===")
for path, name in sorted(unique_routes, key=lambda x: x[0]):
    print(f"HTTP: {path:30s}  |  Función: {name}")

print()

# Now do the same for tienda_service
with open('tienda_service/app.py', 'r', encoding='utf-8') as f:
    content2 = f.read()

routes2 = []
for m in re.finditer(r'@app\.route\([\"\\']([^\"\\']+)[\"\\']', content2):
    path = m.group(1)
    start = m.end() + 1
    lines = content2[start:].split('\n')
    func_name = ''
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('def '):
            func_name = stripped.split()[1]
            break
    
    routes2.append((path, func_name))

unique_routes2 = []
seen2 = set()
for path, name in routes2:
    key = (path, name)
    if key not in seen2:
        seen2.add(key)
        unique_routes2.append((path, name))

print("=== RUTAS DE tienda_service/app.py ===")
for path, name in sorted(unique_routes2, key=lambda x: x[0]):
    print(f"HTTP: {path:30s}  |  Función: {name}")
PYEOF