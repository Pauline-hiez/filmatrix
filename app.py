from gevent import monkey

monkey.patch_all()

"""Application Flask : sert le quiz Filmatrix sous forme de page web"""

import os
import random
import json

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
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
from src.engine import check_answer, convert_answer, scramble_title
from src.models import Attempt, Question, User, Report, Friendship, Notification, GameSession, Tag
from src.score import (
    QUESTIONS_PER_RUN,
    read_run,
    record_answer,
    run_length,
    run_question_id,
    start_run,
)
from src.validation import is_password_valid
from src.badges import check_and_award_badges, BADGES
from src.shop import TITLES, owns_title, purchase_title
from src.levels import (
    BLINDTEST_DURATION,
    DEFAULT_LEVEL,
    LEVELS,
    coins_for_level,
    duration_for,
    resolve_level,
    xp_for_level,
)
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
    remove_friend,
        send_friend_request,
        get_friendship_between
    )
from src.notifications import create_notification, get_unread_count, mark_all_as_read
from src.avatars import AVATARS
from flask_socketio import SocketIO
from src.multiplayer import (
    INVITATION_DURATION_MINUTES,
    QUESTIONS_PER_GAME,
    build_choices,
    create_game_invitation,
    get_ordered_questions,
    is_invitation_expired,
)
from src.socket_events import register_socket_events

load_dotenv()

socketio = SocketIO()

# Description des modes de jeu, utilisée pour construire la grille de la page
# d'accueil. `accent` sert de couleur d'accent CSS pour la carte du mode.
# Métadonnées d'affichage des modes solo : nom, pitch et règle du jeu.
# Cette liste est la seule source : l'accueil, la page des modes et l'écran de
# préparation la lisent tous, pour ne pas décrire le même jeu de trois façons.
# "how" répond à la question que se pose un joueur qui découvre le mode : que
# vais-je voir à l'écran, et qu'attend-on de moi ?
GAME_MODES = [
    {
        "slug": "qcm",
        "name": "Quiz",
        "description": "Réponds à des questions sur tes films préférés.",
        "how": "Une question, quatre propositions. Une seule est la bonne, et leur ordre change à chaque partie.",
        "icon": "?",
        "accent": "#22d3ee",
    },
    {
        "slug": "blindtest",
        "name": "Blind Test",
        "description": "Reconnais les musiques de films cultes.",
        "how": "Un extrait de bande originale se lance. Tape le titre du film ou de la série qu'il accompagne.",
        "icon": "♪",
        "accent": "#60a5fa",
    },
    {
        "slug": "devinette_affiche",
        "name": "Devine le film",
        "description": "Une image, un film à trouver !",
        "how": "Une image tirée du tournage s'affiche, sans le titre. À toi de reconnaître l'œuvre et de l'écrire.",
        "icon": "▶",
        "accent": "#34d399",
    },
    {
        "slug": "citation",
        "name": "Citations",
        "description": "Retrouve le film grâce à une réplique.",
        "how": "Une réplique restée célèbre s'affiche. Retrouve l'œuvre d'où elle sort.",
        "icon": "❝",
        "accent": "#fbbf24",
    },
    {
        "slug": "casting",
        "name": "Acteurs",
        "description": "Reconnais les acteurs célèbres du cinéma.",
        "how": "Trois visages du casting principal, sans leur nom. Trouve ce qu'ils ont tourné ensemble.",
        "icon": "★",
        "accent": "#f472b6",
    },
    {
        "slug": "emoji",
        "name": "Emoji Quiz",
        "description": "Devine le film à partir des emojis.",
        "how": "Une poignée d'emojis raconte l'intrigue à leur manière. Décode-les et donne le titre.",
        "icon": "☺",
        "accent": "#c084fc",
    },
    {
        "slug": "film_melange",
        "name": "Film mélangé",
        "description": "Retrouve le titre à partir des lettres mélangées.",
        "how": "Les lettres du titre sont dans le désordre, les espaces à leur place. Remets-les dans l'ordre.",
        "icon": "⤭",
        "accent": "#a78bfa",
    },
    {
        "slug": "chronologie",
        "name": "Chronologie",
        "description": "Remets les films dans leur ordre de sortie.",
        "how": "Plusieurs titres s'affichent. Clique dessus du plus ancien au plus récent, puis valide.",
        "icon": "⏱",
        "accent": "#38bdf8",
    },
    {
        "slug": "devinette",
        "name": "Devinette",
        "description": "Devine le film grâce à des indices progressifs.",
        "how": "Un premier indice, puis un autre à chaque erreur. Plus tu trouves tôt, plus c'est fort.",
        "icon": "◎",
        "accent": "#fb923c",
    },
    {
        "slug": "vrai_faux",
        "name": "Vrai / Faux",
        "description": "Vraies ou fausses, à toi de trancher.",
        "how": "Une affirmation sur le cinéma s'affiche. Un seul geste : vrai, ou faux.",
        "icon": "±",
        "accent": "#2dd4bf",
    },
]

# Les modes ouverts au multijoueur. Ils le sont tous, mais la liste reste
# explicite : un mode dont l'écran de duel ne saurait pas afficher le média ou
# recueillir la réponse doit pouvoir en être retiré sans toucher au reste.
MULTIPLAYER_MODES = [entry["slug"] for entry in GAME_MODES]


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

    def resolve_content_type(value: str | None) -> str:
        """Ne garde que les types de contenu connus, une chaîne vide sinon"""
        return value if value in ("film", "serie") else ""

    def build_question_query(
        mode: str,
        category: str | None = None,
        tag_id: int | None = None,
        content_type: str | None = None,
    ):
        """Construit la requête des questions jouables pour un mode et ses filtres

        L'ordre est fixé par l'id : deux appels successifs pour la même partie
        doivent renvoyer les questions dans le même ordre, sans quoi le joueur
        rejouerait la même à des positions différentes"""
        query = Question.query.filter_by(mode=mode)

        if category:
            query = query.filter_by(category=category)

        if tag_id:
            query = query.filter(Question.tags.any(Tag.id == tag_id))

        if content_type:
            query = query.filter_by(content_type=content_type)

        return query.order_by(Question.id)

    def playable_question_query(
        mode: str,
        category: str | None = None,
        tag_id: int | None = None,
        content_type: str | None = None,
    ):
        """Restreint aux questions que le joueur peut réellement jouer

        Une question réservée aux comptes renverrait un visiteur vers la page de
        connexion en pleine partie, sa progression perdue : elle n'a rien à faire
        ni dans le tirage, ni dans les compteurs qu'on lui annonce"""
        query = build_question_query(mode, category, tag_id, content_type)

        if not current_user.is_authenticated:
            query = query.filter_by(requires_account=False)

        return query

    def count_run_questions(
        mode: str,
        category: str | None = None,
        tag_id: int | None = None,
        content_type: str | None = None,
    ) -> int:
        """Retourne le nombre de questions que comptera la partie

        Une partie fait QUESTIONS_PER_RUN questions, sauf si les filtres du
        joueur en laissent moins : on ne promet pas un total qu'on ne peut pas
        servir"""
        available = playable_question_query(mode, category, tag_id, content_type).count()
        return min(QUESTIONS_PER_RUN, available)

    def run_filters(
        category: str | None = None,
        tag_id: int | None = None,
        content_type: str | None = None,
    ) -> dict:
        """Décrit les réglages d'une partie, sous une forme rangeable en session"""
        return {"category": category, "tag_id": tag_id, "content_type": content_type}

    def draw_run_questions(
        mode: str,
        category: str | None = None,
        tag_id: int | None = None,
        content_type: str | None = None,
    ) -> list[int]:
        """Tire au sort les questions d'une nouvelle partie

        Le tirage a lieu une seule fois, au lancement : deux parties du même mode
        ne se ressemblent pas, mais à l'intérieur d'une partie l'ordre ne bouge
        plus, sans quoi avancer d'une question en ramènerait une déjà posée"""
        question_ids = [
            row.id for row in playable_question_query(mode, category, tag_id, content_type).all()
        ]
        random.shuffle(question_ids)

        return question_ids[:QUESTIONS_PER_RUN]

    def find_question(
        mode: str,
        position: int,
        category: str | None,
        tag_id: int | None = None,
        content_type: str | None = None,
    ):
        """Cherche la question à une position donnée, parmi celles d'un mode, categorie, tag et type de contenu

        Renvoie None au-delà de la dernière position de la partie : c'est ce qui
        met fin à la partie et renvoie le joueur vers l'écran de score"""
        if position < 1 or position > QUESTIONS_PER_RUN:
            return None

        filters = run_filters(category, tag_id, content_type)
        question_id = run_question_id(session, mode, position, filters)

        if question_id is not None:
            return Question.query.get(question_id)

        # Aucun tirage en session : lien direct vers une question, session
        # expirée ou navigation manuelle. On sert alors l'ordre stable par id,
        # plutôt que de refuser la question au joueur.
        query = build_question_query(mode, category, tag_id, content_type)

        return query.offset(position - 1).limit(1).first()

    def shuffle_options(question) -> list[tuple[int, str]]:
        """Mélange les propositions d'un QCM, chacune gardant son index d'origine

        La bonne réponse est l'option 0 dans la majorité des questions : sans
        mélange, le joueur finit par répondre au réflexe. C'est bien l'index
        d'origine qui repart au serveur, la vérification reste donc inchangée"""
        options = list(enumerate(question.payload["options"]))
        random.shuffle(options)

        return options

    @app.context_processor
    def inject_notifications():
        """Rend le nombre de notifications non lues disponibles dans tous les templates"""
        if current_user.is_authenticated:
            return {"unread_notifications_count": get_unread_count(current_user.id)}
        return {"unread_notifications_count": 0}

    def format_correct_answer(question) -> str:
        """Formate la bonne réponse d'une question en texte lisible pour tous les modes"""
        if question.mode == "qcm":
            index = question.correct_answer["index"]
            return question.payload["options"][index]
        if question.mode == "vrai_faux":
            return  "Vrai" if question.correct_answer["value"] else "Faux"
        if question.mode == "chronologie":
            return "→".join(question.correct_answer["order"])
        return question.correct_answer.get("film") or question.correct_answer.get("title") or ""

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

    def friend_cards(users: list) -> list:
        """Prépare l'affichage d'une liste d'amis : pseudo, avatar et niveau

        Le niveau est calculé ici plutôt que dans le template, pour que les deux
        profils affichent exactement la même chose"""
        return [
            {
                "id": user.id,
                "username": user.username,
                "avatar": user.avatar or "🎬",
                "level": calculate_level(user.total_xp)["level"],
            }
            for user in users
        ]

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
            friends=friend_cards(get_friends_list(current_user.id)),
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
        """Affiche la liste des modes de jeu disponibles

        Le sélecteur films / séries ne filtre pas la grille (tous les modes
        restent jouables) : il suit le joueur jusqu'à l'écran de préparation."""
        return render_template(
            "modes.html",
            modes=GAME_MODES,
            content_type=resolve_content_type(request.args.get("content_type")),
            questions_per_run=QUESTIONS_PER_RUN,
        )

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

    @app.route("/quiz/<mode>")
    def quiz_setup(mode: str) -> str:
        """Écran de préparation : le joueur règle sa partie avant de la lancer

        C'est le seul point d'entrée vers une partie. Tant qu'il n'a pas cliqué
        sur Commencer, aucun chrono ne tourne"""
        mode_info = next((entry for entry in GAME_MODES if entry["slug"] == mode), None)

        if mode_info is None:
            return redirect(url_for("modes"))

        # On ne propose que les thèmes qui ont au moins une question dans ce mode :
        # ailleurs, le joueur choisirait un filtre qui ne renvoie rien.
        mode_tags = (
            Tag.query.filter(Tag.questions.any(Question.mode == mode))
            .order_by(Tag.tag_type, Tag.name)
            .all()
        )

        content_type = resolve_content_type(request.args.get("content_type"))

        # Le compteur doit refléter le filtre : sinon le bouton reste actif
        # alors que la sélection films / séries ne renvoie aucune question. Il
        # ne compte que le jouable : un visiteur ne doit pas se voir promettre
        # des questions réservées aux comptes.
        available = playable_question_query(mode, content_type=content_type).count()

        return render_template(
                "quiz_setup.html",
                mode=mode_info,
                question_count=available,
                run_length=min(QUESTIONS_PER_RUN, available),
                content_type=content_type,
                all_tags=mode_tags,
                levels=LEVELS,
                default_level=DEFAULT_LEVEL,
                blindtest_duration=BLINDTEST_DURATION,
            )

    @app.route("/quiz/<mode>/<int:position>", methods=["GET", "POST"])
    def quiz(mode: str, position: int) -> str:
        """Affiche une question (GET) ou traite la réponse envoyée (POST)."""
        category = request.args.get("category")
        tag_id = request.args.get("tag_id", type=int)
        content_type = request.args.get("content_type")
        level = resolve_level(request.args.get("level"))

        # Le tirage doit précéder la recherche de la question : c'est lui qui
        # décide quelle question occupe la position 1.
        if request.method == "GET" and position == 1:
            start_run(
                session,
                mode,
                question_ids=draw_run_questions(mode, category, tag_id, content_type),
                filters=run_filters(category, tag_id, content_type),
            )

        question = find_question(mode, position, category, tag_id, content_type)

        if question is None:
            return render_template("termine.html", score=read_run(session, mode))

        # Le tirage de la partie en cours fait foi ; à défaut — lien direct,
        # session expirée — on retombe sur ce que les filtres permettent.
        total_questions = run_length(
            session, mode, run_filters(category, tag_id, content_type)
        ) or count_run_questions(mode, category, tag_id, content_type)

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
            earned_xp = 0
            earned_coins = 0

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
                    earned_xp = xp_for_level(level)
                    earned_coins = coins_for_level(level)
                    current_user.total_xp += earned_xp
                    current_user.coins += earned_coins

                db.session.commit()

                new_badge_codes = check_and_award_badges(current_user)
                db.session.commit()

                new_badges = [BADGES[code] for code in new_badge_codes]

            correct_answer_text = None if is_correct else format_correct_answer(question)

            record_answer(session, mode, question.id, is_correct, earned_xp, earned_coins)

            if question.mode == "chronologie":
                correct_order = question.correct_answer["order"]
                if is_timeout:
                    position_results = [False] * len(correct_order)
                else:
                    position_results = [
                        player_answer[i] == correct_order[i]
                        for i in range(len(correct_order))
                    ]
                return {
                    "is_correct": is_correct,
                    "position_results": position_results,
                    "give_up": True,
                    "new_badges": new_badges,
                    "correct_answer": correct_answer_text,
                }

            return {
                "is_correct": is_correct,
                "give_up": True,
                "new_badges": new_badges,
                "correct_answer": correct_answer_text,
            }

        scrambled_title = None
        if question.mode == "film_melange":
            scrambled_title = scramble_title(question.correct_answer["title"])

        options = shuffle_options(question) if question.mode == "qcm" else None

        return render_template(
                "quiz.html",
                question=question,
                scrambled_title=scrambled_title,
                options=options,
                report_reasons=REPORT_REASON,
                level=LEVELS[level],
                duration=duration_for(level, question.mode),
                position=position,
                total_questions=total_questions,
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

    @app.route("/amis/supprimer/<int:user_id>", methods=["POST"])
    @login_required
    def remove_friend_route(user_id: int) -> str:
        """Retire un joueur de la liste d'amis de l'utilisateur connecté"""
        former_friend = User.query.get_or_404(user_id)

        if remove_friend(current_user.id, former_friend.id):
            db.session.commit()
            flash(f"{former_friend.username} ne fait plus partie de tes amis.")
        else:
            flash("Impossible de retirer cet ami.")

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
        friends = friend_cards(get_friends_list(current_user.id))

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

    @app.route("/multijoueur")
    def multiplayer_home() -> str:
        """Présente le mode multijoueur et permet de lancer un défi

        Le multijoueur n'avait aucune porte d'entrée : il fallait passer par la
        fiche publique d'un ami pour découvrir qu'il existait. Cette page lui
        donne une adresse, explique la règle, et met le défi à un clic."""
        multiplayer_modes = [
            entry for entry in GAME_MODES if entry["slug"] in MULTIPLAYER_MODES
        ]

        if not current_user.is_authenticated:
            return render_template(
                "multijoueur.html",
                modes=multiplayer_modes,
                friends=[],
                pending_invitations=[],
                questions_per_game=QUESTIONS_PER_GAME,
                invitation_minutes=INVITATION_DURATION_MINUTES,
            )

        # Invitations reçues et encore valides : sans elles, le joueur ne peut
        # les retrouver que dans la cloche de notifications.
        pending_invitations = [
            game
            for game in GameSession.query.filter_by(
                guest_id=current_user.id, status="invited"
            ).all()
            if not is_invitation_expired(game)
        ]

        return render_template(
            "multijoueur.html",
            modes=multiplayer_modes,
            friends=friend_cards(get_friends_list(current_user.id)),
            pending_invitations=pending_invitations,
            questions_per_game=QUESTIONS_PER_GAME,
            invitation_minutes=INVITATION_DURATION_MINUTES,
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
            flash("Ce mode n'a pas assez de questions pour un duel.")
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

        # Le mélange doit tomber pareil chez les deux adversaires, sinon l'un
        # des deux hérite d'un titre plus lisible que l'autre. La graine est
        # propre à la partie et à la question : elle change d'un duel à l'autre.
        # Graine sous forme de texte : seeder sur un tuple passe par le hachage,
        # déprécié depuis Python 3.9, et rien ne garantit le même résultat d'un
        # processus à l'autre. Une chaîne, elle, donne toujours la même suite.
        shared_seed = f"{game_session.id}-{current_question.id}"

        scrambled_title = None
        if current_question.mode == "film_melange":
            scrambled_title = scramble_title(
                current_question.correct_answer["title"], seed=shared_seed
            )

        # Même exigence pour l'ordre des propositions d'un QCM : mêmes cases,
        # dans le même ordre, pour que la course reste à la loyale.
        options = None
        if current_question.mode == "qcm":
            options = list(enumerate(current_question.payload["options"]))
            random.Random(shared_seed).shuffle(options)

        # En solo le joueur écrit le titre ; en duel il le choisit. Il n'a droit
        # qu'à un essai, et une faute de frappe lui coûterait le point sans
        # recours. Le QCM a déjà ses options, la chronologie attend un ordre.
        choices = None
        if current_question.mode not in ("qcm", "vrai_faux", "chronologie"):
            choices = build_choices(current_question, seed=shared_seed)

        return render_template(
                "multiplayer_game.html",
                game_session=game_session,
                question=current_question,
                opponent=opponent,
                total_questions=len(questions),
                scrambled_title=scrambled_title,
                options=options,
                choices=choices,
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
        """Affiche le profil public d'un joueur

        Le profil est visible de n'importe quel joueur connecté : c'est de là
        qu'on envoie une demande d'ami. Seul le réseau social du joueur (sa
        liste d'amis, les amis en commun) reste réservé à ses amis"""
        if user_id == current_user.id:
            return redirect(url_for("profile"))

        viewed_user = User.query.get_or_404(user_id)

        friendship = get_friendship_between(current_user.id, user_id)

        if friendship is None:
            friendship_state = "none"
        elif friendship.status == "accepted":
            friendship_state = "friends"
        elif friendship.requester_id == current_user.id:
            friendship_state = "request_sent"
        else:
            friendship_state = "request_received"

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

        # Le réseau d'amis du joueur n'est montré qu'à ses amis.
        viewed_user_friends = []
        mutual_friends = []

        if friendship_state == "friends":
            viewed_user_friends = get_friends_list(viewed_user.id)
            current_user_friends = get_friends_list(current_user.id)

            current_user_friend_ids = {friend.id for friend in current_user_friends}
            mutual_friends = friend_cards(
                    [friend for friend in viewed_user_friends if friend.id in current_user_friend_ids]
                )
            viewed_user_friends = friend_cards(viewed_user_friends)

        # Le titre équipé est stocké sous forme de code : on affiche son libellé,
        # comme le fait déjà le profil personnel.
        equipped_title_name = None
        if viewed_user.equipped_title:
            equipped_title_name = TITLES.get(viewed_user.equipped_title, {}).get("name")

        return render_template(
                "profil_public.html",
                multiplayer_modes=[
                    entry for entry in GAME_MODES if entry["slug"] in MULTIPLAYER_MODES
                ],
                viewed_user=viewed_user,
                equipped_title_name=equipped_title_name,
                total_count=total_count,
                correct_count=correct_count,
                level_info=level_info,
                attempts_by_mode=attempts_by_mode,
                all_badges=all_badges,
                viewed_user_friends=viewed_user_friends,
                mutual_friends=mutual_friends,
                friendship_state=friendship_state,
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