import requests

s = requests.Session()
r = s.post(
    "http://127.0.0.1:5001/login",
    data={"correo": "admin@cleoferr.com", "clave": "Admin123!"},
    headers={
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "http://127.0.0.1:5001/login",
    },
    allow_redirects=False,
)
print("status:", r.status_code)
print("Set-Cookie:", r.headers.get("Set-Cookie", "(ninguna - AQUI ESTA EL BUG)"))
print("cookies:", dict(s.cookies))
print("body:", r.text[:200])
