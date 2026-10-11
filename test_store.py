import sys
sys.path.insert(0, 'tienda_service')
from tienda_service.app import app

print('Importando tienda_service...')
app.run(host='127.0.0.1', port=5002, debug=False, use_reloader=False)