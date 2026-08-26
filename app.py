"""Application Flask : sert le quiz Filmatrix sous forme de page web"""

import os
import random
import json

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_migrate import Migrate
from sqlalchemy import func

from src.database import db
from src.engine import check_answer
from src.models import Attempt, Question, User, Report, Friendship, Notification, GameSession, Tag
from src.validation import is_password_valid
from src.badges import check_and_award_badges, BADGES
from src.shop import coins_for_difficulty, TITLES, owns_title, purchase_title
from src.admin import admin_required 
from src.tmdb import (
    build_image_url,
    get_movie_by_id,
    get_movie_cast,
    search_movie,
    search_movies_list,
)
from src.itunes import search_soundtrack_preview
from src.reports import REPORT_REASON
from src.friends import (
        accept_friend_request,
        decline_friend_request,
        get_friends_list,
        send_friend_request,
        get_friendship_between
    )
from src.notifications import create_notification, get_unread_count, mark_all_as_read
from src.avatars import AVATARS
from flask_socketio import SocketIO
from src.multiplayer import create_game_invitation, get_ordered_questions, is_invitation_expired
from src.socket_events import register_socket_events

load_dotenv()

socketio = SocketIO()

# Description des modes de jeu, utilisée pour construire la grille de la page
# d'accueil. `accent` sert de couleur d'accent CSS pour la carte du mode.
GAME_MODES = [
    {
        "slug": "qcm",
        "name": "Quiz",
        "description": "Réponds à des questions sur tes films préférés.",
        "icon": "?",
        "accent": "#22d3ee",
    },
    {
        "slug": "blindtest",
        "name": "Blind Test",
        "description": "Reconnais les musiques de films cultes.",
        "icon": "♪",
        "accent": "#60a5fa",
    },
    {
        "slug": "devinette_affiche",
        "name": "Devine le film",
        "description": "Une image, un film à trouver !",
        "icon": "▶",
        "accent": "#34d399",
    },
    {
        "slug": "citation",
        "name": "Citations",
        "description": "Retrouve le film grâce à une réplique.",
        "icon": "❝",
        "accent": "#fbbf24",
    },
    {
        "slug": "casting",
        "name": "Acteurs",
        "description": "Reconnais les acteurs célèbres du cinéma.",
        "icon": "★",
        "accent": "#f472b6",
    },
    {
        "slug": "emoji",
        "name": "Emoji Quiz",
        "description": "Devine le film à partir des emojis.",
        "icon": "☺",
        "accent": "#c084fc",
    },
    {
        "slug": "film_melange",
        "name": "Film mélangé",
        "description": "Retrouve le titre à partir des lettres mélangées.",
        "icon": "⤭",
        "accent": "#a78bfa",
    },
    {
        "slug": "chronologie",
        "name": "Chronologie",
        "description": "Remets les films dans leur ordre de sortie.",
        "icon": "⏱",
        "accent": "#38bdf8",
    },
    {
        "slug": "devinette",
        "name": "Devinette",
        "description": "Devine le film grâce à des indices progressifs.",
        "icon": "◎",
        "accent": "#fb923c",
    },
    {
        "slug": "vrai_faux",
        "name": "Vrai / Faux",
        "description": "Vraies ou fausses, à toi de trancher.",
        "icon": "±",
        "accent": "#2dd4bf",
    },
]


def calculate_level(total_xp: int) -> dict:
        """Calcule le niveau actuel et le progression vers le niveau suivant"""
        level = 1
        xp_for_next_level = 100
        xp_already_spent = 0

        while total_xp - xp_already_spent >= xp_for_next_level:
            xp_already_spent += xp_for_next_level
            level += 1
            xp_for_next_level = 100 * level 

        xp_in_current_level = total_xp - xp_already_spent

        return {
            "level": level,
            "xp_in_current_level": xp_in_current_level,
            "xp_for_next_level": xp_for_next_level,
            }

def create_app(database_uri: str | None = None) -> Flask:
    """Construit et configure une instance de l'application Flask.

    Le paramètre database_uri permet de fournir une base différente
    (par exemple en mémoire, pour les tests) sans toucher à la vraie base.
    """
    app = Flask(__name__)

    production_database_url = os.environ.get("DATABASE_URL")
    if production_database_url and production_database_url.startswith("postgres://"):
        production_database_url = production_database_url.replace("postgres://", "postgresql://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = (
        database_uri or production_database_url or "sqlite:///filmatrix.db"
    ) 

    app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]

    db.init_app(app)
    Migrate(app, db)
    socketio.init_app(app, cors_allowed_origins="*", async_mode="gevent")
    register_socket_events(socketio)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "login"

    @login_manager.user_loader
    def load_user(user_id: str):
        """Indique à Flask-Login comment retrouver un utilisateur depuis son id de session"""
        return User.query.get(int(user_id))

    def find_question(mode: str, position: int, category: str | None, tag_id: int | None = None):
        """Cherche la question à une position donnée, parmi celles d'un mode, categorie et tag"""
        query = Question.query.filter_by(mode=mode)

        if category:
            query = query.filter_by(category=category)

        if tag_id:
            query = query.filter(Question.tags.any(Tag.id == tag_id))

        mode_questions = query.order_by(Question.id).all()

        index = position - 1
        if index < 0 or index >= len(mode_questions):
            return None

        return mode_questions[index]

    @app.context_processor
    def inject_notifications():
        """Rend le nombre de notifications non lues disponibles dans tous les templates"""
        if current_user.is_authenticated:
            return {"unread_notifications_count": get_unread_count(current_user.id)}
        return {"unread_notifications_count": 0}

    def convert_answer(mode: str, raw_value: str):
        """Convertit la valeur texte du formulaire dans le type attendu par check_answer"""
        if mode == "qcm":
            return int(raw_value)
        if mode == "vrai_faux":
            return raw_value == "true"
        if mode == "citation":
            return raw_value
        if mode == "emoji":
            return raw_value
        if mode == "film_melange":
            return raw_value
        if mode == "chronologie":
            return raw_value.split("|")
        if mode == "devinette":
            return raw_value
        if mode == "devinette_affiche":
            return raw_value
        if mode == "casting":
            return raw_value
        if mode == "blindtest":
            return raw_value
        raise ValueError(f"Mode inconnu : {mode}")

    def scramble_title(title: str) -> str:
        """Mélange aléatoirement les lettres d'un titre en conservant les espaces à leur place"""
        letters = [char for char in title if char != " "]
        random.shuffle(letters)

        scrambled = []
        letter_index = 0
        for char in title:
            if char == " ":
                scrambled.append(" ")
            else:
                scrambled.append(letters[letter_index])
                letter_index += 1

        return "".join(scrambled)

    def xp_for_difficulty(difficulty: str) -> int:
        """Retourne le montant d'XP gagné selon la difficulté de la question"""
        xp_values = {"facile": 10, "moyen": 20, "difficile": 30}
        return xp_values.get(difficulty,10)

    @app.route("/")
    def home() -> str:
        """Page d'accueil : vitrine des modes de jeu, progression et classement"""
        question_counts = dict(
            db.session.query(Question.mode, func.count(Question.id))
            .group_by(Question.mode)
            .all()
        )

        # On n'affiche que les modes qui ont au moins une question en base,
        # pour ne pas envoyer le joueur vers un mode vide.
        playable_modes = [
            dict(mode, question_count=question_counts.get(mode["slug"], 0))
            for mode in GAME_MODES
            if question_counts.get(mode["slug"], 0) > 0
        ]

        top_players = User.query.order_by(User.total_xp.desc()).limit(5).all()

        level_info = None
        correct_count = 0
        if current_user.is_authenticated:
            level_info = calculate_level(current_user.total_xp)
            correct_count = Attempt.query.filter_by(
                user_id=current_user.id, is_correct=True
            ).count()

        return render_template(
            "accueil.html",
            modes=playable_modes,
            top_players=top_players,
            level_info=level_info,
            correct_count=correct_count,
            total_questions=sum(question_counts.values()),
            total_players=User.query.count(),
        )

    @app.route("/inscription", methods=["GET", "POST"])
    def register() -> str:
        """Affiche le formulaire d'inscription (GET) ou crée le compte (POST)."""
        if request.method == "POST":
            username = request.form["username"]
            email = request.form["email"]
            password = request.form["password"]

            if not is_password_valid(password):
                error = "Le mot de passe ne respecte pas les règles de sécurité."
                return render_template("inscription.html", error=error)

            new_user = User(username=username, email=email)
            new_user.set_password(password)

            db.session.add(new_user)
            db.session.commit()

            return redirect(url_for("login"))

        return render_template("inscription.html", error=None)

    @app.route("/connexion", methods=["GET", "POST"])
    def login() -> str:
        """Affiche le formulaire de connexion (GET) ou authentifie l'utilisateur (POST)"""
        if request.method == "POST":
            email = request.form["email"]
            password = request.form["password"]

            user = User.query.filter_by(email=email).first()

            if user is None or not user.verify_password(password):
                error = "Email ou mot de passe incorrect."
                return render_template("connexion.html", error=error)

            login_user(user)
            return redirect(url_for("home"))

        return render_template("connexion.html", error=None)

    @app.route("/deconnexion")
    @login_required
    def logout() -> str:
        """Déconnecte l'utilisateur courant"""
        logout_user()
        return redirect(url_for("home"))

    @app.route("/profil")
    @login_required
    def profile() -> str:
        """Affiche le score et l'historique du joueur connecté"""
        attempts = (
            Attempt.query.filter_by(user_id=current_user.id)
            .order_by(Attempt.answered_at.desc())
            .all()
        )

        total_count = len(attempts)
        correct_count = sum(1 for attempt in attempts if attempt.is_correct)
        level_info = calculate_level(current_user.total_xp)

        attempts_by_mode = {}
        for attempt in attempts:
            mode = attempt.question.mode
            attempts_by_mode.setdefault(mode, []).append(attempt)

        earned_badge_codes = {badge.badge_code for badge in current_user.badges}
        all_badges = []
        for code, info in BADGES.items():
            all_badges.append(
                {
                    "code": code,
                    "name": info["name"],
                    "description": info["description"],
                    "icon": info["icon"],
                    "earned": code in earned_badge_codes,
                }
            )

        equipped_title_name= None
        if current_user.equipped_title:
            equipped_title_name = TITLES.get(current_user.equipped_title, {}).get("name")

        return render_template(
            "profil.html",
            attempts_by_mode=attempts_by_mode,
            total_count=total_count,
            correct_count=correct_count,
            level_info=level_info,
            all_badges=all_badges,
            equipped_title_name=equipped_title_name,
        )

    @app.route("/profil/modifier", methods=["GET", "POST"])
    @login_required
    def edit_profile() -> str:
        """Permet de mofifier son avatar et sa bio"""
        if request.method == "POST":
            selected_avatar = request.form.get("avatar")
            if selected_avatar in AVATARS:
                current_user.avatar = selected_avatar

            bio = request.form.get("bio", "").strip()
            current_user.bio = bio[:280] if bio else None

            db.session.commit()

            flash("Profil mis à jour.")
            return redirect(url_for("profile"))

        return render_template("edit_profile.html", avatars=AVATARS)

    @app.route("/admin/questions")
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

    @app.route("/admin/questions/nouvelle", methods=["GET", "POST"])
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
            return redirect(url_for("admin_questions_list"))

        all_tags = Tag.query.order_by(Tag.tag_type, Tag.name).all()
        return render_template("admin/question_form.html", question=None, all_tags=all_tags)

    @app.route("/admin/questions/<int:question_id>/modifier", methods=["GET", "POST"])
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
            return redirect(url_for("admin_questions_list"))

        all_tags = Tag.query.order_by(Tag.tag_type, Tag.name).all()
        return render_template("admin/question_form.html", question=question, all_tags=all_tags)

    @app.route("/admin/questions/<int:question_id>/supprimer", methods=["POST"])
    @login_required
    @admin_required
    def admin_questions_delete(question_id: int) -> str:
        """Supprime une question"""
        question = Question.query.get_or_404(question_id)
        db.session.delete(question)
        db.session.commit()

        flash("Question supprimée.")
        return redirect(url_for("admin_questions_list"))

    @app.route("/admin/api/recherche-film")
    @login_required
    @admin_required
    def admin_api_search_movies() ->  dict:
        """Recherche plusieurs films pour l'autocomplétion, avec miniatures"""
        query = request.args.get("query", "")
        results = search_movies_list(query)
        return {"results": results}

    @app.route("/admin/api/recherche-affiche")
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

    @app.route("/admin/api/recherche-casting")
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

    @app.route("/admin/api/recherche-audio")
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

    @app.route("/admin/utilisateurs")
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

    @app.route("/admin/utilisateurs/<int:user_id>/basculer-admin", methods=["POST"])
    @login_required
    @admin_required
    def admin_toggle_admin(user_id: int) -> str:
        """Bascule le statut admin d'un utilisateur"""
        if user_id == current_user.id:
            flash("Tu ne peux pas modifier ton propre statut administrateur.")
            return redirect(url_for("admin_users_list"))

        user = User.query.get_or_404(user_id)
        user.is_admin = not user.is_admin
        db.session.commit()

        flash(f"Statut administrateur de {user.username} mis à jour.")
        return redirect(url_for("admin_users_list"))

    @app.route("/admin/utilisateurs/<int:user_id>/supprimer", methods=["POST"])
    @login_required
    @admin_required
    def admin_delete_user(user_id: int) -> str:
        """Supprime un utilisateur et tout son historique"""
        if user_id == current_user.id:
            flash("Tu ne peux pas supprimer ton propre compte depuis cette page.")
            return redirect(url_for("admin_users_list"))

        user = User.query.get_or_404(user_id)
        Attempt.query.filter_by(user_id=user.id).delete()
        db.session.delete(user)
        db.session.commit()

        flash(f"Le compte de {user.username} a été supprimé.")
        return redirect(url_for("admin_users_list"))

    @app.route("/admin/signalements")
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

    @app.route("/admin/tags")
    @login_required
    @admin_required
    def admin_tags_list() -> str:
        """Affiche la liste des tags disponibles"""
        all_tags = Tag.query.order_by(Tag.tag_type, Tag.name).all()
        return render_template("admin/tags_list.html", tags=all_tags, active_admin_section="tags")

    @app.route("/admin/tags/nouveau", methods=["POST"])
    @login_required
    @admin_required
    def admin_tags_new() -> str:
        """Crée un nouveau tag"""
        name = request.form.get("name", "").strip()
        tag_type = request.form.get("tag_type", "genre")

        if name:
            existing = Tag.query.filter_by(name=name).first()
            if existing is None:
                new_tag = Tag(name=name, tag_type=tag_type)
                db.session.add(new_tag)
                db.session.commit()
                flash(f"Tag '{name}' crée.")
            else:
                flash("Ce tag existe déjà.")
        return redirect(url_for("admin_tags_list"))

    @app.route("/admin/tags/<int:tag_id>/supprimer", methods=["POST"])
    @login_required
    @admin_required
    def admin_tags_delete(tag_id: int) -> str:
        """Supprime un tag"""
        tag = Tag.query.get_or_404(tag_id)
        db.session.delete(tag)
        db.session.commit()

        flash("Tag supprimé.")
        return redirect(url_for("admin_tags_list"))

    @app.route("/admin/signalements/<int:report_id>/traiter", methods=["POST"]) 
    @login_required
    @admin_required
    def admin_resolve_report(report_id: int) -> str:
        """Marque un signalement comme traité"""
        report = Report.query.get_or_404(report_id)
        report.is_resolved = True
        db.session.commit()

        flash("Signalement marqué comme traité.")
        return redirect(url_for("admin_reports_list"))   

    @app.route("/modes")
    def modes() -> str:
        """Affiche la liste des modes de jeu disponibles"""
        all_tags = Tag.query.order_by(Tag.tag_type, Tag.name).all()
        return render_template("modes.html", all_tags=all_tags)

    @app.route("/boutique")
    @login_required
    def shop() -> str:
        """Affiche la boutique de titres avec le statut d'achat pour chacun"""
        shop_titles = []
        for code, info in TITLES.items():
            shop_titles.append(
                {
                    "code": code,
                    "name": info["name"],
                    "price": info["price"],
                    "owned": owns_title(current_user, code),
                    "affordable": current_user.coins >= info["price"],
                }
            )

        return render_template("boutique.html", shop_titles=shop_titles)

    @app.route("/boutique/acheter/<title_code>", methods=["POST"])
    @login_required
    def buy_title(title_code: str) -> str:
        """Traite l'achat d'un titre par un utilisateur connecté"""
        success = purchase_title(current_user, title_code)
        db.session.commit()

        if success:
            flash("Titre acheté avec succès.")
        else:
            flash("Achat impossible.")

        return redirect(url_for("shop"))

    @app.route("/boutique/equiper/<title_code>", methods=["POST"])
    @login_required
    def equip_title(title_code: str) -> str:
        """Equipe un titre possédé par l'utilisateur connecté"""
        if owns_title(current_user, title_code):
            current_user.equipped_title = title_code
            db.session.commit()
            flash("Titre équipé.")
        else:
            flash("Tu ne possède pas ce titre.")

        return redirect(url_for("shop"))

    @app.route("/quiz/<mode>/<int:position>", methods=["GET", "POST"])
    def quiz(mode: str, position: int) -> str:
        """Affiche une question (GET) ou traite la réponse envoyée (POST)."""
        category = request.args.get("category")
        tag_id = request.args.get("tag_id", type=int)
        question = find_question(mode, position, category, tag_id)

        if question is None:
            return render_template("termine.html")

        if question.requires_account and not current_user.is_authenticated:
            flash("Connecte-toi pour accéder à cette question.")
            return redirect(url_for("login"))

        if request.method == "POST":
            is_timeout = request.form.get("timeout") == "true"

            if is_timeout:
                is_correct = False
            else:
                raw_answer = request.form["answer"]
                player_answer = convert_answer(question.mode, raw_answer)
                is_correct = check_answer(question, player_answer)

            if question.mode == "devinette" and not is_correct:
                hint_index = int(request.form.get("hint_index", 0))
                hints = question.payload["hints"]

                if hint_index < len(hints) - 1:
                    return {
                        "is_correct": False,
                        "give_up": False,
                        "next_hint": hints[hint_index + 1],
                        "was_timeout": is_timeout,
                    }

            new_badges = []

            if current_user.is_authenticated:
                already_answered_correctly = Attempt.query.filter_by(
                    user_id=current_user.id,
                    question_id=question.id,
                    is_correct=True,
                ).first() is not None

                attempt = Attempt(
                    user_id=current_user.id,
                    question_id=question.id,
                    is_correct=is_correct,
                )
                db.session.add(attempt)

                if is_correct and not already_answered_correctly:
                    current_user.total_xp += xp_for_difficulty(question.difficulty)
                    current_user.coins += coins_for_difficulty(question.difficulty)

                db.session.commit()

                new_badge_codes = check_and_award_badges(current_user)
                db.session.commit()

                new_badges = [BADGES[code] for code in new_badge_codes]

            if question.mode == "chronologie":
                correct_order = question.correct_answer["order"]
                position_results = [
                    player_answer[i] == correct_order[i]
                    for i in range(len(correct_order))
                ]
                return {
                    "is_correct": is_correct,
                    "position_results": position_results,
                    "give_up": True,
                    "new_badges": new_badges,
                }

            return {"is_correct": is_correct, "give_up": True, "new_badges": new_badges}

        scrambled_title = None
        if question.mode == "film_melange":
            scrambled_title = scramble_title(question.correct_answer["title"])

        return render_template(
                "quiz.html",
                question=question,
                scrambled_title=scrambled_title,
                report_reasons=REPORT_REASON,
            )

    @app.route("/signaler/<int:question_id>", methods=["POST"])
    @login_required
    def report_question(question_id: int) -> str:
        """Enregistre un signalement sur une question"""
        reason = request.form.get("reason", "other")

        report = Report(
                user_id=current_user.id,
                question_id=question_id,
                reason=reason,
            )
        db.session.add(report)
        db.session.commit()

        return {"success": True}

    @app.route("/amis/demander/<int:user_id>", methods=["POST"])
    @login_required
    def send_friend_request_route(user_id: int) -> str:
        """Envoie une demande d'amis à un utilisateur"""
        target_user = User.query.get_or_404(user_id)

        success = send_friend_request(current_user, target_user)

        if success:
            create_notification(
                target_user,
                f"{current_user.username} t'a envoyé une demande d'ami.",
                link=url_for("friends_list"),
            )

        db.session.commit()

        if success:
            flash(f"Demande d'ami envoyée à {target_user.username}.")
        else:
            flash("Impossible d'envoyer cette demande.")

        return redirect(request.referrer or url_for("friends_list"))

    @app.route("/amis/accepter/<int:friendship_id>", methods=["POST"])
    @login_required
    def accept_friend_request_route(friendship_id: int) -> str:
        """Accepte une demande d'ami reçue"""
        friendship = Friendship.query.get(friendship_id)
        success = accept_friend_request(friendship_id, current_user.id)

        if success:
            create_notification(
                friendship.requester,
                f"{current_user.username} a accepté ta demande d'ami.",
                link=url_for("friends_list"),
            )

        db.session.commit()

        if success:
            flash("Demande d'ami acceptée.")
        else:
            flash("Impossible d'accepter cette demande.")

        return redirect(url_for("friends_list"))

    @app.route("/amis/refuser/<int:friendship_id>", methods=["POST"])
    @login_required
    def decline_friend_request_route(friendship_id: int) -> str:
        """Refuse ou annule une demande d'ami"""
        success = decline_friend_request(friendship_id, current_user.id)
        db.session.commit()

        if success:
            flash("Demande supprimée.")
        else:
            flash("Impossible de supprimer cette demande.")

        return redirect(url_for("friends_list"))

    @app.route("/amis")
    @login_required
    def friends_list() -> str:
        """Affiche la liste d'amis, les demandes reçues et envoyées"""
        friends = get_friends_list(current_user.id)

        received_requests = [
                friendship
                for friendship in current_user.received_friend_requests
                if friendship.status == "pending"
            ]

        sent_requests = [
                friendship
                for friendship in current_user.sent_friend_requests
                if friendship.status == "pending"
            ]

        return render_template(
                "amis.html",
                friends=friends,
                received_requests=received_requests,
                sent_requests=sent_requests,
            )

    @app.route("/multijoueur/inviter/<int:user_id>", methods=["POST"])
    @login_required
    def invite_to_game(user_id: int) -> str:
        """Invite un ami à une partie multijoueur en mode rapidité"""
        friendship = get_friendship_between(current_user.id, user_id)
        if friendship is None or friendship.status != "accepted":
            flash("Tu dois être ami avec ce joueur pour l'inviter.")
            return redirect(url_for("friends_list"))

        guest = User.query.get_or_404(user_id)
        mode = request.form.get("mode", "qcm")

        game_session = create_game_invitation(current_user, guest, mode)

        if game_session is None:
            flash("Pas assez de questions disponibles pour ce mode.")
            return redirect(url_for("friends_list"))

        db.session.commit()

        create_notification(
                guest,
                f"{current_user.username} t'invite à une partie !",
                link=url_for("game_lobby", game_session_id=game_session.id),
            )
        db.session.commit()

        flash(f"Invitation envoyée à {guest.username}.")
        return redirect(url_for("game_lobby", game_session_id=game_session.id))

    @app.route("/multijoueur/<int:game_session_id>")
    @login_required
    def game_lobby(game_session_id: int) -> str:
        """Affiche la salle d'attente d'une partie multijoueur"""
        game_session = GameSession.query.get_or_404(game_session_id)

        if current_user.id not in (game_session.host_id, game_session.guest_id):
            flash("Tu ne fais pas partie de cette partie.")
            return redirect(url_for("friends_list"))

        if game_session.status == "invited" and is_invitation_expired(game_session):
            game_session.status = "expired"
            db.session.commit()

        return render_template("multiplayer_lobby.html", game_session=game_session)

    @app.route("/multijoueur/<int:game_session_id>/accepter", methods=["POST"])
    @login_required
    def accept_game_invitation(game_session_id: int) -> str:
        """Accepte une invitation de partie multijoueur"""
        game_session = GameSession.query.get_or_404(game_session_id)

        if current_user.id != game_session.guest_id or game_session.status != "invited":
            flash("Impossible d'accepter cette invitation.")
            return redirect(url_for("friends_list"))

        if is_invitation_expired(game_session):
            game_session.status = "expired"
            db.session.commit()
            flash("Cette invitation a expiré.")
            return redirect(url_for("game_lobby", game_session_id=game_session.id))

        game_session.status = "active"
        db.session.commit()

        create_notification(
                game_session.host,
                f"{current_user.username} a accepté ta partie !",
                link=url_for("game_lobby", game_session_id=game_session.id),
            )
        db.session.commit()

        socketio.emit(
                "game_started",
                {"redirect_url": url_for("game_lobby", game_session_id=game_session.id)},
                room=f"user_{game_session.host_id}",
            )

        return redirect(url_for("game_lobby", game_session_id=game_session.id))

    @app.route("/multijoueur/<int:game_session_id>/refuser", methods=["POST"])
    @login_required
    def decline_game_invitation(game_session_id: int) -> str:
        """Refuse une invitation de partie multijoueur"""
        game_session = GameSession.query.get_or_404(game_session_id)

        if current_user.id != game_session.guest_id or game_session.status != "invited":
            flash("Impossible de refuser cette invitation.")
            return redirect(url_for("friends_list"))

        game_session.status = "declined"
        db.session.commit()

        return redirect(url_for("game_lobby", game_session_id=game_session.id))

    @app.route("/multijoueur/<int:game_session_id>/jouer")
    @login_required
    def play_game(game_session_id: int) -> str:
        """Affiche la salle de jeu synchronisée d'une partie multijoueur"""
        game_session = GameSession.query.get_or_404(game_session_id)

        if current_user.id not in (game_session.host_id, game_session.guest_id):
            flash("Tu ne fais pas partie de cette partie.")
            return redirect(url_for("friends_list"))

        if game_session.status != "active":
            return redirect(url_for("game_lobby", game_session_id=game_session.id))

        questions = get_ordered_questions(game_session)

        if game_session.current_question_index >= len(questions):
            return redirect(url_for("game_results", game_session_id=game_session.id))

        current_question = questions[game_session.current_question_index]
        opponent = game_session.guest if current_user.id == game_session.host_id else game_session.host

        return render_template(
                "multiplayer_game.html",
                game_session=game_session,
                question=current_question,
                opponent=opponent,
                total_questions=len(questions)
            )

    @app.route("/multijoueur/<int:game_session_id>/statut")
    @login_required
    def game_session_status(game_session_id: int) -> dict:
        """Renvoie le statut actuel d'une partie"""
        game_session = GameSession.query.get_or_404(game_session_id)

        if current_user.id not in (game_session.host_id, game_session.guest_id):
            return {"status": "forbidden"}
        return {"status": game_session.status}

    @app.route("/multijoueur/<int:game_session_id>/resultats")
    @login_required
    def game_results(game_session_id: int) -> str:
        """Affiche les résultats finaux d'une partie multijoueur avec mort subite si égalité"""
        game_session = GameSession.query.get_or_404(game_session_id)

        if current_user.id not in (game_session.host_id, game_session.guest_id):
            flash("Tu ne fais pas partie de cette partie.")
            return redirect(url_for("friends_list"))

        if game_session.status != "finished":
            game_session.status = "finished"
            db.session.commit()

        if game_session.host_score == game_session.guest_score:
            winner = None
        elif game_session.host_score > game_session.guest_score:
            winner = game_session.host
        else:
            winner = game_session.guest

        opponent = game_session.guest if current_user.id == game_session.host_id else game_session.host
        my_score = game_session.host_score if current_user.id == game_session.host_id else game_session.guest_score
        opponent_score = game_session.guest_score if current_user.id == game_session.host_id else game_session.host_score

        return render_template(
                "multiplayer_results.html",
                game_session=game_session,
                winner=winner,
                opponent=opponent,
                my_score=my_score,
                opponent_score=opponent_score,
            ) 

    @app.route("/joueur/<int:user_id>")
    @login_required
    def public_profile(user_id: int) -> str:
        """Affiche le profil public d'un joueur, uniquement entre amis"""
        if user_id == current_user.id:
            return redirect(url_for("profile"))

        viewed_user = User.query.get_or_404(user_id)

        friendship = get_friendship_between(current_user.id, user_id)
        if friendship is None or friendship.status != "accepted":
            flash("Tu dois être ami avec ce joueur pour voir son profil.")
            return redirect(url_for("friends_list"))

        attempts = Attempt.query.filter_by(user_id=viewed_user.id).all()
        total_count = len(attempts)
        correct_count = sum(1 for attempt in attempts if attempt.is_correct)
        level_info = calculate_level(viewed_user.total_xp)

        attempts_by_mode = {}
        for attempt in attempts:
            mode = attempt.question.mode
            attempts_by_mode.setdefault(mode, 0)
            attempts_by_mode[mode] += 1

        earned_badge_codes = {badge.badge_code for badge in viewed_user.badges}
        all_badges = []
        for code, info in BADGES.items():
            all_badges.append(
                    {
                        "name": info["name"],
                        "icon": info["icon"],
                        "earned": code in earned_badge_codes,
                        }
                )

            viewed_user_friends = get_friends_list(viewed_user.id)
            current_user_friends = get_friends_list(current_user.id)

            current_user_friend_ids = {friend.id for friend in current_user_friends}
            mutual_friends = [
                    friend for friend in viewed_user_friends if friend.id in current_user_friend_ids
                ]

            return render_template(
                    "profil_public.html",
                    viewed_user=viewed_user,
                    total_count=total_count,
                    correct_count=correct_count,
                    level_info=level_info,
                    attempts_by_mode=attempts_by_mode,
                    all_badges=all_badges,
                    viewed_user_friends=viewed_user_friends,
                    mutual_friends=mutual_friends,
                )

    @app.route("/notifications")
    @login_required
    def get_notifications() -> dict:
        """Renvoie les notifications recentes de l'utilisateur et les marque comme lues"""
        notifications = (
            Notification.query.filter_by(user_id=current_user.id)
            .order_by(Notification.created_at.desc())
            .limit(10)
            .all()
        )

        notifications_data = [
            {
                "message": notification.message,
                "link": notification.link,
                "is_read": notification.is_read,
            }
            for notification in notifications
        ]

        mark_all_as_read(current_user.id)
        db.session.commit()

        return {"notifications": notifications_data}


    @app.route("/classement")
    def leaderboard() -> str:
        """Affiche le classement général des joueurs, trié par XP total"""
        results = (
                db.session.query(
                    User.id,
                    User.username,
                    User.total_xp,
                    func.count(Attempt.id).label("total"),
                    func.sum(db.case((Attempt.is_correct, 1), else_=0)).label("correct"),
                )
                .join(Attempt, Attempt.user_id == User.id)
                .group_by(User.id)
                .order_by(User.total_xp.desc())
                .all()
            )

        leaderboard_entries = []
        for result in results:
            level_info = calculate_level(result.total_xp)

            friendship_status = None
            if current_user.is_authenticated and current_user.id != result.id:
                friendship = get_friendship_between(current_user.id, result.id)
                if friendship is not None:
                    friendship_status = friendship.status

            leaderboard_entries.append(
                    {
                        "user_id": result.id,
                        "username": result.username,
                        "total_xp": result.total_xp,
                        "level": level_info["level"],
                        "total": result.total,
                        "correct": result.correct,
                        "friendship_status": friendship_status,
                        }
                )

        return render_template("classement.html", results=leaderboard_entries)

    return app


app = create_app()

if __name__ == "__main__":
    socketio.run(app, debug=True)