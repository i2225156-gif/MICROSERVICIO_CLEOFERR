import os
import shutil

base = r'C:\Users\Usuario\Downloads\automatizacion\MICROSERVICIO_CLEOFERR'

for d in ['auth_service', 'tienda_service']:
    p = os.path.join(base, d, '__pycache__')
    if os.path.exists(p):
        shutil.rmtree(p)
        print(f'Removed {p}')
    else:
        print(f'Not found: {p}')

# Also check for .pyc files
for root, dirs, files in os.walk(base):
    if '__pycache__' in root:
        shutil.rmtree(root)
        print(f'Removed {root}')

print('Done clearing cache')