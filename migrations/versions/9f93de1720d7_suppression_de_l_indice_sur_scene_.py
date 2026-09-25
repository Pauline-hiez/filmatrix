"""suppression de l indice sur scene mystere

Revision ID: 9f93de1720d7
Revises: 3a3a3fd13d60
Create Date: 2026-09-25 11:05:41.438006

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9f93de1720d7'
down_revision = '3a3a3fd13d60'
branch_labels = None
depends_on = None


def upgrade():
    # Le joueur ne reçoit plus aucun indice avant de cliquer : contrairement
    # à Cache-Ciné (qui donne la liste des titres à chercher), Scène Mystère
    # ne guide plus du tout — il clique sur ce qu'il repère lui-même, puis
    # tape le nom de l'œuvre.
    with op.batch_alter_table("mystery_zones", schema=None) as batch_op:
        batch_op.drop_column("clue_text")


def downgrade():
    # Downgrade non fidèle : le texte des indices supprimés à l'upgrade n'est
    # pas récupérable, la colonne revient vide.
    with op.batch_alter_table("mystery_zones", schema=None) as batch_op:
        batch_op.add_column(sa.Column("clue_text", sa.String(length=255), nullable=False, server_default=""))
