"""Baseline migration for Tienda schema snapshot.

This migration marks the current state of the Tienda database schema as the baseline.
It does not create or modify any tables - it simply serves as the starting point
for future Alembic versioned migrations.

The actual schema (producto, venta, categoria, marca, proveedor, inventario_movimiento,
caja, alerta, etc.) was established by the application's seed_data.py and/or
manual SQL execution.

Upgrade: No-op. Marks current schema as baseline.
Downgrade: No-op. Cannot safely reverse without risking data loss.
"""

from alembic import op
import sqlalchemy as sa


revision = "001_baseline_tienda"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """No-op: Documenta el esquema actual como punto de partida.
    
    No ejecuta ningún CREATE TABLE / ALTER TABLE contra la BD.
    El estado actual fue establecido por seed_data.py y/o SQL manual.
    """
    # NOTE: This is a no-op baseline migration.
    # The current Tienda schema (producto, venta, categorias, marcas,
    # proveedor, inventario_movimiento, caja, alertas) exists from
    # seed_data.py or manual SQL. This migration simply stamps the
    # baseline so future migrations can be added on top of it.
    pass


def downgrade():
    """No-op: No reverse this baseline.
    
    Reverting the baseline could cause data loss in the shared Supabase
    database. Treat as immutable.
    """
    # NOTE: Downgrade is a no-op. This baseline must not be reversed.
    # Any attempt to drop tables or columns established by seed_data
    # would affect data integrity.
    pass