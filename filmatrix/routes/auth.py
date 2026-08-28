"""Inscription, connexion et déconnexion."""

from flask import Blueprint, redirect, render_template, request, session, url_for
from flask_login import login_required, login_user, logout_user

from filmatrix.extensions import db
from filmatrix.models import User
from filmatrix.services.validation import is_password_valid


bp = Blueprint("auth", __name__)


@bp.route("/inscription", methods=["GET", "POST"])
def register() -> str:
    """Affiche le formulaire d'inscription (GET) ou crée le compte (POST)."""
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        if not is_password_valid(password):
            error = "Le mot de passe ne respecte pas les règles de sécurité."
            return render_template("auth/inscription.html", error=error)

        new_user = User(username=username, email=email)
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("auth.login"))

    return render_template("auth/inscription.html", error=None)

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
