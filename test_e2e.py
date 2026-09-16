import requests

print('=== Prueba 1: POST form-urlencoded login ===')
r = requests.post('http://127.0.0.1:5001/login', data={
    'correo': 'admin@cleoferr.com', 
    'clave': 'Admin123!'
})
print(f'Status: {r.status_code}')
print(f'Headers: {dict(r.headers)}')
print(f'Body: {r.text[:200]}')
set_cookie = r.headers.get('Set-Cookie', 'NOT FOUND')
print(f'Set-Cookie: {set_cookie[:100] if set_cookie != "NOT FOUND" else "NOT FOUND"}')

print()
print('=== Prueba 2: POST login with Accept JSON ===')
r2 = requests.post('http://127.0.0.1:5001/login', data={
    'correo': 'admin@cleoferr.com', 
    'clave': 'Admin123!'
}, headers={'Accept': 'application/json'})
print(f'Status: {r2.status_code}')
print(f'Headers: {dict(r2.headers)}')
print(f'Body: {r2.text[:200]}')

print()
print('=== Prueba 3: GET /catalogo with cookie from login ===')
# Get the cookie from the first login
jwt_token = r.cookies.get('jwt_token')
print(f'jwt_token from login: {jwt_token[:20] if jwt_token else "None"}')
if jwt_token:
    r3 = requests.get('http://127.0.0.1:5002/catalogo', cookies={'jwt_token': jwt_token})
    print(f'Status: {r3.status_code}')
    print(f'Body: {r3.text[:200]}')
else:
    print('No jwt_token cookie obtained, skipping test 3')

print()
print('=== Prueba 4: GET /catalogo without cookie ===')
r4 = requests.get('http://127.0.0.1:5002/catalogo')
print(f'Status: {r4.status_code}')
print(f'Body: {r4.text[:200]}')

print()
print('=== Prueba 5: GET /catalogo with corrupt token ===')
r5 = requests.get('http://127.0.0.1:5002/catalogo', headers={'Authorization': 'Bearer invalidtoken123'})
print(f'Status: {r5.status_code}')
print(f'Body: {r5.text[:200]}')