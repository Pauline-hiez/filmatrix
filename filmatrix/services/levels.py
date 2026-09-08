"""Difficultés de question : elles fixent les récompenses.

La difficulté est un attribut de chaque Question (voir filmatrix/models.py),
pas un réglage choisi par le joueur : plus elle est élevée, plus une bonne
réponse rapporte. Le temps de réponse, lui, ne dépend PAS de la difficulté
de la question — seulement du mode de jeu (voir MODE_DURATIONS) : un QCM
facile et un QCM difficile laissent exactement le même temps, ce qui change
c'est le gain en cas de bonne réponse.
"""

LEVELS = {
    "facile": {"label": "Facile", "xp": 10, "coins": 2},
    "moyen": {"label": "Moyen", "xp": 20, "coins": 4},
    "difficile": {"label": "Difficile", "xp": 30, "coins": 6},
}

DEFAULT_LEVEL = "moyen"

# Chrono fixe par mode de jeu, indépendant de la difficulté de la question
# tirée : chaque mode demande un effort différent au joueur (lire une
# réplique, ordonner une chronologie, écouter un extrait...), ce qui justifie
# des durées différentes, mais toujours les mêmes pour un mode donné.
MODE_DURATIONS = {
    "qcm": 15,
    "vrai_faux": 12,
    "citation": 20,
    "emoji": 20,
    "film_melange": 20,
    "chronologie": 25,
    "devinette": 20,
    "devinette_affiche": 15,
    "casting": 15,
    "blindtest": 30,
}
DEFAULT_MODE_DURATION = 16


def resolve_level(raw_level: str | None) -> str:
    """Retourne une difficulté valide, en repliant sur la difficulté par défaut

    Sanitize la difficulté portée par une Question (colonne NOT NULL, mais en
    théorie corruptible) : une valeur absente ou fantaisiste ne doit jamais
    faire planter le calcul des gains."""
    if raw_level in LEVELS:
        return raw_level
    return DEFAULT_LEVEL


def duration_for(mode: str) -> int:
    """Retourne le temps de réponse fixe accordé pour ce mode de jeu, en secondes"""
    return MODE_DURATIONS.get(mode, DEFAULT_MODE_DURATION)


def xp_for_level(level: str) -> int:
    """Retourne l'XP gagnée pour une bonne réponse au niveau donné"""
    return LEVELS[resolve_level(level)]["xp"]


def coins_for_level(level: str) -> int:
    """Retourne les pièces gagnées pour une bonne réponse au niveau donné"""
    return LEVELS[resolve_level(level)]["coins"]


def calculate_level(total_xp: int) -> dict:
    """Calcule le niveau actuel et la progression vers le niveau suivant

    Cette fonction vivait dans app.py, que src/badges.py devait alors importer :
    un « from filmatrix import ... » depuis un service rechargerait la fabrique quand le
    serveur est lancé par « python app.py ». Elle parle d'XP et de niveaux, sa
    place est ici."""
    level = 1
    xp_for_next_level = 100
    xp_already_spent = 0

    while total_xp - xp_already_spent >= xp_for_next_level:
        xp_already_spent += xp_for_next_level
        level += 1
        xp_for_next_level = 100 * level

    xp_in_current_level = total_xp - xp_already_spent

    return {
        "level": level,
        "xp_in_current_level": xp_in_current_level,
        "xp_for_next_level": xp_for_next_level,
    }
