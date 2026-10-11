"""Migration: creates recuperacion_contrasena table.

This migration creates the recuperacion_contrasena table used for password
recovery OTP codes. Like verificacion_cuenta, it is independent and does
not add foreign key constraints to shared tables due to shared-BD precautions.

Tables affected:
- recuperacion_contrasena (new)

This migration is safe because:
- recuperacion_contrasena is confirmed exclusive to this project (SÍ in Q6/Q7)
- No structural changes to shared tables (cliente, etc.)
- The id_usuario and id_cliente columns allow NULL, making it flexible
- upgrade() creates the table if it doesn't exist
- downgrade() drops it (safe since it's exclusive)
"""

from alembic import op
import sqlalchemy as sa


revision = "003_create_recuperacion_contrasena"
down_revision = "002_create_verificacion_cuenta"
branch_labels = None
depends_on = None


def upgrade():
    """Create recuperacion_contrasena table."""
    op.create_table(
        "recuperacion_contrasena",
        sa.Column("id_recuperacion", sa.Integer, primary_key=True, nullable=False),
        sa.Column("id_usuario", sa.Integer, nullable=True),
        sa.Column("id_cliente", sa.Integer, nullable=True),
        sa.Column("codigo_hash", sa.Text, nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("NOW()), nullable=False"),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usado", sa.Boolean, server_default=sa.text("FALSE"), nullable=False),
        sa.Column("intentos_fallidos", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("ip_solicitud", sa.VARCHAR(64), nullable=True),
    )


def downgrade():
    """Drop recuperacion_contrasena table.

    Safe to reverse because recuperacion_contrasena is exclusive to this project
    and not used by the external system sharing this Supabase database.
    The id_usuario and id_cliente columns are nullable, further reducing
    risk of affecting shared schema objects.
    """
    op.drop_table("recuperacion_contrasena")