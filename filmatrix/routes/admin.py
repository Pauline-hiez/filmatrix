"""Administration : questions, utilisateurs, signalements et thèmes."""

import json
from pathlib import Path
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import case, func
from werkzeug.utils import secure_filename

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from filmatrix.extensions import db
from filmatrix.permissions import admin_required
from filmatrix.catalog import REPORT_REASON
from filmatrix.catalog_rarities import fragments_for_rarity
from filmatrix.game_modes import GAME_MODES
from filmatrix.models import Album, Attempt, Question, Report, Tag, User, Character, question_tags
from filmatrix.services.tags import merge_tag_into
from filmatrix.integrations.itunes import search_soundtrack_previews, search_soundtrack_preview
from filmatrix.integrations.storage import upload_character_image
from filmatrix.integrations.tmdb import (
    build_image_url,
    genre_ids_to_tags,
    get_genre_maps,
    get_movie_by_id,
    get_movie_cast,
    search_movies_list,
    search_tv_shows_list,
    get_tv_show_by_id,
    get_tv_show_cast,
)


bp = Blueprint("admin", __name__)


@bp.context_processor
def _admin_nav_counts() -> dict:
    """Compteurs affichés à côté de chaque entrée du menu admin."""
    return {
        "admin_counts": {
            "questions": db.session.query(func.count(Question.id)).scalar(),
            "users": db.session.query(func.count(User.id)).scalar(),
            "reports": db.session.query(func.count(Report.id))
            .filter(Report.is_resolved.is_(False))
            .scalar(),
            "tags": db.session.query(func.count(Tag.id)).scalar(),
            "characters": db.session.query(func.count(Character.id)).scalar(),
            "albums": db.session.query(func.count(Album.id)).scalar(),
        }
    }


CHARACTER_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
CHARACTER_IMAGE_MAX_BYTES = 5 * 1024 * 1024


def save_character_image(uploaded_file):
    """Envoie une image de personnage sur le stockage cloud (Cloudflare R2).

    Le disque local du serveur ne survit pas aux déploiements (conteneur
    reconstruit à chaque push) : une image qui y serait écrite disparaîtrait
    au push suivant, d'où le passage par un stockage externe.
    """
    if not uploaded_file or not uploaded_file.filename:
        return None

    original_name = secure_filename(uploaded_file.filename)
    extension = Path(original_name).suffix.lower().lstrip(".")
    if extension not in CHARACTER_IMAGE_EXTENSIONS:
        raise ValueError("Format d'image non accepté. Utilise PNG, JPG, WEBP ou GIF.")

    uploaded_file.seek(0, 2)
    if uploaded_file.tell() > CHARACTER_IMAGE_MAX_BYTES:
        raise ValueError("L'image ne doit pas dépasser 5 Mo.")
    uploaded_file.seek(0)

    filename = f"{uuid4().hex}.{extension}"
    try:
        return upload_character_image(uploaded_file, filename, uploaded_file.mimetype)
    except KeyError as error:
        current_app.logger.exception("Upload R2 : variable d'environnement manquante (%s)", error)
        raise ValueError("Stockage d'images non configuré (variable manquante).") from error
    except (BotoCoreError, ClientError) as error:
        current_app.logger.exception("Upload R2 : échec de l'envoi vers le stockage")
        raise ValueError("Échec de l'envoi de l'image vers le stockage. Réessaie.") from error


@bp.route("/admin/questions")
@login_required 
@admin_required
def admin_questions_list() -> str:
    """Affiche la liste de toutes les questions, groupées par mode pour l'admin"""
    all_questions = Question.query.order_by(Question.mode, Question.id).all()

    questions_by_mode = {}
    for question in all_questions:
        questions_by_mode.setdefault(question.mode, []).append(question)

    # Vignette de la table : la première image utile de la payload (affiche,
    # image de question, photo d'acteur ou option illustrée).
    thumbnails = {}
    for question in all_questions:
        payload = question.payload or {}
        thumb = payload.get("question_image_url") or payload.get("poster_url")
        if not thumb:
            actors = payload.get("actor_photos") or []
            thumb = actors[0] if actors else None
        if not thumb:
            options = payload.get("option_images") or []
            thumb = options[0] if options else None
        thumbnails[question.id] = thumb

    # Statistiques réelles : nombre de réponses et taux de réussite.
    stats_rows = (
        db.session.query(
            Attempt.question_id,
            func.count(Attempt.id).label("answers"),
            func.sum(case((Attempt.is_correct.is_(True), 1), else_=0)).label("correct"),
        )
        .group_by(Attempt.question_id)
        .all()
    )
    question_stats = {
        row.question_id: (
            row.answers,
            round(100 * row.correct / row.answers) if row.answers else None,
        )
        for row in stats_rows
    }

    # Icône et couleur de chaque mode, partagées avec la page des modes.
    mode_meta = {
        mode["slug"]: {"icon": mode["icon"], "accent": mode["accent"]}
        for mode in GAME_MODES
    }

    return render_template(
            "admin/questions_list.html",
            questions_by_mode=questions_by_mode,
            total_count=len(all_questions),
            thumbnails=thumbnails,
            question_stats=question_stats,
            mode_meta=mode_meta,
            active_admin_section="questions"
        )

@bp.route("/admin/questions/nouvelle", methods=["GET", "POST"])
@login_required
@admin_required
def admin_questions_new() -> str:
    """Affiche le formulaire de création (GET) ou le crée (POST)"""
    if request.method == "POST":
        try:
            payload = json.loads(request.form["payload"])
            correct_answer = json.loads(request.form["correct_answer"])
        except json.JSONDecodeError:
            flash("La payload ou la réponse correcte n'est pas un JSON valide")
            return render_template("admin/question_form.html", question=None)

        prompt = request.form["prompt"]
        if request.form["mode"] == "emoji":
            visuals = json.loads(request.form.get("visuals", "[]"))
            payload.setdefault("visuals", visuals)

        new_question = Question(
            mode=request.form["mode"],
            prompt=prompt,
            payload=payload,
            correct_answer=correct_answer,
            requires_account=request.form.get("requires_account") == "on",
            content_type=request.form.get("content_type", "film"),
        )

        selected_tag_ids = request.form.getlist("tags")
        new_question.tags = Tag.query.filter(Tag.id.in_(selected_tag_ids)).all()

        db.session.add(new_question)
        db.session.commit()

        flash("Question créée avec succès.")
        return redirect(url_for("admin.admin_questions_list"))

    all_tags = Tag.query.order_by(Tag.tag_type, Tag.name).all()
    return render_template("admin/question_form.html", question=None, all_tags=all_tags)

@bp.route("/admin/questions/<int:question_id>/modifier", methods=["GET", "POST"])
@login_required
@admin_required
def admin_questions_edit(question_id: int) -> str:
    """Affiche le formulaire de modification (GET) ou applique les changements (POST)"""
    question = Question.query.get_or_404(question_id)

    if request.method == "POST":
        try:
            payload = json.loads(request.form["payload"])
            correct_answer = json.loads(request.form["correct_answer"])
        except json.JSONDecodeError:
            flash("Le payload ou la réponse correcte n'est pas un JSON valide.")
            return render_template("admin/question_form.html", question=question)

        question.mode = request.form["mode"]
        question.prompt = request.form["prompt"]
        if request.form["mode"] == "emoji":
            payload.setdefault("visuals", json.loads(request.form.get("visuals", "[]")))
        question.payload = payload
        question.correct_answer = correct_answer
        question.requires_account = request.form.get("requires_account") == "on"
        question.content_type = request.form.get("content_type", question.content_type)

        selected_tag_ids = request.form.getlist("tags")
        question.tags = Tag.query.filter(Tag.id.in_(selected_tag_ids)).all()

        db.session.commit()

        flash("Question modifiée avec succès.")
        return redirect(url_for("admin.admin_questions_list"))

    all_tags = Tag.query.order_by(Tag.tag_type, Tag.name).all()
    template = "admin/question_form_modal.html" if request.headers.get("X-Requested-With") == "XMLHttpRequest" else "admin/question_form.html"
    return render_template(template, question=question, all_tags=all_tags)

@bp.route("/admin/questions/<int:question_id>/supprimer", methods=["POST"])
@login_required
@admin_required
def admin_questions_delete(question_id: int) -> str:
    """Supprime une question"""
    question = Question.query.get_or_404(question_id)
    db.session.delete(question)
    db.session.commit()

    flash("Question supprimée.")
    return redirect(url_for("admin.admin_questions_list"))

@bp.route("/admin/api/recherche-film")
@login_required
@admin_required
def admin_api_search_movies() ->  dict:
    """Recherche films ET séries pour l'autocomplétion, avec miniatures.

    Les deux listes sont fusionnées et entrelacées pour que chaque type
    apparaisse tôt dans les résultats (une série en 11e position serait
    sinon invisible avec une limite de 5).
    """
    query = request.args.get("query", "")
    movies = search_movies_list(query, limit=5)
    shows = search_tv_shows_list(query, limit=5)

    interleaved = []
    for pair in zip(movies, shows):
        interleaved.extend(pair)
    interleaved.extend(movies[len(shows):] if len(movies) > len(shows) else shows[len(movies):])

    return {"results": interleaved[:8]}

@bp.route("/admin/api/genres-tmdb")
@login_required
@admin_required
def admin_api_genres_tmdb() -> dict:
    """Traduit un film/série TMDB en noms de tags genre, pour pré-cocher le
    formulaire de question à la sélection d'une œuvre."""
    movie_id = request.args.get("movie_id", type=int)
    content_type = request.args.get("content_type", "film")

    result = None
    if movie_id:
        result = get_tv_show_by_id(movie_id) if content_type == "serie" else get_movie_by_id(movie_id)

    if result is None:
        return {"genres": []}

    movie_genres, tv_genres = get_genre_maps()
    genre_map = tv_genres if content_type == "serie" else movie_genres
    return {"genres": genre_ids_to_tags(result["genre_ids"], genre_map)}

@bp.route("/admin/api/recherche-affiche")
@login_required
@admin_required
def admin_api_poster() -> dict:
    """Récupère l'image de scène (backdrop) TMDB pour un film ou une série"""
    movie_id = request.args.get("movie_id", type=int)
    content_type = request.args.get("content_type", "film")

    result = None
    if movie_id:
        if content_type == "serie":
            result = get_tv_show_by_id(movie_id)
        else:
            result = get_movie_by_id(movie_id)

    if result is None:
        return {"success": False, "error": "Film introuvable."}

    poster_url = build_image_url(result.get("backdrop_path"))
    return {"success": True, "poster_url": poster_url, "official_title": result["title"]}

@bp.route("/admin/api/recherche-casting")
@login_required
@admin_required
def admin_api_cast() -> dict:
    """Récupère les photos des principaux acteurs pour un film ou une série"""
    movie_id = request.args.get("movie_id", type=int)
    content_type = request.args.get("content_type", "film")

    result = None
    if movie_id:
        if content_type == "serie":
            result = get_tv_show_by_id(movie_id)
        else:
            result = get_movie_by_id(movie_id)

    if result is None:
        return {"success": False, "error": "Film introuvable."}

    if content_type == "serie":
        cast = get_tv_show_cast(result["id"], limit=3)
    else:
        cast = get_movie_cast(result["id"], limit=3)

    actor_photos = [
        build_image_url(actor["profile_path"]) for actor in cast if actor["profile_path"]
    ]
    return {"success": True, "actor_photos": actor_photos, "official_title": result["title"]}

@bp.route("/admin/api/recherche-personnages")
@login_required
@admin_required
def admin_api_characters() -> dict:
    """Récupère le casting complet (acteur + personnage + photo) d'un film ou série"""
    movie_id = request.args.get("movie_id", type=int)
    content_type = request.args.get("content_type", "film")

    if content_type == "serie":
        result = get_tv_show_by_id(movie_id) if movie_id else None
    else:
        result = get_movie_by_id(movie_id) if movie_id else None

    if result is None:
        return {"success": False, "error": "Introuvable."}

    if content_type == "serie":
        cast = get_tv_show_cast(result["id"], limit=10)
    else:
        cast = get_movie_cast(result["id"], limit=10)

    characters = [
        {
            "character_name": actor["character"],
            "actor_name": actor["name"],
            "photo_url": build_image_url(actor["profile_path"]),
        }
        for actor in cast
        if actor.get("character") and actor.get("profile_path")
    ]

    return {"success": True, "characters": characters, "official_title": result["title"]}

@bp.route("/admin/api/recherche-audio")
@login_required
@admin_required
def admin_api_audio() -> dict:
    """Recherche plusieurs préécoutes audio pour un film sélectionné."""
    title = request.args.get("title", "")
    search_term = request.args.get("search_term") or f"{title} soundtrack"
    previews = search_soundtrack_previews(search_term, limit=6)

    if not previews:
        return {"success": False, "error": "Aucun extrait audio trouvé."}

    return {"success": True, "audio_options": previews, "audio_url": previews[0]["audio_url"]}

@bp.route("/admin/utilisateurs")
@login_required
@admin_required
def admin_users_list() -> str:
    """Affiche la liste des utilisateurs pour l'admin"""
    all_users = User.query.order_by(User.username).all()

    users_data = []
    for user in all_users:
        correct_count = Attempt.query.filter_by(user_id=user.id, is_correct=True).count()
        users_data.append(
            {
                "id": user.id,
                "username": user.username,
                "avatar": user.avatar,
                "email": user.email,
                "is_admin": user.is_admin,
                "total_xp": user.total_xp,
                "coins": user.coins,
                "correct_count": correct_count,
            }
        )

    return render_template(
        "admin/users_list.html",
        users=users_data,
        active_admin_section="users",
    )

@bp.route("/admin/utilisateurs/<int:user_id>/basculer-admin", methods=["POST"])
@login_required
@admin_required
def admin_toggle_admin(user_id: int) -> str:
    """Bascule le statut admin d'un utilisateur"""
    if user_id == current_user.id:
        flash("Tu ne peux pas modifier ton propre statut administrateur.")
        return redirect(url_for("admin.admin_users_list"))

    user = User.query.get_or_404(user_id)
    user.is_admin = not user.is_admin
    db.session.commit()

    flash(f"Statut administrateur de {user.username} mis à jour.")
    return redirect(url_for("admin.admin_users_list"))

@bp.route("/admin/utilisateurs/<int:user_id>/supprimer", methods=["POST"])
@login_required
@admin_required
def admin_delete_user(user_id: int) -> str:
    """Supprime un utilisateur et tout son historique"""
    if user_id == current_user.id:
        flash("Tu ne peux pas supprimer ton propre compte depuis cette page.")
        return redirect(url_for("admin.admin_users_list"))

    user = User.query.get_or_404(user_id)
    Attempt.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()

    flash(f"Le compte de {user.username} a été supprimé.")
    return redirect(url_for("admin.admin_users_list"))

@bp.route("/admin/signalements")
@login_required
@admin_required
def admin_reports_list() -> str:
    """Affiche la liste des signalements pour l'admin"""
    all_reports = Report.query.order_by(Report.is_resolved, Report.created_at.desc()).all()

    reports_data = []
    for report in all_reports:
        reports_data.append(
                {
                    "id": report.id,
                    "reporter_username": report.user.username,
                    "question_id": report.question_id,
                    "question_prompt": report.question.prompt,
                    "question_mode": report.question.mode,
                    "reason_label": REPORT_REASON.get(report.reason, report.reason),
                    "is_resolved": report.is_resolved,
                    "created_at": report.created_at,
                    }
            )

        return render_template(
                "admin/reports_list.html",
                reports=reports_data,
                active_admin_section="reports",
            )

@bp.route("/admin/tags")
@login_required
@admin_required
def admin_tags_list() -> str:
    """Affiche la liste des tags disponibles"""
    all_tags = Tag.query.order_by(Tag.tag_type, Tag.name).all()
    question_counts = dict(
        db.session.query(question_tags.c.tag_id, func.count(question_tags.c.question_id))
        .group_by(question_tags.c.tag_id)
        .all()
    )
    return render_template(
        "admin/tags_list.html",
        tags=all_tags,
        question_counts=question_counts,
        active_admin_section="tags",
    )

@bp.route("/admin/tags/nouveau", methods=["POST"])
@login_required
@admin_required
def admin_tags_new() -> str:
    """Crée un nouveau tag"""
    name = request.form.get("name", "").strip()
    tag_type = request.form.get("tag_type", "genre")
    allowed_types = {"genre", "univers", "pays", "epoque", "annee", "realisateur", "acteur", "studio", "autre"}
    if tag_type not in allowed_types:
        tag_type = "autre"

    if name:
        existing = Tag.query.filter(func.lower(Tag.name) == name.lower()).first()
        if existing is None:
            new_tag = Tag(name=name, tag_type=tag_type)
            db.session.add(new_tag)
            db.session.commit()
            flash(f"Tag '{name}' crée.")
        else:
            flash("Ce tag existe déjà.")
    return redirect(url_for("admin.admin_tags_list"))

@bp.route("/admin/tags/<int:tag_id>/renommer", methods=["POST"])
@login_required
@admin_required
def admin_tags_rename(tag_id: int) -> str:
    """Renomme un tag existant"""
    tag = Tag.query.get_or_404(tag_id)
    name = request.form.get("name", "").strip()

    if not name:
        flash("Le nom ne peut pas être vide.")
        return redirect(url_for("admin.admin_tags_list"))

    existing = Tag.query.filter(func.lower(Tag.name) == name.lower(), Tag.id != tag.id).first()
    if existing is not None:
        flash("Ce tag existe déjà.")
        return redirect(url_for("admin.admin_tags_list"))

    tag.name = name
    db.session.commit()
    flash(f"Tag renommé en '{name}'.")
    return redirect(url_for("admin.admin_tags_list"))

@bp.route("/admin/tags/fusionner", methods=["POST"])
@login_required
@admin_required
def admin_tags_merge() -> str:
    """Fusionne un tag univers dans un autre : questions, personnages et défis
    quotidiens du doublon sont réassignés au tag conservé avant sa suppression."""
    keeper_id = request.form.get("keeper_id", type=int)
    dup_id = request.form.get("dup_id", type=int)

    if not keeper_id or not dup_id or keeper_id == dup_id:
        flash("Sélection invalide pour la fusion.")
        return redirect(url_for("admin.admin_tags_list"))

    keeper = Tag.query.get_or_404(keeper_id)
    dup = Tag.query.get_or_404(dup_id)
    if keeper.tag_type != "univers" or dup.tag_type != "univers":
        flash("La fusion n'est disponible que pour les tags univers.")
        return redirect(url_for("admin.admin_tags_list"))

    merge_tag_into(keeper, dup)
    db.session.commit()
    flash(f"'{dup.name}' fusionné dans '{keeper.name}'.")
    return redirect(url_for("admin.admin_tags_list"))

@bp.route("/admin/tags/<int:tag_id>/supprimer", methods=["POST"])
@login_required
@admin_required
def admin_tags_delete(tag_id: int) -> str:
    """Supprime un tag"""
    tag = Tag.query.get_or_404(tag_id)
    db.session.delete(tag)
    db.session.commit()

    flash("Tag supprimé.")
    return redirect(url_for("admin.admin_tags_list"))

@bp.route("/admin/signalements/<int:report_id>/traiter", methods=["POST"]) 
@login_required
@admin_required
def admin_resolve_report(report_id: int) -> str:
    """Marque un signalement comme traité"""
    report = Report.query.get_or_404(report_id)
    report.is_resolved = True
    db.session.commit()

    flash("Signalement marqué comme traité.")
    return redirect(url_for("admin.admin_reports_list"))

@bp.route("/admin/personnages")
@login_required
@admin_required
def admin_characters_list() -> str:
    """Affiche la liste des personnages, groupés par univers"""
    all_characters = Character.query.order_by(Character.tag_id, Character.name).all()

    characters_by_tag = {}
    for character in all_characters:
        characters_by_tag.setdefault(character.tag.name, []).append(character)

    return render_template(
        "admin/characters_list.html",
        characters_by_tag=characters_by_tag,
        total_count=len(all_characters),
        active_admin_section="characters",
    )


@bp.route("/admin/personnages/nouveau", methods=["GET", "POST"])
@login_required
@admin_required
def admin_characters_new() -> str:
    """Affiche le formulaire de création ou de modification d'un personnage."""
    character_id = request.args.get("character_id", type=int)
    character = Character.query.get(character_id) if character_id else None

    if request.method == "POST":
        if character is None:
            character = Character()
            db.session.add(character)

        character.name = request.form["name"]
        character.tag_id = int(request.form["tag_id"])
        character.rarity = request.form["rarity"]

        # Posés avant la tentative d'upload : si elle échoue, le formulaire
        # réaffiché (character non commité) doit pouvoir se rendre sans
        # planter sur des champs encore vides — les defaults de colonne ne
        # s'appliquent qu'au flush en base, pas avant.
        try:
            fragments_required = int(request.form.get("fragments_required", ""))
        except (TypeError, ValueError):
            fragments_required = 0
        if fragments_required < 1:
            fragments_required = fragments_for_rarity(character.rarity)
        character.fragments_required = fragments_required
        character.image_x = float(request.form.get("image_x", 0))
        character.image_y = float(request.form.get("image_y", 0))
        character.image_scale = float(request.form.get("image_scale", 100))
        character.frame_x = float(request.form.get("frame_x", 0))
        character.frame_y = float(request.form.get("frame_y", 0))
        character.frame_scale = float(request.form.get("frame_scale", 125))

        uploaded_image = request.files.get("image_file")
        if uploaded_image and uploaded_image.filename:
            try:
                character.image_url = save_character_image(uploaded_image)
            except ValueError as error:
                db.session.rollback()
                flash(str(error))
                saga_tags = Tag.query.filter_by(tag_type="univers").order_by(Tag.name).all()
                albums = Album.query.order_by(Album.sort_order, Album.name).all()
                return render_template("admin/character_form.html", character=character, saga_tags=saga_tags, albums=albums)

        # Albums : un personnage peut appartenir à plusieurs collections.
        selected_album_ids = request.form.getlist("album_ids")
        character.albums = Album.query.filter(Album.id.in_(selected_album_ids)).all()
        db.session.commit()

        flash("Personnage modifié avec succès." if character_id else "Personnage créé avec succès.")
        return redirect(url_for("admin.admin_characters_list"))

    saga_tags = Tag.query.filter_by(tag_type="univers").order_by(Tag.name).all()
    albums = Album.query.order_by(Album.sort_order, Album.name).all()
    return render_template("admin/character_form.html", character=character, saga_tags=saga_tags, albums=albums)


@bp.route("/admin/personnages/<int:character_id>/supprimer", methods=["POST"])
@login_required
@admin_required
def admin_characters_delete(character_id: int) -> str:
    """Supprime un personnage"""
    character = Character.query.get_or_404(character_id)
    db.session.delete(character)
    db.session.commit()

    flash("Personnage supprimé.")
    return redirect(url_for("admin.admin_characters_list"))


@bp.route("/admin/albums")
@login_required
@admin_required
def admin_albums_list() -> str:
    """Affiche la liste des albums de collection"""
    albums = Album.query.order_by(Album.sort_order, Album.name).all()
    return render_template(
        "admin/albums_list.html",
        albums=albums,
        active_admin_section="albums",
    )


def build_album_suggestions(limit: int = 8) -> list[dict]:
    """Suggestions de création rapide : une par univers qui a
    des personnages collectionnables mais pas encore d'album. Chaque entrée
    pré-remplit le nom, les tags et les personnages du formulaire."""
    existing_names = {
        name.casefold()
        for (name,) in Album.query.with_entities(Album.name).all()
    }
    suggestions: list[dict] = []
    franchise_tags = Tag.query.filter_by(tag_type="univers").order_by(Tag.name).all()
    for tag in franchise_tags:
        if tag.name.casefold() in existing_names:
            continue
        characters = Character.query.filter_by(tag_id=tag.id).order_by(Character.name).all()
        if not characters:
            continue
        suggestions.append({
            "name": tag.name,
            "tag_ids": [tag.id],
            "character_ids": [character.id for character in characters],
        })
    # Les franchises les plus fournies d'abord : ce sont les collections les
    # plus utiles à créer en premier.
    suggestions.sort(key=lambda item: -len(item["character_ids"]))
    return suggestions[:limit]


@bp.route("/admin/albums/nouveau", methods=["GET", "POST"])
@login_required
@admin_required
def admin_albums_new() -> str:
    """Crée ou modifie un album de collection"""
    album_id = request.args.get("album_id", type=int)
    album = Album.query.get(album_id) if album_id else None

    if request.method == "POST":
        name = request.form["name"].strip()

        # Un nom d'album est unique : on refuse proprement un doublon plutôt que
        # de laisser la contrainte UNIQUE faire planter la page.
        query = Album.query.filter(Album.name == name)
        if album is not None:
            query = query.filter(Album.id != album.id)
        if not name or query.first() is not None:
            flash("Ce nom d'album est déjà utilisé. Choisis-en un autre.")
            all_tags = Tag.query.order_by(Tag.tag_type, Tag.name).all()
            characters = Character.query.order_by(Character.name).all()
            return render_template(
                "admin/album_form.html",
                album=album,
                all_tags=all_tags,
                characters=characters,
                suggestions=[],
            )

        if album is None:
            album = Album()
            db.session.add(album)

        album.name = name
        album.description = request.form.get("description") or None
        album.sort_order = int(request.form.get("sort_order", 0))
        album.is_published = request.form.get("is_published") == "on"

        selected_tag_ids = request.form.getlist("tags")
        album.tags = Tag.query.filter(Tag.id.in_(selected_tag_ids)).all()

        selected_character_ids = request.form.getlist("characters")
        album.characters = Character.query.filter(
            Character.id.in_(selected_character_ids)
        ).all()

        db.session.commit()
        flash("Album modifié avec succès." if album_id else "Album créé avec succès.")
        return redirect(url_for("admin.admin_albums_list"))

    all_tags = Tag.query.order_by(Tag.tag_type, Tag.name).all()
    characters = Character.query.order_by(Character.name).all()
    return render_template(
        "admin/album_form.html",
        album=album,
        all_tags=all_tags,
        characters=characters,
        suggestions=[] if album else build_album_suggestions(),
    )


@bp.route("/admin/albums/<int:album_id>/supprimer", methods=["POST"])
@login_required
@admin_required
def admin_albums_delete(album_id: int) -> str:
    """Supprime un album"""
    album = Album.query.get_or_404(album_id)
    db.session.delete(album)
    db.session.commit()

    flash("Album supprimé.")
    return redirect(url_for("admin.admin_albums_list"))
