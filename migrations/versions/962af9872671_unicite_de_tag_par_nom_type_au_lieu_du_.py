"""unicite de tag par (nom, type) au lieu du nom seul

Revision ID: 962af9872671
Revises: 31d84dfdb01a
Create Date: 2026-09-11 10:33:23.714713

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '962af9872671'
down_revision = '31d84dfdb01a'
branch_labels = None
depends_on = None


def upgrade():
    # L'ancienne contrainte UNIQUE(name) est déclarée en ligne dans le CREATE
    # TABLE d'origine (pas de nom explicite, portée par un autoindex SQLite) :
    # ni batch_alter_table seul, ni recreate='always', ne suffisent à la
    # faire disparaître (vérifié empiriquement : elle survit dans les deux
    # cas, aux côtés de la nouvelle contrainte composite). Reconstruction
    # manuelle de la table en SQL brut, seule approche fiable ici.
    op.execute("""
        CREATE TABLE tags_new (
            id INTEGER NOT NULL PRIMARY KEY,
            name VARCHAR(50) NOT NULL,
            tag_type VARCHAR(20) NOT NULL,
            CONSTRAINT uq_tags_name_tag_type UNIQUE (name, tag_type)
        )
    """)
    op.execute("INSERT INTO tags_new (id, name, tag_type) SELECT id, name, tag_type FROM tags")
    op.execute("DROP TABLE tags")
    op.execute("ALTER TABLE tags_new RENAME TO tags")


def downgrade():
    op.execute("""
        CREATE TABLE tags_new (
            id INTEGER NOT NULL PRIMARY KEY,
            name VARCHAR(50) NOT NULL UNIQUE,
            tag_type VARCHAR(20) NOT NULL
        )
    """)
    op.execute("INSERT INTO tags_new (id, name, tag_type) SELECT id, name, tag_type FROM tags")
    op.execute("DROP TABLE tags")
    op.execute("ALTER TABLE tags_new RENAME TO tags")
