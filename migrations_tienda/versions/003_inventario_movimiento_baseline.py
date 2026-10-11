"""Baseline migration for inventario_movimiento schema snapshot.

This migration marks the current state of the inventario_movimiento table schema as the baseline
for the Tienda database. It does not create or modify any tables - it simply serves
as the starting point for future Alembic versioned migrations related to inventory movements.

The actual schema (id_movimiento, tipo, id_producto, id_proveedor, cantidad, precio_unitario,
stock_resultante, observacion, id_usuario, fecha) was established by the application's
seed_data.py and/or manual SQL execution.

Upgrade: No-op. Marks current schema as baseline.
Downgrade: No-op. Cannot safely reverse without risking data loss.
"""

from alembic import op
import sqlalchemy as sa


revision = "003_inventario_movimiento_baseline"
down_revision = "002_proveedor_baseline"
branch_labels = None
depends_on = None


def upgrade():
    """No-op: Documenta el esquema actual como punto de partida.
    
    No ejecuta ningún CREATE TABLE / ALTER TABLE contra la BD.
    El estado actual fue establecido por seed_data.py y/o SQL manual.
    Se trata la tabla 'inventario_movimiento' con precaución máxima por posible compartición.
    """
    # NOTE: This is a no-op baseline migration.
    # The current inventario_movimiento schema exists from seed_data.py or manual SQL.
    # This migration simply stamps the baseline so future migrations
    # can be added on top of it. No structural changes are made.
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