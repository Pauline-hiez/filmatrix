"""Logique métier de la collection de personnages : fragments et déblocage."""

from datetime import datetime, timedelta

import random

from filmatrix.extensions import db
from filmatrix.models import Album, Character, UserCharacter, Question
from filmatrix.models import Tag
from filmatrix.catalog_rarities import humanize_tag_name
from filmatrix.services.puzzle import get_puzzle_grid, puzzle_columns


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


# Fenêtre pendant laquelle un album affiche le badge "Nouveau" dans l'aperçu
# profil, après le dernier fragment gagné dessus.
NEW_FRAGMENT_WINDOW = timedelta(hours=48)


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
    progress.last_fragment_at = datetime.utcnow()

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
        # Grille puzzle : autant de cases que de fragments requis (voir
        # puzzle.py). On envoie l'état après le gain, la liste des cases qui
        # viennent d'être révélées, et le nombre de colonnes pour l'affichage.
        "puzzle_grid": grid_now,
        "puzzle_new_cells": new_cells,
        "puzzle_columns": puzzle_columns(len(grid_now)),
    }

def get_album_summaries(user, only_started: bool = False) -> list[dict]:
    """Renvoie un résumé de progression pour chaque album publié.

    only_started=True ne renvoie que les albums où le joueur a déjà gagné au
    moins un fragment (personnage débloqué ou en cours) - utilisé pour
    l'aperçu de la page profil, qui ne doit pas lister des albums jamais
    entamés (voir la page collection complète pour ceux-là)."""
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
        progress_rows = UserCharacter.query.filter(
            UserCharacter.user_id == user.id,
            UserCharacter.character_id.in_(character_ids),
        ).all()
        unlocked_ids = {row.character_id for row in progress_rows if row.unlocked_at is not None}
        started_rows = [row for row in progress_rows if row.fragments > 0 or row.unlocked_at is not None]
        in_progress_rows = [row for row in progress_rows if row.fragments > 0 and row.unlocked_at is None]
        in_progress = bool(in_progress_rows)

        if only_started and not unlocked_ids and not in_progress:
            continue

        featured_character = next(
            (character for character in characters if character.id in unlocked_ids),
            None,
        )
        teaser_character = None
        teaser_fragments = 0
        if featured_character is None and in_progress_rows:
            most_advanced_row = max(in_progress_rows, key=lambda row: row.fragments)
            teaser_character = next(
                (character for character in characters if character.id == most_advanced_row.character_id),
                None,
            )
            teaser_fragments = most_advanced_row.fragments
        display_character = featured_character or teaser_character or characters[0]

        # Personnage en cours (pas encore débloqué) : même rendu puzzle que la
        # page collection/album.html, plutôt qu'un flou artificiel qui pouvait
        # passer pour un bug d'affichage - seules les cases déjà gagnées
        # laissent deviner un bout de l'image.
        teaser_puzzle_grid = None
        teaser_puzzle_columns = None
        if teaser_character is not None:
            teaser_puzzle_grid = get_puzzle_grid(
                teaser_character.id, teaser_fragments, teaser_character.fragments_required
            )
            teaser_puzzle_columns = puzzle_columns(len(teaser_puzzle_grid))

        last_fragment_at = max(
            (row.last_fragment_at for row in started_rows if row.last_fragment_at),
            default=None,
        )
        is_new = (
            last_fragment_at is not None
            and datetime.utcnow() - last_fragment_at < NEW_FRAGMENT_WINDOW
        )

        # Fraction de fragments gagnés sur le total requis par l'album, plus
        # fine que unlocked_count/total_count pour trier les albums entamés :
        # deux personnages à 1/10 et 9/10 fragments sont tous deux "0 débloqué".
        fragments_by_character = {row.character_id: row.fragments for row in progress_rows}
        total_fragments = sum(
            character.fragments_required if character.id in unlocked_ids
            else fragments_by_character.get(character.id, 0)
            for character in characters
        )
        total_required = sum(character.fragments_required for character in characters)
        progress_fraction = total_fragments / total_required if total_required else 0

        summaries.append(
            {
                "album_id": album.id,
                "name": album.name,
                "description": album.description,
                "cover_image_url": album.image_url,
                "cover_image_x": album.image_x,
                "cover_image_y": album.image_y,
                "cover_image_scale": album.image_scale,
                "image_url": display_character.image_url if featured_character is not None else None,
                "teaser_image_url": display_character.image_url if teaser_character is not None else None,
                "teaser_character_id": teaser_character.id if teaser_character is not None else None,
                "teaser_puzzle_grid": teaser_puzzle_grid,
                "teaser_puzzle_columns": teaser_puzzle_columns,
                "unlocked_count": len(unlocked_ids),
                "total_count": len(characters),
                "in_progress": in_progress,
                "is_complete": len(unlocked_ids) == len(characters),
                "is_new": is_new,
                "progress_fraction": progress_fraction,
                # Réglages de cadrage du personnage vedette, pour un rendu
                # identique dans le profil et la collection.
                "image_x": display_character.image_x,
                "image_y": display_character.image_y,
                "image_scale": display_character.image_scale,
                "frame_x": display_character.frame_x,
                "frame_y": display_character.frame_y,
                "frame_scale": display_character.frame_scale,
                "rarity": display_character.rarity,
            }
        )

    if only_started:
        summaries.sort(key=lambda summary: summary["progress_fraction"], reverse=True)

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