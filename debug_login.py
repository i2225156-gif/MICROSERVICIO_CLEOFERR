import requests

# Test 1: form POST without special headers
print('=== Test 1: Plain form POST ===')
r = requests.post('http://127.0.0.1:5001/login', data={
    'correo': 'admin@cleoferr.com', 
    'clave': 'Admin123!'
})
print(f'Status: {r.status_code}')
print(f'Accept header: {r.request.headers.get("Accept", "")}')
print(f'X-Requested-With: {r.request.headers.get("X-Requested-With", "")}')
print(f'Set-Cookie: {r.headers.get("Set-Cookie", "NONE")}')
print(f'Body: {r.text[:100]}')
print()

# Test 2: form POST with Accept JSON
print('=== Test 2: Form POST with Accept: application/json ===')
r2 = requests.post('http://127.0.0.1:5001/login', data={
    'correo': 'admin@cleoferr.com', 
    'clave': 'Admin123!'
}, headers={'Accept': 'application/json'})
print(f'Status: {r2.status_code}')
print(f'Accept header: {r2.request.headers.get("Accept", "")}')
print(f'X-Requested-With: {r2.request.headers.get("X-Requested-With", "")}')
print(f'Set-Cookie: {r2.headers.get("Set-Cookie", "NONE")}')
print(f'Body: {r2.text[:100]}')
print()

# Test 3: form POST with both headers
print('=== Test 3: Form POST with both HTML-detecting headers ===')
r3 = requests.post('http://127.0.0.1:5001/login', data={
    'correo': 'admin@cleoferr.com', 
    'clave': 'Admin123!'
}, headers={
    'Accept': 'text/html',
    'X-Requested-With': ''
})
print(f'Status: {r3.status_code}')
print(f'Accept header: {r3.request.headers.get("Accept", "")}')
print(f'X-Requested-With: {r3.request.headers.get("X-Requested-With", "")}')
print(f'Set-Cookie: {r3.headers.get("Set-Cookie", "NONE")}')
print(f'Body: {r3.text[:100]}')