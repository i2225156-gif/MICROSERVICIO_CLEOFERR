import os
os.chdir(r'C:\Users\Usuario\Downloads\automatizacion\MICROSERVICIO_CLEOFERR')

with open('tienda_service\\app.py', 'r') as f:
    lines = f.readlines()

count = 0
for i, line in enumerate(lines, 1):
    if '@app.route' in line and '/\"" in line:
        count += 1
        print(f'L{i}: {line.strip()[:60]}')

print(f'Total routes with /": {count}')