#!/usr/bin/env python
# Verify duplicate routes in tienda_service

with open('tienda_service/app.py', 'r') as f:
    lines = f.readlines()

count = 0
for i, line in enumerate(lines, 1):
    line_str = line.strip()
    if '@app.route' in line_str and '/\"" in line_str:
        count += 1
        print(f'L{i}: {line_str[:60]}')

print(f'Total routes with /": {count}')

# Also just count @app.route lines
count2 = sum(1 for l in lines if '@app.route' in l.strip())
print(f'Total @app.route lines: {count2}')