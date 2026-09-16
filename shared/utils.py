"""Utilidades compartidas para auth_service y tienda_service.

Estas funciones ayudan a verificar JWTs y proteger rutas Flask.

Nota: La clave secreta se pasa como parámetro para que cada servicio use
la suya propia desde su .env.
"""

import jwt


def verificar_jwt(token, secret_key):
    """Verifica y decodifica un token JWT.

    Args:
        token: string del token (sin el prefijo "Bearer ").
        secret_key: clave secreta para verificar la firma (debe ser la misma
            que la usada para firmar el token).

    Returns:
        dict con el payload del JWT si es válido y no expirado.

    Raises:
        Exception: Si el token está expirado o es inválido.
    """
    try:
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise Exception("Token expirado")
    except jwt.InvalidTokenError:
        raise Exception("Token inválido")


def extract_token_from_header(auth_header):
    """Extrae el token del header Authorization: Bearer <token>.

    Returns:
        string del token limpio, o None si el header no tiene el formato esperado.
    """
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


def extract_token_from_cookie(cookie_str):
    """Extrae el token del header Set-Cookie o cookie del navegador.
    
    Busca un patron como: token=abc123 o jwt=abc123
    """
    if not cookie_str:
        return None
    # Buscar token en cookie (patrón simple)
    import re
    match = re.search(r'(?:token|jwt)=([^;\s]+)', cookie_str)
    if match:
        return match.group(1)
    return None