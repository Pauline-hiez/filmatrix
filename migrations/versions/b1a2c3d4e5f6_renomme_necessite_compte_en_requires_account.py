"""renomme necessite_compte en requires_account

Revision ID: b1a2c3d4e5f6
Revises: 75606549a741
Create Date: 2026-08-05

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1a2c3d4e5f6'
down_revision = '75606549a741'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.alter_column(
            'necessite_compte',
            new_column_name='requires_account',
            existing_type=sa.Boolean(),
            existing_nullable=False,
            existing_server_default=sa.false(),
        )


def downgrade():
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.alter_column(
            'requires_account',
            new_column_name='necessite_compte',
            existing_type=sa.Boolean(),
            existing_nullable=False,
            existing_server_default=sa.false(),
        )
