import requests
import traceback

print('=== Attempting login ===')
try:
    r = requests.post('http://127.0.0.1:5001/login', data={
        'correo': 'admin@cleoferr.com', 
        'clave': 'Admin123!'
    })
    print(f'Status: {r.status_code}')
    print(f'Body: {r.text[:500]}')
except Exception as e:
    print(f'Exception type: {type(e).__name__}')
    print(f'Exception: {e}')
    print('Full traceback:')
    traceback.print_exc()