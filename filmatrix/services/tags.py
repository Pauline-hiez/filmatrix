"""Fusion de tags dupliqués depuis l'écran d'administration."""

from filmatrix.extensions import db
from filmatrix.models import Character, DailyChallenge, Tag, question_tags


def merge_tag_into(keeper: Tag, dup: Tag) -> None:
    """Déplace toutes les références de `dup` vers `keeper`, puis supprime `dup`."""
    keeper_question_ids = {
        row.question_id
        for row in db.session.execute(
            question_tags.select().where(question_tags.c.tag_id == keeper.id)
        )
    }

    # Les questions déjà liées au keeper et au dup n'ont pas besoin d'une
    # seconde entrée : on supprime la ligne du dup, sinon le UPDATE suivant
    # créerait un doublon de clé primaire (question_id, tag_id).
    for row in db.session.execute(
        question_tags.select().where(question_tags.c.tag_id == dup.id)
    ):
        if row.question_id in keeper_question_ids:
            db.session.execute(
                question_tags.delete().where(
                    question_tags.c.tag_id == dup.id,
                    question_tags.c.question_id == row.question_id,
                )
            )

    db.session.execute(
        question_tags.update()
        .where(question_tags.c.tag_id == dup.id)
        .values(tag_id=keeper.id)
    )
    Character.query.filter_by(tag_id=dup.id).update({"tag_id": keeper.id})
    DailyChallenge.query.filter_by(target_tag_id=dup.id).update({"target_tag_id": keeper.id})
    db.session.delete(dup)
