import requests

print('=' * 60)
print('PRUEBA 1: POST form-urlencoded login (HTML form flow)')
print('=' * 60)
r = requests.post('http://127.0.0.1:5001/login', data={
    'correo': 'admin@cleoferr.com', 
    'clave': 'Admin123!'
}, allow_redirects=False)
print(f'Status: {r.status_code}')
set_cookie = r.headers.get('Set-Cookie', 'NONE')
sc_display = set_cookie[:80] if set_cookie != 'NONE' else 'NONE'
print(f'Set-Cookie: {sc_display}')
print(f'Location: {r.headers.get("Location", "NONE")}')
print(f'Body preview: {r.text[:100]}')
has_cookie = 'jwt_token=' in set_cookie if set_cookie != 'NONE' else False
print(' OK - Cookie jwt_token obtained' if has_cookie else ' FAIL - No cookie obtained')
print()

# Follow the redirect to get the final state
print('Following redirect...')
r_follow = requests.get('http://127.0.0.1:5001/', cookies={'jwt_token': r.cookies.get('jwt_token', '')})
print(f'After redirect - Status: {r_follow.status_code}')
print(f'After redirect - Body preview: {r_follow.text[:100]}')
print()

print('=' * 60)
print('PRUEBA 2: POST login with Accept: application/json (API flow)')
print('=' * 60)
r2 = requests.post('http://127.0.0.1:5001/login', data={
    'correo': 'admin@cleoferr.com', 
    'clave': 'Admin123!'
}, headers={'Accept': 'application/json'})
print(f'Status: {r2.status_code}')
print(f'Body: {r2.text[:200]}')
token_exists = 'token' in r2.text
print(' OK - Token obtained' if token_exists else ' FAIL - No token obtained')
print()

print('=' * 60)
print('PRUEBA 3: GET /catalogo with cookie from login')
print('=' * 60)
jwt_token = r.cookies.get('jwt_token', '')
if jwt_token:
    r3 = requests.get('http://127.0.0.1:5002/catalogo', cookies={'jwt_token': jwt_token})
    print(f'Status: {r3.status_code}')
    print(f'Body preview: {r3.text[:200]}')
else:
    print(' SKIP - No jwt_token from Prueba 1')
print()

print('=' * 60)
print('PRUEBA 4: GET /productos sin token (público o protegido?)')
print('=' * 60)
r4 = requests.get('http://127.0.0.1:5002/productos')
print(f'Status: {r4.status_code}')
print(f'Body preview: {r4.text[:200]}')
is_200 = r4.status_code == 200
is_401 = r4.status_code == 401
print(' OK - Public (200)' if is_200 else (' OK - Protected (401)' if is_401 else f' ? Status {r4.status_code}'))
print()

print('=' * 60)
print('PRUEBA 5: GET /productos con token corrupto')
print('=' * 60)
r5 = requests.get('http://127.0.0.1:5002/productos', headers={'Authorization': 'Bearer invalidtoken123'})
print(f'Status: {r5.status_code}')
print(f'Body preview: {r5.text[:200]}')
is_401_5 = r5.status_code == 401
print(' OK - 401 Unauthorized' if is_401_5 else f' ? Status {r5.status_code}')