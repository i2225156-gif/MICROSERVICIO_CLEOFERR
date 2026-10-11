"""Baseline migration for Auth schema snapshot.

This migration marks the current state of the Auth database schema as the baseline.
It does not create or modify any tables - it simply serves as the starting point
for future Alembic versioned migrations.

The actual schema (verificacion_cuenta, recuperacion_contrasena, cliente columns,
unique indexes, etc.) was established by the application's bootstrap process
(_inicializar_schema_auth in app.py) and/or manual SQL execution.

Upgrade: No-op. Marks current schema as baseline.
Downgrade: No-op. Cannot safely reverse without risking data loss in shared DB.
"""

from alembic import op
import sqlalchemy as sa


revision = "001_baseline_auth"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """No-op: Documenta el esquema actual como punto de partida.
    
    No ejecuta ningún CREATE TABLE / ALTER TABLE contra la BD.
    El estado actual fue establecido por el bootstrap de app.py y/o SQL manual.
    """
    # NOTE: This is a no-op baseline migration.
    # The current Auth schema (verificacion_cuenta, recuperacion_contrasena,
    # cliente columns/indices) exists from app.py bootstrap or manual SQL.
    # This migration simply stamps the baseline so future migrations
    # can be added on top of it.
    pass


def downgrade():
    """No-op: No reverse this baseline.
    
    Reverting the baseline could data loss or break the other system
    sharing this Supabase database. Treat as immutable.
    """
    # NOTE: Downgrade is a no-op. This baseline must not be reversed.
    # Any attempt to drop tables or columns established by the bootstrap
    # would affect the other system using this shared Supabase database.
    pass