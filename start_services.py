import subprocess
import sys
import os
import time
import requests

# DON'T kill existing processes - just start new ones
# The ports 5001/5002 were verified as free earlier

# Start auth_service
auth_proc = subprocess.Popen(
    [sys.executable, 'auth_service\\app.py'],
    cwd='C:\\Users\\Usuario\\Downloads\\automatizacion\\MICROSERVICIO_CLEOFERR',
    stdout=open('auth_out.log', 'w'),
    stderr=open('auth_err.log', 'w')
)

# Start tienda_service
tienda_proc = subprocess.Popen(
    [sys.executable, 'tienda_service\\app.py'],
    cwd='C:\\Users\\Usuario\\Downloads\\automatizacion\\MICROSERVICIO_CLEOFERR',
    stdout=open('tienda_out.log', 'w'),
    stderr=open('tienda_err.log', 'w')
)

print(f'auth_service PID: {auth_proc.pid}')
print(f'tienda_service PID: {tienda_proc.pid}')

# Wait for startup
time.sleep(8)

# Check if running
auth_ok = auth_proc.poll() is None
tienda_ok = tienda_proc.poll() is None

print(f'auth_service running: {auth_ok}')
print(f'tienda_service running: {tienda_ok}')

if auth_ok:
    try:
        r = requests.get('http://127.0.0.1:5001/')
        print(f'auth_service responding: status {r.status_code}, body: {r.text[:100]}')
    except Exception as e:
        print(f'auth_service connection error: {e}')

if tienda_ok:
    try:
        r = requests.get('http://127.0.0.1:5002/')
        print(f'tienda_service responding: status {r.status_code}, body: {r.text[:100]}')
    except Exception as e:
        print(f'tienda_service connection error: {e}')
"