"""Fonctions de validation des données saisies par l'utilisateur"""

import re

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
