"""retrait de category et difficulty sur questions

La difficulté est désormais un réglage choisi par le joueur avant la partie
(voir filmatrix/services/levels.py) : elle ne fixe plus que le chrono et les
récompenses, et n'a plus à être portée par chaque question. La catégorie, elle,
n'était plus utilisée par aucun écran de jeu.

Revision ID: d5f2a91c7b08
Revises: 387acc3d06a2
Create Date: 2026-08-28

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd5f2a91c7b08'
down_revision = '387acc3d06a2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.drop_column('category')
        batch_op.drop_column('difficulty')


def downgrade():
    # Les valeurs d'origine ne sont pas récupérables : on remet les colonnes
    # avec une valeur de repli, ce qui suffit à satisfaire la contrainte NOT NULL.
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('category', sa.String(length=50),
                                      nullable=False, server_default='anecdote'))
        batch_op.add_column(sa.Column('difficulty', sa.String(length=20),
                                      nullable=False, server_default='moyen'))
