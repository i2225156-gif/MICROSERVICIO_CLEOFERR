import re

# Fix login.html - recover password should be in auth_service (5001)
with open('auth_service/templates/login.html', 'r', encoding='utf-8') as f:
    content = f.read()

# The recuperar_contrasena link currently points to 5002, should be 5001
old = 'http://127.0.0.1:5002/recuperar_contrasena?origen=admin'
new = 'http://127.0.0.1:5001/recuperar_contrasena?origen=admin'

if old in content:
    content = content.replace(old, new)
    print('Fixed login.html: recuperar_contrasena -> auth_service (5001)')
else:
    print('Not found in login.html: ' + old)

# Also fix login_cliente link if present
old2 = 'http://127.0.0.1:5002/login_cliente'
new2 = 'http://127.0.0.1:5001/login_cliente'
if old2 in content:
    content = content.replace(old2, new2)
    print('Fixed login.html: login_cliente -> auth_service (5001)')

with open('auth_service/templates/login.html', 'w', encoding='utf-8') as f:
    f.write(content)

# Fix login_cliente.html
with open('auth_service/templates/login_cliente.html', 'r', encoding='utf-8') as f:
    content2 = f.read()

old3 = 'http://127.0.0.1:5002/verificar_registro'
new3 = 'http://127.0.0.1:5001/verificar_registro'
if old3 in content2:
    content2 = content2.replace(old3, new3)
    print('Fixed login_cliente.html: verificar_registro -> auth_service (5001)')

old4 = 'http://127.0.0.1:5002/login_cliente'
new4 = 'http://127.0.0.1:5001/login_cliente'
if old4 in content2:
    content2 = content2.replace(old4, new4)
    print('Fixed login_cliente.html: login_cliente -> auth_service (5001)')

old5 = 'http://127.0.0.1:5002/recuperar_contrasena'
new5 = 'http://127.0.0.1:5001/recuperar_contrasena'
if old5 in content2:
    content2 = content2.replace(old5, new5)
    print('Fixed login_cliente.html: recuperar_contrasena -> auth_service (5001)')

with open('auth_service/templates/login_cliente.html', 'w', encoding='utf-8') as f:
    f.write(content2)

print('Done fixing auth links')