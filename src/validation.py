"""Fonctions de validation des données saisies par l'utilisateur"""

import re 

def mot_de_passe_valide(mot_de_passe: str) -> bool:
    """Vérifie qu'un mot de passe respecte les règles de sécutité
    8 caractères minimum, au moins une majuscule, une minuscule, un chiffre et un caractère spécial"""
    if len(mot_de_passe) < 8:
        return False
    if not re.search(r"[A-Z]", mot_de_passe):
        return False
    if not re.search(r"[a-z]", mot_de_passe):
        return False
    if not re.search(r"[0-9]", mot_de_passe):
        return False
    if not re.search(r"[^A-Za-z0-9]", mot_de_passe):
        return False
    return True