"""Administration : questions, utilisateurs, signalements et thèmes."""

import json

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from filmatrix.extensions import db
from filmatrix.permissions import admin_required
from filmatrix.catalog import REPORT_REASON
from filmatrix.models import Attempt, Question, Report, Tag, User
from filmatrix.integrations.itunes import search_soundtrack_preview
from filmatrix.integrations.tmdb import (
    build_image_url,
    get_movie_by_id,
    get_movie_cast,
    search_movies_list,
)


bp = Blueprint("admin", __name__)


@bp.route("/admin/questions")
@login_required 
@admin_required
def admin_questions_list() -> str:
    """Affiche la liste de toutes les questions, groupées par mode pour l'admin"""
    all_questions = Question.query.order_by(Question.mode, Question.id).all()

    questions_by_mode = {}
    for question in all_questions:
        questions_by_mode.setdefault(question.mode, []).append(question)

    return render_template(
            "admin/questions_list.html",
            questions_by_mode=questions_by_mode,
            total_count=len(all_questions),
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

        new_question = Question(
            mode=request.form["mode"],
            category=request.form["category"],
            difficulty=request.form["difficulty"],
            prompt=request.form["prompt"],
            payload=payload,
            correct_answer=correct_answer,
            requires_account=request.form.get("requires_account") == "on",
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
        question.category = request.form["category"]
        question.difficulty = request.form["difficulty"]
        question.prompt = request.form["prompt"]
        question.payload = payload
        question.correct_answer = correct_answer
        question.requires_account = request.form.get("requires_account") == "on"

        selected_tag_ids = request.form.getlist("tags")
        question.tags = Tag.query.filter(Tag.id.in_(selected_tag_ids)).all()

        db.session.commit()

        flash("Question modifiée avec succès.")
        return redirect(url_for("admin.admin_questions_list"))

    all_tags = Tag.query.order_by(Tag.tag_type, Tag.name).all()
    return render_template("admin/question_form.html", question=question, all_tags=all_tags)

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
    """Recherche plusieurs films pour l'autocomplétion, avec miniatures"""
    query = request.args.get("query", "")
    results = search_movies_list(query)
    return {"results": results}

@bp.route("/admin/api/recherche-affiche")
@login_required
@admin_required
def admin_api_poster() -> dict:
    """Récupère l'image de scène (backdrop) TMDB pour un film sélectionné"""
    movie_id = request.args.get("movie_id", type=int)
    movie = get_movie_by_id(movie_id) if movie_id else None

    if movie is None:
        return {"success": False, "error": "Film introuvable."}

    poster_url = build_image_url(movie.get("backdrop_path"))
    return {"success": True, "poster_url": poster_url, "official_title": movie["title"]}

@bp.route("/admin/api/recherche-casting")
@login_required
@admin_required
def admin_api_cast() -> dict:
    """Récupère les photos des principaux acteurs pour un film sélectionné"""
    movie_id = request.args.get("movie_id", type=int)
    movie = get_movie_by_id(movie_id) if movie_id else None

    if movie is None:
        return {"success": False, "error": "Film introuvable."}

    cast = get_movie_cast(movie["id"], limit=3)
    actor_photos = [
        build_image_url(actor["profile_path"]) for actor in cast if actor["profile_path"]
    ]
    return {"success": True, "actor_photos": actor_photos, "official_title": movie["title"]}

@bp.route("/admin/api/recherche-audio")
@login_required
@admin_required
def admin_api_audio() -> dict:
    """Recherche un extrait audio via iTunes pour un film sélectionné"""
    title = request.args.get("title", "")
    search_term = request.args.get("search_term") or f"{title} soundtrack"

    audio_url = search_soundtrack_preview(search_term)

    if audio_url is None:
        return {"success": False, "error": "Aucun extrait audio trouvé."}

    return {"success": True, "audio_url": audio_url}

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
    return render_template("admin/tags_list.html", tags=all_tags, active_admin_section="tags")

@bp.route("/admin/tags/nouveau", methods=["POST"])
@login_required
@admin_required
def admin_tags_new() -> str:
    """Crée un nouveau tag"""
    name = request.form.get("name", "").strip()
    tag_type = request.form.get("tag_type", "genre")
    allowed_types = {"genre", "saga", "univers", "pays", "epoque", "annee", "realisateur", "acteur", "studio", "autre"}
    if tag_type not in allowed_types:
        tag_type = "autre"

    if name:
        existing = Tag.query.filter_by(name=name).first()
        if existing is None:
            new_tag = Tag(name=name, tag_type=tag_type)
            db.session.add(new_tag)
            db.session.commit()
            flash(f"Tag '{name}' crée.")
        else:
            flash("Ce tag existe déjà.")
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
