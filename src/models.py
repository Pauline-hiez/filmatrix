"""Modèles de données du moteur de jeu Filmatrix"""

from src.database import db
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime


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
    requires_account = db.Column(db.Boolean, nullable=False, default=False)

class User(db.Model, UserMixin):
    """Représente un compte joueur"""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    total_xp = db.Column(db.Integer, nullable=False, default=0)
    coins = db.Column(db.Integer, nullable=False, default=0)
    equipped_title = db.Column(db.String(50), nullable=True)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    avatar = db.Column(db.String(10), nullable=True)
    bio = db.Column(db.String(280), nullable=True)

    def set_password(self, password: str) -> None:
        "Hash le mot de passe fourni et le stocke (jamais en clair)"
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password: str) -> bool:
        """Vérifie qu'un mot de passe correspond au hash stocké"""
        return check_password_hash(self.password_hash, password)

class Attempt(db.Model):
    """Représente une réponse donnée par un joueur à une question"""

    __tablename__ = "attempts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)
    answered_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    question = db.relationship("Question")
    user = db.relationship("User", backref="attempts")

class UserBadge(db.Model):
    """Représente un badge obtenu par un joueur"""
    __tablename__ = "user_badges"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    badge_code = db.Column(db.String(50), nullable = False)
    earned_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", backref="badges")

class UserTitle(db.Model):
    """Représente un titre possédé par un utilisateur"""

    __tablename__ = "user_titles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title_code = db.Column(db.String(50), nullable=False)
    purchassed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", backref="titles")

class Report(db.Model):
    """Représente un signalement fait par un joueur sur une question"""

    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    reason = db.Column(db.String(50), nullable=False)
    is_resolved = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", backref="reports")
    question = db.relationship("Question", backref="reports")

class Friendship(db.Model):
    """Représente une relation d'amitié entre deux utilisateurs"""

    __tablename__ = "friendships"

    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    requester = db.relationship("User", foreign_keys=[requester_id], backref="sent_friend_requests")
    receiver = db.relationship("User", foreign_keys=[receiver_id], backref="received_friend_requests")

class Notification(db.Model):
    """Représente une notification reçue par un utilisateur"""

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    link = db.Column(db.String(255), nullable=True)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", backref="notifications")