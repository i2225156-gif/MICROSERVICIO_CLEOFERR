"""Baseline migration for cliente schema snapshot.

This migration marks the current state of the cliente table schema as the baseline
for the Auth database. It does not create or modify any tables - it simply serves
as the starting point for future Alembic versioned migrations related to the cliente
table, considering it may be shared with an external system.

The actual schema (id_tipo_documento, nro_documento, nombre, apellido, email,
telefono, direccion, contrasena, activo, origen) was established by the application's
bootstrap process (_inicializar_schema_auth in app.py) and/or manual SQL execution.

Upgrade: No-op. Marks current schema as baseline.
Downgrade: No-op. Cannot safely reverse without risking data loss in shared DB.
"""

from alembic import op
import sqlalchemy as sa


revision = "004_cliente_baseline"
down_revision = "003_create_recuperacion_contrasena"
branch_labels = None
depends_on = None


def upgrade():
    """No-op: Documenta el esquema actual como punto de partida.
    
    No ejecuta ningún CREATE TABLE / ALTER TABLE contra la BD.
    El estado actual fue establecido por el bootstrap de app.py y/o SQL manual.
    Se trata la tabla 'cliente' como compartida con máxima precaución.
    """
    # NOTE: This is a no-op baseline migration.
    # The current cliente schema exists from app.py bootstrap or manual SQL.
    # This migration simply stamps the baseline so future migrations
    # can be added on top of it. No structural changes are made.
    pass


def downgrade():
    """No-op: No reverse this baseline.
    
    Reverting the baseline could cause data loss or break the other system
    sharing this Supabase database. Treat as immutable.
    """
    # NOTE: Downgrade is a no-op. This baseline must not be reversed.
    # Any attempt to drop tables or columns established by the bootstrap
    # would affect the other system using this shared Supabase database.
    pass