"""Logique métier de la collection de personnages : fragments et déblocage."""

from datetime import datetime

import random

from filmatrix.extensions import db
from filmatrix.models import Character, UserCharacter, Question


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
            }
        )

    return result

def award_fragment_for_question(user, question: Question) -> tuple[Character, bool] | None:
    """Donne un fragment à un personnage verrouillé au hasard, parmi les sagas de la question.

    Renvoie (personnage, vient_d_etre_debloque) si un fragment a été donné,
    ou None si la question n'est liée à aucune saga ayant des personnages.
    """
    saga_tags = [tag for tag in question.tags if tag.tag_type == "saga"]
    if not saga_tags:
        return None

    saga_tag_ids = [tag.id for tag in saga_tags]
    candidate_characters = Character.query.filter(Character.tag_id.in_(saga_tag_ids)).all()
    if not candidate_characters:
        return None

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