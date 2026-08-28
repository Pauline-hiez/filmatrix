"""Niveaux de jeu : ils fixent le temps de réponse et les récompenses.

Le niveau est choisi par le joueur avant la partie, sur la page des modes. Il
ne dépend plus de la difficulté enregistrée sur chaque question : plus le
niveau monte, moins le joueur a de temps, et plus une bonne réponse rapporte.
"""

LEVELS = {
    "facile": {"label": "Facile", "duration": 22, "xp": 10, "coins": 2},
    "moyen": {"label": "Moyen", "duration": 16, "xp": 20, "coins": 4},
    "difficile": {"label": "Difficile", "duration": 12, "xp": 30, "coins": 6},
}

DEFAULT_LEVEL = "moyen"

# Le blindtest garde une durée fixe : il faut d'abord écouter l'extrait musical,
# un chrono de 12 secondes ne laisserait pas le temps de reconnaître le film.
BLINDTEST_DURATION = 30


def resolve_level(raw_level: str | None) -> str:
    """Retourne un niveau valide, en repliant sur le niveau par défaut

    Le niveau arrive par l'URL : il peut être absent (lien direct vers une
    question) ou fantaisiste, on ne lui fait donc jamais confiance"""
    if raw_level in LEVELS:
        return raw_level
    return DEFAULT_LEVEL


def duration_for(level: str, mode: str) -> int:
    """Retourne le temps de réponse accordé pour une question, en secondes"""
    if mode == "blindtest":
        return BLINDTEST_DURATION
    return LEVELS[resolve_level(level)]["duration"]


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
