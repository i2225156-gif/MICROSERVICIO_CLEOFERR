import subprocess
import time
import sys
import os
import requests

# Set environment variables
os.environ['SECRET_KEY'] = 'test-jwt-secret-key-must-be-long-enough'
os.environ['DATABASE_URI_AUTH'] = 'postgresql://postgres:postgres@localhost:5432/postgres'
os.environ['DATABASE_URI_TIENDA'] = 'postgresql://postgres:postgres@localhost:5432/postgres_tienda'

# Kill any existing python processes on ports 5001/5002
try:
    os.system('taskkill /F /IM python.exe 2>nul')
    time.sleep(1)
except:
    pass

# Start auth_service
print("Iniciando auth_service...")
proc = subprocess.Popen(
    [sys.executable, "auth_service\\app.py"],
    cwd="C:\\Users\\Usuario\\Downloads\\automatizacion\\MICROSERVICIO_CLEOFERR",
    stdout=open("auth_service_out.log", "w"),
    stderr=open("auth_service_err.log", "w")
)
print(f"PID: {proc.pid}")
time.sleep(3)

# Verificar que el servidor está arriba
try:
    r = requests.get("http://127.0.0.1:5001/")
    print(f"Servidor arriba: status {r.status_code}")
except Exception as e:
    print(f"Servidor no respondiendo: {e}")
    print("Contenido de error log:")
    with open("auth_service_err.log") as f:
        print(f.read())
    proc.terminate()
    sys.exit(1)

# Probar login administrativo
print("\n--- TEST: POST /login (admin) ---")
try:
    r = requests.post("http://127.0.0.1:5001/login", data={
        "correo": "admin@cleoferr.com",
        "clave": "Admin123!",
    })
    print(f"Status: {r.status_code}")
    print(f"Body: {r.text[:500]}")
    
    if r.status_code == 200:
        data = r.json()
        if data.get("exito") and "token" in data:
            token = data["token"]
            print(f"\n✓ Login exitoso!")
            print(f"Token: {token[:80]}...")
            
            # Probar acceder con el token al catálogo (aunque es auth_service, probemos un endpoint protegido)
            print("\n--- TEST: GET / con token ---")
            r2 = requests.get("http://127.0.0.1:5001/", headers={"Authorization": f"Bearer {token}"})
            print(f"Status: {r2.status_code}")
            print(f"Body: {r2.text[:200]}")
            
            # Probar sin token
            print("\n--- TEST: GET / sin token ---")
            r3 = requests.get("http://127.0.0.1:5001/")
            print(f"Status: {r3.status_code}")
            print(f"Body: {r3.text[:200]}")
        else:
            print(f"✗ Respuesta inesperada: {data}")
    else:
        print("✗ Login fallido")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    # Detener proceso
    proc.terminate()
    proc.wait()
    print("\n--- Servidor detenido ---")
    
    # Mostrar logs si hay error
    if proc.returncode != 0:
        print("Errores en el log:")
        with open("auth_service_err.log") as f:
            print(f.read())