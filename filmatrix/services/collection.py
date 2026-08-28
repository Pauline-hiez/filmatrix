"""Logique métier de la collection de personnages : fragments et déblocage."""

from datetime import datetime

from filmatrix.extensions import db
from filmatrix.models import Character, UserCharacter


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