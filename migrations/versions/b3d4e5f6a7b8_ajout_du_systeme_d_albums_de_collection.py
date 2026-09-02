"""Ajout du système d'albums de collection

Revision ID: b3d4e5f6a7b8
Revises: a8b7c6d5e4f3
"""

from alembic import op
import sqlalchemy as sa

revision = "b3d4e5f6a7b8"
down_revision = "a8b7c6d5e4f3"
branch_labels = None
depends_on = None


def _humanize(name: str) -> str:
    """Transforme un slug en vrai nom : indiana-jones -> Indiana Jones."""
    if " " in name or any(char.isupper() for char in name):
        return name
    return name.replace("-", " ").title()


def upgrade():
    op.create_table(
        "albums",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=280), nullable=True),
        sa.Column("image_url", sa.String(length=255), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("name", name="uq_albums_name"),
    )
    op.create_table(
        "album_tags",
        sa.Column("album_id", sa.Integer(), sa.ForeignKey("albums.id"), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id"), primary_key=True),
    )
    op.create_table(
        "album_characters",
        sa.Column("album_id", sa.Integer(), sa.ForeignKey("albums.id"), primary_key=True),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("characters.id"), primary_key=True),
    )

    # On ne perd aucune collection existante : chaque saga/univers qui possède
    # des personnages devient un album, lié à son tag, avec ses personnages.
    bind = op.get_bind()
    from sqlalchemy import text

    rows = bind.execute(
        text(
            "SELECT t.id AS tag_id, t.name AS tag_name FROM tags t "
            "WHERE t.tag_type IN ('saga', 'univers') "
            "AND EXISTS (SELECT 1 FROM characters c WHERE c.tag_id = t.id)"
        )
    ).fetchall()

    used_names = {
        row[0]
        for row in bind.execute(text("SELECT name FROM albums")).fetchall()
    }

    for tag_id, tag_name in rows:
        base = _humanize(tag_name)
        name = base
        suffix = 2
        while name in used_names:
            name = f"{base} {suffix}"
            suffix += 1
        used_names.add(name)

        bind.execute(
            text(
                "INSERT INTO albums (name, sort_order, is_published, created_at) "
                "VALUES (:name, 0, 1, CURRENT_TIMESTAMP)"
            ),
            {"name": name},
        )
        album_id = bind.execute(
            text("SELECT id FROM albums WHERE name = :name"), {"name": name}
        ).scalar()

        bind.execute(
            text("INSERT INTO album_tags (album_id, tag_id) VALUES (:album, :tag)"),
            {"album": album_id, "tag": tag_id},
        )
        bind.execute(
            text(
                "INSERT INTO album_characters (album_id, character_id) "
                "SELECT :album, id FROM characters WHERE tag_id = :tag"
            ),
            {"album": album_id, "tag": tag_id},
        )


def downgrade():
    op.drop_table("album_characters")
    op.drop_table("album_tags")
    op.drop_table("albums")
