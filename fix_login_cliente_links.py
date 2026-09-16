import re

with open('auth_service/templates/login_cliente.html', 'r', encoding='utf-8') as f:
    content = f.read()

# List of old -> new replacements
replacements = [
    ('href="/verificar_registro"', 'href="http://127.0.0.1:5002/verificar_registro"'),
    ('href="/login_cliente"', 'href="http://127.0.0.1:5002/login_cliente"'),
    ('href="/recuperar_contrasena"', 'href="http://127.0.0.1:5002/recuperar_contrasena"'),
    ('href="/registro_cliente"', 'href="http://127.0.0.1:5002/registro_cliente"'),
]

for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        print(f'Replaced: {old} -> {new}')
    else:
        print(f'Not found: {old}')

with open('auth_service/templates/login_cliente.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')