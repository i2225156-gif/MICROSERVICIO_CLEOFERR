#!/usr/bin/env python
"""Test flow: start both services, test login+JWT, test catalog access."""
import subprocess
import sys
import os
import time
import json
import requests

# Set env vars first
os.environ['SECRET_KEY'] = 'test-jwt-secret-key-long-enough-for-production'
os.environ['DATABASE_URI_AUTH'] = 'postgresql://postgres:postgres@localhost:5432/postgres'
os.environ['DATABASE_URI_TIENDA'] = 'postgresql://postgres:postgres@localhost:5432/postgres_tienda'

def kill_existing():
    """Kill any existing python processes on ports 5001/5002"""
    os.system('taskkill /F /IM python.exe 2>nul')
    time.sleep(2)

def start_service(script_path, port, env_vars=None):
    """Start a Flask service and return the process."""
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)
    proc = subprocess.Popen(
        [sys.executable, script_path],
        cwd='C:\\Users\\Usuario\\Downloads\\automatizacion\\MICROSERVICIO_CLEOFERR',
        env=env,
        stdout=open(f'{port}_out.log', 'w'),
        stderr=open(f'{port}_err.log', 'w')
    )
    return proc

def wait_for_server(port, timeout=15):
    """Wait until server responds on given port."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f'http://127.0.0.1:{port}/')
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False

# Kill any existing
kill_existing()

# Start services
print("Starting auth_service on port 5001...")
p1 = start_service('auth_service\\app.py', 5001)

print("Starting tienda_service on port 5002...")
p2 = start_service('tienda_service\\app.py', 5002)

# Wait for servers
print("Waiting for servers to start...")
if not wait_for_server(5001):
    print("ERROR: auth_service no arrancó")
    with open('auth_err.log') as f:
        print(f.read())
    p1.terminate()
    p2.terminate()
    sys.exit(1)

if not wait_for_server(5002):
    print("ERROR: tienda_service no arrancó")
    with open('tienda_err.log') as f:
        print(f.read())
    p1.terminate()
    p2.terminate()
    sys.exit(1)

print("\nBoth servers are up!")
print()

# Test 1: Login admin
print("=" * 60)
print("TEST 1: POST /login (admin)")
print("=" * 60)
try:
    r = requests.post('http://127.0.0.1:5001/login', data={
        'correo': 'admin@cleoferr.com',
        'clave': 'Admin123!'
    })
    print(f"Status: {r.status_code}")
    body = r.text
    print(f"Body (first 500): {body[:500]}")
    
    if r.status_code != 200:
        print("✗ Login fallido - status no 200")
        p1.terminate()
        p2.terminate()
        sys.exit(1)
    
    data = r.json()
    if not data.get('exito') or 'token' not in data:
        print("✗ Login fallido - respuesta JSON inesperada")
        print(f"Body completo: {body}")
        p1.terminate()
        p2.terminate()
        sys.exit(1)
    
    token = data['token']
    print(f"\n✓ JWT token recibido: {token[:60]}...")
    print(f"Token type: {type(token)}")
except Exception as e:
    print(f"✗ Error en login: {e}")
    p1.terminate()
    p2.terminate()
    sys.exit(1)

print()

# Test 2: GET /catalogo con JWT
print("=" * 60)
print("TEST 2: GET /catalogo con JWT Bearer token")
print("=" * 60)
try:
    r = requests.get('http://127.0.0.1:5002/catalogo', headers={
        'Authorization': f'Bearer {token}'
    })
    print(f"Status: {r.status_code}")
    print(f"Body (first 500): {r.text[:500]}")
    
    if r.status_code == 200:
        # Verify it's real content, not just JSON error
        if 'producto' in r.text.lower() or 'Error' not in r.text[:50]:
            print("\n✓ Catálogo accedido exitosamente con JWT")
            # Show a snippet of catalog data
            import re
            # Look for product names
            products = re.findall(r'"nombre"\s*:\s*"([^"]+)"', r.text)
            if products:
                print(f"  Productos encontrados: {products[:3]}")
            else:
                print("  (cuerpo del catálogo recibido, longitud:", len(r.text), ")")
        else:
            print("✗ Catálogo respondido pero parece error JSON")
    elif r.status_code == 401:
        print("✗ Token inválido o expirado - login requiere re-autenticación")
    else:
        print(f"✗ Status inesperado: {r.status_code}")
except Exception as e:
    print(f"✗ Error al acceder al catálogo: {e}")

print()

# Test 3: Sin token (debe dar 401)
print("=" * 60)
print("TEST 3: GET /catalogo SIN token (debe 401)")
print("=" * 60)
try:
    r = requests.get('http://127.0.0.1:5002/catalogo')
    print(f"Status: {r.status_code}")
    if r.status_code == 401:
        print("✓ Correctamente rechazado sin token (401)")
    else:
        print(f"✗ Se esperaba 401, got {r.status_code}")
        print(f"Body: {r.text[:200]}")
except Exception as e:
    print(f"✗ Error: {e}")

print()

# Test 4: Token corrupto (debe dar 401)
print("=" * 60)
print("TEST 4: GET /catalogo CON TOKEN CORRUPTO (debe 401)")
print("=" * 60)
try:
    r = requests.get('http://127.0.0.1:5002/catalogo', headers={
        'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6-fake-token'
    })
    print(f"Status: {r.status_code}")
    if r.status_code == 401:
        print("✓ Correctamente rechazado con token corrupto (401)")
    else:
        print(f"✗ Se esperaba 401, got {r.status_code}")
        print(f"Body: {r.text[:200]}")
except Exception as e:
    print(f"✗ Error: {e}")

print()
print("=" * 60)
print("ALL TESTS COMPLETED - Now stopping servers")
print("=" * 60)

# Stop services
print("Stopping services...")
p1.terminate()
p2.terminate()
p1.wait()
p2.wait()
print("Services stopped.")

# Show any relevant logs
print("\n--- auth_service errors (if any) ---")
try:
    with open('auth_err.log') as f:
        print(f.read())
except: pass

print("\n--- tienda_service errors (if any) ---")
try:
    with open('tienda_err.log') as f:
        print(f.read())
except: pass