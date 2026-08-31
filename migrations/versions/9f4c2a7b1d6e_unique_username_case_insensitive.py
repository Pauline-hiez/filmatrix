"""unique username case insensitive

Revision ID: 9f4c2a7b1d6e
Revises: b1c3986bae79
Create Date: 2026-08-31

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9f4c2a7b1d6e"
down_revision = "53dc09a277e0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "uq_users_username_lower",
        "users",
        [sa.text("lower(username)")],
        unique=True,
    )


def downgrade():
    op.drop_index("uq_users_username_lower", table_name="users")
