"""Módulo de acceso a datos compartido para auth_service y tienda_service.

Cada servicio llama a la función correspondiente según su necesidad:
- crear_engine_auth() → engine para BD auth (usuarios, cliente, rol, sesion, verificacion_cuenta)
- crear_engine_tienda() → engine para BD tienda (producto, venta, inventario, caja, etc.)

Cada servicio crea su propio engine y lo pasa a SQLAlchemy(db=).
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

load_dotenv()

# Opciones de engine compartidas (NullPool por Supabase)
_ENGINE_OPTIONS = {
    "poolclass": NullPool,
}


def crear_engine_auth():
    """Crea y retorna el engine para la base de datos de autenticación."""
    from sqlalchemy import create_engine
    uri = os.environ.get("DATABASE_URI_AUTH")
    if not uri:
        raise RuntimeError(
            "DATABASE_URI_AUTH no definida en el archivo .env. "
            "Revisa la variable de entorno."
        )
    return create_engine(uri, **_ENGINE_OPTIONS)


def crear_engine_tienda():
    """Crea y retorna el engine para la base de datos de la tienda."""
    from sqlalchemy import create_engine
    uri = os.environ.get("DATABASE_URI_TIENDA")
    if not uri:
        raise RuntimeError(
            "DATABASE_URI_TIENDA no definida en el archivo .env. "
            "Revisa la variable de entorno."
        )
    return create_engine(uri, **_ENGINE_OPTIONS)