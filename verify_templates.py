import os, re

templates_dir = r'C:\Users\Usuario\Downloads\automatizacion\MICROSERVICIO_CLEOFERR\auth_service\templates'

for t in ['login.html', 'login_cliente.html', 'cliente_form.html', 'cambiar_clave.html']:
    path = os.path.join(templates_dir, t)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        print(f'=== {t} ===')
        urls = re.findall(r'href=[\'"]([^\'"]+)[\'"]', content)
        for u in urls:
            if u and not u.startswith('http') and not u.startswith('//'):
                print(f'  Relative: {u}')
            else:
                print(f'  Absolute: {u}')
        print()