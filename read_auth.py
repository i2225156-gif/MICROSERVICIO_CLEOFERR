with open('auth_service\\app.py', 'r') as f:
    lines = f.readlines()
for i, line in enumerate(lines, 1):
    print(f'{i}: {line}', end='')