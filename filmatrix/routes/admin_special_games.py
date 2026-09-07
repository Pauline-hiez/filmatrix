"""Administration des Jeux Spéciaux : scènes et zones de Cache-Ciné.

Fichier séparé de routes/admin.py (déjà volumineux) plutôt que d'y ajouter
encore une section : même garde d'accès (@admin_required), même pattern de
formulaire que admin_characters_new (routes/admin.py), juste un autre
blueprint enregistré à côté dans filmatrix/__init__.py.
"""

import json
from pathlib import Path
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError
from werkzeug.utils import secure_filename

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import login_required

from filmatrix.extensions import db
from filmatrix.integrations.storage import upload_special_game_image
from filmatrix.models import CacheCineReference, CacheCineScene
from filmatrix.permissions import admin_required
from filmatrix.routes.admin import _admin_nav_counts

bp = Blueprint("admin_special_games", __name__)


@bp.context_processor
def _inject_admin_counts() -> dict:
    """Réutilise les compteurs de la nav admin existante (routes/admin.py)
    et y ajoute celui des scènes Cache-Ciné, pour que la barre latérale
    partagée (templates/admin/base_admin.html) fonctionne aussi sur les
    pages de ce blueprint."""
    context = _admin_nav_counts()
    context["admin_counts"]["cache_cine"] = db.session.query(CacheCineScene.id).count()
    return context


SCENE_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
SCENE_IMAGE_MAX_BYTES = 8 * 1024 * 1024
DIFFICULTIES = ["facile", "moyen", "difficile", "expert"]


def save_scene_image(uploaded_file):
    """Envoie l'image d'une scène Cache-Ciné sur le stockage cloud (Cloudflare R2).

    Même logique que save_character_image (routes/admin.py) : le disque local
    du serveur ne survit pas aux déploiements.
    """
    if not uploaded_file or not uploaded_file.filename:
        return None

    original_name = secure_filename(uploaded_file.filename)
    extension = Path(original_name).suffix.lower().lstrip(".")
    if extension not in SCENE_IMAGE_EXTENSIONS:
        raise ValueError("Format d'image non accepté. Utilise PNG, JPG, WEBP ou GIF.")

    uploaded_file.seek(0, 2)
    if uploaded_file.tell() > SCENE_IMAGE_MAX_BYTES:
        raise ValueError("L'image ne doit pas dépasser 8 Mo.")
    uploaded_file.seek(0)

    filename = f"cache-cine/{uuid4().hex}.{extension}"
    try:
        return upload_special_game_image(uploaded_file, filename, uploaded_file.mimetype)
    except KeyError as error:
        current_app.logger.exception("Upload R2 : variable d'environnement manquante (%s)", error)
        raise ValueError("Stockage d'images non configuré (variable manquante).") from error
    except (BotoCoreError, ClientError) as error:
        current_app.logger.exception("Upload R2 : échec de l'envoi vers le stockage")
        raise ValueError("Échec de l'envoi de l'image vers le stockage. Réessaie.") from error


@bp.route("/admin/jeux-speciaux/cache-cine")
@login_required
@admin_required
def admin_cache_cine_list() -> str:
    """Affiche la liste des scènes Cache-Ciné."""
    scenes = CacheCineScene.query.order_by(CacheCineScene.created_at.desc()).all()
    reference_counts = {
        scene.id: CacheCineReference.query.filter_by(scene_id=scene.id).count() for scene in scenes
    }
    return render_template(
        "admin/cache_cine_list.html",
        scenes=scenes,
        reference_counts=reference_counts,
        active_admin_section="cache_cine",
    )


@bp.route("/admin/jeux-speciaux/cache-cine/nouveau", methods=["GET", "POST"])
@login_required
@admin_required
def admin_cache_cine_new() -> str:
    """Affiche le formulaire de création ou de modification d'une scène Cache-Ciné."""
    scene_id = request.args.get("scene_id", type=int)
    scene = CacheCineScene.query.get(scene_id) if scene_id else None

    if request.method == "POST":
        if scene is None:
            scene = CacheCineScene()
            db.session.add(scene)

        scene.title = request.form["title"]
        scene.difficulty = request.form.get("difficulty", "moyen")
        try:
            scene.time_limit_seconds = int(request.form.get("time_limit_seconds", 120))
        except (TypeError, ValueError):
            scene.time_limit_seconds = 120
        scene.is_active = request.form.get("is_active") == "on"

        uploaded_image = request.files.get("image_file")
        if uploaded_image and uploaded_image.filename:
            try:
                scene.image_url = save_scene_image(uploaded_image)
            except ValueError as error:
                db.session.rollback()
                flash(str(error))
                return render_template(
                    "admin/cache_cine_form.html", scene=scene, difficulties=DIFFICULTIES, existing_references=[]
                )

        # Les zones sont entièrement redéfinies à chaque sauvegarde plutôt que
        # diffées : le volume par scène reste faible (quelques références),
        # et l'éditeur visuel (static/js/admin_cache_cine_zones.js) envoie
        # déjà la liste complète et à jour dans un seul champ cachė JSON.
        try:
            references_data = json.loads(request.form.get("references_json", "[]"))
        except (TypeError, ValueError):
            references_data = []

        if scene.id is not None:
            CacheCineReference.query.filter_by(scene_id=scene.id).delete()
        db.session.flush()

        for order_index, entry in enumerate(references_data):
            title = (entry.get("title") or "").strip()
            if not title:
                continue
            db.session.add(
                CacheCineReference(
                    scene_id=scene.id,
                    title=title,
                    pos_x=float(entry.get("pos_x", 0)),
                    pos_y=float(entry.get("pos_y", 0)),
                    width=float(entry.get("width", 10)),
                    height=float(entry.get("height", 10)),
                    order_index=order_index,
                )
            )

        db.session.commit()

        flash("Scène modifiée avec succès." if scene_id else "Scène créée avec succès.")
        return redirect(url_for("admin_special_games.admin_cache_cine_list"))

    existing_references = []
    if scene is not None:
        existing_references = [
            {
                "title": reference.title,
                "pos_x": reference.pos_x,
                "pos_y": reference.pos_y,
                "width": reference.width,
                "height": reference.height,
            }
            for reference in CacheCineReference.query.filter_by(scene_id=scene.id)
            .order_by(CacheCineReference.order_index)
            .all()
        ]

    return render_template(
        "admin/cache_cine_form.html", scene=scene, difficulties=DIFFICULTIES, existing_references=existing_references
    )


@bp.route("/admin/jeux-speciaux/cache-cine/<int:scene_id>/supprimer", methods=["POST"])
@login_required
@admin_required
def admin_cache_cine_delete(scene_id: int) -> str:
    """Supprime une scène Cache-Ciné et ses références."""
    scene = CacheCineScene.query.get_or_404(scene_id)
    CacheCineReference.query.filter_by(scene_id=scene.id).delete()
    db.session.delete(scene)
    db.session.commit()

    flash("Scène supprimée.")
    return redirect(url_for("admin_special_games.admin_cache_cine_list"))
