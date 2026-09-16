with open('auth_service/templates/cambiar_clave.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the fixed link with the conditional logic
old = '''<a href="http://127.0.0.1:5002/productos" class="btn btn-outline-light"><i class="fa fa-arrow-left me-1"></i>Volver</a>'''

new = '''{% if session.rol == 'cliente' %}<a href="http://127.0.0.1:5002/catalogo" class="btn btn-outline-light"><i class="fa fa-arrow-left me-1"></i>Volver</a>
{% else %}<a href="http://127.0.0.1:5002/productos" class="btn btn-outline-light"><i class="fa fa-arrow-left me-1"></i>Volver{% endif %}'''

# Actually, let me just put back the original Jinja2 conditional from the user's description
# The original was: {% if session.rol == 'cliente' %}/catalogo{% else %}/productos{% endif %}
# But we need absolute URLs for tienda_service

old2 = '''<a href="http://127.0.0.1:5002/productos" class="btn btn-outline-light"><i class="fa fa-arrow-left me-1"></i>Volver</a>'''

new2 = '''{% if session.rol == 'cliente' %}<a href="http://127.0.0.1:5002/catalogo" class="btn btn-outline-light"><i class="fa fa-arrow-left me-1"></i>Volver</a>
{% else %}<a href="http://127.0.0.1:5002/productos" class="btn btn-outline-light"><i class="fa fa-arrow-left me-1"></i>Volver{% endif %}'''

if old2 in content:
    content = content.replace(old2, new2)
    print('Restored conditional logic in cambiar_clave.html')
else:
    print('Old string not found for cambiar_clave')

with open('auth_service/templates/cambiar_clave.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')