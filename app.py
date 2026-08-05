"""Application Flask : sert le quiz Filmatrix sous forme de page web"""

from flask import Flask, render_template, request 

from src.engine import check_answer
from src.database import db
from src.models import Question, User, Attempt
import os
from dotenv import load_dotenv
from flask_login import LoginManager
from src.validation import mot_de_passe_valide
from flask import Flask, redirect, render_template, request, url_for, flash
from flask_login import login_user, login_required, logout_user, current_user
from flask_migrate import Migrate

load_dotenv()

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///filmatrix.db"
app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "connexion"

@login_manager.user_loader
def charger_utilisateur(user_id: str):
    """Indique à Flask-Login comment retrouver un utilisateur depuis son id de session"""
    return User.query.get(int(user_id))

def trouver_question(mode: str, position: int):
    """Cherche la question à une position donnée, parmi celles d'un mode précis"""
    questions_du_mode = (
            Question.query.filter_by(mode=mode).order_by(Question.id).all()
        )

    index = position - 1
    if index < 0 or index >= len(questions_du_mode):
        return None

    return questions_du_mode[index]

def convertir_reponse(mode: str, valeur_brute: str):
    """Convertit la valeur texte du formulaire dans le type attendu par check_answer"""
    if mode == "qcm":
        return int(valeur_brute)
    if mode == "vrai_faux":
        return valeur_brute == "true"
    raise ValueError(f"Mode inconnu : {mode}")

@app.route("/")
def accueil() -> str:
    """Page d'accueil du site"""
    return render_template("accueil.html")

@app.route("/inscription", methods=["GET", "POST"])
def inscription() -> str:
    """Affiche le formulaire d'inscription (GET) ou crée le compte (POST)."""
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        if not mot_de_passe_valide(password):
            erreur = "Le mot de passe ne respecte pas les règles de sécurité."
            return render_template("inscription.html", erreur=erreur)

        nouvel_utilisateur = User(username=username, email=email)
        nouvel_utilisateur.set_password(password)

        db.session.add(nouvel_utilisateur)
        db.session.commit()

        return redirect(url_for("connexion"))

    return render_template("inscription.html", erreur=None)

@app.route("/connexion", methods=["GET", "POST"])
def connexion() -> str:
    """Affiche le formulaire de connexion (GET) ou authentifie l'utilisateur (POST)"""
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        utilisateur = User.query.filter_by(email=email).first()

        if utilisateur is None or not utilisateur.verifier_mot_de_passe(password):
            erreur = "Email ou mot de passe incorrect."
            return render_template("connexion.html", erreur=erreur)

        login_user(utilisateur)
        return redirect(url_for("accueil"))

    return render_template("connexion.html", erreur=None)

@app.route("/deconnexion")
@login_required
def deconnexion() -> str:
    """Déconnecte l'utilisateur courant"""
    logout_user()
    return redirect(url_for("accueil"))

@app.route("/modes")
def modes() -> str:
    """Affiche la liste des modes de jeu disponibles"""
    return render_template("modes.html")

@app.route("/quiz/<mode>/<int:position>", methods=["GET", "POST"])
def quiz(mode: str, position: int) -> str:
    """Affiche une question (GET) ou traite la réponse envoyée (POST)."""
    question = trouver_question(mode, position)

    if question is None:
        return render_template("termine.html")

    if question.necessite_compte and not current_user.is_authenticated:
        flash("Connecte-toi pour accéder à cette question.")
        return redirect(url_for("connexion"))

    if request.method == "POST":
        reponse_brute = request.form["reponse"]
        reponse_joueur = convertir_reponse(question.mode, reponse_brute)
        est_correct = check_answer(question, reponse_joueur)

        if current_user.is_authenticated:
            tentative = Attempt(
                    user_id=current_user.id,
                    question_id=question.id,
                    is_correct=est_correct,
                )
            db.session.add(tentative)
            db.session.commit()
            
        return render_template(
            "resultat.html",
            est_correct=est_correct,
            mode=mode,
            position_suivante=position + 1,
        )

    return render_template("quiz.html", question=question)

if __name__ == "__main__":
    app.run(debug=True)