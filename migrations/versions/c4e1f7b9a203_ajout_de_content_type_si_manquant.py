"""ajout de content_type si manquant

Revision ID: c4e1f7b9a203
Revises: 52d3ad0dcab3
Create Date: 2026-08-27 14:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4e1f7b9a203'
down_revision = '52d3ad0dcab3'
branch_labels = None
depends_on = None


def upgrade():
    # Migration de reparation : l'ancien build.sh faisait "flask db stamp head"
    # au lieu de "flask db upgrade", donc la base de production a ete marquee
    # comme etant a jour alors que 52d3ad0dcab3 n'avait jamais tourne.
    # On rattrape la colonne manquante, et on ne fait rien la ou elle existe deja.
    colonnes = [c["name"] for c in sa.inspect(op.get_bind()).get_columns("questions")]
    if "content_type" in colonnes:
        return

    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('content_type', sa.String(length=10),
                                      nullable=False, server_default='film'))

    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.alter_column('content_type',
                              existing_type=sa.String(length=10),
                              existing_nullable=False,
                              server_default=None)


def downgrade():
    # La colonne appartient a 52d3ad0dcab3, c'est a elle de la supprimer.
    pass
