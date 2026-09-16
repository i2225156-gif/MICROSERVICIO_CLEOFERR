with open('auth_service/templates/cambiar_clave.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the back link that conditionally points to /catalogo or /productos
old = '''<a href="{% if session.rol == 'cliente' %}/catalogo{% else %}/productos{% endif %}" class="btn btn-outline-light"><i class="fa fa-arrow-left me-1"></i>Volver</a>'''

new = '''<a href="http://127.0.0.1:5002/productos" class="btn btn-outline-light"><i class="fa fa-arrow-left me-1"></i>Volver</a>'''

if old in content:
    content = content.replace(old, new)
    print('Replaced cambiar_clave.html link')
else:
    print('Old string not found - checking content...')
    # Try to find similar patterns
    if '/catalogo' in content:
        print('Found /catalogo in file')
    if '/productos' in content:
        print('Found /productos in file')

with open('auth_service/templates/cambiar_clave.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')