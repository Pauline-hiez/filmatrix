"""Galerie de collection : personnages bloqués et en cours de déblocage"""

from flask import Blueprint, render_template
from flask_login import current_user, login_required

from filmatrix.models import Character, Tag, UserCharacter
from filmatrix.services.puzzle import get_puzzle_grid

bp = Blueprint("collection", __name__)

@bp.route("/collection")
@login_required
def collection_overview() -> str:
    """Affiche la vue d'ensemble de la collection, groupée par saga"""
    saga_tags = Tag.query.filter_by(tag_type="saga").order_by(Tag.name).all()

    sagas_summary = []
    for tag in saga_tags:
        characters = Character.query.filter_by(tag_id=tag.id).all()
        if not characters:
            continue

        unlocked_count = UserCharacter.query.filter(
                UserCharacter.user_id == current_user.id,
                UserCharacter.character_id.in_([Character.id for character in characters]),
                UserCharacter.unlocked_at.isnot(None),
            ).count()

        sagas_summary.append(
                {
                    "tag_id": tag.id,
                    "name": tag.name,
                    "unlocked_count": unlocked_count,
                    "total_count": len(characters),
                }
            )

    return render_template("collection/overview.html", sagas=sagas_summary)

@bp.route("/collection/<int:tag_id>")
@login_required
def collection_saga(tag_id: int) -> str:
    """Affiche tous les personnages d'une saga, avec leur progression puzzle"""
    tag = Tag.query.get_or_404(tag_id)
    characters = Character.query.filter_by(tag_id=tag_id).order_by(Character.name).all()

    characters_data = []
    for character in characters:
        progress = UserCharacter.query.filter_by(
            user_id=current_user.id, character_id=character.id
        ).first()

        fragments = progress.fragments if progress else 0
        is_unlocked = progress is not None and progress.unlocked_at is not None

        characters_data.append(
            {
                "id": character.id,
                "name": character.name,
                "rarity": character.rarity,
                "image_url": character.image_url,
                "fragments": fragments,
                "fragments_required": character.fragments_required,
                "is_unlocked": is_unlocked,
                "puzzle_grid": get_puzzle_grid(character.id, fragments, character.fragments_required),
            }
        )

    return render_template("collection/saga.html", tag=tag, characters=characters_data)