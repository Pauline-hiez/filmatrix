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


def _postgres_unique_constraint_name(single_column: str) -> str | None:
    """Trouve le nom (auto-généré par Postgres) de la contrainte UNIQUE qui
    ne porte que sur single_column - jamais fiable à deviner à l'avance
    (dépend de la convention de nommage au moment de la création)."""
    bind = op.get_bind()
    row = bind.execute(sa.text("""
        SELECT tc.constraint_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        WHERE tc.table_name = 'tags' AND tc.constraint_type = 'UNIQUE'
        GROUP BY tc.constraint_name
        HAVING COUNT(*) = 1 AND MAX(kcu.column_name::text) = :col
    """), {"col": single_column}).first()
    return row[0] if row else None


def upgrade():
    dialect = op.get_bind().dialect.name

    if dialect == "postgresql":
        # Postgres autorise ALTER TABLE ... DROP CONSTRAINT directement, sans
        # reconstruire la table (contrairement à SQLite) - et c'est heureux :
        # une reconstruction façon SQLite (DROP TABLE + recréation) échoue ici
        # à cause des clés étrangères de question_tags/characters/
        # daily_challenges/album_tags/submission_tags/submission_reviewed_tags,
        # et casserait au passage la séquence d'auto-incrément de l'id
        # (constaté en échec réel au déploiement - la transaction Postgres
        # s'annule proprement, aucune donnée perdue, mais rien n'avance).
        constraint_name = _postgres_unique_constraint_name("name")
        if constraint_name:
            op.drop_constraint(constraint_name, "tags", type_="unique")
        op.create_unique_constraint("uq_tags_name_tag_type", "tags", ["name", "tag_type"])
        return

    # SQLite : l'ancienne contrainte UNIQUE(name) est déclarée en ligne dans
    # le CREATE TABLE d'origine (pas de nom explicite, portée par un
    # autoindex) - ni batch_alter_table seul, ni recreate='always', ne
    # suffisent à la faire disparaître (vérifié empiriquement : elle survit
    # dans les deux cas, aux côtés de la nouvelle contrainte composite).
    # Reconstruction manuelle de la table, seule approche fiable ici - sans
    # risque pour l'auto-incrément sur SQLite (rowid, pas de séquence dédiée).
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
    dialect = op.get_bind().dialect.name

    if dialect == "postgresql":
        op.drop_constraint("uq_tags_name_tag_type", "tags", type_="unique")
        op.create_unique_constraint("uq_tags_name", "tags", ["name"])
        return

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
