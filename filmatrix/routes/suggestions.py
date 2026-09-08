"""Suggestions de questions par les joueurs : création, historique et
assistant de recherche TMDB (miroir des endpoints admin, sans le contrôle
admin_required, pour un joueur connecté)."""

import json

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from filmatrix.extensions import db
from filmatrix.models import QuestionSubmission, Tag
from filmatrix.services.suggestions import WEEKLY_SUBMISSION_LIMIT, remaining_weekly_quota
from filmatrix.integrations.itunes import search_soundtrack_previews
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


bp = Blueprint("suggestions", __name__)


@bp.route("/suggestions/nouvelle", methods=["GET", "POST"])
@login_required
def new_suggestion() -> str:
    """Affiche le formulaire de suggestion (GET) ou l'enregistre (POST)"""
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if request.method == "POST":
        if remaining_weekly_quota(current_user) <= 0:
            error = f"Tu as atteint la limite de {WEEKLY_SUBMISSION_LIMIT} suggestions cette semaine."
            if is_ajax:
                return {"success": False, "error": error}, 429
            return render_template(
                "suggestions/new_suggestion.html",
                all_tags=Tag.query.order_by(Tag.tag_type, Tag.name).all(),
                remaining=0,
                weekly_limit=WEEKLY_SUBMISSION_LIMIT,
            ), 429

        try:
            payload = json.loads(request.form["payload"])
            correct_answer = json.loads(request.form["correct_answer"])
        except json.JSONDecodeError:
            error = "La question n'est pas au bon format."
            if is_ajax:
                return {"success": False, "error": error}, 400
            return render_template(
                "suggestions/new_suggestion.html",
                all_tags=Tag.query.order_by(Tag.tag_type, Tag.name).all(),
                remaining=remaining_weekly_quota(current_user),
                weekly_limit=WEEKLY_SUBMISSION_LIMIT,
            ), 400

        prompt = request.form["prompt"]
        if request.form["mode"] == "emoji":
            visuals = json.loads(request.form.get("visuals", "[]"))
            payload.setdefault("visuals", visuals)

        submission = QuestionSubmission(
            user_id=current_user.id,
            mode=request.form["mode"],
            prompt=prompt,
            payload=payload,
            correct_answer=correct_answer,
            content_type=request.form.get("content_type", "film"),
            difficulty=request.form.get("difficulty", "moyen"),
        )

        selected_tag_ids = request.form.getlist("tags")
        submission.tags = Tag.query.filter(Tag.id.in_(selected_tag_ids)).all()

        db.session.add(submission)
        db.session.commit()

        if is_ajax:
            return {"success": True, "redirect": url_for("suggestions.my_suggestions")}
        return redirect(url_for("suggestions.my_suggestions"))

    all_tags = Tag.query.order_by(Tag.tag_type, Tag.name).all()
    template = "suggestions/_suggestion_form_fields.html" if is_ajax else "suggestions/new_suggestion.html"
    return render_template(
        template,
        all_tags=all_tags,
        remaining=remaining_weekly_quota(current_user),
        weekly_limit=WEEKLY_SUBMISSION_LIMIT,
    )


@bp.route("/suggestions/mes-suggestions")
@login_required
def my_suggestions() -> str:
    """Historique des suggestions du joueur connecté"""
    submissions = (
        QuestionSubmission.query.filter_by(user_id=current_user.id)
        .order_by(QuestionSubmission.created_at.desc())
        .all()
    )
    return render_template(
        "suggestions/my_suggestions.html",
        submissions=submissions,
        remaining=remaining_weekly_quota(current_user),
        weekly_limit=WEEKLY_SUBMISSION_LIMIT,
    )


@bp.route("/suggestions/api/recherche-film")
@login_required
def suggestions_api_search_movies() -> dict:
    """Recherche films ET séries pour l'autocomplétion (miroir de admin_api_search_movies)"""
    query = request.args.get("query", "")
    movies = search_movies_list(query, limit=5)
    shows = search_tv_shows_list(query, limit=5)

    interleaved = []
    for pair in zip(movies, shows):
        interleaved.extend(pair)
    interleaved.extend(movies[len(shows):] if len(movies) > len(shows) else shows[len(movies):])

    return {"results": interleaved[:8]}


@bp.route("/suggestions/api/genres-tmdb")
@login_required
def suggestions_api_genres_tmdb() -> dict:
    """Traduit un film/série TMDB en noms de tags genre (miroir de admin_api_genres_tmdb)"""
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


@bp.route("/suggestions/api/recherche-affiche")
@login_required
def suggestions_api_poster() -> dict:
    """Image de scène (backdrop) TMDB (miroir de admin_api_poster)"""
    movie_id = request.args.get("movie_id", type=int)
    content_type = request.args.get("content_type", "film")

    result = None
    if movie_id:
        result = get_tv_show_by_id(movie_id) if content_type == "serie" else get_movie_by_id(movie_id)

    if result is None:
        return {"success": False, "error": "Film introuvable."}

    poster_url = build_image_url(result.get("backdrop_path"))
    return {"success": True, "poster_url": poster_url, "official_title": result["title"]}


@bp.route("/suggestions/api/recherche-jaquette")
@login_required
def suggestions_api_movie_poster() -> dict:
    """Affiche officielle TMDB, avec le titre (miroir de admin_api_movie_poster)"""
    movie_id = request.args.get("movie_id", type=int)
    content_type = request.args.get("content_type", "film")

    result = None
    if movie_id:
        result = get_tv_show_by_id(movie_id) if content_type == "serie" else get_movie_by_id(movie_id)

    if result is None:
        return {"success": False, "error": "Film introuvable."}

    poster_url = build_image_url(result.get("poster_path"))
    if not poster_url:
        return {"success": False, "error": "Aucune affiche disponible pour ce titre."}

    return {"success": True, "poster_url": poster_url, "official_title": result["title"]}


@bp.route("/suggestions/api/recherche-casting")
@login_required
def suggestions_api_cast() -> dict:
    """Photos des principaux acteurs (miroir de admin_api_cast)"""
    movie_id = request.args.get("movie_id", type=int)
    content_type = request.args.get("content_type", "film")

    result = None
    if movie_id:
        result = get_tv_show_by_id(movie_id) if content_type == "serie" else get_movie_by_id(movie_id)

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


@bp.route("/suggestions/api/recherche-audio")
@login_required
def suggestions_api_audio() -> dict:
    """Préécoutes audio pour un film sélectionné (miroir de admin_api_audio)"""
    title = request.args.get("title", "")
    search_term = request.args.get("search_term") or f"{title} soundtrack"
    previews = search_soundtrack_previews(search_term, limit=6)

    if not previews:
        return {"success": False, "error": "Aucun extrait audio trouvé."}

    return {"success": True, "audio_options": previews, "audio_url": previews[0]["audio_url"]}
