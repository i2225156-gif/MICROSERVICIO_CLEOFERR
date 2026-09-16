import re

with open('auth_service/templates/cliente_form.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace absolute URL with relative URL (since template is served from auth_service)
old = 'href="http://127.0.0.1:5002/clientes"'
new = 'href="/clientes"'

if old in content:
    content = content.replace(old, new)
    print('Reverted cliente_form.html link to relative')
else:
    print('Not found: ' + old)

with open('auth_service/templates/cliente_form.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')