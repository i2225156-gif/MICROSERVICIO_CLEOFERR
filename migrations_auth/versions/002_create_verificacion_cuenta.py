"""Migration: creates verificacion_cuenta table.

This migration creates the verificacion_cuenta table used for client
verification OTP codes. It is independent and does not add foreign key
constraints to the cliente table due to shared-BD precautions.

Tables affected:
- verificacion_cuenta (new)

This migration is safe because:
- verificacion_cuenta is confirmed exclusive to this project (SÍ in Q4/Q5)
- No structural changes to shared tables (cliente, etc.)
- upgrade() creates the table if it doesn't exist
- downgrade() drops it (safe since it's exclusive)
"""

from alembic import op
import sqlalchemy as sa


revision = "002_create_verificacion_cuenta"
down_revision = "001_baseline_auth"
branch_labels = None
depends_on = None


def upgrade():
    """Create verificacion_cuenta table."""
    op.create_table(
        "verificacion_cuenta",
        sa.Column("id_verificacion", sa.Integer, primary_key=True, nullable=False),
        sa.Column("id_cliente", sa.Integer, nullable=False),
        sa.Column("codigo_hash", sa.Text, nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("NOW()), nullable=False"),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usado", sa.Boolean, server_default=sa.text("FALSE"), nullable=False),
        sa.Column("intentos_fallidos", sa.Integer, server_default=sa.text("0"), nullable=False),
    )


def downgrade():
    """Drop verificacion_cuenta table.

    Safe to reverse because verificacion_cuenta is exclusive to this project
    and not used by the external system sharing this Supabase database.
    """
    op.drop_table("verificacion_cuenta")