import sys
sys.path.insert(0, 'tienda_service')
from tienda_service.app import app

print('Import exitoso')

try:
    app.run(host='127.0.0.1', port=5002, debug=False, use_reloader=False)
except Exception as e:
    print(f'Error al arrancar: {type(e).__name__}: {e}')