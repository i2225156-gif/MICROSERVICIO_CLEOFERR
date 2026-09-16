import requests

# Test: form POST with Accept text/html (should trigger HTML form flow)
print('=== Test: Accept text/html (should trigger HTML form flow) ===')
r = requests.post('http://127.0.0.1:5001/login', data={
    'correo': 'admin@cleoferr.com', 
    'clave': 'Admin123!'
}, headers={'Accept': 'text/html'})
print(f'Status: {r.status_code}')
sc = r.headers.get('Set-Cookie', 'NONE')
print(f'Set-Cookie: {sc[:50] if sc != "NONE" else "NONE"}')
print(f'Body: {r.text[:200]}')
print(f'Headers: {dict(r.headers)}')