"""Application Flask : sert le quiz Filmatrix sous forme de page web"""

import os

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

load_dotenv()


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
        raise ValueError(f"Mode inconnu : {mode}")

    @app.route("/")
    def home() -> str:
        """Page d'accueil du site"""
        return render_template("accueil.html")

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

        return render_template(
            "profil.html",
            attempts=attempts,
            total_count=total_count,
            correct_count=correct_count,
        )

    @app.route("/modes")
    def modes() -> str:
        """Affiche la liste des modes de jeu disponibles"""
        return render_template("modes.html")

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
            if request.form.get("timeout") == "true":
                is_correct = False
            else:
                raw_answer = request.form["answer"]
                player_answer = convert_answer(question.mode, raw_answer)
                is_correct = check_answer(question, player_answer)

            if current_user.is_authenticated:
                attempt = Attempt(
                    user_id=current_user.id,
                    question_id=question.id,
                    is_correct=is_correct,
                )
                db.session.add(attempt)
                db.session.commit()

            return {"is_correct": is_correct}

        return render_template("quiz.html", question=question)

    @app.route("/classement")
    def leaderboard() -> str:
        """Affiche le classement général des joueurs par nombre de bonnes réponses"""
        results = (
            db.session.query(
                User.username,
                func.count(Attempt.id).label("total"),
                func.sum(db.case((Attempt.is_correct, 1), else_=0)).label("correct"),
            )
            .join(Attempt, Attempt.user_id == User.id)
            .group_by(User.id)
            .order_by(func.sum(db.case((Attempt.is_correct, 1), else_=0)).desc())
            .all()
        )
        return render_template("classement.html", results=results)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)