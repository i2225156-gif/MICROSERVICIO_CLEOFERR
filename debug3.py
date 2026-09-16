import requests

# Test: form POST - capturar el redirect
print('=== Test: Form POST - follow redirects ===')
r = requests.post('http://127.0.0.1:5001/login', data={
    'correo': 'admin@cleoferr.com', 
    'clave': 'Admin123!'
}, allow_redirects=False)  # IMPORTANT: don't follow redirects
print(f'Status: {r.status_code}')
print(f'Location: {r.headers.get("Location", "NONE")}')
print(f'Set-Cookie: {r.headers.get("Set-Cookie", "NONE")[:80] if r.headers.get("Set-Cookie") else "NONE"}')
print(f'Body: {r.text[:200]}')
print(f'All headers: {dict(r.headers)}')
print()

# Test: form POST - follow redirects (default)
print('=== Test: Form POST - follow redirects (default) ===')
r2 = requests.post('http://127.0.0.1:5001/login', data={
    'correo': 'admin@cleoferr.com', 
    'clave': 'Admin123!'}
)
print(f'Status: {r2.status_code}')
print(f'Final URL: {r2.url}')
print(f'Set-Cookie: {r2.headers.get("Set-Cookie", "NONE")[:80] if r2.headers.get("Set-Cookie") else "NONE"}')
print(f'Body: {r2.text[:200]}')