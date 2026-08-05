"""Modèles de données du moteur de jeu Filmatrix"""

from src.database import db
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash


class Question(db.Model):
    """Représente une question générique, quel que soit son mode de jeu.

    Le champ `payload` contient les données propres au mode (ex: les 4
    options d'un QCM). Le champ `correct_answer` contient la bonne
    réponse, dans un format adapté au mode
    """

    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    mode = db.Column(db.String(50), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    difficulty = db.Column(db.String(20), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    payload = db.Column(db.JSON, nullable=False)
    correct_answer = db.Column(db.JSON, nullable=False)
    necessite_compte = db.Column(db.Boolean, nullable=False, default=False)

class User(db.Model, UserMixin):
    """Représente un compte joueur"""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, mot_de_passe: str) -> None:
        "Hash le mot de passe fourni et le stocke (jamais en clair)"
        self.password_hash = generate_password_hash(mot_de_passe)

    def verifier_mot_de_passe(self, mot_de_passe: str) -> bool:
        """Vérifie qu'un mot de passe correspond au hash stocké"""
        return check_password_hash(self.password_hash, mot_de_passe)