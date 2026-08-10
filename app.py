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
from src.models import Attempt, Question, User
from src.validation import is_password_valid
from src.badges import check_and_award_badges, BADGES
from src.shop import coins_for_difficulty, TITLES, owns_title, purchase_title
from src.admin import admin_required 

load_dotenv()

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

    app.config["SQLALCHEMY_DATABASE_URI"] = database_uri or "sqlite:///filmatrix.db"
    app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]

    db.init_app(app)
    Migrate(app, db)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "login"

    @login_manager.user_loader
    def load_user(user_id: str):
        """Indique à Flask-Login comment retrouver un utilisateur depuis son id de session"""
        return User.query.get(int(user_id))

    def find_question(mode: str, position: int, category: str | None):
        """Cherche la question à une position donnée, parmi celles d'un mode et d'une catégorie"""
        query = Question.query.filter_by(mode=mode)

        if category:
            query = query.filter_by(category=category)

        mode_questions = query.order_by(Question.id).all()

        index = position - 1
        if index < 0 or index >= len(mode_questions):
            return None

        return mode_questions[index]

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

    @app.route("/admin/questions")
    @login_required 
    @admin_required
    def admin_questions_list() -> str:
        """Affiche la liste de toutes les questions, pour l'admin"""
        all_questions = Question.query.order_by(Question.mode, Question.id).all()
        return render_template("admin/questions_list.html", questions=all_questions)

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
                    require_account=request.form.get("requires_account") == "on",
                )
            db.session.add(new_question)
            db.session.commit()

            flash("Question créée avec succès.")
            return redirect(url_for("admin_questions_list"))
        return render_template("admin/question_form.html", question=None)

    @app.route("/modes")
    def modes() -> str:
        """Affiche la liste des modes de jeu disponibles"""
        return render_template("modes.html")

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
        question = find_question(mode, position, category)

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

        return render_template("quiz.html", question=question, scrambled_title=scrambled_title)

    @app.route("/classement")
    def leaderboard() -> str:
        """Affiche le classement général des joueurs, trié par XP total"""
        results = (
                db.session.query(
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
            leaderboard_entries.append(
                {
                    "username": result.username,
                    "total_xp": result.total_xp,
                    "level": level_info["level"],
                    "total": result.total,
                    "correct": result.correct,
                }
            )

        return render_template("classement.html", results=leaderboard_entries)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)