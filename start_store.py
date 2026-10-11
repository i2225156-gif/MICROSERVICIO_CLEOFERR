@echo off
python -c "
import sys
sys.path.insert(0, 'tienda_service')
from tienda_service.app import app
print('Import exitoso')
app.run(host='127.0.0.1', port=5002, debug=False, use_reloader=False)
" > tienda_startup.txt 2>&1
echo Servicio started