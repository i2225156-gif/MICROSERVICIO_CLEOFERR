import re, os

templates_dir = r'C:\Users\Usuario\Downloads\automatizacion\MICROSERVICIO_CLEOFERR\auth_service\templates'

for t in ['login.html', 'login_cliente.html', 'cambiar_clave.html', 'cliente_form.html']:
    path = os.path.join(templates_dir, t)
    if not os.path.exists(path):
        print(f'{t}: NOT FOUND')
        continue
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find href and action attributes
    links = re.findall(r'(?:href|action)=["\']([^"\']+)["\']', content)
    
    print(f'=== {t} ===')
    for link in links:
        # Check if it's a relative route that should be changed
        if link and not link.startswith('http') and not link.startswith('https') and not link.startswith('//'):
            # Check for common routes that should point to tienda_service
            if link.startswith('/') and link != '/':
                print(f'  Route: {link} -> SHOULD BE http://127.0.0.1:5002{link}')
            else:
                print(f'  Link: {link}')
        elif link.startswith('http') or link.startswith('//'):
            print(f'  External URL: {link}')
    print()