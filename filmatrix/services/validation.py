"""Fonctions de validation des données saisies par l'utilisateur"""

import re

from sqlalchemy import func

from filmatrix.extensions import db
from filmatrix.models import User


def normalize_username(username: str) -> str:
    """Normalise un pseudo pour appliquer l'unicité sans distinction de casse."""
    return " ".join((username or "").strip().split()).casefold()


def username_exists(username: str) -> bool:
    """Indique si un pseudo est déjà utilisé, quelle que soit sa casse."""
    normalized = normalize_username(username)
    if not normalized:
        return False
    return db.session.query(User.id).filter(func.lower(User.username) == normalized).first() is not None


def suggest_username(username: str) -> str:
    """Propose un pseudo disponible à partir du pseudo demandé."""
    base = " ".join((username or "").strip().split()) or "Joueur"
    if not username_exists(base):
        return base

    suffix = 2
    while username_exists(f"{base}{suffix}"):
        suffix += 1
    return f"{base}{suffix}"


def is_password_valid(password: str) -> bool:
    """Vérifie qu'un mot de passe respecte les règles de sécutité
    8 caractères minimum, au moins une majuscule, une minuscule, un chiffre et un caractère spécial"""
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    if not re.search(r"[^A-Za-z0-9]", password):
        return False
    return True
