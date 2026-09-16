import re

with open('auth_service/templates/login.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the specific link
old = 'href="/recuperar_contrasena?origen=admin"'
new = 'href="http://127.0.0.1:5002/recuperar_contrasena?origen=admin"'

if old in content:
    content = content.replace(old, new)
    print('Replaced login.html link')
else:
    print('Old string not found')

with open('auth_service/templates/login.html', 'w', encoding='utf-8') as f:
    f.write(content)