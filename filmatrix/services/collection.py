"""Logique métier de la collection de personnages : fragments et déblocage."""

from datetime import datetime

import random

from filmatrix.extensions import db
from filmatrix.models import Character, UserCharacter, Question
from filmatrix.models import Tag
from filmatrix.catalog_rarities import humanize_tag_name
from filmatrix.services.puzzle import get_puzzle_grid


def get_or_create_progress(user, character: Character) -> UserCharacter:
    """Récupère la progression d'un joueur sur un personnage, ou la crée si absente."""
    progress = UserCharacter.query.filter_by(
        user_id=user.id, character_id=character.id
    ).first()

    if progress is None:
        progress = UserCharacter(user_id=user.id, character_id=character.id, fragments=0)
        db.session.add(progress)

    return progress


def add_fragments(user, character: Character, amount: int) -> bool:
    """Ajoute des fragments à un personnage pour un joueur. Renvoie True si le personnage vient d'être débloqué."""
    progress = get_or_create_progress(user, character)

    was_unlocked = progress.unlocked_at is not None
    progress.fragments = min(progress.fragments + amount, character.fragments_required)

    if not was_unlocked and progress.fragments >= character.fragments_required:
        progress.unlocked_at = datetime.utcnow()
        return True

    return False


def get_characters_for_tag(user, tag_id: int) -> list[dict]:
    """Renvoie tous les personnages d'une franchise, avec la progression du joueur."""
    characters = Character.query.filter_by(tag_id=tag_id).all()

    result = []
    for character in characters:
        progress = UserCharacter.query.filter_by(
            user_id=user.id, character_id=character.id
        ).first()

        fragments = progress.fragments if progress else 0
        is_unlocked = progress is not None and progress.unlocked_at is not None

        result.append(
            {
                "id": character.id,
                "name": character.name,
                "rarity": character.rarity,
                "image_url": character.image_url,
                "fragments": fragments,
                "fragments_required": character.fragments_required,
                "is_unlocked": is_unlocked,
                "image_x": character.image_x,
                "image_y": character.image_y,
                "image_scale": character.image_scale,
                "frame_x": character.frame_x,
                "frame_y": character.frame_y,
                "frame_scale": character.frame_scale,
            }
        )

    return result

def _universe_tags(question: Question) -> list[Tag]:
    """Tags de franchise de la question (saga ou univers).

    Certaines franchises sont typées « saga », d'autres « univers ». Les deux
    désignent un monde à personnages, donc les deux doivent fournir des cibles
    de collection.
    """
    return [tag for tag in question.tags if tag.tag_type in ("saga", "univers")]


def award_fragment_for_question(
    user, question: Question, character_name: str | None = None
) -> tuple[Character, bool] | None:
    """Donne un fragment cohérent avec la question répondue.

    Le fragment provient toujours de la franchise (saga ou univers) à laquelle
    la question appartient, pour que le joueur gagne des morceaux de l'œuvre
    qu'il vient de jouer.

    - Si ``character_name`` est fourni (citation « Qui a dit ça »), on cible
      directement ce personnage, à condition qu'il fasse partie de la franchise
      et qu'il ne soit pas déjà débloqué.
    - Sinon, on tire un personnage verrouillé au hasard dans la franchise.

    Renvoie (personnage, vient_d_etre_debloque), ou None si la question n'est
    liée à aucune franchise ou si tous ses personnages sont déjà débloqués.
    """
    universe_tags = _universe_tags(question)
    if not universe_tags:
        return None

    universe_tag_ids = [tag.id for tag in universe_tags]
    candidate_characters = Character.query.filter(Character.tag_id.in_(universe_tag_ids)).all()
    if not candidate_characters:
        return None

    # Cible explicite : la citation vise un personnage en particulier.
    if character_name:
        named = [
            character
            for character in candidate_characters
            if character.name.lower() == character_name.lower()
            and not get_or_create_progress(user, character).unlocked_at
        ]
        if named:
            just_unlocked = add_fragments(user, named[0], 1)
            return named[0], just_unlocked

    locked_characters = [
        character
        for character in candidate_characters
        if not get_or_create_progress(user, character).unlocked_at
    ]

    if not locked_characters:
        return None

    chosen_character = random.choice(locked_characters)
    just_unlocked = add_fragments(user, chosen_character, 1)

    return chosen_character, just_unlocked

def fragment_result_payload(user, fragment_result: tuple[Character, bool] | None) -> dict | None:
    """Construit la payload envoyée au front pour la notification de gain.

    Sert à afficher le portrait du personnage (avec son cadre), sa franchise,
    sa rareté et sa progression, plutôt qu'un simple texte.
    """
    if fragment_result is None:
        return None

    character, just_unlocked = fragment_result
    progress = get_or_create_progress(user, character)
    tag = Tag.query.get(character.tag_id)

    after_fragments = min(progress.fragments, character.fragments_required)
    grid_now = get_puzzle_grid(character.id, after_fragments, character.fragments_required)
    grid_before = get_puzzle_grid(
        character.id, max(after_fragments - 1, 0), character.fragments_required
    )
    new_cells = [
        index
        for index in range(len(grid_now))
        if grid_now[index] and not grid_before[index]
    ]

    return {
        "character_id": character.id,
        "character_name": character.name,
        "just_unlocked": just_unlocked,
        "image_url": character.image_url,
        "rarity": character.rarity,
        "fragments": after_fragments,
        "fragments_required": character.fragments_required,
        "progress_percent": round(after_fragments * 100 / character.fragments_required),
        "saga_name": humanize_tag_name(tag.name) if tag else None,
        "image_x": character.image_x,
        "image_y": character.image_y,
        "image_scale": character.image_scale,
        "frame_x": character.frame_x,
        "frame_y": character.frame_y,
        "frame_scale": character.frame_scale,
        # Grille puzzle 3x3 : on envoie l'état après le gain et la liste des cases
        # qui viennent d'être révélées, pour animer la case dans le toast.
        "puzzle_grid": grid_now,
        "puzzle_new_cells": new_cells,
    }


def get_saga_summaries(user) -> list[dict]:
    """Renvoie un résumé de progression pour chaque franchise ayant des personnages

    Les franchises sont typées « saga » ou « univers » : on couvre les deux pour
    ne pas laisser de côté les univers (qui sont les plus nombreux).
    """
    saga_tags = (
        Tag.query.filter(Tag.tag_type.in_(["saga", "univers"]))
        .order_by(Tag.name)
        .all()
    )

    summaries = []
    for tag in saga_tags:
        characters = Character.query.filter_by(tag_id=tag.id).all()
        if not characters:
            continue

        character_ids = [character.id for character in characters]
        unlocked_character_ids = {
            row.character_id
            for row in UserCharacter.query.filter(
                UserCharacter.user_id == user.id,
                UserCharacter.character_id.in_(character_ids),
                UserCharacter.unlocked_at.isnot(None),
            ).all()
        }

        # Une vignette qui montre ce que le joueur a déjà débloqué donne plus
        # envie de continuer qu'une image tirée au hasard dans la franchise.
        featured_character = next(
            (character for character in characters if character.id in unlocked_character_ids),
            characters[0],
        )

        summaries.append(
                {
                    "tag_id": tag.id,
                    "name": humanize_tag_name(tag.name),
                    "unlocked_count": len(unlocked_character_ids),
                    "total_count": len(characters),
                    "image_url": featured_character.image_url if featured_character.id in unlocked_character_ids else None,
                    # On propage les réglages de cadrage du personnage vedette pour
                    # que le profil et la collection affichent exactement le même
                    # rendu que l'aperçu admin.
                    "image_x": featured_character.image_x,
                    "image_y": featured_character.image_y,
                    "image_scale": featured_character.image_scale,
                    "frame_x": featured_character.frame_x,
                    "frame_y": featured_character.frame_y,
                    "frame_scale": featured_character.frame_scale,
                }
            )

    return summaries

def award_guaranteed_fragment(user, minimum_rarity: list[str] | None = None) -> tuple[Character, bool] | None:
    """Donne un fragment garanti à un personnage verrouillé au hasard, toutes sagas confondues.

    Si minimum_rarity est fourni, ne tire que parmi les personnages de ces raretés.
    """
    query = Character.query
    if minimum_rarity:
        query = query.filter(Character.rarity.in_(minimum_rarity))

    candidate_characters = query.all()

    locked_characters = [
        character
        for character in candidate_characters
        if not get_or_create_progress(user, character).unlocked_at
    ]

    if not locked_characters:
        return None

    chosen_character = random.choice(locked_characters)
    just_unlocked = add_fragments(user, chosen_character, 1)

    return chosen_character, just_unlocked