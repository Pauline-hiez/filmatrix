"""Inscription, connexion et déconnexion."""

from flask import Blueprint, redirect, render_template, request, session, url_for
from sqlalchemy.exc import IntegrityError
from flask_login import login_required, login_user, logout_user

from filmatrix.extensions import db
from filmatrix.models import User
from filmatrix.services.validation import is_password_valid, suggest_username, username_exists


bp = Blueprint("auth", __name__)


@bp.route("/inscription", methods=["GET", "POST"])
def register() -> str:
    """Affiche le formulaire d'inscription (GET) ou crée le compte (POST)."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not username:
            return render_template(
                "auth/inscription.html",
                error="Choisis un pseudo.",
                username=username,
                email=email,
                username_suggestion="Joueur",
            )

        if username_exists(username):
            return render_template(
                "auth/inscription.html",
                error="Ce pseudo est déjà utilisé.",
                username=username,
                email=email,
                username_suggestion=suggest_username(username),
            )

        if not is_password_valid(password):
            error = "Le mot de passe ne respecte pas les règles de sécurité."
            return render_template(
                "auth/inscription.html",
                error=error,
                username=username,
                email=email,
            )

        new_user = User(username=username, email=email)
        new_user.set_password(password)

        db.session.add(new_user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return render_template(
                "auth/inscription.html",
                error="Ce pseudo ou cette adresse email est déjà utilisé(e).",
                username=username,
                email=email,
                username_suggestion=suggest_username(username),
            )

        return redirect(url_for("auth.login"))

    return render_template("auth/inscription.html", error=None, username="", email="")

@bp.route("/connexion", methods=["GET", "POST"])
def login() -> str:
    """Affiche le formulaire de connexion (GET) ou authentifie l'utilisateur (POST)"""
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if user is None or not user.verify_password(password):
            error = "Email ou mot de passe incorrect."
            return render_template("auth/connexion.html", error=error)

        login_user(user)
        return redirect(url_for("main.home"))

    return render_template("auth/connexion.html", error=None)

@bp.route("/deconnexion")
@login_required
def logout() -> str:
    """Déconnecte l'utilisateur courant"""
    logout_user()
    return redirect(url_for("main.home"))
