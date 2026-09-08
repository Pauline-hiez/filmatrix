"""ajout de difficulty sur questions

La difficulté redevient un attribut de chaque question, plutôt qu'un réglage
choisi par le joueur avant la partie (voir filmatrix/services/levels.py) :
c'est elle qui fixe désormais le chrono et les gains d'une question donnée.
Aucune valeur d'origine n'est récupérable (colonne déjà supprimée par
d5f2a91c7b08) : toutes les questions existantes reçoivent "moyen".

Revision ID: 5489101f9e0f
Revises: ac3cc90a5893
Create Date: 2026-09-08 13:38:12.337620

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5489101f9e0f'
down_revision = 'ac3cc90a5893'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('difficulty', sa.String(length=20),
                                      nullable=False, server_default='moyen'))
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.alter_column('difficulty',
                              existing_type=sa.String(length=20),
                              existing_nullable=False,
                              server_default=None)


def downgrade():
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.drop_column('difficulty')
