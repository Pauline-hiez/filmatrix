"""Inscription, connexion et déconnexion.

Chaque route sert deux publics : un navigateur normal (page complète, avec
logo/accroche/atouts - voir auth/connexion.html et inscription.html) et la
modale JS (static/js/auth_modal.js), qui ne charge que le fragment central
(auth/_connexion_form.html, _inscription_form.html) en AJAX et attend du JSON
en retour d'un POST plutôt qu'une redirection HTTP classique."""

from flask import Blueprint, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError
from flask_login import login_required, login_user, logout_user

from filmatrix.extensions import db
from filmatrix.models import User
from filmatrix.services.validation import is_password_valid, suggest_username, username_exists


bp = Blueprint("auth", __name__)


def _is_ajax() -> bool:
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _register_response(**context):
    """Rend soit la page complète, soit (requête AJAX) juste le fragment de
    formulaire encapsulé dans le JSON attendu par la modale."""
    if _is_ajax():
        html = render_template("auth/_inscription_form.html", **context)
        return {"success": False, "html": html}
    return render_template("auth/inscription.html", **context)


def _login_response(error: str):
    if _is_ajax():
        html = render_template("auth/_connexion_form.html", error=error)
        return {"success": False, "html": html}
    return render_template("auth/connexion.html", error=error)


@bp.route("/inscription", methods=["GET", "POST"])
def register() -> str:
    """Affiche le formulaire d'inscription (GET) ou crée le compte (POST)."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        if not username:
            return _register_response(
                error="Choisis un pseudo.",
                username=username,
                email=email,
                username_suggestion="Joueur",
            )

        if username_exists(username):
            return _register_response(
                error="Ce pseudo est déjà utilisé.",
                username=username,
                email=email,
                username_suggestion=suggest_username(username),
            )

        if not is_password_valid(password):
            return _register_response(
                error="Le mot de passe ne respecte pas les règles de sécurité.",
                username=username,
                email=email,
            )

        if password != password_confirm:
            return _register_response(
                error="Les mots de passe ne correspondent pas.",
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
            return _register_response(
                error="Ce pseudo ou cette adresse email est déjà utilisé(e).",
                username=username,
                email=email,
                username_suggestion=suggest_username(username),
            )

        if _is_ajax():
            return {"success": True, "redirect": url_for("auth.login")}
        return redirect(url_for("auth.login"))

    if _is_ajax():
        return render_template("auth/_inscription_form.html", error=None, username="", email="")
    return render_template("auth/inscription.html", error=None, username="", email="")

@bp.route("/connexion", methods=["GET", "POST"])
def login() -> str:
    """Affiche le formulaire de connexion (GET) ou authentifie l'utilisateur (POST)"""
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if user is None or not user.verify_password(password):
            return _login_response("Email ou mot de passe incorrect.")

        login_user(user, remember=request.form.get("remember") == "on")
        if _is_ajax():
            return {"success": True, "redirect": url_for("main.home")}
        return redirect(url_for("main.home"))

    if _is_ajax():
        return render_template("auth/_connexion_form.html", error=None)
    return render_template("auth/connexion.html", error=None)

@bp.route("/deconnexion")
@login_required
def logout() -> str:
    """Déconnecte l'utilisateur courant"""
    logout_user()
    return redirect(url_for("main.home"))
