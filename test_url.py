import sys
import time
sys.path.insert(0, 'tienda_service')

# Dar un momento para que el servicio se inicie
time.sleep(3)

from tienda_service.app import app
# No arrancamos el servidor de nuevo, solo verificamos la ruta
# Usaremos urllib para hacer la petición

import urllib.request
try:
    req = urllib.request.urlopen('http://127.0.0.1:5002/')
    response = req.read().decode('utf-8')
    print('Status: 200 (implicito por éxito en urllib)')
    print('Body:', response[:200])
except Exception as e:
    print(f'Error: {e}')