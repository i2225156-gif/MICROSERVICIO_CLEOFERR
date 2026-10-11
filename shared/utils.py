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


def extract_token_from_cookie(cookie_value):
    """Devuelve el valor de la cookie jwt_token.

    NOTA (bug corregido): antes esta función hacía regex sobre un header
    completo tipo "jwt_token=abc", pero todos los call sites le pasan el
    resultado de request.cookies.get("jwt_token") que YA es solo el valor.
    El regex anterior no hacía match sobre el valor puro y devolvía None,
    rompiendo el login por cookie. Ahora acepta ambas formas por seguridad:
      - valor puro del JWT -> se devuelve tal cual
      - cadena "jwt_token=valor" (header crudo) -> se extrae el valor
    """
    if not cookie_value:
        return None
    import re
    # Si trae formato "nombre=valor", extraer el valor; si no, es el valor puro
    match = re.search(r'(?:jwt_token|token|jwt)=([^;\s]+)', cookie_value)
    if match:
        return match.group(1)
    # Valor puro (un JWT empieza con "eyJ" típicamente, pero no filtramos)
    return cookie_value.strip()