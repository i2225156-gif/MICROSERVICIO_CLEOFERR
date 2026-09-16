import re

with open('auth_service/templates/cliente_form.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace /clientes links
old = 'href="/clientes"'
new = 'href="http://127.0.0.1:5002/clientes"'

if old in content:
    content = content.replace(old, new)
    print('Replaced cliente_form.html link')
else:
    print('Not found: ' + old)

with open('auth_service/templates/cliente_form.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')