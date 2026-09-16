@echo off
set SECRET_KEY=test-jwt-secret-key-long-enough-for-production
set DATABASE_URI_AUTH=postgresql://postgres:postgres@localhost:5432/postgres
set DATABASE_URI_TIENDA=postgresql://postgres:postgres@localhost:5432/postgres_tienda

cd "C:\Users\Usuario\Downloads\automatizacion\MICROSERVICIO_CLEOFERR"

rem Start auth_service
start "auth_service" /b python auth_service\app.py > auth_out.log 2>&1
timeout /t 3 >nul

start "tienda_service" /b python tienda_service\app.py > tienda_out.log 2>&1
timeout /t 3 >nul

echo Services started
echo auth_service PID: %%
echo tienda_service PID: %%