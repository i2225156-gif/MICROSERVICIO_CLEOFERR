# Prueba del bloque Verificacion de cuentas + filtro de periodo.
import urllib.request, urllib.error, urllib.parse, http.cookiejar
from dotenv import load_dotenv
load_dotenv()

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj),
                                     urllib.request.HTTPRedirectHandler())
def req(url, data=None, headers=None, method=None):
    r = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        resp = opener.open(r); return resp.status, resp.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")

s, b = req("http://127.0.0.1:5001/login",
           urllib.parse.urlencode({"correo": "admin@cleoferr.com", "clave": "Admin123!"}).encode(),
           {"Content-Type": "application/x-www-form-urlencoded"}, "POST")
print("login:", s)

# 1) titulo nuevo + bloque verificacion presente
s, b = req("http://127.0.0.1:5002/reportes")
t1 = "REPORTES DE NEGOCIO" in b
t2 = "Clientes que completaron su registro" in b
t3 = "Códigos enviados en el periodo" in b
t4 = "Clientes que no terminaron de registrarse" in b
t5 = "Periodo" in b and 'name="periodo"' in b
print(f"[1] /reportes: {s} titulo={t1} bloque_vf={t2} kpi_tasa={t3} kpi_sin_usar={t4} selector={t5}")

# 2) periodos
for p in ("semanal", "mensual", "anual", "personalizado"):
    s, b = req(f"http://127.0.0.1:5002/reportes/generar?tipo=ventas&periodo={p}&desde=&hasta=")
    vf_ok = "Clientes que completaron su registro" in b
    print(f"[2] periodo={p}: status={s} vf_bloque={vf_ok}")

ok = all([t1, t2, t3, t4, t5]) and s == 200
print("\nRESULTADO:", "OK" if ok else "FALLA")
