"""Ajout du cadrage des images de personnages

Revision ID: a8b7c6d5e4f3
Revises: 9f4c2a7b1d6e
"""

from alembic import op
import sqlalchemy as sa

revision = "a8b7c6d5e4f3"
down_revision = "c6664a46dd41"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("characters") as batch_op:
        batch_op.add_column(sa.Column("image_x", sa.Float(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("image_y", sa.Float(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("image_scale", sa.Float(), nullable=False, server_default="100"))
        batch_op.add_column(sa.Column("frame_x", sa.Float(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("frame_y", sa.Float(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("frame_scale", sa.Float(), nullable=False, server_default="100"))


def downgrade():
    with op.batch_alter_table("characters") as batch_op:
        batch_op.drop_column("frame_scale")
        batch_op.drop_column("frame_y")
        batch_op.drop_column("frame_x")
        batch_op.drop_column("image_scale")
        batch_op.drop_column("image_y")
        batch_op.drop_column("image_x")
