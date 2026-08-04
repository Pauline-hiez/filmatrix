"""Application Flask : sert le quiz Filmatrix sous forme de page web"""

from flask import Flask, render_template, request 

from data.questions import QUESTIONS 
from src.engine import check_answer
from src.database import db
from src.models import Question

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///filmatrix.db"
db.init_app(app)

with app.app_context():
    db.create_all()

def trouver_question(question_id: int):
    """Cherche une question par son id dans la liste des QUESTIONS"""
    for question in QUESTIONS:
        if question.id == question_id:
            return question
    return None

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

@app.route("/quiz/<int:question_id>", methods=["GET", "POST"])
def quiz(question_id: int) -> str:
    """Affiche une question (GET) ou traite la réponse envoyée (POST)"""
    question = trouver_question(question_id)

    if question is None:
        return render_template("termine.html")

    if request.method == "POST":
        reponse_brute = request.form["reponse"]
        reponse_joueur = convertir_reponse(question.mode, reponse_brute)
        est_correct = check_answer(question, reponse_joueur)
        question_suivante_id = question_id + 1
        return render_template(
            "resultat.html",
            est_correct=est_correct,
            question_suivante_id=question_suivante_id,
            )

    return render_template("quiz.html", question=question)

if __name__ == "__main__":
    app.run(debug=True)