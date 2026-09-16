import sys
sys.path.insert(0, r'C:\Users\Usuario\Downloads\automatizacion\MICROSERVICIO_CLEOFERR')

# Test 1: Direct bcrypt.checkpw
import bcrypt
hash_from_db = '$2b$12$Gc96OXiKc8BPrxLGHt09XOAxZeQrGu42S4hAiTr/Lmc.ouD21S.rK'
password = 'Admin123!'

try:
    result = bcrypt.checkpw(password.encode('utf-8'), hash_from_db.encode('utf-8'))
    print(f'Test 1 - bcrypt.checkpw with DB hash: {result}')
except Exception as e:
    print(f'Test 1 - bcrypt.checkpw with DB hash error: {type(e).__name__}: {e}')

# Test 2: With generated hash
test_password = 'Admin123!'
generated_hash = bcrypt.hashpw(test_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
print(f'Test 2 - Generated hash: {generated_hash}')

try:
    result = bcrypt.checkpw(test_password.encode('utf-8'), generated_hash.encode('utf-8'))
    print(f'Test 2 - bcrypt.checkpw with generated hash: {result}')
except Exception as e:
    print(f'Test 2 - error: {type(e).__name__}: {e}')

# Test 3: Flask-Bcrypt instance method
from auth_service.app import app, bcrypt as app_bcrypt
print(f'Test 3 - app_bcrypt type: {type(app_bcrypt)}')

# Test 4: Flask-Bcrypt with generated hash
try:
    result = app_bcrypt.check_password_hash(generated_hash, test_password)
    print(f'Test 3a - Flask-Bcrypt with generated hash: {result}')
except Exception as e:
    print(f'Test 3a - Flask-Bcrypt with generated hash error: {type(e).__name__}: {e}')

# Test 5: Flask-Bcrypt with DB hash
try:
    result = app_bcrypt.check_password_hash(hash_from_db, test_password)
    print(f'Test 3b - Flask-Bcrypt with DB hash: {result}')
except Exception as e:
    print(f'Test 3b - Flask-Bcrypt with DB hash error: {type(e).__name__}: {e}')