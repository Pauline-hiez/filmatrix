"""Galerie de collection : personnages bloqués et en cours de déblocage"""

from flask import Blueprint, render_template
from flask_login import current_user, login_required

from filmatrix.models import Album, UserCharacter
from filmatrix.services.puzzle import get_puzzle_grid
from filmatrix.services.collection import get_album_summaries
from filmatrix.catalog_rarities import RARITIES

bp = Blueprint("collection", __name__)

@bp.route("/collection")
@login_required
def collection_overview() -> str:
    """Affiche la vue d'ensemble de la collection, groupée par album"""
    albums = get_album_summaries(current_user)
    return render_template("collection/overview.html", albums=albums)

@bp.route("/collection/<int:album_id>")
@login_required
def collection_album(album_id: int) -> str:
    """Affiche tous les personnages d'un album, avec leur progression puzzle"""
    album = Album.query.get_or_404(album_id)

    characters_data = []
    for character in album.characters:
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
                "image_x": character.image_x,
                "image_y": character.image_y,
                "image_scale": character.image_scale,
                "frame_x": character.frame_x,
                "frame_y": character.frame_y,
                "frame_scale": character.frame_scale,
            }
        )

    return render_template(
        "collection/album.html",
        album=album,
        characters=characters_data,
        rarities=RARITIES,
    )