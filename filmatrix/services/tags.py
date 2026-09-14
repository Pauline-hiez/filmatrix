"""Fusion de tags dupliqués depuis l'écran d'administration."""

from filmatrix.extensions import db
from filmatrix.models import (
    Character,
    DailyChallenge,
    Tag,
    album_tags,
    question_tags,
    submission_reviewed_tags,
    submission_tags,
)

# Toute table d'association (secondary=) qui référence tags.id : un tag
# fusionné doit voir TOUTES ses références déplacées, pas seulement celles
# des questions publiées - un tag encore porté par une suggestion en attente
# (submission_tags) ou son historique de revue (submission_reviewed_tags)
# laisserait sinon des lignes orphelines une fois `dup` supprimé (incident
# rencontré une première fois avec un lot de suggestions généré en masse).
ASSOCIATION_TABLES = (question_tags, submission_tags, submission_reviewed_tags, album_tags)


def merge_tag_into(keeper: Tag, dup: Tag) -> None:
    """Déplace toutes les références de `dup` vers `keeper`, puis supprime `dup`."""
    for table in ASSOCIATION_TABLES:
        owner_column = table.c[table.columns.keys()[0]]  # question_id / submission_id / album_id...

        keeper_owner_ids = {
            row[0]
            for row in db.session.execute(table.select().where(table.c.tag_id == keeper.id))
        }

        # Une ligne déjà liée au keeper n'a pas besoin d'une seconde entrée
        # pour dup : on la supprime, sinon le UPDATE suivant créerait un
        # doublon de clé primaire (owner_id, tag_id).
        for row in db.session.execute(table.select().where(table.c.tag_id == dup.id)):
            if row[0] in keeper_owner_ids:
                db.session.execute(
                    table.delete().where(table.c.tag_id == dup.id, owner_column == row[0])
                )

        db.session.execute(table.update().where(table.c.tag_id == dup.id).values(tag_id=keeper.id))

    Character.query.filter_by(tag_id=dup.id).update({"tag_id": keeper.id})
    DailyChallenge.query.filter_by(target_tag_id=dup.id).update({"target_tag_id": keeper.id})
    db.session.delete(dup)
