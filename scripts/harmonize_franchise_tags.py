"""Harmonise les noms des tags de franchise (saga / univers).

Corrige le doublon slug <-> nom humanisé (ex. « breaking-bad » vs
« Breaking Bad ») qui fait apparaître chaque univers en double dans le
sélecteur de jeu et qui répartit les questions entre deux tags.

- Fusionne les tags d'une même franchise (clé = nom normalisé sans accents
  ni ponctuation) en gardant le nom humanisé, et déplace vers lui les
  questions, les personnages et les défis quotidiens qui pointaient vers les
  doublons. La clé ignore aussi les apostrophes pour rattraper les variantes
  typographiques (« Maman j'ai raté l'avion » vs « Maman Jai Rate Lavion »).
- Fusionne les tags genre/autre qui portent en réalité un nom de franchise
  (ex. « Star Wars » classé genre) dans le tag de franchise correspondant.
- Renomme les tags encore en slug vers leur vrai nom (indiana-jones -> Indiana
  Jones), sans collision avec un tag existant.
- Supprime les tags de franchise devenus orphelins (aucune question, aucun
  personnage) pour ne pas laisser de slug vide derrière.

Idempotent : relancer ce script ne change plus rien.

    python -m scripts.harmonize_franchise_tags
"""
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.exc import IntegrityError

from wsgi import app

from filmatrix.extensions import db
from filmatrix.models import Character, DailyChallenge, Tag, question_tags
from filmatrix.catalog_rarities import humanize_tag_name

FRANCHISE_TYPES = ("saga", "univers")


def key(name: str) -> str:
    """Clé de normalisation : minuscules sans accents ni ponctuation.

    On ne remplace pas la ponctuation par un tiret mais on la supprime :
    c'est ce qui permet de rapprocher « j'ai » de « jai » (variante de saisie
    sans apostrophe) comme « Ça » de « Ca ».
    """
    decomposed = unicodedata.normalize("NFKD", name.lower())
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", without_accents)


def is_slug(name: str) -> bool:
    """Un nom est un slug s'il est en minuscules sans espace ni majuscule."""
    return " " not in name and not any(char.isupper() for char in name)


def move_tag_references(keeper: Tag, dup: Tag) -> None:
    """Déplace toutes les références de `dup` vers `keeper`."""
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


def merge_groups() -> int:
    """Fusionne les tags d'une même franchise. Renvoie le nombre de suppressions."""
    tags = Tag.query.filter(Tag.tag_type.in_(FRANCHISE_TYPES)).all()

    groups: dict[tuple[str, str], list[Tag]] = {}
    for tag in tags:
        groups.setdefault((tag.tag_type, key(tag.name)), []).append(tag)

    deleted = 0
    for (tag_type, _), members in groups.items():
        if len(members) < 2:
            continue
        # On garde de préférence le nom humanisé.
        keeper = next((m for m in members if not is_slug(m.name)), members[0])
        for member in members:
            if member.id == keeper.id:
                continue
            move_tag_references(keeper, member)
            deleted += 1
            print(f"  fusion {member.name!r} ({member.tag_type}) -> {keeper.name!r}")

    return deleted


def merge_cross_type() -> int:
    """Fusionne les tags d'une même franchise répartis entre saga et univers.

    Ex. ``halloween`` (saga) et ``Halloween`` (univers) : la même œuvre, deux
    tags. On garde de préférence l'univers (le sélecteur met les univers en
    avant) et on rabat tout le reste dessus.
    """
    groups: dict[str, list[Tag]] = {}
    for tag in Tag.query.filter(Tag.tag_type.in_(FRANCHISE_TYPES)).all():
        groups.setdefault(key(tag.name), []).append(tag)

    deleted = 0
    for _, members in groups.items():
        if len(members) < 2:
            continue
        # Priorité : univers > saga, puis nom humanisé > slug.
        keeper = min(
            members,
            key=lambda t: (0 if t.tag_type == "univers" else 1, 0 if not is_slug(t.name) else 1),
        )
        for member in members:
            if member.id == keeper.id:
                continue
            move_tag_references(keeper, member)
            deleted += 1
            print(
                f"  fusion inter-types {member.name!r} ({member.tag_type}) -> "
                f"{keeper.name!r} ({keeper.tag_type})"
            )

    return deleted


def humanize_remaining_slugs() -> int:
    """Renomme les tags de franchise encore en slug, en évitant toute collision.

    Chaque renommage est committé isolément : si un nom est déjà pris (contrainte
    UNIQUE), on espace ("Conjuring", "Conjuring 2", ...) sans jamais échouer.
    """
    tags = Tag.query.filter(Tag.tag_type.in_(FRANCHISE_TYPES)).all()
    taken = {tag.name for tag in tags}

    renamed = 0
    for tag in tags:
        if not is_slug(tag.name):
            continue
        base = humanize_tag_name(tag.name)
        new_name = base
        suffix = 2
        while new_name in taken:
            new_name = f"{base} {suffix}"
            suffix += 1

        old_name = tag.name
        try:
            tag.name = new_name
            db.session.commit()
            taken.add(new_name)
            renamed += 1
            print(f"  renomme {old_name!r} -> {new_name!r}")
        except IntegrityError:
            db.session.rollback()
            print(f"  renommage ignoré {old_name!r} (collision)")

    return renamed


def purge_orphan_franchise_tags() -> int:
    """Supprime les tags de franchise sans question ni personnage."""
    deleted = 0
    for tag in Tag.query.filter(Tag.tag_type.in_(FRANCHISE_TYPES)).all():
        has_questions = db.session.execute(
            question_tags.select().where(question_tags.c.tag_id == tag.id).limit(1)
        ).first() is not None
        has_characters = (
            Character.query.filter_by(tag_id=tag.id).first() is not None
        )
        has_challenge = DailyChallenge.query.filter_by(target_tag_id=tag.id).first()
        if not has_questions and not has_characters and not has_challenge:
            db.session.delete(tag)
            deleted += 1
            print(f"  purge {tag.name!r} ({tag.tag_type})")

    return deleted


def merge_franchise_lookalikes() -> int:
    """Fusionne les tags genre/autre qui portent un nom de franchise.

    Ex. « Star Wars » classé genre alors que l'univers existe déjà : les deux
    entrent en collision (le renommage du slug devenait impossible) et le
    sélecteur de genre proposait une franchise. On rabat tout sur le tag de
    franchise (univers prioritaire) quand les clés normalisées coïncident.
    """
    franchise = Tag.query.filter(Tag.tag_type.in_(FRANCHISE_TYPES)).all()
    franchise_by_key: dict[str, Tag] = {}
    for tag in franchise:
        # Priorité univers > saga, puis nom humanisé > slug.
        current = franchise_by_key.get(key(tag.name))
        if current is None or (
            (tag.tag_type == "univers", not is_slug(tag.name))
            > (current.tag_type == "univers", not is_slug(current.name))
        ):
            franchise_by_key[key(tag.name)] = tag

    deleted = 0
    for tag in Tag.query.filter(Tag.tag_type.in_(("genre", "autre"))).all():
        keeper = franchise_by_key.get(key(tag.name))
        if keeper is None or keeper.id == tag.id:
            continue
        move_tag_references(keeper, tag)
        deleted += 1
        print(
            f"  fusion {tag.name!r} ({tag.tag_type}) -> "
            f"{keeper.name!r} ({keeper.tag_type})"
        )

    return deleted


def main() -> None:
    with app.app_context():
        # Chaque phase est committée séparément : c'est ce qui garantit que les
        # fusions persistent et que le renommage / la purge travaillent sur un
        # état propre en base (évite les conflits UNIQUE pendant l'autoflush).
        merged = merge_groups()
        db.session.commit()

        cross_merged = merge_cross_type()
        db.session.commit()

        lookalikes_merged = merge_franchise_lookalikes()
        db.session.commit()

        renamed = humanize_remaining_slugs()
        db.session.commit()

        purged = purge_orphan_franchise_tags()
        db.session.commit()

        print(
            f"\n{merged + cross_merged + lookalikes_merged} fusion(s) "
            f"dont {cross_merged} inter-types et {lookalikes_merged} genre/autre, "
            f"{renamed} renommage(s), {purged} purgé(s)."
        )


if __name__ == "__main__":
    main()
