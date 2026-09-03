"""Logique métier de la collection de personnages : fragments et déblocage."""

from datetime import datetime

import random

from filmatrix.extensions import db
from filmatrix.models import Album, Character, UserCharacter, Question
from filmatrix.models import Tag
from filmatrix.catalog_rarities import humanize_tag_name
from filmatrix.services.puzzle import get_puzzle_grid


# Poids de spécificité des types de tags : un album lié à un univers est
# plus précis qu'un album de genre. C'est ce qui départage plusieurs albums.
TAG_TYPE_SPECIFICITY = {
    "univers": 4,
    "genre": 3,
    "realisateur": 2,
    "acteur": 2,
    "studio": 2,
    "pays": 2,
    "epoque": 2,
    "annee": 1,
    "autre": 1,
}


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


def _matched_albums(question: Question) -> list[Album]:
    """Albums liés aux tags de la question, triés du plus spécifique au moins.

    La spécificité est pondérée par le type de tag (univers > genre > ...).
    Un album qui correspond à un univers précis passe ainsi avant un album de
    genre, comme demandé pour le gain de fragments.
    """
    question_tag_ids = {tag.id for tag in question.tags}
    if not question_tag_ids:
        return []

    albums = Album.query.filter(
        Album.tags.any(Tag.id.in_(question_tag_ids))
    ).all()

    scored = []
    for album in albums:
        score = sum(
            TAG_TYPE_SPECIFICITY.get(tag.tag_type, 1)
            for tag in album.tags
            if tag.id in question_tag_ids
        )
        if score:
            scored.append((score, album))

    scored.sort(key=lambda item: (-item[0], item[1].sort_order, item[1].id))
    return [album for _, album in scored]


def award_fragment_for_question(
    user, question: Question, character_name: str | None = None
) -> tuple[Character, bool] | None:
    """Donne un fragment cohérent avec la question, depuis un album.

    Les albums liés aux tags de la question sont parcourus du plus spécifique
    au moins spécifique :

    - Si ``character_name`` est fourni (citation « Qui a dit ça »), on cible
      directement ce personnage dans le premier album qui le contient, à
      condition qu'il ne soit pas déjà débloqué.
    - Sinon, on prend le premier album (le plus spécifique) qui a un personnage
      encore verrouillé et on y tire au hasard.

    Renvoie (personnage, vient_d_etre_debloque), ou None si aucun album ne
    correspond à la question ou si tous leurs personnages sont débloqués.
    """
    matched_albums = _matched_albums(question)
    if not matched_albums:
        return None

    # Cible explicite : la citation vise un personnage en particulier.
    if character_name:
        for album in matched_albums:
            for character in album.characters:
                if (
                    character.name.lower() == character_name.lower()
                    and not get_or_create_progress(user, character).unlocked_at
                ):
                    just_unlocked = add_fragments(user, character, 1)
                    return character, just_unlocked

    # Sinon : premier album (le plus spécifique) avec un personnage verrouillé.
    for album in matched_albums:
        locked_characters = [
            character
            for character in album.characters
            if not get_or_create_progress(user, character).unlocked_at
        ]
        if locked_characters:
            chosen_character = random.choice(locked_characters)
            just_unlocked = add_fragments(user, chosen_character, 1)
            return chosen_character, just_unlocked

    return None

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

def get_album_summaries(user) -> list[dict]:
    """Renvoie un résumé de progression pour chaque album publié."""
    albums = (
        Album.query.filter_by(is_published=True)
        .order_by(Album.sort_order, Album.name)
        .all()
    )

    summaries = []
    for album in albums:
        characters = album.characters
        if not characters:
            continue

        character_ids = [character.id for character in characters]
        unlocked_ids = {
            row.character_id
            for row in UserCharacter.query.filter(
                UserCharacter.user_id == user.id,
                UserCharacter.character_id.in_(character_ids),
                UserCharacter.unlocked_at.isnot(None),
            ).all()
        }

        featured_character = next(
            (character for character in characters if character.id in unlocked_ids),
            characters[0],
        )

        summaries.append(
            {
                "album_id": album.id,
                "name": album.name,
                "description": album.description,
                "image_url": featured_character.image_url if featured_character.id in unlocked_ids else None,
                "unlocked_count": len(unlocked_ids),
                "total_count": len(characters),
                # Réglages de cadrage du personnage vedette, pour un rendu
                # identique dans le profil et la collection.
                "image_x": featured_character.image_x,
                "image_y": featured_character.image_y,
                "image_scale": featured_character.image_scale,
                "frame_x": featured_character.frame_x,
                "frame_y": featured_character.frame_y,
                "frame_scale": featured_character.frame_scale,
                "rarity": featured_character.rarity,
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