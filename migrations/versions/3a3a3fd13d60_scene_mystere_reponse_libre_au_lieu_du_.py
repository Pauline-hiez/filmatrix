"""scene mystere reponse libre au lieu du qcm

Revision ID: 3a3a3fd13d60
Revises: bf129d47f2b1
Create Date: 2026-09-25 10:47:43.618270

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3a3a3fd13d60'
down_revision = 'bf129d47f2b1'
branch_labels = None
depends_on = None


mystery_options = sa.table(
    "mystery_options",
    sa.column("id", sa.Integer),
    sa.column("zone_id", sa.Integer),
    sa.column("label", sa.String),
    sa.column("is_correct", sa.Boolean),
    sa.column("order_index", sa.Integer),
)

mystery_answers = sa.table(
    "mystery_answers",
    sa.column("id", sa.Integer),
    sa.column("zone_id", sa.Integer),
    sa.column("text", sa.String),
    sa.column("is_correct", sa.Boolean),
    sa.column("order_index", sa.Integer),
)


def upgrade():
    # Le joueur tape désormais lui-même le nom de l'œuvre au lieu de choisir
    # dans un QCM à 4 options : les options fausses (is_correct=False)
    # n'ont plus aucun rôle et sont supprimées avant la bascule de schéma ;
    # l'option correcte de chaque zone devient sa première réponse acceptée.
    bind = op.get_bind()
    bind.execute(mystery_options.delete().where(mystery_options.c.is_correct.is_(False)))

    op.rename_table("mystery_options", "mystery_answers")
    with op.batch_alter_table("mystery_answers", schema=None) as batch_op:
        batch_op.alter_column("label", new_column_name="text")
        batch_op.drop_column("is_correct")


def downgrade():
    # Downgrade non fidèle à 100% : les options fausses supprimées à l'upgrade
    # ne sont pas recréées (elles n'existent plus nulle part). Chaque réponse
    # restante redevient une option correcte isolée.
    with op.batch_alter_table("mystery_answers", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_correct", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.alter_column("text", new_column_name="label")

    op.rename_table("mystery_answers", "mystery_options")
